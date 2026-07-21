// =========== RTA - REAL TIME ALERT ============
// server.js — API REST para o dashboard de alertas
// ================================================

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express = require("express");
const cors = require("cors");
const crypto = require("crypto");
const cookieParser = require("cookie-parser");
const pool = require("./db");
const queries = require("./queries");

const app = express();
const PORT = parseInt(process.env.RTA_PORT || "3021", 10);

// ─── SSO — Command Center ─────────────────────────────────────────────────────
// O login é centralizado no Command Center, que emite o cookie `portal_token`
// (JWT HS256 assinado com PORTAL_JWT_SECRET). O RTA apenas valida esse cookie.
// Se ausente/inválido → redireciona para o Command Center.
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
    req.rtaUser = user; // { id, email, displayName, role, ... }
    return next();
  }
  // Não autenticado — redireciona para o login centralizado (Command Center)
  if (req.path.startsWith("/api/")) {
    return res.status(401).json({ success: false, error: "Não autenticado. Faça login no Command Center." });
  }
  return res.redirect(commandCenterUrl(req));
}

// ─── Log de acesso no Command Center ──────────────────────────────────────────
// Notifica o Command Center de que um usuário autenticado entrou no RTA.
// Fire-and-forget: nunca bloqueia nem quebra o carregamento da página.
// Throttle em memória: no máximo 1 registro por usuário a cada 30 min.
const _accessSeen = new Map();
const _ACCESS_TTL_MS = 30 * 60 * 1000;

function logAccess(req) {
  try {
    if (typeof fetch !== "function") return;
    const token = req.cookies && req.cookies.portal_token;
    const user = req.rtaUser;
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
      body: JSON.stringify({ system: "rta" }),
      signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout
        ? AbortSignal.timeout(4000)
        : undefined,
    }).catch((e) => console.warn("[RTA] Log de acesso falhou:", e.message));
  } catch (e) {
    console.warn("[RTA] Log de acesso erro:", e.message);
  }
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------
app.use(cookieParser());
app.use(cors({
  origin: process.env.RTA_CORS_ORIGIN || "*",
  methods: ["GET"],
  credentials: true,
}));
app.use(express.json());

// Servir frontend estatico (pasta ../frontend) — protegido por auth
const frontendPath = path.join(__dirname, "..", "frontend");

