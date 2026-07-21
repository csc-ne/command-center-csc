// =========== COMMAND CENTER CSC ============
// middleware/auth.js — Validação de JWT
// ==========================================

const jwt  = require("jsonwebtoken");
const pool = require("../db");

const JWT_SECRET = process.env.PORTAL_JWT_SECRET || "portal-jwt-secret-change-me";

// ─── Middleware: requer sessão autenticada (JWT válido) ──────────────────────
function requireSession(req, res, next) {
  const token = req.cookies.portal_token;
  if (!token) {
    return res.status(401).json({ success: false, error: "Não autenticado." });
  }
  try {
    const payload = jwt.verify(token, JWT_SECRET);
    req.user = payload;
    return next();
  } catch (err) {
    return res.status(401).json({ success: false, error: "Sessão inválida ou expirada." });
  }
}

// ─── Gerar JWT ───────────────────────────────────────────────────────────────
function signToken(payload, expiresIn = "8h") {
  return jwt.sign(payload, JWT_SECRET, { expiresIn });
}

// ─── Verificar JWT sem middleware ─────────────────────────────────────────────
function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
}

// ─── Registrar tentativa de login ────────────────────────────────────────────
async function logLoginAttempt(email, ip, success, failureReason = null) {
  try {
    await pool.query(
      `INSERT INTO login_attempts (email, ip_address, success, failure_reason)
       VALUES ($1, $2, $3, $4)`,
      [email, ip, success, failureReason]
    );
  } catch (err) {
    console.error("[AUTH] Erro ao registrar tentativa:", err.message);
  }
}

module.exports = {
  requireSession,
  signToken,
  verifyToken,
  logLoginAttempt,
  JWT_SECRET,
};
