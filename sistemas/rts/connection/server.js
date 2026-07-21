const path = require("path");

// .env centralizado em C:\env\.env no host Windows.
// No container Linux, o docker-compose monta esse arquivo em /app/.env
// (equivalente a path.join(__dirname, "..", ".env") a partir de /app/connection/).
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
const _dotenvResult = require("dotenv").config({ path: _envPath });
if (_dotenvResult.error) {
  console.error("[RTS] Erro ao carregar .env:", _dotenvResult.error.message);
  console.error("[RTS] Caminho tentado:", _envPath);
} else {
  console.log("[RTS] .env carregado de:", _envPath);
}

const express = require("express"),
  app = express(),
  db = require("./db"),
  { DateTime } = require("luxon"),
  server = require("http").createServer(app),
  io = require("socket.io")(server),
  crypto = require("crypto");

// ─── SSO — Command Center ────────────────────────────────────────────────────
// O login deixou de ser próprio do RTS. O Command Center (portal) emite o
// cookie `portal_token` (JWT HS256, assinado com PORTAL_JWT_SECRET) e o RTS
// apenas valida esse cookie. Sem cookie-parser: lemos o cookie do header.
const _PORTAL_JWT_SECRET   = process.env.PORTAL_JWT_SECRET || "";
const _COMMAND_CENTER_URL  = process.env.COMMAND_CENTER_URL || "";
const _COMMAND_CENTER_PORT = process.env.COMMAND_CENTER_PORT || "4001";

// Lê um cookie do header da requisição (RTS não usa cookie-parser).
function getCookie(req, name) {
  const raw = req.headers.cookie || "";
  for (const part of raw.split(";")) {
    const i = part.indexOf("=");
    if (i > -1 && part.slice(0, i).trim() === name) {
      return decodeURIComponent(part.slice(i + 1).trim());
    }
  }
  return null;
}

// Valida um JWT HS256 (header.payload.signature) assinado pelo Command Center.
function validatePortalToken(token) {
  if (!token || !_PORTAL_JWT_SECRET) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [h, p, sig] = parts;
  try {
    const header = JSON.parse(Buffer.from(h, "base64url").toString("utf8"));
    if (!header || header.alg !== "HS256") return null;
    const expected = crypto
      .createHmac("sha256", _PORTAL_JWT_SECRET)
      .update(h + "." + p)
      .digest("base64url");
    const sigBuf = Buffer.from(sig);
    const expBuf = Buffer.from(expected);
    if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) return null;
    const payload = JSON.parse(Buffer.from(p, "base64url").toString("utf8"));
    if (!payload.exp || Date.now() / 1000 > payload.exp) return null; // exp em segundos (JWT)
    return payload;
  } catch (_) {
    return null;
  }
}

// URL do Command Center; deriva do hostname da requisição se não houver env.
function commandCenterUrl(req) {
  if (_COMMAND_CENTER_URL) return _COMMAND_CENTER_URL;
  const hostname = (req.get("host") || "").split(":")[0];
  return `${req.protocol}://${hostname}:${_COMMAND_CENTER_PORT}`;
}

// Firebase Realtime Database
var admin = require("firebase-admin");
if (!process.env.SERVICE_ACCOUNT) {
  console.error("[RTS] ERRO: SERVICE_ACCOUNT não definido. Verifique o arquivo .env na raiz do projeto.");
  console.error("[RTS] .env esperado em:", _envPath);
  process.exit(1);
}
var _serviceAccountFile = path.join(__dirname, process.env.SERVICE_ACCOUNT + ".json");
console.log("[RTS] Carregando service account:", _serviceAccountFile);
var serviceAccount = require(_serviceAccountFile);

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: process.env.DATABASE_URL,
  databaseAuthVariableOverride: {
    uid: process.env.UID,
  },
});

var rtdb = admin.database();
console.log("Conectado ao RTDB");

var ref = rtdb.ref("/chats");

// ─── Estado de filtro PER-SOCKET ─────────────────────────────────────────────
// ANTES: dayInterval, queryStartDate e queryEndDate eram variáveis globais do
// processo, causando o bug onde o filtro de um usuário afetava todos os outros.
// AGORA: cada socket mantém seu próprio estado de filtro.
const _socketFilters = new Map(); // socket.id → {dayInterval, startDate, endDate}

function _getFilter(socketId) {
  if (!_socketFilters.has(socketId)) {
    _socketFilters.set(socketId, { dayInterval: 1, startDate: "", endDate: "" });
  }
  return _socketFilters.get(socketId);
}

// Monitora a mudança da última mensagem
ref.on("child_changed", function (snapshot) {
  var snap = snapshot.val();
  processMessage(snap);
});

// Monitora quando um novo número entrar em contato
ref.on("child_added", function (snapshot) {
  /**
   * OBS: se NÃO usarmos um limitToFirst(1) nessa referência, teríamos 1 vantagem e 2 desvantagens.
   *
   * Vantagem: Quando o cliente mandar uma mensagem e este server estiver desligado, o programa vai captar essa mensagem.
   * Ou seja, ele pegará todas as mensagens fora do horário do expediente após religar o server.
   *
   * Desvantagem 1: Toda vez que ligar esse server, ele retornará TODAS as mensagens.
   * (Não só as mensagens que foram enviadas enquanto o server estava OFF, mas TODAS que estiverem na nuvem).
   * Ou seja, se o volume for muito grande, significa que isso vai consumir mais do "cota gratuita de Downloads" do Firebase
   *
   * Desvantagem 2: A depender do volume que chegar ao ligar o server, pode sobrecarregar o dashboard.
   *
   */
  var snap = snapshot.val();
  processMessage(snap);
});

