// =========== DFA Dashboard — Frontend Server ============
const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express = require("express");
const http    = require("http");

const app  = express();
const PORT = parseInt(process.env.DFA_FRONTEND_PORT || "4013", 10);
const BACKEND_URL = process.env.DFA_BACKEND_URL || "http://dfa-backend:4012";

const backendParsed = new URL(BACKEND_URL);

// ─── Manual proxy /api → backend (sem dependência de http-proxy-middleware) ──
app.use("/api", (req, res) => {
  const targetPath = "/api" + (req.url || "");
  const options = {
    hostname: backendParsed.hostname,
    port:     backendParsed.port || 4012,
    path:     targetPath,
    method:   req.method,
    headers:  { ...req.headers, host: backendParsed.host },
    timeout:  120000,
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on("error", (err) => {
    console.error("[DFA-PROXY] Erro:", err.message);
    if (!res.headersSent) {
      res.status(502).json({ success: false, error: "Backend indisponível: " + err.message });
    }
  });

  proxyReq.on("timeout", () => {
    proxyReq.destroy();
    if (!res.headersSent) {
      res.status(504).json({ success: false, error: "Backend timeout" });
    }
  });

  req.pipe(proxyReq, { end: true });
});

// Health check
app.get("/healthz", (_req, res) => res.json({ status: "ok", service: "dfa-dashboard-frontend" }));

// Arquivos estáticos
app.use(express.static(path.join(__dirname), { maxAge: "1h", etag: true }));

// SPA fallback
app.get("*", (_req, res) => res.sendFile(path.join(__dirname, "index.html")));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[DFA-FRONTEND] Rodando na porta ${PORT}`);
  console.log(`[DFA-FRONTEND] Proxy /api → ${BACKEND_URL}`);
});
