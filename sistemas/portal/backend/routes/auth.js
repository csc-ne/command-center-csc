// =========== COMMAND CENTER CSC ============
// routes/auth.js — Login, registro, verificacao email, aprovacao admin
// =============================================

const express = require("express");
const crypto  = require("crypto");
const bcrypt  = require("bcryptjs");
const pool    = require("../db");
const {
  signToken,
  requireSession,
  logLoginAttempt,
} = require("../middleware/auth");
const {
  sendVerificationCode,
  sendAdminApprovalRequest,
  sendApprovalConfirmation,
} = require("../services/email");
const { logAudit } = require("../services/audit");

const router = express.Router();

const BCRYPT_ROUNDS      = 12;
const COOKIE_MAX_AGE     = 8 * 60 * 60 * 1000; // 8h
const VERIFY_CODE_TTL    = 10 * 60 * 1000; // 10 min
const APPROVAL_TOKEN_TTL = 7 * 24 * 60 * 60 * 1000; // 7 dias

// --- POST /api/auth/register ---
router.post("/register", async (req, res) => {
  try {
    const { email, password, displayName } = req.body;
    const ip = req.ip || req.connection.remoteAddress;

    if (!email || !password || !displayName) {
      return res.status(400).json({ success: false, error: "Email, senha e nome sao obrigatorios." });
    }

    const cleanEmail = email.toLowerCase().trim();

    if (!cleanEmail.endsWith("@venezanet.com")) {
      return res.status(400).json({ success: false, error: "Apenas emails @venezanet.com sao permitidos." });
    }

    if (password.length < 8) {
      return res.status(400).json({ success: false, error: "Senha deve ter no minimo 8 caracteres." });
    }

    // Verificar duplicidade
    const exists = await pool.query("SELECT id, status FROM users WHERE email = $1", [cleanEmail]);
    if (exists.rows.length > 0) {
      const user = exists.rows[0];
      if (user.status === "pending_verification") {
        const code = generateCode();
        await pool.query(
          `INSERT INTO email_verifications (user_id, code, expires_at)
           VALUES ($1, $2, NOW() + INTERVAL '10 minutes')
           ON CONFLICT (user_id) DO UPDATE SET code = $2, verified = FALSE, attempts = 0, expires_at = NOW() + INTERVAL '10 minutes'`,
          [user.id, code]
        );
        await sendVerificationCode(cleanEmail, displayName, code);
        return res.json({
          success: true,
          step: "verify_email",
          userId: user.id,
          message: "Codigo de verificacao reenviado para seu email.",
        });
      }
      if (user.status === "pending_approval") {
        return res.status(409).json({
          success: false,
          error: "Cadastro ja realizado. Aguardando aprovacao do administrador.",
          step: "pending_approval",
        });
      }
      return res.status(409).json({ success: false, error: "Email ja cadastrado." });
    }

    // Criar usuario com status pending_verification
    const passwordHash = await bcrypt.hash(password, BCRYPT_ROUNDS);
    const result = await pool.query(
      `INSERT INTO users (email, password_hash, display_name, role, status)
       VALUES ($1, $2, $3, 'operador', 'pending_verification')
       RETURNING id, email, display_name`,
      [cleanEmail, passwordHash, displayName.trim()]
    );
    const newUser = result.rows[0];

    // Gerar codigo 4 digitos
    const code = generateCode();
    await pool.query(
      `INSERT INTO email_verifications (user_id, code, expires_at)
       VALUES ($1, $2, NOW() + INTERVAL '10 minutes')
       ON CONFLICT (user_id) DO UPDATE SET code = $2, verified = FALSE, attempts = 0, expires_at = NOW() + INTERVAL '10 minutes'`,
      [newUser.id, code]
    );

    // Enviar email com codigo
    await sendVerificationCode(cleanEmail, displayName.trim(), code);

    await logAudit({
      userId: newUser.id,
      userEmail: cleanEmail,
      action: "register_started",
      category: "auth",
      details: { displayName: displayName.trim() },
      ip, userAgent: req.headers["user-agent"],
    });

    console.log(`[AUTH] Registro iniciado: ${cleanEmail}`);

    return res.status(201).json({
      success: true,
      step: "verify_email",
      userId: newUser.id,
      message: "Codigo de verificacao enviado para seu email.",
    });
  } catch (err) {
    console.error("[AUTH] Erro no registro:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- POST /api/auth/verify-email ---
router.post("/verify-email", async (req, res) => {
  try {
    const { userId, code } = req.body;
    const ip = req.ip || req.connection.remoteAddress;

    if (!userId || !code) {
      return res.status(400).json({ success: false, error: "ID e codigo sao obrigatorios." });
    }

    const verifResult = await pool.query(
      `SELECT v.*, u.email, u.display_name, u.status as user_status
       FROM email_verifications v
       JOIN users u ON u.id = v.user_id
       WHERE v.user_id = $1`,
      [userId]
    );

    if (verifResult.rows.length === 0) {
      return res.status(404).json({ success: false, error: "Nenhuma verificacao pendente." });
    }

    const verif = verifResult.rows[0];

    if (verif.verified || verif.user_status === "pending_approval") {
      return res.json({
        success: true,
        step: "pending_approval",
        message: "Email ja verificado. Aguardando aprovacao do administrador.",
      });
    }

    if (new Date(verif.expires_at) < new Date()) {
      return res.status(410).json({ success: false, error: "Codigo expirado. Faca o cadastro novamente." });
    }

    if (verif.attempts >= 5) {
      return res.status(429).json({ success: false, error: "Muitas tentativas. Faca o cadastro novamente." });
    }

    await pool.query(
      "UPDATE email_verifications SET attempts = attempts + 1 WHERE id = $1",
      [verif.id]
    );

    if (verif.code !== code.trim()) {
      return res.status(401).json({
        success: false,
        error: "Codigo incorreto.",
        attemptsLeft: 4 - verif.attempts,
      });
    }

    // Codigo correto
    await pool.query("UPDATE email_verifications SET verified = TRUE WHERE id = $1", [verif.id]);
    await pool.query(
      "UPDATE users SET status = 'pending_approval', updated_at = NOW() WHERE id = $1",
      [userId]
    );

    // Gerar token de aprovacao para o admin
    const approvalToken = crypto.randomBytes(48).toString("hex");
    await pool.query(
      `INSERT INTO approval_tokens (user_id, token, expires_at)
       VALUES ($1, $2, NOW() + INTERVAL '7 days')`,
      [userId, approvalToken]
    );

    // Enviar email ao admin
    await sendAdminApprovalRequest(verif.email, verif.display_name, approvalToken);

    await logAudit({
      userId, userEmail: verif.email,
      action: "email_verified",
      category: "auth",
      details: { approvalSentTo: "csc.ne@venezanet.com" },
      ip, userAgent: req.headers["user-agent"],
    });

    console.log(`[AUTH] Email verificado: ${verif.email}. Aguardando aprovacao admin.`);

    return res.json({
      success: true,
      step: "pending_approval",
      message: "Email verificado! Aguardando o administrador do sistema liberar seu acesso.",
    });
  } catch (err) {
    console.error("[AUTH] Erro verify-email:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- GET /api/auth/approve/:token ---
// Se ?role= presente, aprova direto (clique do email). Senao, retorna dados.
router.get("/approve/:token", async (req, res) => {
  try {
    const { token } = req.params;
    const roleFromQuery = req.query.role;
    const ip = req.ip || req.connection.remoteAddress;

    const result = await pool.query(
      `SELECT a.*, u.email, u.display_name, u.created_at as user_created
       FROM approval_tokens a
       JOIN users u ON u.id = a.user_id
       WHERE a.token = $1`,
      [token]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ success: false, error: "Token de aprovacao invalido." });
    }

    const approval = result.rows[0];

    if (approval.used) {
      return res.json({
        success: true,
        alreadyApproved: true,
        message: "Este usuario ja foi aprovado.",
        approvedRole: approval.approved_role,
        user: { email: approval.email, displayName: approval.display_name },
      });
    }

    if (new Date(approval.expires_at) < new Date()) {
      return res.status(410).json({ success: false, error: "Token de aprovacao expirado." });
    }

    // Se role veio na query, aprova direto (clique do email)
    const validRoles = ["admin", "operador", "visualizador"];
    if (roleFromQuery && validRoles.includes(roleFromQuery)) {
      await pool.query(
        "UPDATE users SET status = 'active', role = $2, is_active = TRUE, updated_at = NOW() WHERE id = $1",
        [approval.user_id, roleFromQuery]
      );
      await pool.query(
        "UPDATE approval_tokens SET used = TRUE, approved_by = $2, approved_role = $3 WHERE id = $1",
        [approval.id, "admin_via_email", roleFromQuery]
      );

      const { sendApprovalConfirmation } = require("../services/email");
      await sendApprovalConfirmation(approval.email, approval.display_name, roleFromQuery);

      await logAudit({
        userId: approval.user_id,
        userEmail: approval.email,
        action: "user_approved",
        category: "admin",
        details: { role: roleFromQuery, approvedBy: "admin_via_email" },
        ip, userAgent: req.headers["user-agent"],
      });

      console.log(`[AUTH] Usuario aprovado via email: ${approval.email} como ${roleFromQuery}`);

      return res.json({
        success: true,
        approved: true,
        message: `Acesso aprovado para ${approval.display_name} como ${roleFromQuery}.`,
        user: { email: approval.email, displayName: approval.display_name, role: roleFromQuery },
      });
    }

    // Sem role na query: retorna dados para tela de aprovacao (fallback)
    return res.json({
      success: true,
      user: {
        id: approval.user_id,
        email: approval.email,
        displayName: approval.display_name,
        createdAt: approval.user_created,
      },
      roles: ["operador", "visualizador", "admin"],
    });
  } catch (err) {
    console.error("[AUTH] Erro approve GET:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- POST /api/auth/approve ---
router.post("/approve", async (req, res) => {
  try {
    const { token, role } = req.body;
    const ip = req.ip || req.connection.remoteAddress;

    const validRoles = ["admin", "operador", "visualizador"];
    if (!token || !role || !validRoles.includes(role)) {
      return res.status(400).json({ success: false, error: "Token e nivel de acesso valido sao obrigatorios." });
    }

    const result = await pool.query(
      `SELECT a.*, u.email, u.display_name
       FROM approval_tokens a
       JOIN users u ON u.id = a.user_id
       WHERE a.token = $1`,
      [token]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ success: false, error: "Token invalido." });
    }

    const approval = result.rows[0];

    if (approval.used) {
      return res.status(410).json({ success: false, error: "Ja aprovado anteriormente." });
    }

    if (new Date(approval.expires_at) < new Date()) {
      return res.status(410).json({ success: false, error: "Token expirado." });
    }

    // Aprovar usuario
    await pool.query(
      "UPDATE users SET status = 'active', role = $2, is_active = TRUE, updated_at = NOW() WHERE id = $1",
      [approval.user_id, role]
    );

    // Marcar token como usado
    await pool.query(
      "UPDATE approval_tokens SET used = TRUE, approved_by = $2, approved_role = $3 WHERE id = $1",
      [approval.id, "admin_via_email", role]
    );

    // Enviar email de confirmacao ao usuario
    await sendApprovalConfirmation(approval.email, approval.display_name, role);

    await logAudit({
      userId: approval.user_id,
      userEmail: approval.email,
      action: "user_approved",
      category: "admin",
      details: { role, approvedBy: "admin_via_email" },
      ip, userAgent: req.headers["user-agent"],
    });

    console.log(`[AUTH] Usuario aprovado: ${approval.email} como ${role}`);

    return res.json({
      success: true,
      message: `Acesso aprovado para ${approval.display_name} como ${role}.`,
      user: {
        email: approval.email,
        displayName: approval.display_name,
        role,
      },
    });
  } catch (err) {
    console.error("[AUTH] Erro approve POST:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- POST /api/auth/check-status ---
router.post("/check-status", async (req, res) => {
  try {
    const { userId } = req.body;
    if (!userId) {
      return res.status(400).json({ success: false, error: "userId obrigatorio." });
    }

    const result = await pool.query("SELECT status FROM users WHERE id = $1", [userId]);
    if (result.rows.length === 0) {
      return res.status(404).json({ success: false, error: "Usuario nao encontrado." });
    }

    return res.json({ success: true, status: result.rows[0].status });
  } catch (err) {
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- POST /api/auth/login ---
router.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;
    const ip = req.ip || req.connection.remoteAddress;

    if (!email || !password) {
      return res.status(400).json({ success: false, error: "Email e senha sao obrigatorios." });
    }

    if (!email.endsWith("@venezanet.com")) {
      await logLoginAttempt(email, ip, false, "dominio_invalido");
      return res.status(400).json({ success: false, error: "Apenas emails @venezanet.com sao permitidos." });
    }

    const userResult = await pool.query(
      "SELECT id, email, password_hash, display_name, role, status, mfa_enabled, is_active FROM users WHERE email = $1",
      [email.toLowerCase().trim()]
    );

    if (userResult.rows.length === 0) {
      await logLoginAttempt(email, ip, false, "usuario_nao_encontrado");
      return res.status(401).json({ success: false, error: "Credenciais invalidas." });
    }

    const user = userResult.rows[0];

    // Verificar status do cadastro
    if (user.status === "pending_verification") {
      return res.status(403).json({
        success: false,
        error: "Verifique seu email primeiro.",
        step: "verify_email",
        userId: user.id,
      });
    }
    if (user.status === "pending_approval") {
      return res.status(403).json({
        success: false,
        error: "Aguardando aprovacao do administrador.",
        step: "pending_approval",
      });
    }
    if (user.status === "inactive" || !user.is_active) {
      await logLoginAttempt(email, ip, false, "usuario_inativo");
      return res.status(403).json({ success: false, error: "Conta desativada. Contate o administrador." });
    }

    // Verificar senha
    const passwordValid = await bcrypt.compare(password, user.password_hash);
    if (!passwordValid) {
      await logLoginAttempt(email, ip, false, "senha_invalida");
      return res.status(401).json({ success: false, error: "Credenciais invalidas." });
    }

    // Atualizar last_access_at
    await pool.query("UPDATE users SET last_access_at = NOW() WHERE id = $1", [user.id]);

    // Senha OK -> MFA por email (sempre)
    const pendingToken = signToken(
      { id: user.id, email: user.email, purpose: "mfa_pending" },
      "10m"
    );

    await logLoginAttempt(email, ip, true, null);
    await logAudit({
      userId: user.id, userEmail: user.email,
      action: "login_password_ok_mfa_pending",
      category: "auth", ip, userAgent: req.headers["user-agent"],
    });

    return res.json({
      success: true,
      mfaRequired: true,
      pendingToken,
      user: { email: user.email, displayName: user.display_name },
    });
  } catch (err) {
    console.error("[AUTH] Erro no login:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- GET /api/auth/me ---
router.get("/me", requireSession, async (req, res) => {
  try {
    const userResult = await pool.query(
      "SELECT id, email, display_name, role, status, mfa_enabled, last_access_at FROM users WHERE id = $1",
      [req.user.id]
    );
    if (userResult.rows.length === 0) {
      return res.status(404).json({ success: false, error: "Usuario nao encontrado." });
    }
    const u = userResult.rows[0];

    return res.json({
      success: true,
      user: {
        id: u.id, email: u.email, displayName: u.display_name,
        role: u.role, status: u.status, mfaEnabled: u.mfa_enabled,
        lastAccess: u.last_access_at,
      },
    });
  } catch (err) {
    console.error("[AUTH] Erro em /me:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// --- POST /api/auth/logout ---
router.post("/logout", (req, res) => {
  if (req.cookies.portal_token) {
    const { verifyToken } = require("../middleware/auth");
    const payload = verifyToken(req.cookies.portal_token);
    if (payload) {
      logAudit({
        userId: payload.id, userEmail: payload.email,
        action: "logout", category: "auth",
        ip: req.ip, userAgent: req.headers["user-agent"],
      });
    }
  }
  res.clearCookie("portal_token", { path: "/" });
  return res.json({ success: true, message: "Logout realizado." });
});

// --- Helper: gerar codigo 4 digitos ---
function generateCode() {
  return String(Math.floor(1000 + Math.random() * 9000));
}

module.exports = router;