async function processMessage(snap) {
  try {
    // Conversão de UNIX para um formato de data e hora convencional.
    // Usa zona BRT para que a data gravada no banco seja coerente com o
    // horário local do expediente (evita data errada após 21h BRT = meia-noite UTC).
    var dtReceived = DateTime.fromSeconds(
        parseInt(snap.last_timestamp)
      ).setZone("America/Sao_Paulo");

    // IMPORTANTE: usar toISODate() garante formato "YYYY-MM-DD" com zero-padding.
    // O formato anterior (`${year}-${month}-${day}`) gerava "2026-6-17" (sem padding),
    // quebrando comparações de string nas queries WHERE data_recebimento >= $1.
    var dateReceived = dtReceived.toISODate();
    var timeReceivedFormatted = dtReceived.toFormat("HH:mm");

    // Salva no banco de dados a mensagem chegada ao servidor
    const save = await db.saveMessage(
      snap.last_id_msg,
      snap.contact_infos.profile_name,
      snap.contact_infos.phone_id,
      snap.last_message,
      dateReceived,
      timeReceivedFormatted
    );

    // ── Salva no rts_chat (histórico de conversa bidirecional) ──
    const phoneId = snap.contact_infos.phone_id;
    try {
      await db.saveChatMessage({
        telefone: phoneId,
        direcao: "in",
        mensagem: snap.last_message,
        remetente: snap.contact_infos.profile_name,
        idMensagemWpp: snap.last_id_msg,
        idSolicitacao: snap.last_id_msg,
      });

      // Notifica operadores que têm chat aberto com este telefone
      const sockets = await io.fetchSockets();
      for (const s of sockets) {
        if (s._chatPhone === phoneId) {
          s.emit("chatMessage", {
            telefone: phoneId,
            direcao: "in",
            mensagem: snap.last_message,
            remetente: snap.contact_infos.profile_name,
            data_hora: new Date().toISOString(),
          });
        }
      }
    } catch (chatErr) {
      console.warn("[RTS] Erro ao salvar msg no rts_chat:", chatErr.message);
    }

    // Envia a mensagem para o dashboard
    var data = { rtdb: snap, timestamp_arrived: Date.now() };
    if (save === true) {
      // Nova solicitação — notifica o dashboard com card novo
      io.emit("newMsgRTDB", data);
    } else if (save === "updated") {
      // Mensagem vinculada a solicitação existente — atualiza a lista
      // sem criar card novo (evita duplicação de solicitações)
      await sendInfoDBToAll(process.env.TABLE_RTDB, "msgWaitingAssist");
    }
  } catch (err) {
    console.error("[RTS] Erro em processMessage:", err.message);
  }
}
// Final do script de integração com o RTDB

// Envia dados do BD para UM socket específico, usando os filtros DELE.
async function sendInfoDBToSocket(socket, tableName, eventName) {
  try {
    const f = _getFilter(socket.id);
    const resultado = await db.selectTable(tableName, f.dayInterval, f.startDate, f.endDate);
    socket.emit(eventName, { database: resultado, time: Date.now() });
  } catch (err) {
    console.error(`[RTS] Erro ao enviar ${eventName} para socket ${socket.id}:`, err.message);
  }
}

// Envia dados do BD para TODOS os sockets, cada um com seus próprios filtros.
async function sendInfoDBToAll(tableName, eventName) {
  const sockets = await io.fetchSockets();
  for (const s of sockets) {
    try {
      const f = _getFilter(s.id);
      const resultado = await db.selectTable(tableName, f.dayInterval, f.startDate, f.endDate);
      s.emit(eventName, { database: resultado, time: Date.now() });
    } catch (err) {
      console.error(`[RTS] Erro ao enviar ${eventName} para socket ${s.id}:`, err.message);
    }
  }
}

// ─── Sessão HTTP removida — autenticação centralizada no Command Center (SSO) ──

// ─── Middleware de autenticação ────────────────────────────────────────────────
function requireAuth(req, res, next) {
  const user = validatePortalToken(getCookie(req, "portal_token"));
  if (user) {
    req.user = user; // { id, email, displayName, role, ... }
    return next();
  }
  if (req.path.startsWith("/api/")) {
    return res.status(401).json({ success: false, error: "Não autenticado. Faça login no Command Center." });
  }
  return res.redirect(commandCenterUrl(req));
}

// ─── Log de acesso no Command Center ──────────────────────────────────────────
// Notifica o Command Center de que um usuário autenticado entrou no RTS.
// Fire-and-forget: nunca bloqueia nem quebra o carregamento da página.
// Throttle em memória: no máximo 1 registro por usuário a cada 30 min.
const _accessSeen = new Map();
const _ACCESS_TTL_MS = 30 * 60 * 1000;

function logAccess(req) {
  try {
    if (typeof fetch !== "function") return;
    const token = getCookie(req, "portal_token");
    const user = req.user;
    if (!token || !user) return;

    const key = user.id || user.email || "?";
    const now = Date.now();
    if (now - (_accessSeen.get(key) || 0) < _ACCESS_TTL_MS) return;
    _accessSeen.set(key, now);

    const ip = String(req.headers["x-forwarded-for"] || req.ip || "")
      .split(",")[0].trim();
    const ua = req.headers["user-agent"] || "";

    fetch(commandCenterUrl(req) + "/api/audit/access", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Cookie": "portal_token=" + token,
        "X-Forwarded-For": ip,
        "X-Client-User-Agent": ua,
      },
      body: JSON.stringify({ system: "rts" }),
      signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout
        ? AbortSignal.timeout(4000)
        : undefined,
    }).catch((e) => console.warn("[RTS] Log de acesso falhou:", e.message));
  } catch (e) {
    console.warn("[RTS] Log de acesso erro:", e.message);
  }
}

