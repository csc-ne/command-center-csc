// =========== COMMAND CENTER CSC ============
// routes/admin.js — Rotas administrativas (somente admins)
// =============================================

const express = require("express");
const pool    = require("../db");
const { requireSession } = require("../middleware/auth");

const router = express.Router();

// ─── Middleware: somente admin ───────────────────────────────────────────────
function requireAdmin(req, res, next) {
  if (!req.user || req.user.role !== "admin") {
    return res.status(403).json({ success: false, error: "Acesso restrito a administradores." });
  }
  return next();
}

// ─── GET /api/admin/users ────────────────────────────────────────────────────
// Lista todos os usuarios com status, role, ultimo acesso
router.get("/users", requireSession, requireAdmin, async (_req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, email, display_name, role, status, mfa_enabled, is_active,
              last_access_at, created_at, updated_at
       FROM users
       ORDER BY created_at DESC`
    );
    return res.json({ success: true, users: result.rows });
  } catch (err) {
    console.error("[ADMIN] Erro listar users:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// ─── GET /api/admin/users/pending ────────────────────────────────────────────
// Lista usuarios aguardando aprovacao
router.get("/users/pending", requireSession, requireAdmin, async (_req, res) => {
  try {
    const result = await pool.query(
      `SELECT u.id, u.email, u.display_name, u.status, u.created_at,
              a.token, a.used, a.expires_at as token_expires
       FROM users u
       LEFT JOIN approval_tokens a ON a.user_id = u.id AND a.used = FALSE
       WHERE u.status IN ('pending_verification', 'pending_approval')
       ORDER BY u.created_at DESC`
    );
    return res.json({ success: true, users: result.rows });
  } catch (err) {
    console.error("[ADMIN] Erro listar pendentes:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// ─── GET /api/admin/logs ─────────────────────────────────────────────────────
// Lista audit logs com filtros opcionais
router.get("/logs", requireSession, requireAdmin, async (req, res) => {
  try {
    const { category, userId, action, limit = 100, offset = 0 } = req.query;

    let query = "SELECT * FROM audit_logs WHERE 1=1";
    const params = [];
    let paramIdx = 1;

    if (category) {
      query += ` AND category = $${paramIdx++}`;
      params.push(category);
    }
    if (userId) {
      query += ` AND user_id = $${paramIdx++}`;
      params.push(userId);
    }
    if (action) {
      query += ` AND action LIKE $${paramIdx++}`;
      params.push(`%${action}%`);
    }

    query += ` ORDER BY created_at DESC LIMIT $${paramIdx++} OFFSET $${paramIdx++}`;
    params.push(Math.min(parseInt(limit, 10), 500), parseInt(offset, 10));

    const result = await pool.query(query, params);

    // Total para paginacao
    let countQuery = "SELECT COUNT(*) FROM audit_logs WHERE 1=1";
    const countParams = [];
    let cIdx = 1;
    if (category) { countQuery += ` AND category = $${cIdx++}`; countParams.push(category); }
    if (userId) { countQuery += ` AND user_id = $${cIdx++}`; countParams.push(userId); }
    if (action) { countQuery += ` AND action LIKE $${cIdx++}`; countParams.push(`%${action}%`); }

    const countResult = await pool.query(countQuery, countParams);

    return res.json({
      success: true,
      logs: result.rows,
      total: parseInt(countResult.rows[0].count, 10),
    });
  } catch (err) {
    console.error("[ADMIN] Erro listar logs:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

module.exports = router;
