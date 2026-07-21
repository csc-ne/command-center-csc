// =========== COMMAND CENTER CSC ============
// routes/mfa.js — MFA via código por email + push approval
// ==========================================

const express = require("express");
const crypto  = require("crypto");
const pool    = require("../db");
const {
  signToken,
  verifyToken,
  logLoginAttempt,
} = require("../middleware/auth");
const { sendMfaLoginCode } = require("../services/email");

const router = express.Router();

const COOKIE_MAX_AGE = 8 * 60 * 60 * 1000; // 8h
const MFA_CODE_TTL   = 5 * 60 * 1000;       // 5 min

// Gera código numérico de 6 dígitos
function generateCode() {
  return crypto.randomInt(100000, 999999).toString();
}

// Gera token opaco para push approval
function generatePushToken() {
  return crypto.randomBytes(48).toString("hex");
}

// ─── POST /api/mfa/send-code ────────────────────────────────────────────────
// Gera código 6 dígitos + push token, salva no DB, envia email.
// Requer pendingToken (do login email+senha).
router.post("/send-code", async (req, res) => {
  try {
    const { pendingToken } = req.body;
    if (!pendingToken) {
      return res.status(400).json({ success: false, error: "Token pendente é obrigatório." });
    }

    const payload = verifyToken(pendingToken);
    if (!payload || payload.purpose !== "mfa_pending") {
      return res.status(401).json({ success: false, error: "Token inválido ou expirado." });
    }

    const userId = payload.id;
    const userEmail = payload.email;

    // Buscar display_name
    const userResult = await pool.query(
      "SELECT display_name FROM users WHERE id = $1",
      [userId]
    );
    if (userResult.rows.length === 0) {
      return res.status(404).json({ success: false, error: "Usuário não encontrado." });
    }
    const displayName = userResult.rows[0].display_name;

    // Invalidar códigos anteriores do mesmo usuário
    await pool.query(
      "DELETE FROM mfa_email_codes WHERE user_id = $1",
      [userId]
    );

    // Gerar novo código + push token
    const code = generateCode();
    const pushToken = generatePushToken();
    const expiresAt = new Date(Date.now() + MFA_CODE_TTL);

    await pool.query(
      `INSERT INTO mfa_email_codes (user_id, code, push_token, expires_at)
       VALUES ($1, $2, $3, $4)`,
      [userId, code, pushToken, expiresAt]
    );

    // Enviar email
    const emailResult = await sendMfaLoginCode(userEmail, displayName, code, pushToken);
    if (!emailResult.sent) {
      console.error(`[MFA] Falha ao enviar email MFA para ${userEmail}:`, emailResult.reason);
      return res.status(500).json({ success: false, error: "Falha ao enviar email. Tente novamente." });
    }

    console.log(`[MFA] Código enviado para ${userEmail}`);
    return res.json({
      success: true,
      message: "Código enviado para seu email.",
      expiresIn: MFA_CODE_TTL / 1000, // segundos
    });
  } catch (err) {
    console.error("[MFA] Erro send-code:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// ─── POST /api/mfa/verify ───────────────────────────────────────────────────
// Verifica código de 6 dígitos digitado pelo usuário.
router.post("/verify", async (req, res) => {
  try {
    const { pendingToken, code } = req.body;
    const ip = req.ip || req.connection.remoteAddress;

    if (!pendingToken || !code) {
      return res.status(400).json({ success: false, error: "Token e código são obrigatórios." });
    }
    if (code.length !== 6) {
      return res.status(400).json({ success: false, error: "Código deve ter 6 dígitos." });
    }

    const payload = verifyToken(pendingToken);
    if (!payload || payload.purpose !== "mfa_pending") {
      return res.status(401).json({ success: false, error: "Token inválido ou expirado." });
    }

    const userId = payload.id;
    const userEmail = payload.email;

    // Buscar código válido
    const codeResult = await pool.query(
      `SELECT id, code, verified FROM mfa_email_codes
       WHERE user_id = $1 AND expires_at > NOW()
       ORDER BY created_at DESC LIMIT 1`,
      [userId]
    );

    if (codeResult.rows.length === 0) {
      await logLoginAttempt(userEmail, ip, false, "mfa_email_codigo_expirado");
      return res.status(401).json({ success: false, error: "Código expirado. Solicite um novo." });
    }

    const mfaRecord = codeResult.rows[0];

    // Já foi aprovado via push?
    if (mfaRecord.verified) {
      return await completeLogin(res, userId, ip);
    }

    // Verificar código
    if (mfaRecord.code !== code) {
      await logLoginAttempt(userEmail, ip, false, "mfa_email_codigo_invalido");
      return res.status(401).json({ success: false, error: "Código inválido." });
    }

    // Marcar como verificado
    await pool.query("UPDATE mfa_email_codes SET verified = TRUE WHERE id = $1", [mfaRecord.id]);

    return await completeLogin(res, userId, ip);
  } catch (err) {
    console.error("[MFA] Erro verify:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// ─── GET /api/mfa/verify-push/:token ────────────────────────────────────────
// Push approval — clicado no email. Marca como verificado e retorna página de confirmação.
router.get("/verify-push/:token", async (req, res) => {
  try {
    const { token } = req.params;

    const result = await pool.query(
      `UPDATE mfa_email_codes SET verified = TRUE
       WHERE push_token = $1 AND expires_at > NOW() AND verified = FALSE
       RETURNING user_id`,
      [token]
    );

    if (result.rows.length === 0) {
      return res.send(pushResultPage(false));
    }

    console.log(`[MFA] Push approval usado para user_id=${result.rows[0].user_id}`);
    return res.send(pushResultPage(true));
  } catch (err) {
    console.error("[MFA] Erro verify-push:", err.message);
    return res.send(pushResultPage(false));
  }
});

function pushResultPage(success) {
  const title = success ? "Login autorizado!" : "Link invalido ou expirado";
  const msg = success
    ? "Voce ja pode fechar esta aba. O login sera completado automaticamente na outra janela."
    : "Este link pode ter expirado ou ja foi utilizado. Solicite um novo codigo.";
  const color = success ? "#F0AB00" : "#ef4444";
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
<style>body{margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;}
.box{text-align:center;padding:48px 32px;max-width:400px;}
h1{color:${color};font-size:24px;margin-bottom:12px;}
p{color:#a3a3a3;font-size:15px;line-height:1.5;}
</style></head><body><div class="box"><h1>${title}</h1><p>${msg}</p></div></body></html>`;
}

// ─── GET /api/mfa/check-push ────────────────────────────────────────────────
// Polling do frontend — verifica se o push foi aprovado.
router.get("/check-push", async (req, res) => {
  try {
    const { pendingToken } = req.query;
    if (!pendingToken) {
      return res.status(400).json({ success: false, error: "Token pendente é obrigatório." });
    }

    const payload = verifyToken(pendingToken);
    if (!payload || payload.purpose !== "mfa_pending") {
      return res.status(401).json({ success: false, error: "Token inválido ou expirado." });
    }

    const result = await pool.query(
      `SELECT verified FROM mfa_email_codes
       WHERE user_id = $1 AND expires_at > NOW()
       ORDER BY created_at DESC LIMIT 1`,
      [payload.id]
    );

    if (result.rows.length === 0) {
      return res.json({ success: true, approved: false, expired: true });
    }

    if (result.rows[0].verified) {
      // Push foi aprovado — completar login
      const ip = req.ip || req.connection.remoteAddress;
      return await completeLogin(res, payload.id, ip);
    }

    return res.json({ success: true, approved: false, expired: false });
  } catch (err) {
    console.error("[MFA] Erro check-push:", err.message);
    return res.status(500).json({ success: false, error: "Erro interno." });
  }
});

// ─── Helper: completar login ────────────────────────────────────────────────
async function completeLogin(res, userId, ip) {
  const userResult = await pool.query(
    "SELECT id, email, display_name, role FROM users WHERE id = $1",
    [userId]
  );
  if (userResult.rows.length === 0) {
    return res.status(404).json({ success: false, error: "Usuário não encontrado." });
  }
  const user = userResult.rows[0];

  // Ativar MFA se ainda não ativo (primeiro login = setup automático)
  await pool.query(
    "UPDATE users SET mfa_enabled = TRUE, updated_at = NOW() WHERE id = $1 AND mfa_enabled = FALSE",
    [userId]
  );

  const sessionToken = signToken({
    id:          user.id,
    email:       user.email,
    displayName: user.display_name,
    role:        user.role,
  });

  await logLoginAttempt(user.email, ip, true, null);

  // Limpar códigos usados
  await pool.query("DELETE FROM mfa_email_codes WHERE user_id = $1", [userId]);

  res.cookie("portal_token", sessionToken, {
    httpOnly: true,
    secure:   process.env.COOKIE_SECURE === "true",
    sameSite: "lax",
    maxAge:   COOKIE_MAX_AGE,
    path:     "/",
  });

  return res.json({
    success:  true,
    approved: true,
    user: {
      id:          user.id,
      email:       user.email,
      displayName: user.display_name,
      role:        user.role,
    },
  });
}

module.exports = router;
