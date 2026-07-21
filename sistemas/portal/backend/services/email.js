// =========== COMMAND CENTER CSC ============
// services/email.js - Envio de emails via SMTP Office365 (Nodemailer + OAuth2 XOAUTH2)
//
// Autenticacao: OAuth2 client credentials (App-Only) via MSAL.
// - App Registration no Entra ID com Application permission SMTP.SendAsApp
// - Exchange RBAC: New-ManagementRoleAssignment "Application SMTP.SendAsApp" scoped a SMTP_USER
// - SMTP_USER precisa ser uma mailbox real e ativa (ex: csc.noreply@venezanet.com)
//
// Fluxo:
//   1. MSAL obtem access_token via client_credentials
//   2. Token e cacheado ate proximo do vencimento (5 min de margem)
//   3. Nodemailer usa auth.type "OAuth2" + accessToken -> XOAUTH2 SASL no SMTP
// =============================================

const nodemailer = require("nodemailer");
const msal = require("@azure/msal-node");

const SMTP_HOST  = process.env.SMTP_HOST  || "smtp.office365.com";
const SMTP_PORT  = parseInt(process.env.SMTP_PORT || "587", 10);
const SMTP_USER  = process.env.SMTP_USER  || "";
const SMTP_FROM  = process.env.SMTP_FROM  || SMTP_USER;
const ADMIN_EMAIL  = process.env.ADMIN_EMAIL || "csc.ne@venezanet.com";
const PORTAL_URL   = process.env.PORTAL_FRONTEND_URL || "http://localhost:4001";
const BACKEND_URL  = process.env.PORTAL_BACKEND_URL || "http://localhost:4000";

const AZURE_TENANT_ID     = process.env.AZURE_TENANT_ID     || "";
const AZURE_CLIENT_ID     = process.env.AZURE_CLIENT_ID     || "";
const AZURE_CLIENT_SECRET = process.env.AZURE_CLIENT_SECRET || "";

const AUTHORITY   = AZURE_TENANT_ID ? `https://login.microsoftonline.com/${AZURE_TENANT_ID}` : "";
const OAUTH_SCOPE = ["https://outlook.office365.com/.default"];

const OAUTH_CONFIGURED = Boolean(AZURE_TENANT_ID && AZURE_CLIENT_ID && AZURE_CLIENT_SECRET && SMTP_USER);

// --- MSAL client (singleton) ---
let msalApp = null;
if (OAUTH_CONFIGURED) {
  msalApp = new msal.ConfidentialClientApplication({
    auth: {
      clientId:     AZURE_CLIENT_ID,
      authority:    AUTHORITY,
      clientSecret: AZURE_CLIENT_SECRET,
    },
  });
}

// --- Cache manual do access_token ---
// MSAL tem cache interno mas o comportamento de acquireTokenByClientCredential varia
// entre versoes. Mantemos um cache proprio simples para garantir refresh proximo do exp.
let cachedAccessToken   = null;
let cachedTokenExpiresAt = 0; // epoch ms

async function getAccessToken() {
  if (!OAUTH_CONFIGURED) {
    throw new Error("OAuth2 nao configurado (AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET/SMTP_USER ausentes)");
  }

  const now = Date.now();
  const marginMs = 5 * 60 * 1000; // renova com 5 min de folga
  if (cachedAccessToken && now < cachedTokenExpiresAt - marginMs) {
    return cachedAccessToken;
  }

  const result = await msalApp.acquireTokenByClientCredential({ scopes: OAUTH_SCOPE });
  if (!result || !result.accessToken) {
    throw new Error("MSAL retornou resposta sem accessToken");
  }

  cachedAccessToken = result.accessToken;
  cachedTokenExpiresAt = result.expiresOn
    ? new Date(result.expiresOn).getTime()
    : now + 55 * 60 * 1000; // fallback: 55 min

  return cachedAccessToken;
}

async function createTransporter() {
  const accessToken = await getAccessToken();
  return nodemailer.createTransport({
    host: SMTP_HOST,
    port: SMTP_PORT,
    secure: false, // STARTTLS
    auth: {
      type: "OAuth2",
      user: SMTP_USER,
      accessToken, // nodemailer usa como e — nao tenta refresh (client_credentials nao suporta refresh_token)
    },
    tls: {
      ciphers: "SSLv3",
      rejectUnauthorized: false,
    },
  });
}

