// =========== PSI Dashboard — Frontend Server ============
const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express = require("express");
const http    = require("http");

const app  = express();
const PORT = parseInt(process.env.PSI_FRONTEND_PORT || "4015", 10);
const BACKEND_URL = process.env.PSI_BACKEND_URL || "http://psi-backend:4014";

const backendParsed = new URL(BACKEND_URL);

// ─── Manual proxy /api → backend (sem dependência de http-proxy-middleware) ──
app.use("/api", (req, res) => {
  const targetPath = "/api" + (req.url || "");
  const options = {
    hostname: backendParsed.hostname,
    port:     backendParsed.port || 4014,
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
    console.error("[PSI-PROXY] Erro:", err.message);
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
app.get("/healthz", (_req, res) => res.json({ status: "ok", service: "psi-dashboard-frontend" }));

// index.html sempre sem cache — garante que todos os browsers carreguem o bridge atualizado
app.get("/", (_req, res) => {
  res.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  res.sendFile(path.join(__dirname, "index.html"));
});

// Outros arquivos estáticos com cache normal
app.use(express.static(path.join(__dirname), { maxAge: "1h", etag: true }));

// SPA fallback (também sem cache)
app.get("*", (_req, res) => {
  res.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  res.sendFile(path.join(__dirname, "index.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[PSI-FRONTEND] Rodando na porta ${PORT}`);
  console.log(`[PSI-FRONTEND] Proxy /api → ${BACKEND_URL}`);
});
