// =========== COMMAND CENTER CSC ============
// server.js — Frontend estático + proxy para backend API
// =============================================

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
// No container Linux, o docker-compose monta esse arquivo em /app/.env.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express     = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const cookieParser = require("cookie-parser");

const app  = express();
const PORT = parseInt(process.env.PORTAL_FRONTEND_PORT || "4001", 10);
const BACKEND_URL = process.env.PORTAL_BACKEND_URL || "http://portal-backend:4000";

// ─── Middlewares ─────────────────────────────────────────────────────────────
app.use(cookieParser());

// ─── Proxy API → backend ─────────────────────────────────────────────────────
app.use("/api", createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  xfwd: true,            // encaminha X-Forwarded-For com o IP real do cliente
  // 120s: queries pesadas do dashboard (KPIs) estouravam os 30s e o navegador
  // recebia ERR_EMPTY_RESPONSE. proxyTimeout cobre o socket backend->proxy.
  timeout: 120000,
  proxyTimeout: 120000,
  onError: (err, _req, res) => {
    console.error("[PROXY] Erro:", err.message);
    if (!res.headersSent) {
      res.status(502).json({ success: false, error: "Backend indisponível." });
    }
  },
}));

// ─── Health check (antes do static/wildcard) ────────────────────────────────
app.get("/healthz", (_req, res) => {
  res.json({ status: "ok", service: "portal-frontend" });
});

// ─── Arquivos estáticos ──────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname), {
  maxAge: "1h",
  etag: true,
}));

// ─── SPA fallback — qualquer rota não-API serve o index.html ─────────────────
app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "index.html"));
});

// ─── Start ───────────────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[CSC-FRONTEND] Rodando na porta ${PORT}`);
});