// --- Verificar conexao SMTP no boot ---
async function verifySmtp() {
  if (!OAUTH_CONFIGURED) {
    console.warn("[EMAIL] OAuth2 nao configurado. Emails desabilitados.");
    return false;
  }
  try {
    const t = await createTransporter();
    await t.verify();
    console.log("[EMAIL] SMTP OAuth2 conectado com sucesso (mailbox " + SMTP_USER + ").");
    return true;
  } catch (err) {
    console.error("[EMAIL] Falha na conexao SMTP OAuth2:", err.message);
    if (String(err.message).includes("535") || String(err.message).includes("5.7.3")) {
      console.error("[EMAIL] Codigo 535/5.7.3 = token invalido ou role SMTP.SendAsApp nao aplicada. Verificar RBAC no Exchange.");
    }
    return false;
  }
}

// --- Estilos compartilhados para os templates ---
const emailStyles = `
  body { margin: 0; padding: 0; background: #0a0a0a; font-family: 'Segoe UI', Arial, sans-serif; }
  .container { max-width: 520px; margin: 40px auto; background: #1a1a1a; border-radius: 10px; border: 1px solid #262626; overflow: hidden; }
  .header { background: linear-gradient(90deg, #F0AB00, #c48d00); padding: 20px 30px; }
  .header h1 { margin: 0; color: #0a0a0a; font-size: 18px; font-weight: 700; }
  .body { padding: 30px; color: #f5f5f5; line-height: 1.6; font-size: 14px; }
  .code-box { background: #141414; border: 2px solid #F0AB00; border-radius: 8px; padding: 16px; text-align: center; margin: 20px 0; }
  .code { font-size: 32px; font-weight: 800; color: #F0AB00; letter-spacing: 8px; font-family: 'Consolas', monospace; }
  .btn { display: inline-block; background: #F0AB00; color: #0a0a0a; text-decoration: none; padding: 12px 32px; border-radius: 6px; font-weight: 700; font-size: 14px; margin: 16px 0; }
  .btn:hover { background: #c48d00; }
  .info-table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  .info-table td { padding: 8px 0; color: #a3a3a3; font-size: 13px; border-bottom: 1px solid #262626; }
  .info-table td:first-child { color: #525252; width: 120px; }
  .info-table td:last-child { color: #f5f5f5; font-weight: 500; }
  .footer { padding: 16px 30px; background: #111111; text-align: center; color: #525252; font-size: 11px; }
  .muted { color: #525252; font-size: 12px; }
`;

// --- 1. Email de verificacao (4 digitos) para o usuario ---
async function sendVerificationCode(toEmail, displayName, code) {
  const html = `<!DOCTYPE html><html><head><style>${emailStyles}</style></head><body>
    <div class="container">
      <div class="header"><h1>Command Center CSC</h1></div>
      <div class="body">
        <p>Ola, <strong>${displayName}</strong>.</p>
        <p>Seu codigo de verificacao para completar o cadastro:</p>
        <div class="code-box">
          <div class="code">${code}</div>
        </div>
        <p class="muted">Este codigo expira em 10 minutos. Se voce nao solicitou este cadastro, ignore este email.</p>
      </div>
      <div class="footer">Command Center CSC - Venezanet</div>
    </div>
  </body></html>`;

  return sendMail({
    to: toEmail,
    subject: `[CSC] Codigo de verificacao: ${code}`,
    html,
  });
}

// --- 2. Email de notificacao para o admin ---
async function sendAdminApprovalRequest(userEmail, displayName, approvalToken) {
  const baseUrl = `${PORTAL_URL}/approve?token=${approvalToken}`;

  const html = `<!DOCTYPE html><html><head><style>${emailStyles}
    .role-buttons { text-align: center; margin: 24px 0; }
    .role-btn { display: inline-block; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 700; font-size: 14px; margin: 0 6px; }
    .role-btn-operador { background: #F0AB00; color: #0a0a0a; }
    .role-btn-visualizador { background: #3b82f6; color: #ffffff; }
    .role-btn-admin { background: #ef4444; color: #ffffff; }
  </style></head><body>
    <div class="container">
      <div class="header"><h1>Nova solicitacao de acesso</h1></div>
      <div class="body">
        <p>Um novo usuario solicitou acesso ao <strong>Command Center CSC</strong>:</p>
        <table class="info-table">
          <tr><td>Nome</td><td>${displayName}</td></tr>
          <tr><td>Email</td><td>${userEmail}</td></tr>
          <tr><td>Solicitado em</td><td>${new Date().toLocaleString("pt-BR", { timeZone: "America/Recife" })}</td></tr>
        </table>
        <p>Selecione o nivel de acesso para aprovar:</p>
        <div class="role-buttons">
          <a href="${baseUrl}&role=operador" class="role-btn role-btn-operador">Operador</a>
          <a href="${baseUrl}&role=visualizador" class="role-btn role-btn-visualizador">Visualizador</a>
          <a href="${baseUrl}&role=admin" class="role-btn role-btn-admin">Admin</a>
        </div>
        <p class="muted">Ao clicar, o acesso sera aprovado automaticamente com o nivel selecionado. Este link expira em 7 dias.</p>
      </div>
      <div class="footer">Command Center CSC - Venezanet</div>
    </div>
  </body></html>`;

  return sendMail({
    to: ADMIN_EMAIL,
    subject: `[CSC] Solicitacao de acesso: ${displayName} (${userEmail})`,
    html,
  });
}

