// =========== RDA - RELATÓRIOS DE DESEMPENHO AUTOMÁTICOS ============
// server.js — Frontend server (Express estático + proxy para API Flask)
// ===================================================================
//
// Serve o frontend estático e faz proxy das chamadas /api/* para o
// backend Flask. Valida autenticação via cookie rts_token (mesmo
// padrão do RTA).

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

// ─── Autenticação via token compartilhado com RTS ─────────────────────────────
const _AUTH_SECRET = process.env.RDA_AUTH_SECRET || process.env.APP_SECRET || "";
const _RTS_LOGIN_URL = process.env.RTS_LOGIN_URL || "/login";

function validateAuthToken(token) {
  if (!token || !_AUTH_SECRET) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [b64, sig] = parts;
  const expectedSig = crypto.createHmac("sha256", _AUTH_SECRET).update(b64).digest("base64url");
  if (sig !== expectedSig) return null;
  try {
    const payload = JSON.parse(Buffer.from(b64, "base64url").toString("utf8"));
    if (!payload.exp || Date.now() > payload.exp) return null;
    return payload;
  } catch (_) {
    return null;
  }
}

function requireAuth(req, res, next) {
  const token = req.cookies && req.cookies.rts_token;
  const user = validateAuthToken(token);
  if (user) {
    req.rdaUser = user;
    return next();
  }
  // Não autenticado — redireciona para login do RTS
  const hostname = req.get("host").split(":")[0];
  const rtsBase = `${req.protocol}://${hostname}:8080`;
  const rdaOrigin = `${req.protocol}://${req.get("host")}`;
  const loginUrl = `${rtsBase}/login?redirect=${encodeURIComponent(rdaOrigin)}`;
  if (req.path.startsWith("/api/") || req.path.startsWith("/relatorios/")) {
    return res.status(401).json({ success: false, error: "Não autenticado. Faça login no RTS." });
  }
  return res.redirect(loginUrl);
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

// Proteção de autenticação — tudo abaixo exige login no RTS
app.use(requireAuth);

// Proxy para API + relatórios → backend Flask
// Usa filtro interno do http-proxy-middleware (1º argumento) para que
// o path completo seja preservado. NÃO montar via app.use("/api", proxy)
// — Express strip o prefixo e causa path duplicado (/api/api/...).
app.use(createProxyMiddleware(
  ["/api/**", "/relatorios/**"],
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
app.use(express.static(frontendPath));

// Fallback: SPA
app.get("*", (_req, res) => {
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