// ---------------------------------------------------------------------------
// Health check (público — Docker precisa acessar sem auth)
// ---------------------------------------------------------------------------
app.get("/healthz", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ status: "ok", service: "rta-backend", timestamp: new Date().toISOString() });
  } catch (err) {
    res.status(503).json({ status: "error", error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Proteção de autenticação — tudo abaixo exige login no RTS
// ---------------------------------------------------------------------------
app.use(requireAuth);

// Frontend estático (servido após auth)
app.use(express.static(frontendPath, { index: false }));

// ---------------------------------------------------------------------------
// Helper: data de hoje no fuso America/Sao_Paulo (evita que apos 21h BRT
// o default vire o dia seguinte por causa do UTC)
// ---------------------------------------------------------------------------
function todayBRT() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
  // "sv-SE" formata como YYYY-MM-DD (ISO)
}

// ---------------------------------------------------------------------------
// Helper: extrai datas da query string (default = hoje em BRT)
// ---------------------------------------------------------------------------
function parseDates(req) {
  const today = todayBRT();
  const start = req.query.start || today;
  const end = req.query.end || today;
  return { start, end };
}

// ---------------------------------------------------------------------------
// API: Contagem de alertas (cards de resumo)
// GET /api/alerts/counts?start=YYYY-MM-DD&end=YYYY-MM-DD
// Retorna contagem por tipo + regional + totais
// ---------------------------------------------------------------------------
app.get("/api/alerts/counts", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const [byRegional, totals] = await Promise.all([
      pool.query(queries.ALERT_COUNTS_BY_REGIONAL, [start, end]),
      pool.query(queries.ALERT_COUNTS_TOTAL, [start, end]),
    ]);
    res.json({
      byRegional: byRegional.rows,
      totals: totals.rows,
      period: { start, end },
    });
  } catch (err) {
    console.error("[RTA] Erro em /api/alerts/counts:", err.message);
    res.status(500).json({ error: "Erro ao buscar contagens: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Geolocalizacao de alertas (mapa) — com filtros
// GET /api/alerts/geo?start=&end=&color=&tipo=&regional=
// ---------------------------------------------------------------------------
app.get("/api/alerts/geo", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const color = req.query.color || null;
    const tipo = req.query.tipo || null;
    const regional = req.query.regional || null;
    const { rows } = await pool.query(queries.GEO_ALERTS, [start, end, color, tipo, regional]);
    res.json({ count: rows.length, alerts: rows, period: { start, end } });
  } catch (err) {
    console.error("[RTA] Erro em /api/alerts/geo:", err.message);
    res.status(500).json({ error: "Erro ao buscar geolocalizacao: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Detalhamento de alertas (tabela)
// GET /api/alerts/detail?start=&end=&color=&tipo=
// ---------------------------------------------------------------------------
app.get("/api/alerts/detail", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const color = req.query.color || null;
    const tipo = req.query.tipo || null;
    const { rows } = await pool.query(queries.ALERT_DETAIL, [start, end, color, tipo]);
    res.json({ count: rows.length, alerts: rows, period: { start, end } });
  } catch (err) {
    console.error("[RTA] Erro em /api/alerts/detail:", err.message);
    res.status(500).json({ error: "Erro ao buscar detalhamento: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Alertas por dia (grafico de barras)
// GET /api/alerts/monthly?start=YYYY-MM-DD&end=YYYY-MM-DD
// Default: inicio do mes atual ate hoje
// ---------------------------------------------------------------------------
app.get("/api/alerts/monthly", async (req, res) => {
  try {
    const today = todayBRT();
    const monthStart = today.slice(0, 8) + "01"; // primeiro dia do mes
    const start = req.query.start || monthStart;
    const end = req.query.end || today;
    const { rows } = await pool.query(queries.ALERTS_BY_DAY, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RTA] Erro em /api/alerts/monthly:", err.message);
    res.status(500).json({ error: "Erro ao buscar dados mensais: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Ranking de maquinas por cor
// GET /api/alerts/ranking?color=RED&start=&end=
// ---------------------------------------------------------------------------
app.get("/api/alerts/ranking", async (req, res) => {
  try {
    const color = (req.query.color || "RED").toUpperCase();
    const allowed = new Set(["RED", "YELLOW", "BLUE", "GRAY"]);
    if (!allowed.has(color)) {
      return res.status(400).json({ error: "Cor invalida. Use RED, YELLOW, BLUE ou GRAY." });
    }
    const today = todayBRT();
    const monthStart = today.slice(0, 8) + "01";
    const start = req.query.start || monthStart;
    const end = req.query.end || today;
    const { rows } = await pool.query(queries.TOP_MACHINES_BY_COLOR, [color, start, end]);
    res.json({ color, count: rows.length, machines: rows, period: { start, end } });
  } catch (err) {
    console.error("[RTA] Erro em /api/alerts/ranking:", err.message);
    res.status(500).json({ error: "Erro ao buscar ranking: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// Fallback: SPA — qualquer rota nao-API serve o index.html
// ---------------------------------------------------------------------------
app.get("*", (req, res) => {
  logAccess(req); // fire-and-forget — registra acesso no Command Center
  res.sendFile(path.join(frontendPath, "index.html"));
});

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[RTA] Real Time Alert rodando na porta ${PORT}`);
  console.log(`[RTA] Frontend: http://localhost:${PORT}`);
  console.log(`[RTA] API: http://localhost:${PORT}/api/alerts/counts`);
});