// --- 3. Email de confirmacao para o usuario (acesso aprovado) ---
async function sendApprovalConfirmation(toEmail, displayName, role) {
  const roleLabels = {
    admin: "Administrador",
    operador: "Operador",
    visualizador: "Visualizador",
  };

  const html = `<!DOCTYPE html><html><head><style>${emailStyles}</style></head><body>
    <div class="container">
      <div class="header"><h1>Acesso aprovado!</h1></div>
      <div class="body">
        <p>Ola, <strong>${displayName}</strong>.</p>
        <p>Seu acesso ao <strong>Command Center CSC</strong> foi aprovado.</p>
        <table class="info-table">
          <tr><td>Nivel de acesso</td><td>${roleLabels[role] || role}</td></tr>
        </table>
        <p>Voce ja pode fazer login com o email e senha que definiu no cadastro.</p>
        <div style="text-align:center;">
          <a href="${PORTAL_URL}" class="btn">Acessar Command Center</a>
        </div>
        <p class="muted">Apos o login sera necessario configurar a autenticacao MFA (codigo no app autenticador).</p>
      </div>
      <div class="footer">Command Center CSC - Venezanet</div>
    </div>
  </body></html>`;

  return sendMail({
    to: toEmail,
    subject: "[CSC] Seu acesso foi aprovado!",
    html,
  });
}

// --- 4. Email de codigo MFA para login (6 digitos + push approval) ---
async function sendMfaLoginCode(toEmail, displayName, code, pushToken) {
  const pushUrl = `${PORTAL_URL}/api/mfa/verify-push/${pushToken}`;

  const html = `<!DOCTYPE html><html><head><style>${emailStyles}</style></head><body>
    <div class="container">
      <div class="header"><h1>Codigo de acesso — Command Center</h1></div>
      <div class="body">
        <p>Ola, <strong>${displayName}</strong>.</p>
        <p>Seu codigo de verificacao para acessar o Command Center:</p>
        <div class="code-box">
          <div class="code">${code}</div>
        </div>
        <p style="text-align:center; margin: 20px 0 8px;">Ou, se preferir, clique no botao abaixo para autorizar o login diretamente:</p>
        <div style="text-align:center;">
          <a href="${pushUrl}" class="btn">Autorizar login</a>
        </div>
        <p class="muted">Este codigo expira em 5 minutos. Se voce nao solicitou este acesso, ignore este email e considere trocar sua senha.</p>
      </div>
      <div class="footer">Command Center CSC - Venezanet</div>
    </div>
  </body></html>`;

  return sendMail({
    to: toEmail,
    subject: `[CSC] Codigo de acesso: ${code}`,
    html,
  });
}

// --- Helper interno ---
async function sendMail({ to, subject, html }) {
  if (!OAUTH_CONFIGURED) {
    console.warn(`[EMAIL] OAuth2 nao configurado. Email para ${to} nao enviado: ${subject}`);
    return { sent: false, reason: "oauth2_not_configured" };
  }

  try {
    const transporter = await createTransporter();
    const info = await transporter.sendMail({
      from: `"Command Center CSC" <${SMTP_FROM}>`,
      to,
      subject,
      html,
    });
    console.log(`[EMAIL] Enviado para ${to}: ${subject} (${info.messageId})`);
    return { sent: true, messageId: info.messageId };
  } catch (err) {
    console.error(`[EMAIL] Falha ao enviar para ${to}:`, err.message);
    // Se o token expirou entre acquire e uso, invalida o cache para forcar refresh na proxima
    if (String(err.message).match(/535|5\.7\.3|invalid.?token|unauthoriz/i)) {
      cachedAccessToken = null;
      cachedTokenExpiresAt = 0;
    }
    return { sent: false, reason: err.message };
  }
}

module.exports = {
  verifySmtp,
  sendVerificationCode,
  sendAdminApprovalRequest,
  sendApprovalConfirmation,
  sendMfaLoginCode,
  ADMIN_EMAIL,
};
