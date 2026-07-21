// =========== RCA - Relatorio de Coletas e Analises ============
// server.js — API REST para o dashboard de analises quimicas
// =============================================================

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
const PORT = parseInt(process.env.RCA_PORT || "3031", 10);

// --- SSO — Command Center -------------------------------------------------
const _PORTAL_JWT_SECRET = process.env.PORTAL_JWT_SECRET || "";
const _COMMAND_CENTER_URL = process.env.COMMAND_CENTER_URL || "";
const _COMMAND_CENTER_PORT = process.env.COMMAND_CENTER_PORT || "4001";

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
    if (!payload.exp || Date.now() / 1000 > payload.exp) return null;
    return payload;
  } catch (_) {
    return null;
  }
}

function commandCenterUrl(req) {
  if (_COMMAND_CENTER_URL) return _COMMAND_CENTER_URL;
  const hostname = (req.get("host") || "").split(":")[0];
  return `${req.protocol}://${hostname}:${_COMMAND_CENTER_PORT}`;
}

function requireAuth(req, res, next) {
  const token = req.cookies && req.cookies.portal_token;
  const user = validatePortalToken(token);
  if (user) {
    req.rcaUser = user;
    return next();
  }
  if (req.path.startsWith("/api/")) {
    return res.status(401).json({ success: false, error: "Nao autenticado. Faca login no Command Center." });
  }
  return res.redirect(commandCenterUrl(req));
}

// --- Log de acesso no Command Center --------------------------------------
const _accessSeen = new Map();
const _ACCESS_TTL_MS = 30 * 60 * 1000;

function logAccess(req) {
  try {
    if (typeof fetch !== "function") return;
    const token = req.cookies && req.cookies.portal_token;
    const user = req.rcaUser;
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
      body: JSON.stringify({ system: "rca" }),
      signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout
        ? AbortSignal.timeout(4000)
        : undefined,
    }).catch((e) => console.warn("[RCA] Log de acesso falhou:", e.message));
  } catch (e) {
    console.warn("[RCA] Log de acesso erro:", e.message);
  }
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------
app.use(cookieParser());
app.use(cors({
  origin: process.env.RCA_CORS_ORIGIN || "*",
  methods: ["GET"],
  credentials: true,
}));
app.use(express.json());

const frontendPath = path.join(__dirname, "..", "frontend");

// ---------------------------------------------------------------------------
// Health check (publico)
// ---------------------------------------------------------------------------
app.get("/healthz", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ status: "ok", service: "rca-backend", timestamp: new Date().toISOString() });
  } catch (err) {
    res.status(503).json({ status: "error", error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Protecao de autenticacao
// ---------------------------------------------------------------------------
app.use(requireAuth);

// Frontend estatico (servido apos auth)
app.use(express.static(frontendPath, { index: false }));

// ---------------------------------------------------------------------------
// Helper: extrai datas da query string
// ---------------------------------------------------------------------------
function parseDates(req) {
  const today = new Date().toISOString().slice(0, 10);
  const start = req.query.start || today;
  const end = req.query.end || today;
  return { start, end };
}

// ---------------------------------------------------------------------------
// API: Visao Geral (card grande — total de amostras)
// GET /api/rca/overview?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/overview", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const [total, criticidades, porOrigem] = await Promise.all([
      pool.query(queries.TOTAL_AMOSTRAS, [start, end]),
      pool.query(queries.DISTRIBUICAO_CRITICIDADES, [start, end]),
      pool.query(queries.AMOSTRAS_POR_ORIGEM, [start, end]),
    ]);
    res.json({
      total: total.rows[0] ? parseInt(total.rows[0].total_distinto, 10) : 0,
      criticidades: criticidades.rows,
      porOrigem: porOrigem.rows,
      period: { start, end },
    });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/overview:", err.message);
    res.status(500).json({ error: "Erro ao buscar visao geral: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras processadas por dia (grafico de linha)
// GET /api/rca/amostras-dia?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/amostras-dia", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.AMOSTRAS_POR_DIA, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/amostras-dia:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras por familia de equipamento
// GET /api/rca/amostras-familia?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/amostras-familia", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.AMOSTRAS_POR_FAMILIA, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/amostras-familia:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras por estado (novo)
// GET /api/rca/amostras-estado?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/amostras-estado", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.AMOSTRAS_POR_ESTADO, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/amostras-estado:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras por modelo (novo)
// GET /api/rca/amostras-modelo?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/amostras-modelo", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.AMOSTRAS_POR_MODELO, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/amostras-modelo:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras por compartimento (novo)
// GET /api/rca/amostras-compartimento?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/amostras-compartimento", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.AMOSTRAS_POR_COMPARTIMENTO, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/amostras-compartimento:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Resultados criticos no periodo
// GET /api/rca/criticos?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/criticos", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.RESULTADOS_CRITICOS, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/criticos:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Geolocalizacao dos resultados criticos
// GET /api/rca/geo-criticos?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/geo-criticos", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.GEO_CRITICOS, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/geo-criticos:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Ultimos resultados no periodo (tabela grande com analises)
// GET /api/rca/resultados?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/resultados", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.RESULTADOS_PERIODO, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/resultados:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras por cliente (obra_nome top 10)
// GET /api/rca/amostras-cliente?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/amostras-cliente", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const { rows } = await pool.query(queries.AMOSTRAS_POR_CLIENTE, [start, end]);
    res.json({ count: rows.length, data: rows, period: { start, end } });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/amostras-cliente:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// API: Amostras canceladas e segregadas (detalhe)
// GET /api/rca/canceladas?start=&end=
// ---------------------------------------------------------------------------
app.get("/api/rca/canceladas", async (req, res) => {
  try {
    const { start, end } = parseDates(req);
    const [detalhe, totais] = await Promise.all([
      pool.query(queries.AMOSTRAS_CANCELADAS_SEGREGADAS, [start, end]),
      pool.query(queries.TOTAL_CANCELADAS_SEGREGADAS, [start, end]),
    ]);
    res.json({
      count: detalhe.rows.length,
      detalhe: detalhe.rows,
      totais: totais.rows,
      period: { start, end },
    });
  } catch (err) {
    console.error("[RCA] Erro em /api/rca/canceladas:", err.message);
    res.status(500).json({ error: "Erro: " + err.message });
  }
});

// ---------------------------------------------------------------------------
// Fallback: SPA
// ---------------------------------------------------------------------------
app.get("*", (req, res) => {
  logAccess(req);
  res.sendFile(path.join(frontendPath, "index.html"));
});

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[RCA] Analise de Lubrificantes S360 rodando na porta ${PORT}`);
  console.log(`[RCA] Frontend: http://localhost:${PORT}`);
  console.log(`[RCA] API: http://localhost:${PORT}/api/rca/overview`);
});