// ─── Rotas públicas: login ─────────────────────────────────────────────────────

/** Login centralizado — redireciona para o Command Center */
app.get("/login", (req, res) => {
  return res.redirect(commandCenterUrl(req));
});

/** Login próprio do RTS desativado — autenticação unificada no Command Center */
app.post("/api/auth/login", express.json(), (req, res) => {
  return res.status(410).json({
    success: false,
    error: "O login do RTS foi unificado. Acesse pelo Command Center.",
  });
});

/** Logout — limpa cookies locais e volta ao Command Center */
app.get("/logout", (req, res) => {
  res.clearCookie("rts_token", { path: "/" });
  res.clearCookie("portal_token", { path: "/" });
  return res.redirect(commandCenterUrl(req));
});

// ─── Rotas protegidas: raiz e dashboard ───────────────────────────────────────

/** Rota raiz — exige autenticação */
app.get("/", requireAuth, (req, res) => {
  logAccess(req); // fire-and-forget — registra acesso no Command Center
  res.sendFile(path.join(__dirname, "..", "index.html"));
});

/** Bloqueia acesso direto a /index.html sem autenticação */
app.get("/index.html", requireAuth, (req, res) => {
  logAccess(req); // fire-and-forget — registra acesso no Command Center
  res.sendFile(path.join(__dirname, "..", "index.html"));
});

// Carrega os arquivos estáticos (CSS, JS, imagens, áudios, etc.)
// index: false impede que express.static sirva index.html automaticamente para /
app.use(express.static(path.join(__dirname, "/.."), { index: false }));

// Middleware para leitura de JSON no body das requisições REST
app.use(express.json());

// GET /api/me — retorna dados do usuário logado (para o frontend saber quem está autenticado)
app.get("/api/me", requireAuth, (req, res) => {
  const u = req.user || {};
  res.json({
    id: u.id || null,
    email: u.email || null,
    displayName: u.displayName || null,
    role: u.role || null,
  });
});

// ── Socket.IO — identifica usuário do Command Center via cookie ──────────────
io.use((socket, next) => {
  const raw = socket.handshake.headers.cookie || "";
  let tokenVal = null;
  for (const part of raw.split(";")) {
    const i = part.indexOf("=");
    if (i > -1 && part.slice(0, i).trim() === "portal_token") {
      tokenVal = decodeURIComponent(part.slice(i + 1).trim());
      break;
    }
  }
  const user = validatePortalToken(tokenVal);
  socket.ccUser = user; // pode ser null se não autenticado
  next(); // não bloqueia — conexões sem token ainda funcionam (compatibilidade)
});

// Logo após iniciar a página, o servidor fará o primeiro envio do banco de dados para não deixar o feed em branco
io.on("connection", async (socket) => {
  // Inicializa filtro padrão para este socket (dayInterval=1 = último dia)
  _socketFilters.set(socket.id, { dayInterval: 1, startDate: "", endDate: "" });

  await sendInfoDBToSocket(socket, process.env.TABLE_ALERTS, "newEvent");
  await sendInfoDBToSocket(socket, process.env.TABLE_RTDB, "msgWaitingAssist");

  // Escuta a mensagem enviada do dashboard para o servidor de quando o atendimento for iniciado
  socket.on("customerAssisted", async (data) => {
    try {
      var datetimeAssist = DateTime.fromMillis(data.time).toObject();
      var hourAssist = datetimeAssist.hour.toLocaleString("en-us", {
        minimumIntegerDigits: 2,
      });
      var minuteAssist = datetimeAssist.minute.toLocaleString("en-us", {
        minimumIntegerDigits: 2,
      });
      var timeAssist = `${hourAssist}:${minuteAssist}`;

      // Identifica o usuário do Command Center que iniciou o atendimento
      const ccUserName = (socket.ccUser && socket.ccUser.displayName) || data.ccUserName || null;
      const ccUserEmail = (socket.ccUser && socket.ccUser.email) || data.ccUserEmail || null;

      await db.updateAssistOnDB(data.id, timeAssist, ccUserName, ccUserEmail);

      // Re-emitir dados atualizados para todos os clientes (cada um com seus filtros)
      await sendInfoDBToAll(process.env.TABLE_RTDB, "msgWaitingAssist");
    } catch (err) {
      console.error("[RTS] Erro em customerAssisted:", err.message);
    }
  });

  // Escuta as informações escritas pelo usuário ao encerrar o atendimento
  socket.on("serviceSubmitted", async (data) => {
    try {
      // Inclui o usuário do Command Center que encerrou o atendimento
      data.ccUserName = (socket.ccUser && socket.ccUser.displayName) || data.ccUserName || null;
      data.ccUserEmail = (socket.ccUser && socket.ccUser.email) || data.ccUserEmail || null;

      // Salva as informações no BD
      await db.saveSubmittedNote(data);

      // Re-emitir dados atualizados para todos os clientes (cada um com seus filtros)
      await sendInfoDBToAll(process.env.TABLE_RTDB, "msgWaitingAssist");
    } catch (err) {
      console.error("[RTS] Erro em serviceSubmitted:", err.message);
    }
  });

  socket.on("getNoteOfService", async (data) => {
    try {
      const note = await db.selectTableWithParams(process.env.TABLE_RTDB, {
        title: "id_mensagem",
        value: data.msgId,
      });

      // Envia apenas para o socket que pediu (não para todos)
      socket.emit("sendNoteOfService", note);
    } catch (err) {
      console.error("[RTS] Erro em getNoteOfService:", err.message);
    }
  });

  socket.on("changeDayInterval", async (data) => {
    try {
      // Atualiza APENAS o filtro DESTE socket (não afeta outros usuários)
      const f = _getFilter(socket.id);
      f.dayInterval = data;
      f.startDate = "";
      f.endDate = "";

      await sendInfoDBToSocket(socket, process.env.TABLE_ALERTS, "newEvent");
      await sendInfoDBToSocket(socket, process.env.TABLE_RTDB, "msgWaitingAssist");
    } catch (err) {
      console.error("[RTS] Erro em changeDayInterval:", err.message);
    }
  });

  socket.on("changeStartAndEndDates", async (data1, data2) => {
    try {
      // Atualiza APENAS o filtro DESTE socket (não afeta outros usuários)
      const f = _getFilter(socket.id);
      f.startDate = data1;
      f.endDate = data2;
      f.dayInterval = 0;

      await sendInfoDBToSocket(socket, process.env.TABLE_ALERTS, "newEvent");
      await sendInfoDBToSocket(socket, process.env.TABLE_RTDB, "msgWaitingAssist");
    } catch (err) {
      console.error("[RTS] Erro em changeStartAndEndDates:", err.message);
    }
  });

  // ── Chat em tempo real — vincula socket ao telefone do cliente ────────────
  // Quando o operador abre o chat de um cliente, o frontend emite "chatOpen"
  // com o telefone. Isso marca o socket para receber chatMessage em tempo real.
  socket.on("chatOpen", (data) => {
    socket._chatPhone = data.telefone || null;
    console.log(`[RTS] Chat aberto: socket ${socket.id} → telefone ${socket._chatPhone}`);
  });

  socket.on("chatClose", () => {
    console.log(`[RTS] Chat fechado: socket ${socket.id} → telefone ${socket._chatPhone}`);
    socket._chatPhone = null;
  });

  // Limpa o estado do filtro e chat quando o socket desconecta (libera memória)
  socket.on("disconnect", () => {
    _socketFilters.delete(socket.id);
    // _chatPhone é limpo automaticamente com o socket
  });
});

