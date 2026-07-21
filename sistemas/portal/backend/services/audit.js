// =========== COMMAND CENTER CSC ============
// services/audit.js — Registro de acoes na plataforma (audit log)
// =============================================

const pool = require("../db");

// ─── Registrar acao no audit log ─────────────────────────────────────────────
async function logAudit({ userId, userEmail, action, category = "auth", details = null, ip = null, userAgent = null }) {
  try {
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_email, action, category, details, ip_address, user_agent)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [userId || null, userEmail, action, category, details ? JSON.stringify(details) : null, ip, userAgent]
    );
  } catch (err) {
    // Nunca deixa falha de audit quebrar o fluxo principal
    console.error("[AUDIT] Falha ao registrar:", err.message);
  }
}

module.exports = { logAudit };
