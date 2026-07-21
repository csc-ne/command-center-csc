// =========== COMMAND CENTER CSC ============
// routes/audit.js — Registro de acessos vindos de RTS / RTA / RDA
// =============================================
//
// POST /api/audit/access
//   "Ping" de acesso enviado pelos sistemas satelites (RTS, RTA, RDA)
//   quando um usuario autenticado abre cada sistema. O usuario e
//   identificado pelo cookie portal_token (mesmo JWT do SSO) e o evento
//   e gravado em audit_logs com category='access'.
//
//   Esta rota e montada ANTES do rate limiter global (ver server.js):
//   o trafego e servidor-para-servidor (um POST por carga de pagina) e
//   nao deve consumir a cota de 100 req / 15 min compartilhada.
//
//   Nao exige perfil admin — qualquer sessao valida registra o proprio
//   acesso. A identidade vem do token assinado, nao do corpo da request,
//   entao um cliente nao consegue forjar o acesso de outro usuario.

const express = require("express");
const router  = express.Router();
const { verifyToken } = require("../middleware/auth");
const { logAudit }    = require("../services/audit");

// Sistemas satelites reconhecidos + rotulo amigavel para o detalhe do log.
const SYSTEMS = {
  rts: "RTS - Real Time Solutions",
  rta: "RTA - Real Time Alert",
  rda: "RDA - Relatorios de Desempenho",
  als: "RCA - Relatorio de Coletas e Analises",
  rca: "RCA - Relatorio de Coletas e Analises",
  fi: "FI - Fleet Intelligence",
};

router.post("/access", async (req, res) => {
  // ── Identidade: cookie de SSO emitido pelo Command Center ──────────────────
  const token = req.cookies && req.cookies.portal_token;
  const user  = token ? verifyToken(token) : null;
  if (!user) {
    return res.status(401).json({ success: false, error: "Nao autenticado." });
  }

  // ── Sistema de origem ──────────────────────────────────────────────────────
  const sys = String((req.body && req.body.system) || "").toLowerCase().trim();
  if (!SYSTEMS[sys]) {
    return res.status(400).json({ success: false, error: "Sistema invalido." });
  }

  // ── IP / User-Agent reais do cliente, encaminhados pelo sistema satelite ───
  const ip = String(req.headers["x-forwarded-for"] || req.ip || "")
    .split(",")[0].trim() || null;
  const userAgent =
    req.headers["x-client-user-agent"] || req.headers["user-agent"] || null;

  await logAudit({
    userId:    user.id || null,
    userEmail: user.email || "-",
    action:    `acesso_${sys}`,
    category:  "access",
    details:   { system: sys, systemName: SYSTEMS[sys] },
    ip,
    userAgent,
  });

  return res.json({ success: true });
});

module.exports = router;