// ─── REST API — Chat / Atendimento in-app ────────────────────────────────────

// Constantes WhatsApp Business API (reutiliza .env do rts-core)
const _WPP_PHONE_ID = process.env.PHONE_NUMBER_ID || "103829652641038";
const _WPP_API_VERSION = "v17.0";

/** Lê o token WPP do .env em runtime (mesmo padrão do whatsapp_api.py) */
function _getWppToken() {
  // Relê .env para pegar token atualizado sem restart
  require("dotenv").config({ path: _envPath, override: true });
  return process.env.TKWPP || null;
}

/**
 * POST /api/chat/send
 * Body: { telefone, mensagem, idSolicitacao }
 * Envia texto livre via WhatsApp Business API (dentro da janela de 24h)
 * e salva no rts_chat.
 */
app.post("/api/chat/send", requireAuth, async (req, res) => {
  try {
    const { telefone, mensagem, idSolicitacao } = req.body || {};

    if (!telefone || !mensagem || !mensagem.trim()) {
      return res.status(400).json({ success: false, error: "Telefone e mensagem são obrigatórios." });
    }

    const token = _getWppToken();
    if (!token) {
      return res.status(503).json({ success: false, error: "Token WhatsApp não configurado (TKWPP)." });
    }

    // Verifica janela de 24h — última mensagem inbound do cliente
    const lastInbound = await db.getLastInboundTime(telefone);
    if (lastInbound) {
      const hoursElapsed = (Date.now() - new Date(lastInbound).getTime()) / (1000 * 60 * 60);
      if (hoursElapsed > 24) {
        return res.status(422).json({
          success: false,
          error: "Janela de 24h expirada. O cliente precisa enviar uma nova mensagem para reabrir a conversa.",
          code: "WINDOW_EXPIRED",
          hoursElapsed: Math.round(hoursElapsed),
        });
      }
    }

    // Envia texto livre via WhatsApp Business API
    const url = `https://graph.facebook.com/${_WPP_API_VERSION}/${_WPP_PHONE_ID}/messages`;
    const wppPayload = {
      messaging_product: "whatsapp",
      to: `55${telefone}`,
      type: "text",
      text: { body: mensagem.trim() },
    };

    const wppRes = await fetch(url, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(wppPayload),
    });

    const wppBody = await wppRes.json();

    if (!wppRes.ok || wppBody.error) {
      const err = wppBody.error || {};
      console.error("[RTS] WhatsApp API erro ao enviar texto:", JSON.stringify(err));

      // Erro específico: janela de 24h expirada (erro 131047 ou 131028)
      if (err.code === 131047 || err.code === 131028) {
        return res.status(422).json({
          success: false,
          error: "Janela de 24h expirada. O cliente precisa enviar uma nova mensagem.",
          code: "WINDOW_EXPIRED",
        });
      }

      return res.status(502).json({
        success: false,
        error: `WhatsApp API: [${err.code || wppRes.status}] ${err.message || "Erro desconhecido"}`,
      });
    }

    // Extrai wamid da resposta da Meta
    const wamid = (wppBody.messages && wppBody.messages[0] && wppBody.messages[0].id) || null;

    // Salva no rts_chat
    const ccUser = req.user || {};
    const saved = await db.saveChatMessage({
      telefone,
      direcao: "out",
      mensagem: mensagem.trim(),
      remetente: ccUser.displayName || null,
      remetenteEmail: ccUser.email || null,
      idMensagemWpp: wamid,
      idSolicitacao: idSolicitacao || null,
    });

    // Notifica todos os sockets que têm chat aberto com este telefone
    // (inclui o remetente — para confirmar entrega)
    const sockets = await io.fetchSockets();
    for (const s of sockets) {
      if (s._chatPhone === telefone) {
        s.emit("chatMessage", {
          telefone,
          direcao: "out",
          mensagem: mensagem.trim(),
          remetente: ccUser.displayName || null,
          remetenteEmail: ccUser.email || null,
          data_hora: saved.data_hora || new Date().toISOString(),
          wamid,
        });
      }
    }

    console.log(`[RTS] Chat enviado para ${telefone} por ${ccUser.displayName || "?"}`);
    res.json({ success: true, wamid });

  } catch (err) {
    console.error("[RTS] Erro em /api/chat/send:", err.message);
    res.status(500).json({ success: false, error: "Erro interno ao enviar mensagem." });
  }
});

