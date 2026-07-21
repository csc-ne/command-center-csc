// =========== RDA - RELATÓRIOS DE DESEMPENHO AUTOMÁTICOS ============
// server.js — Frontend server (Express estático + proxy para API Flask)
// ===================================================================
//
// Serve o frontend estático e faz proxy das chamadas /api/* e
// /relatorios/* para o backend Flask.
//
// AUTENTICAÇÃO (SSO — Command Center):
//   O login deixou de ser próprio do RDA. O Command Center (portal) é o
//   provedor único de login e emite o cookie `portal_token` (JWT HS256
//   assinado com PORTAL_JWT_SECRET). O RDA apenas valida esse cookie.
//   Sem cookie/JWT válido → redireciona para o Command Center.

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express = require("express");
const cookieParser = require("cookie-parser");
const crypto = require("crypto");
const { createProxyMiddleware } = require("http-proxy-middleware");

const app = express();
const PORT = parseInt(process.env.RDA_FRONTEND_PORT || "5050", 10);

// URL do backend Flask (dentro do Docker, comunica via nome do serviço)
const BACKEND_URL = process.env.RDA_BACKEND_URL || "http://rda-backend:5051";

// ─── SSO — Command Center ─────────────────────────────────────────────────────
const _PORTAL_JWT_SECRET   = process.env.PORTAL_JWT_SECRET || "";
const _COMMAND_CENTER_URL  = process.env.COMMAND_CENTER_URL || "";
const _COMMAND_CENTER_PORT = process.env.COMMAND_CENTER_PORT || "4001";

// Valida um JWT HS256 (header.payload.signature) assinado pelo Command Center.
function validatePortalToken(token) {
  if (!token || !_PORTAL_JWT_SECRET) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [h, p, sig] = parts;
  try {
    const header = JSON.parse(Buffer.from(h, "base64url").toString("utf8"));
    if (!header || header.alg !== "HS256") return null;
    const expected = crypto
      .createHmac("sha256", _PORTAL_JWT_SECRET)
      .update(h + "." + p)
      .digest("base64url");
    const sigBuf = Buffer.from(sig);
    const expBuf = Buffer.from(expected);
    if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) return null;
    const payload = JSON.parse(Buffer.from(p, "base64url").toString("utf8"));
    // jsonwebtoken grava exp em SEGUNDOS (Unix epoch).
    if (!payload.exp || Date.now() / 1000 > payload.exp) return null;
    return payload;
  } catch (_) {
    return null;
  }
}

// URL do Command Center; deriva do hostname da requisição se não houver env.
function commandCenterUrl(req) {
  if (_COMMAND_CENTER_URL) return _COMMAND_CENTER_URL;
  const hostname = (req.get("host") || "").split(":")[0];
  return `${req.protocol}://${hostname}:${_COMMAND_CENTER_PORT}`;
}

function requireAuth(req, res, next) {
  const token = req.cookies && req.cookies.portal_token;
  const user = validatePortalToken(token);
  if (user) {
    req.rdaUser = user; // { id, email, displayName, role, ... }
    return next();
  }
  // Não autenticado — chamadas de API recebem 401; navegação é redirecionada.
  if (req.path.startsWith("/api/") || req.path.startsWith("/relatorios/")) {
    return res.status(401).json({ success: false, error: "Não autenticado. Faça login no Command Center." });
  }
  return res.redirect(commandCenterUrl(req));
}

// ─── Log de acesso no Command Center ──────────────────────────────────────────
// Notifica o Command Center de que um usuário autenticado entrou no RDA.
// Fire-and-forget: nunca bloqueia nem quebra o carregamento da página.
// Throttle em memória: no máximo 1 registro por usuário a cada 30 min
// (evita poluir o audit log a cada refresh/navegação).
const _accessSeen = new Map();
const _ACCESS_TTL_MS = 30 * 60 * 1000;

function logAccess(req) {
  try {
    if (typeof fetch !== "function") return;
    const token = req.cookies && req.cookies.portal_token;
    const user = req.rdaUser;
    if (!token || !user) return;

    const key = user.id || user.email || "?";
    const now = Date.now();
    if (now - (_accessSeen.get(key) || 0) < _ACCESS_TTL_MS) return;
    _accessSeen.set(key, now);

    const ip = String(req.headers["x-forwarded-for"] || req.ip || "")
      .split(",")[0].trim();
    const ua = req.headers["user-agent"] || "";

    fetch(commandCenterUrl(req) + "/api/audit/access", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Cookie": "portal_token=" + token,
        "X-Forwarded-For": ip,
        "X-Client-User-Agent": ua,
      },
      body: JSON.stringify({ system: "rda" }),
      signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout
        ? AbortSignal.timeout(4000)
        : undefined,
    }).catch((e) => console.warn("[RDA] Log de acesso falhou:", e.message));
  } catch (e) {
    console.warn("[RDA] Log de acesso erro:", e.message);
  }
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------
app.use(cookieParser());
// NOTA: express.json() NÃO é usado aqui propositalmente.
// Se fosse usado antes do proxy, ele consumiria o body stream
// e o http-proxy-middleware não conseguiria reenviar o POST body
// para o backend Flask. O proxy repassa o body raw diretamente.

// Health check (público)
app.get("/healthz", (_req, res) => {
  res.json({ status: "ok", service: "rda-frontend", timestamp: new Date().toISOString() });
});

// Proteção de autenticação — tudo abaixo exige login no Command Center
app.use(requireAuth);

// Proxy para API + relatórios → backend Flask
// Usa filtro interno do http-proxy-middleware (1º argumento) para que
// o path completo seja preservado. NÃO montar via app.use("/api", proxy)
// — Express strip o prefixo e causa path duplicado (/api/api/...).
app.use(createProxyMiddleware(
  ["/api/**", "/relatorios/**", "/relatorios-mensais/**"],
  {
    target: BACKEND_URL,
    changeOrigin: true,
    proxyTimeout: 600000,     // 10 min — geração de PDF demora
    timeout: 600000,
    onProxyReq: (proxyReq, req) => {
      if (req.headers.cookie) {
        proxyReq.setHeader("Cookie", req.headers.cookie);
      }
    },
    onError: (err, _req, res) => {
      console.error("[RDA] Proxy error:", err.message);
      if (!res.headersSent) {
        res.status(502).json({ message: "Erro de comunicação com o backend: " + err.message });
      }
    },
  }
));

// Frontend estático (servido após auth)
const frontendPath = path.join(__dirname);
app.use(express.static(frontendPath, { index: false }));

// Fallback: SPA — registra o acesso e serve o index.html
app.get("*", (req, res) => {
  logAccess(req); // fire-and-forget
  res.sendFile(path.join(frontendPath, "index.html"));
});

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[RDA] Frontend rodando na porta ${PORT}`);
  console.log(`[RDA] Backend proxy: ${BACKEND_URL}`);
  console.log(`[RDA] http://localhost:${PORT}`);
});
