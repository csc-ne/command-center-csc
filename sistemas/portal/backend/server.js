// =========== COMMAND CENTER CSC ============
// server.js — API de Autenticação com MFA/TOTP
// =============================================

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
// No container Linux, o docker-compose monta esse arquivo em /app/.env
// (equivalente a path.join(__dirname, "..", ".env") a partir de /app/backend/).
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express    = require("express");
const cors       = require("cors");
const helmet     = require("helmet");
const rateLimit  = require("express-rate-limit");
const cookieParser = require("cookie-parser");

const authRoutes  = require("./routes/auth");
const mfaRoutes   = require("./routes/mfa");
const adminRoutes = require("./routes/admin");
const auditRoutes = require("./routes/audit");
const dashboardRoutes = require("./routes/dashboard");
const pool        = require("./db");
const { verifySmtp } = require("./services/email");

const app  = express();
const PORT = parseInt(process.env.PORTAL_BACKEND_PORT || "4000", 10);

// O backend roda atras do proxy portal-frontend (exatamente 1 hop).
// trust proxy=1 faz req.ip usar X-Forwarded-For do proxy.
// NOTA: em ambiente Docker, todos os requests chegam via gateway interno
// (172.x.x.x), entao rate limit por IP puro nao distingue usuarios.
// Os keyGenerators abaixo combinam IP + identidade para evitar bloqueios
// indevidos quando varios usuarios estao na mesma rede/gateway Docker.
app.set("trust proxy", 1);

// ─── Middlewares globais ─────────────────────────────────────────────────────
app.use(helmet());
app.use(cors({
  origin: process.env.PORTAL_FRONTEND_URL || "http://localhost:4001",
  credentials: true,
}));
app.use(express.json({ limit: "1mb" }));
app.use(cookieParser());

// Log de acesso dos sistemas satelites (RTS/RTA/RDA/RCA) — montado ANTES do
// rate limiter: e trafego servidor-para-servidor e nao deve consumir a cota.
app.use("/api/audit", auditRoutes);

// Rate limit global — chave por IP + cookie de sessao (quando existir).
// Isso evita que todos os usuarios atras do mesmo gateway Docker compartilhem
// um unico bucket. Usuarios sem cookie usam somente IP (pre-login).
app.use(rateLimit({
  windowMs: 15 * 60 * 1000, // 15 min
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    const token = (req.cookies && req.cookies.portal_token) || "";
    // Extrai trecho unico do JWT (payload) para diferenciar usuarios
    const parts = token.split(".");
    const identity = parts.length === 3 ? parts[1].slice(0, 16) : "";
    return req.ip + ":" + identity;
  },
  message: { success: false, error: "Muitas requisicoes. Tente novamente em 15 minutos." },
}));

// Rate limit para auth — chave por email do body (registro, login).
// Cada usuario tem seu proprio bucket, independente do IP/gateway Docker.
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    const email = (req.body && req.body.email) || "";
    return email ? "auth:" + email.toLowerCase().trim() : req.ip;
  },
  message: { success: false, error: "Muitas tentativas de login. Aguarde 15 minutos." },
});

// Rate limit para MFA — chave por pendingToken (identifica o usuario
// em processo de MFA) para que cada fluxo de login tenha seu bucket.
// Limite mais alto que auth porque MFA envolve multiplos requests
// (enviar codigo, verificar codigo, push approval, polling).
const mfaLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 60,
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    // pendingToken e enviado no body de todos os endpoints MFA.
    // Extrair o payload (parte 1 do JWT) como chave unica por sessao de login.
    const pending = (req.body && req.body.pendingToken) || "";
    if (pending) {
      const parts = pending.split(".");
      if (parts.length === 3) return "mfa:" + parts[1].slice(0, 24);
    }
    // Fallback: cookie portal_token ou IP
    const portal = (req.cookies && req.cookies.portal_token) || "";
    if (portal) {
      const parts = portal.split(".");
      if (parts.length === 3) return "mfa:" + parts[1].slice(0, 24);
    }
    return req.ip;
  },
  message: { success: false, error: "Muitas tentativas de verificacao. Aguarde 15 minutos." },
});

// ─── Rotas ───────────────────────────────────────────────────────────────────
app.use("/api/auth",  authLimiter, authRoutes);
app.use("/api/mfa",   mfaLimiter,  mfaRoutes);
app.use("/api/admin", adminRoutes);
app.use("/api/dashboard", dashboardRoutes);

// ─── Health check ────────────────────────────────────────────────────────────
app.get("/healthz", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ status: "ok", service: "csc-backend" });
  } catch (err) {
    res.status(503).json({ status: "error", error: err.message });
  }
});

// ─── 404 ─────────────────────────────────────────────────────────────────────
app.use((_req, res) => {
  res.status(404).json({ success: false, error: "Rota nao encontrada." });
});

// ─── Error handler ───────────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error("[CSC-BACKEND] Erro:", err.message);
  res.status(500).json({ success: false, error: "Erro interno do servidor." });
});

// ─── Start ───────────────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", async () => {
  console.log(`[CSC-BACKEND] Rodando na porta ${PORT}`);
  await verifySmtp();
});