/**
 * GET /api/chat/history/:telefone
 * Retorna histórico de chat com um cliente.
 */
app.get("/api/chat/history/:telefone", requireAuth, async (req, res) => {
  try {
    const { telefone } = req.params;
    if (!telefone) {
      return res.status(400).json({ success: false, error: "Telefone é obrigatório." });
    }
    const messages = await db.getChatHistory(telefone);

    // Calcula se a janela de 24h ainda está aberta
    const lastInbound = await db.getLastInboundTime(telefone);
    let windowOpen = false;
    let windowExpiresAt = null;
    if (lastInbound) {
      const expiresAt = new Date(new Date(lastInbound).getTime() + 24 * 60 * 60 * 1000);
      windowOpen = Date.now() < expiresAt.getTime();
      windowExpiresAt = expiresAt.toISOString();
    }

    res.json({ success: true, messages, windowOpen, windowExpiresAt });
  } catch (err) {
    console.error("[RTS] Erro em /api/chat/history:", err.message);
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── REST API — Gerenciamento de Clientes (protegido) ─────────────────────────

/**
 * GET /api/clientes/buscar?nome=...&idOrg=...&telefone=...
 * Busca clientes na tabela `contatos` com filtros.
 * Exige pelo menos um parâmetro preenchido.
 */
app.get("/api/clientes/buscar", requireAuth, async (req, res) => {
  try {
    const { nome = "", idOrg = "", telefone = "" } = req.query;
    const result = await db.searchClientes(nome, idOrg, telefone);
    res.json({ success: true, data: result });
  } catch (err) {
    console.error("[RTS] Erro ao buscar clientes:", err.message);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * POST /api/clientes/adicionar
 * Body: { uf, cliente, idOrg, responsavel, telefone, email, cen }
 * Adiciona um novo cliente na tabela `contatos`.
 */
app.post("/api/clientes/adicionar", requireAuth, async (req, res) => {
  try {
    const {
      uf = "",
      cliente = "",
      idOrg = "",
      responsavel = "",
      telefone = "",
      email = "",
      cen = "",
    } = req.body;

    if (!cliente || cliente.trim().length === 0) {
      return res
        .status(400)
        .json({ success: false, error: "Nome do cliente é obrigatório." });
    }

    await db.addCliente(
      uf.trim(),
      cliente.trim(),
      idOrg.trim(),
      responsavel.trim(),
      telefone.trim(),
      email.trim(),
      cen.trim()
    );
    console.log(`[RTS] Cliente adicionado: ${cliente.trim()}`);
    res.json({ success: true, message: "Cliente adicionado com sucesso." });
  } catch (err) {
    // Conflito de nome duplicado — retorna 409 para o front tratar com mensagem amigável.
    if (err && err.code === "DUPLICATE_CLIENTE") {
      console.warn(`[RTS] Cadastro bloqueado — cliente duplicado: ${err.message}`);
      return res.status(409).json({ success: false, error: err.message, code: "DUPLICATE_CLIENTE" });
    }
    console.error("[RTS] Erro ao adicionar cliente:", err.message);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * PUT /api/clientes/editar/:id
 * Body: { uf, cliente, idOrg, responsavel, telefone, email, cen }
 * Atualiza os dados de um cliente existente na tabela `contatos`.
 */
app.put("/api/clientes/editar/:id", requireAuth, async (req, res) => {
  try {
    const { id } = req.params;
    const {
      uf = "",
      cliente = "",
      idOrg = "",
      responsavel = "",
      telefone = "",
      email = "",
      cen = "",
    } = req.body;

    if (!cliente || cliente.trim().length === 0) {
      return res
        .status(400)
        .json({ success: false, error: "Nome do cliente é obrigatório." });
    }

    await db.updateCliente(
      id,
      uf.trim(),
      cliente.trim(),
      idOrg.trim(),
      responsavel.trim(),
      telefone.trim(),
      email.trim(),
      cen.trim()
    );
    console.log(`[RTS] Cliente ID ${id} atualizado: ${cliente.trim()}`);
    res.json({ success: true, message: "Cliente atualizado com sucesso." });
  } catch (err) {
    // Conflito de nome duplicado na edição — retorna 409.
    if (err && err.code === "DUPLICATE_CLIENTE") {
      console.warn(`[RTS] Edição bloqueada — cliente duplicado: ${err.message}`);
      return res.status(409).json({ success: false, error: err.message, code: "DUPLICATE_CLIENTE" });
    }
    console.error("[RTS] Erro ao editar cliente:", err.message);
    res.status(500).json({ success: false, error: err.message });
  }
});

// === REST API: Configuracao dinamica (toggle WPP) ============================
// Estado consumido pelo loop Python (batch_alert_sender + runtime_config.py).
// Tabela `runtime_config` criada on-demand por db.getRuntimeConfig.
// Modos suportados:
//   AUTO       -> respeita business_hours (08h-17h50 Seg-Sex)
//   FORCE_ON   -> envia sempre (operador autorizou fora-de-hora)
//   FORCE_OFF  -> bloqueia envio ate nova ordem
//cd C:\Users\henrique.albuquerque\Desktop\RTS
// ligar o firebase
//firebase use prod
//firebase deploy --only functions
// =============================================================================

const _WPP_ALLOWED_MODES = new Set(["AUTO", "FORCE_ON", "FORCE_OFF"]);

// Emails autorizados a visualizar e alterar o modo WPP e acessar relatórios de todos os usuários.
// Outros usuários veem apenas seus próprios dados.
// Origem: RTS_WPP_ADMIN_EMAILS (CSV) no .env central (C:\env\.env).
// Se vazio, apenas o próprio usuário acessa seus dados (fail-safe: ninguém vira admin acidental).
const _WPP_ADMIN_EMAILS = new Set(
  (process.env.RTS_WPP_ADMIN_EMAILS || "")
    .split(",")
    .map(s => s.trim().toLowerCase())
    .filter(Boolean)
);

// GET /api/config/wpp-mode -> {mode, updated_at, updated_by}
// Restrito a emails em _WPP_ADMIN_EMAILS — outros recebem 403.
app.get("/api/config/wpp-mode", requireAuth, async (req, res) => {
  const email = (req.user && req.user.email) || "";
  if (!_WPP_ADMIN_EMAILS.has(email.toLowerCase())) {
    return res.status(403).json({ error: "Sem permissao para visualizar configuracao WPP." });
  }
  try {
    const row = await db.getRuntimeConfig("wpp_mode");
    if (!row) {
      return res.json({ mode: "AUTO", updated_by: "system", updated_at: null });
    }
    res.json({
      mode: row.valor,
      updated_at: row.atualizado_em,
      updated_by: row.atualizado_por,
    });
  } catch (err) {
    console.error("[RTS] Erro ao ler wpp_mode:", err.message);
    res.status(500).json({ error: "Erro ao ler configuracao" });
  }
});

// POST /api/config/wpp-mode  body: {mode: 'AUTO'|'FORCE_ON'|'FORCE_OFF'}
// Restrito a emails em _WPP_ADMIN_EMAILS — outros recebem 403.
app.post("/api/config/wpp-mode", requireAuth, async (req, res) => {
  const email = (req.user && req.user.email) || "";
  if (!_WPP_ADMIN_EMAILS.has(email.toLowerCase())) {
    return res.status(403).json({ error: "Sem permissao para alterar configuracao WPP." });
  }
  try {
    const { mode } = req.body || {};
    if (!_WPP_ALLOWED_MODES.has(mode)) {
      return res.status(400).json({
        error: "Modo invalido. Use AUTO, FORCE_ON ou FORCE_OFF.",
      });
    }
    const who = (req.user && (req.user.email || req.user.displayName)) || "-";
    await db.setRuntimeConfig("wpp_mode", mode, who);
    console.log("[RTS] wpp_mode alterado para " + mode + " por " + who);
    res.json({ ok: true, mode: mode, updated_by: who });
  } catch (err) {
    console.error("[RTS] Erro ao salvar wpp_mode:", err.message);
    res.status(500).json({ error: "Erro ao salvar configuracao" });
  }
});

// =============================================================================

// === REST API: Logs do dashboard ============================================
// 3 endpoints, todos protegidos por requireAuth, retornam JSON.
//
//   GET /api/logs/alertas?limit=50&filter=all       -> lista alertas
//   GET /api/logs/envios?limit=50                   -> apenas enviados (atalho)
//   GET /api/logs/sistema?lines=200&level=ALL       -> tail do rts-core.log
//
// /api/logs/sistema le diretamente do arquivo /app/logs/rts-core.log,
// que e bind-mount ../logs:/app/logs:ro. Se o arquivo nao existir
// (rts-core nao subiu ainda ou logs zerados), retorna lista vazia.
// =============================================================================

const _fs = require("fs");
const _LOG_FILE = "/app/logs/output/rts-core.log";

app.get("/api/logs/alertas", requireAuth, async (req, res) => {
  try {
    const limit = parseInt(req.query.limit, 10) || 50;
    const filter = (req.query.filter || "all").toString();
    const allowed = new Set(["all", "enviados", "pendentes"]);
    const f = allowed.has(filter) ? filter : "all";
    const rows = await db.getLogsAlertas(limit, f);
    res.json({ count: rows.length, filter: f, alertas: rows });
  } catch (err) {
    console.error("[RTS] Erro em /api/logs/alertas:", err.message);
    res.status(500).json({ error: "Erro ao ler alertas: " + err.message });
  }
});

app.get("/api/logs/envios", requireAuth, async (req, res) => {
  try {
    const limit = parseInt(req.query.limit, 10) || 50;
    const rows = await db.getLogsAlertas(limit, "enviados");
    res.json({ count: rows.length, envios: rows });
  } catch (err) {
    console.error("[RTS] Erro em /api/logs/envios:", err.message);
    res.status(500).json({ error: "Erro ao ler envios: " + err.message });
  }
});

app.get("/api/logs/sistema", requireAuth, (req, res) => {
  const maxLines = Math.max(10, Math.min(parseInt(req.query.lines, 10) || 200, 2000));
  const level = (req.query.level || "ALL").toString().toUpperCase();
  const allowedLevels = new Set(["ALL", "INFO", "WARNING", "ERROR"]);
  const lvl = allowedLevels.has(level) ? level : "ALL";

  _fs.stat(_LOG_FILE, (errStat, st) => {
    if (errStat) {
      return res.json({ count: 0, level: lvl, source: _LOG_FILE, lines: [], note: "Log file nao existe ainda." });
    }
    _fs.readFile(_LOG_FILE, "utf-8", (errRead, data) => {
      if (errRead) {
        console.error("[RTS] Erro ao ler log file:", errRead.message);
        return res.status(500).json({ error: "Erro ao ler log: " + errRead.message });
      }
      const all = data.split("\n").filter(Boolean);
      let filtered = all;
      if (lvl !== "ALL") {
        const re = new RegExp("\\[" + lvl + "\\]");
        filtered = all.filter((l) => re.test(l));
      }
      const tail = filtered.slice(-maxLines);
      res.json({
        count: tail.length,
        level: lvl,
        source: _LOG_FILE,
        size: st.size,
        lines: tail,
      });
    });
  });
});

// ─── Log do Firebase Deploy ──────────────────────────────────────────────────
// Expoe o conteudo de logs/firebase_deploy.log para o painel de logs de sistema.
const _FIREBASE_LOG = path.join(__dirname, "..", "logs", "firebase_deploy.log");

app.get("/api/logs/firebase", requireAuth, (req, res) => {
  const maxLines = Math.max(10, Math.min(parseInt(req.query.lines, 10) || 100, 500));
  _fs.stat(_FIREBASE_LOG, (errStat, st) => {
    if (errStat) {
      return res.json({ count: 0, source: "firebase_deploy.log", lines: [], note: "Nenhum deploy registrado ainda." });
    }
    _fs.readFile(_FIREBASE_LOG, "utf-8", (errRead, data) => {
      if (errRead) {
        return res.status(500).json({ error: "Erro ao ler log firebase: " + errRead.message });
      }
      const all = data.split("\n").filter(Boolean);
      const tail = all.slice(-maxLines);
      res.json({ count: tail.length, source: "firebase_deploy.log", size: st.size, lines: tail });
    });
  });
});

// =============================================================================
// === REST API: Métricas por usuário e relatório CSV ==========================
//
//   GET /api/metrics/tma?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&usuario=nome
//     → {rows: [{nome_perfil, dia, total_solicitacoes, total_atendidos, tma_minutos}]}
//     Usuários comuns: retorna apenas seus próprios dados (ignora param usuario).
//     Admins: podem passar usuario=all ou usuario=<nome> para ver qualquer perfil.
//
//   GET /api/metrics/usuarios
//     → {usuarios: ["Ana", "Carlos", ...]}
//     Apenas admins têm acesso.
//
//   GET /api/reports/csv?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&usuario=nome
//     → download de arquivo CSV com TM Proatividade + TM Atendimento por dia/usuário.
//
// =============================================================================

function _validateDateParam(val, fallback) {
  if (!val || !/^\d{4}-\d{2}-\d{2}$/.test(val)) return fallback;
  return val;
}

// Retorna a data de "hoje" no fuso BRT (America/Sao_Paulo) como "YYYY-MM-DD".
// Usar new Date().toISOString().slice(0,10) retorna UTC, que após 21h BRT
// já é o dia seguinte — causando queries com range errado.
function _todayBRT() {
  return DateTime.now().setZone("America/Sao_Paulo").toISODate();
}

// GET /api/metrics/tma
app.get("/api/metrics/tma", requireAuth, async (req, res) => {
  try {
    const email     = ((req.user && req.user.email) || "").toLowerCase();
    const isAdmin   = _WPP_ADMIN_EMAILS.has(email);
    const today     = _todayBRT();
    const startDate = _validateDateParam(req.query.startDate, today.slice(0, 7) + "-01");
    const endDate   = _validateDateParam(req.query.endDate,   today);

    // Usuário comum só vê seus próprios dados; admin pode escolher
    let userFilter = null;
    if (isAdmin) {
      const q = (req.query.usuario || "all").trim();
      userFilter = q === "all" ? null : q;
    } else {
      // Usa o displayName do token como nome_perfil
      userFilter = (req.user && req.user.displayName) || null;
    }

    const rows = await db.getTmaPorUsuario(startDate, endDate, userFilter);
    res.json({ rows, isAdmin, startDate, endDate });
  } catch (err) {
    console.error("[RTS] Erro em /api/metrics/tma:", err.message);
    res.status(500).json({ error: "Erro ao calcular TMA: " + err.message });
  }
});

// GET /api/metrics/usuarios — lista de perfis (apenas admins)
app.get("/api/metrics/usuarios", requireAuth, async (req, res) => {
  const email   = ((req.user && req.user.email) || "").toLowerCase();
  const isAdmin = _WPP_ADMIN_EMAILS.has(email);
  if (!isAdmin) {
    return res.status(403).json({ error: "Sem permissão." });
  }
  try {
    const [usuarios, ccUsers] = await Promise.all([
      db.getListaUsuarios(),
      db.getListaCcUsers(),
    ]);
    res.json({ usuarios, ccUsers });
  } catch (err) {
    console.error("[RTS] Erro em /api/metrics/usuarios:", err.message);
    res.status(500).json({ error: "Erro ao listar usuários: " + err.message });
  }
});

// GET /api/reports/csv
// Parâmetros: startDate, endDate, usuario (WPP profile), ccUser (Command Center user)
app.get("/api/reports/csv", requireAuth, async (req, res) => {
  try {
    const email     = ((req.user && req.user.email) || "").toLowerCase();
    const isAdmin   = _WPP_ADMIN_EMAILS.has(email);
    const today     = _todayBRT();
    const startDate = _validateDateParam(req.query.startDate, today.slice(0, 7) + "-01");
    const endDate   = _validateDateParam(req.query.endDate,   today);

    let userFilter = null;
    if (isAdmin) {
      const q = (req.query.usuario || "all").trim();
      userFilter = q === "all" ? null : q;
    } else {
      userFilter = (req.user && req.user.displayName) || null;
    }

    // Filtro por usuário do Command Center
    const ccUserParam = (req.query.ccUser || "all").trim();
    const ccUserFilter = (isAdmin && ccUserParam !== "all") ? ccUserParam : null;

    // Só busca dados por CC user se um operador específico foi selecionado
    const useCcBreakdown = ccUserFilter != null;
    const [tmaRows, tmpRows, ccRows] = await Promise.all([
      db.getTmaPorUsuario(startDate, endDate, userFilter),
      db.getTmpDiario(startDate, endDate),
      useCcBreakdown
        ? db.getTmaPorCcUser(startDate, endDate, ccUserFilter)
        : Promise.resolve([]),
    ]);

    // Indexa TMP por dia para lookup rápido
    const tmpByDay = {};
    tmpRows.forEach((r) => {
      const dia = r.dia instanceof Date
        ? DateTime.fromJSDate(r.dia).setZone("America/Sao_Paulo").toISODate()
        : String(r.dia).slice(0, 10);
      tmpByDay[dia] = r.tmp_minutos != null ? r.tmp_minutos : "";
    });

    const BOM = "﻿"; // UTF-8 BOM para Excel abrir corretamente
    const sep = ";";

    // Se um operador CC específico foi selecionado, gera CSV com breakdown
    if (useCcBreakdown) {
      // CSV com breakdown: Operador CC | Data | Contato WPP | Solicitações | Atendidos | TMA | TMP Sistema
      const header = [
        "Operador Command Center",
        "Data",
        "Contato WhatsApp",
        "Total Solicitações",
        "Total Atendidos",
        "TM Atendimento (min)",
        "TM Proatividade Sistema (min)",
      ].join(sep);

      const lines = ccRows.map((r) => {
        const dia = r.dia instanceof Date
          ? r.dia.toISOString().slice(0, 10)
          : String(r.dia).slice(0, 10);
        return [
          `"${(r.cc_user || "").replace(/"/g, '""')}"`,
          dia,
          `"${(r.nome_perfil || "").replace(/"/g, '""')}"`,
          r.total_solicitacoes ?? 0,
          r.total_atendidos    ?? 0,
          r.tma_minutos        != null ? r.tma_minutos : "",
          tmpByDay[dia]        != null ? tmpByDay[dia] : "",
        ].join(sep);
      });

      const csv = BOM + [header, ...lines].join("\r\n");
      const suffix = ccUserFilter ? `_${ccUserFilter.replace(/\s+/g, '_')}` : "_todos_operadores";
      const filename = `relatorio_rts_por_operador${suffix}_${startDate}_${endDate}.csv`;

      res.setHeader("Content-Type", "text/csv; charset=utf-8");
      res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
      return res.send(csv);
    }

    // CSV padrão (por contato WPP, sem breakdown CC)
    const header = [
      "Usuário",
      "Data",
      "Total Solicitações",
      "Total Atendidos",
      "TM Atendimento (min)",
      "TM Proatividade Sistema (min)",
    ].join(sep);

    const lines = tmaRows.map((r) => {
      const dia = r.dia instanceof Date
        ? DateTime.fromJSDate(r.dia).setZone("America/Sao_Paulo").toISODate()
        : String(r.dia).slice(0, 10);
      return [
        `"${(r.nome_perfil || "").replace(/"/g, '""')}"`,
        dia,
        r.total_solicitacoes ?? 0,
        r.total_atendidos    ?? 0,
        r.tma_minutos        != null ? r.tma_minutos : "",
        tmpByDay[dia]        != null ? tmpByDay[dia] : "",
      ].join(sep);
    });

    const csv = BOM + [header, ...lines].join("\r\n");
    const filename = `relatorio_rts_${startDate}_${endDate}.csv`;

    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
    res.send(csv);
  } catch (err) {
    console.error("[RTS] Erro em /api/reports/csv:", err.message);
    res.status(500).json({ error: "Erro ao gerar CSV: " + err.message });
  }
});

// =============================================================================

server.listen(8080);
console.log("O dashboard esta em funcionamento. Acesse-o em http://localhost:8080");

// Refresh automático a cada 30s — envia para cada socket com seus próprios filtros
setInterval(async () => {
  try {
    const sockets = await io.fetchSockets();
    for (const s of sockets) {
      const f = _getFilter(s.id);
      if (f.dayInterval > 0) {
        const resultado = await db.selectTable("alertas", f.dayInterval, f.startDate, f.endDate);
        s.emit("newEvent", { database: resultado, time: Date.now() });
      }
    }
  } catch (err) {
    console.error("[RTS] Erro no refresh automático:", err.message);
  }
}, 30000);
