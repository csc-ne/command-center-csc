const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

// ── PostgreSQL (principal) ────────────────────────────────────────────────────
const { Pool: PgPool } = require("pg");

const _pgPool = new PgPool({
  host:     process.env.PG_HOST,
  port:     parseInt(process.env.PG_PORT || "5432", 10),
  database: process.env.PG_DB,
  user:     process.env.PG_USER,
  password: process.env.PG_PASS,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000, // 10s — evita hang indefinido se PG estiver lento/indisponível
});

_pgPool.on("error", (err) => {
  console.error("[RTS] Erro no pool PostgreSQL:", err.message);
});

// ── MySQL (apenas para tabela usuarios — sem equivalente PG ainda) ────────────
const username  = process.env.USERNAME_DB;
const password  = process.env.PASSWORD_DB;
const host      = process.env.HOST_DB;
const schema    = process.env.SCHEMA_DB;

async function _connectMySQL() {
  if (global._mysqlConn && global._mysqlConn.connection &&
      global._mysqlConn.connection.state !== "disconnected") {
    return global._mysqlConn;
  }
  const mysql = require("mysql2/promise");
  global._mysqlConn = await mysql.createConnection(
    `mysql://${username}:${password}@${host}:3306/${schema}`
  );
  return global._mysqlConn;
}

// Mantém compat com código legado que chama connect()
async function connect() { return _connectMySQL(); }

_connectMySQL().catch((err) => {
  console.error("[RTS] Aviso: conexao MySQL falhou (usado apenas para usuarios):", err.message);
});

// ── Mensagens (rts_mensagens — PostgreSQL) ────────────────────────────────────

async function saveMessage(idMessage, profileName, phone, message, dateReceived, hourReceived) {
  const client = await _pgPool.connect();
  try {
    // 1. Dedup por id_mensagem
    const dup = await client.query(
      "SELECT id_mensagem FROM rts_mensagens WHERE id_mensagem = $1 LIMIT 1",
      [idMessage]
    );
    if (dup.rows.length > 0) return false;

    // 2. Se já existe solicitação ABERTA para o mesmo telefone, atualiza em vez de inserir
    const open = await client.query(
      "SELECT id_mensagem FROM rts_mensagens " +
      "WHERE telefone = $1 AND tipo_finalizacao IS NULL " +
      "ORDER BY data_recebimento DESC, hora_recebimento DESC LIMIT 1",
      [phone]
    );
    if (open.rows.length > 0) {
      const existingId = open.rows[0].id_mensagem;
      await client.query(
        "UPDATE rts_mensagens SET mensagem = $1, data_recebimento = $2, hora_recebimento = $3 " +
        "WHERE id_mensagem = $4",
        [message, dateReceived, hourReceived, existingId]
      );
      console.log(`[RTS] Mensagem de ${phone} vinculada à solicitação existente (${existingId}) — sem duplicata`);
      return "updated";
    }

    // 3. Nova solicitação
    await client.query(
      "INSERT INTO rts_mensagens " +
      "(id_mensagem, nome_perfil, telefone, mensagem, data_recebimento, hora_recebimento, foi_atendido, hora_atendimento) " +
      "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
      [idMessage, profileName, phone, message, dateReceived, hourReceived, false, "0"]
    );
    return true;
  } finally {
    client.release();
  }
}

async function updateAssistOnDB(messageId, timeAssist, ccUserName, ccUserEmail) {
  const client = await _pgPool.connect();
  try {
    await client.query(
      "UPDATE rts_mensagens SET foi_atendido = true, hora_atendimento = $1, " +
      "atendido_por_cc = $2, atendido_por_cc_email = $3 " +
      "WHERE id_mensagem = $4",
      [timeAssist, ccUserName || null, ccUserEmail || null, messageId]
    );
  } finally {
    client.release();
  }
}

async function saveSubmittedNote(notes) {
  const serviceTp = notes.serviceType === "finished" ? "Atendido" : "Não atendido";

  let rdrService;
  switch (notes.redirectService) {
    case "services": rdrService = "Serviços"; break;
    case "others":   rdrService = "Outros";   break;
    default:         rdrService = "Nenhum";   break;
  }

  const client = await _pgPool.connect();
  try {
    await client.query(
      "UPDATE rts_mensagens SET " +
      "tipo_finalizacao = $1, data_hora_finalizacao = $2, setor_direcionado = $3, " +
      "chassi = $4, alerta_tratado = $5, observacao = $6, " +
      "finalizado_por_cc = $7, finalizado_por_cc_email = $8 " +
      "WHERE id_mensagem = $9",
      [serviceTp, notes.dateTimeClicked, rdrService,
       notes.pinMachine, notes.alertSubject, notes.noteInput,
       notes.ccUserName || null, notes.ccUserEmail || null, notes.messageId]
    );
  } finally {
    client.release();
  }
}

// ── Normalizadores PG→Frontend ───────────────────────────────────────────────
// O PostgreSQL retorna colunas em lowercase. O frontend (script.js) espera
// UPPERCASE para alertas e mixed-case para mensagens. Esses helpers mapeiam
// os nomes para manter compatibilidade sem alterar o frontend.

function _normalizeAlertRow(row) {
  return {
    ID:            row.id,
    CHASSI:        row.chassi,
    CLIENTE:       row.cliente,
    ALERTA:        row.alerta,
    DATA_ALERTA:   row.data_alerta,
    HORA_ALERTA:   row.hora_alerta,
    DATA_ENVIO:    row.data_envio,
    HORA_ENVIO:    row.hora_envio,
    LATITUDE:      row.latitude,
    LONGITUDE:     row.longitude,
    ENVIADO_PARA:  row.enviado_para,
    ID_MENSAGEM:   row.id_mensagem,
    HORIMETRO:     row.horimetro,
  };
}

function _normalizeMessageRow(row) {
  return {
    Id_mensagem:          row.id_mensagem,
    Nome_perfil:          row.nome_perfil,
    Telefone:             row.telefone,
    Mensagem:             row.mensagem,
    Data_recebimento:     row.data_recebimento,
    Hora_Recebimento:     row.hora_recebimento,
    Foi_atendido:         row.foi_atendido,
    Hora_atendimento:     row.hora_atendimento,
    Tipo_Finalizacao:     row.tipo_finalizacao,
    Data_Hora_Finalizacao: row.data_hora_finalizacao,
    Setor_Direcionado:    row.setor_direcionado,
    Chassi:               row.chassi,
    Alerta_Tratado:       row.alerta_tratado,
    Observacao:           row.observacao,
  };
}

// ── selectTable / selectTableWithParams (PostgreSQL) ─────────────────────────
// Mapeia os nomes antigos de env (tableAlerts / tableRTDB) para as tabelas PG.

const _TABLE_MAP_NODE = {
  [process.env.TABLE_ALERTS || "alertas"]:       "rts_alertas",
  [process.env.TABLE_RTDB   || "mensagens_rtdb"]: "rts_mensagens",
};

function _resolvePgTable(tableName) {
  return _TABLE_MAP_NODE[tableName] || tableName;
}

async function selectTable(tableName, dayInterval, startDate, endDate) {
  const pgTable = _resolvePgTable(tableName);
  const isAlerts   = pgTable === "rts_alertas";
  const isMessages = pgTable === "rts_mensagens";

  let q;
  const params = [];

  if (dayInterval == 0) {
    if (isAlerts) {
      q = `SELECT * FROM ${pgTable} WHERE data_alerta::date BETWEEN $1::date AND $2::date`;
      params.push(startDate, endDate);
    } else if (isMessages) {
      q = `SELECT * FROM ${pgTable} WHERE data_recebimento::date BETWEEN $1::date AND $2::date`;
      params.push(startDate, endDate);
    } else {
      q = `SELECT * FROM ${pgTable}`;
    }
  } else {
    if (isAlerts) {
      q = `SELECT * FROM ${pgTable} WHERE data_alerta::date >= CURRENT_DATE - ${parseInt(dayInterval)}`;
    } else if (isMessages) {
      q = `SELECT * FROM ${pgTable} WHERE data_recebimento::date >= CURRENT_DATE - ${parseInt(dayInterval)}`;
    } else {
      q = `SELECT * FROM ${pgTable}`;
    }
  }

  // Ordena ASC para que o frontend (prepend) coloque o mais recente no topo
  if (isAlerts) {
    q += " ORDER BY data_alerta ASC, hora_alerta ASC";
  } else if (isMessages) {
    q += " ORDER BY data_recebimento ASC, hora_recebimento ASC";
  }

  const client = await _pgPool.connect();
  try {
    const res = await client.query(q, params);
    if (isAlerts)   return res.rows.map(_normalizeAlertRow);
    if (isMessages) return res.rows.map(_normalizeMessageRow);
    return res.rows;
  } finally {
    client.release();
  }
}

async function selectTableWithParams(tableName, params) {
  const pgTable = _resolvePgTable(tableName);
  let q;
  const values = [];

  if (params) {
    q = `SELECT * FROM ${pgTable} WHERE ${params.title} = $1`;
    values.push(params.value);
  } else {
    q = `SELECT * FROM ${pgTable}`;
  }

  const client = await _pgPool.connect();
  try {
    const res = await client.query(q, values);
    const pgTable = _resolvePgTable(tableName);
    if (pgTable === "rts_alertas")   return res.rows.map(_normalizeAlertRow);
    if (pgTable === "rts_mensagens") return res.rows.map(_normalizeMessageRow);
    return res.rows;
  } finally {
    client.release();
  }
}

// ── Logs de Alertas (rts_alertas — PostgreSQL) ────────────────────────────────

async function getLogsAlertas(limit = 50, filter = "all") {
  const lim = Math.max(1, Math.min(parseInt(limit, 10) || 50, 500));

  let where = "";
  if (filter === "enviados") {
    where = "WHERE enviado_para IS NOT NULL AND enviado_para <> '' AND enviado_para <> 'WPP_NAO_ENVIADO'";
  } else if (filter === "pendentes") {
    where = "WHERE enviado_para IS NULL OR enviado_para = '' OR enviado_para = 'WPP_NAO_ENVIADO'";
  }

  const sql =
    "SELECT id, chassi, cliente, alerta, data_alerta, hora_alerta, " +
    "horimetro, enviado_para, id_mensagem " +
    `FROM rts_alertas ${where} ` +
    "ORDER BY data_alerta DESC, hora_alerta DESC " +
    `LIMIT ${lim}`;

  const client = await _pgPool.connect();
  try {
    const res = await client.query(sql);
    return res.rows.map((r) => {
      const enviado = r.enviado_para;
      let status = "pendente";
      if (enviado && enviado !== "WPP_NAO_ENVIADO" && enviado !== "") {
        status = "enviado";
      } else if (enviado === "WPP_NAO_ENVIADO") {
        status = "falha";
      }
      return {
        id:          r.id,
        chassi:      r.chassi,
        cliente:     r.cliente,
        alerta:      r.alerta,
        data:        r.data_alerta,
        hora:        r.hora_alerta,
        horimetro:   r.horimetro,
        enviado_para: enviado,
        msg_id:      r.id_mensagem,
        status,
      };
    });
  } finally {
    client.release();
  }
}

// ── Autenticação de Usuários (MySQL — rts_usuarios não existe no PG ainda) ───

async function findUsuarioByEmail(email) {
  const conn = await _connectMySQL();
  const [rows] = await conn.query(
    `SELECT * FROM \`${schema}\`.usuarios WHERE email = ? AND ativo = 1 LIMIT 1`,
    [email]
  );
  return rows[0] || null;
}

async function updateUltimoAcesso(userId) {
  const conn = await _connectMySQL();
  await conn.query(
    `UPDATE \`${schema}\`.usuarios SET ultimo_acesso = NOW() WHERE id = ?`,
    [userId]
  );
}

// ── Gerenciamento de Clientes (rts_contatos — PostgreSQL) ─────────────────────

async function searchClientes(nome, idOrg, telefone) {
  const conditions = [];
  const params = [];
  let idx = 1;

  if (nome && nome.trim().length > 0) {
    conditions.push(`cliente ILIKE $${idx++}`);
    params.push(`%${nome.trim()}%`);
  }
  if (idOrg && idOrg.trim().length > 0) {
    conditions.push(`jdlink_id ILIKE $${idx++}`);
    params.push(`%${idOrg.trim()}%`);
  }
  if (telefone && telefone.trim().length > 0) {
    conditions.push(`telefone ILIKE $${idx++}`);
    params.push(`%${telefone.trim()}%`);
  }

  if (conditions.length === 0) return [];

  const q =
    `SELECT * FROM rts_contatos WHERE ${conditions.join(" AND ")}` +
    ` ORDER BY cliente ASC LIMIT 50`;

  const client = await _pgPool.connect();
  try {
    const res = await client.query(q, params);
    return res.rows.map(_normalizeContato);
  } finally {
    client.release();
  }
}

async function findClienteByNome(nome, ignoreId = null) {
  if (!nome || !nome.trim()) return null;

  const params = [nome.trim()];
  let q = "SELECT * FROM rts_contatos WHERE LOWER(TRIM(cliente)) = LOWER(TRIM($1)) LIMIT 1";

  if (ignoreId !== null && ignoreId !== undefined && String(ignoreId).length > 0) {
    q = "SELECT * FROM rts_contatos WHERE LOWER(TRIM(cliente)) = LOWER(TRIM($1)) AND identificador <> $2 LIMIT 1";
    params.push(ignoreId);
  }

  const client = await _pgPool.connect();
  try {
    const res = await client.query(q, params);
    return res.rows[0] ? _normalizeContato(res.rows[0]) : null;
  } finally {
    client.release();
  }
}

async function addCliente(uf, cliente, idOrg, responsavel, telefone, email, cen) {
  const existente = await findClienteByNome(cliente);
  if (existente) {
    const err = new Error(
      "Já existe um cliente cadastrado com este nome: \"" + existente.Cliente + "\"."
    );
    err.code = "DUPLICATE_CLIENTE";
    err.existente = existente;
    throw err;
  }

  const client = await _pgPool.connect();
  try {
    await client.query(
      "INSERT INTO rts_contatos (uf, cliente, jdlink_id, responsavel, telefone, email, cen) " +
      "VALUES ($1, $2, $3, $4, $5, $6, $7)",
      [uf, cliente, idOrg, responsavel, telefone, email, cen]
    );
    return true;
  } finally {
    client.release();
  }
}

async function updateCliente(id, uf, cliente, idOrg, responsavel, telefone, email, cen) {
  const colisao = await findClienteByNome(cliente, id);
  if (colisao) {
    const err = new Error(
      "Já existe outro cliente cadastrado com este nome: \"" + colisao.Cliente + "\"."
    );
    err.code = "DUPLICATE_CLIENTE";
    err.existente = colisao;
    throw err;
  }

  const client = await _pgPool.connect();
  try {
    await client.query(
      "UPDATE rts_contatos SET " +
      "uf = $1, cliente = $2, jdlink_id = $3, responsavel = $4, " +
      "telefone = $5, email = $6, cen = $7 " +
      "WHERE identificador = $8",
      [uf, cliente, idOrg, responsavel, telefone, email, cen, id]
    );
    return true;
  } finally {
    client.release();
  }
}

function _normalizeContato(row) {
  return {
    Identificador: row.identificador,
    UF:            row.uf,
    Cliente:       row.cliente,
    JDLink_ID:     row.jdlink_id,
    Responsável:   row.responsavel,
    Telefone:      row.telefone,
    Email:         row.email,
    CEN:           row.cen,
  };
}

// ── Runtime Config (rts_runtime_config — PostgreSQL) ──────────────────────────

const _RUNTIME_CONFIG_DDL_PG =
  "CREATE TABLE IF NOT EXISTS rts_runtime_config (" +
    "chave VARCHAR(64) PRIMARY KEY," +
    "valor VARCHAR(255) NOT NULL," +
    "atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP," +
    "atualizado_por VARCHAR(255) NULL" +
  ")";

async function _ensureRuntimeConfigTable() {
  const client = await _pgPool.connect();
  try {
    await client.query(_RUNTIME_CONFIG_DDL_PG);
    await client.query(
      "INSERT INTO rts_runtime_config (chave, valor, atualizado_por) " +
      "VALUES ('wpp_mode', 'AUTO', 'system') ON CONFLICT (chave) DO NOTHING"
    );
  } finally {
    client.release();
  }
}

async function getRuntimeConfig(chave) {
  await _ensureRuntimeConfigTable();
  const client = await _pgPool.connect();
  try {
    const res = await client.query(
      "SELECT valor, atualizado_em, atualizado_por FROM rts_runtime_config WHERE chave = $1 LIMIT 1",
      [chave]
    );
    return res.rows[0] || null;
  } finally {
    client.release();
  }
}

async function setRuntimeConfig(chave, valor, atualizadoPor) {
  await _ensureRuntimeConfigTable();
  const client = await _pgPool.connect();
  try {
    await client.query(
      "INSERT INTO rts_runtime_config (chave, valor, atualizado_por) VALUES ($1, $2, $3) " +
      "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, " +
      "atualizado_por = EXCLUDED.atualizado_por, atualizado_em = CURRENT_TIMESTAMP",
      [chave, valor, atualizadoPor || null]
    );
    return true;
  } finally {
    client.release();
  }
}

// ── Métricas de Tempo por Usuário ─────────────────────────────────────────────

/**
 * TM Atendimento por usuário por dia.
 * Calcula avg(hora_atendimento - hora_recebimento) apenas para:
 *   - registros atendidos (foi_atendido = true)
 *   - horário comercial: 08:00–17:50 Seg–Sex
 *   - excluindo observações com "teste"
 *   - diferença positiva (descarta inconsistências de dado)
 *
 * @param {string} startDate  YYYY-MM-DD
 * @param {string} endDate    YYYY-MM-DD
 * @param {string|null} nomePerfilFilter  null/'all' = todos; string = filtra perfil
 */
async function getTmaPorUsuario(startDate, endDate, nomePerfilFilter) {
  const client = await _pgPool.connect();
  try {
    const params = [startDate, endDate];
    let profileClause = '';
    if (nomePerfilFilter && nomePerfilFilter !== 'all') {
      params.push(nomePerfilFilter);
      profileClause = `AND m.nome_perfil = $${params.length}`;
    }

    const q = `
      SELECT
        m.nome_perfil,
        m.data_recebimento::date AS dia,
        COUNT(*)                                          AS total_solicitacoes,
        COUNT(*) FILTER (WHERE m.foi_atendido = true)     AS total_atendidos,
        ROUND(AVG(
          CASE
            WHEN m.foi_atendido = true
              AND m.hora_atendimento IS NOT NULL
              AND m.hora_atendimento <> '0'
              AND m.hora_atendimento ~ '^[0-2]?[0-9]:[0-5][0-9]$'
              AND m.hora_recebimento ~ '^[0-2]?[0-9]:[0-5][0-9]$'
              AND m.hora_atendimento::time > m.hora_recebimento::time
              AND m.hora_recebimento::time >= '08:00'::time
              AND m.hora_recebimento::time <= '17:50'::time
              AND EXTRACT(DOW FROM m.data_recebimento) BETWEEN 1 AND 5
            THEN EXTRACT(EPOCH FROM (
              m.hora_atendimento::time - m.hora_recebimento::time
            )) / 60.0
            ELSE NULL
          END
        ))::int AS tma_minutos
      FROM rts_mensagens m
      WHERE
        m.data_recebimento::date >= $1::date
        AND m.data_recebimento::date <= $2::date
        AND (m.observacao IS NULL OR m.observacao NOT ILIKE '%teste%')
        ${profileClause}
      GROUP BY m.nome_perfil, m.data_recebimento::date
      ORDER BY dia DESC, m.nome_perfil
    `;

    const res = await client.query(q, params);
    return res.rows;
  } finally {
    client.release();
  }
}

/**
 * TM Proatividade diário (sistema): avg(hora_envio - hora_alerta) em rts_alertas.
 * Métrica de sistema — não segmentada por usuário.
 */
async function getTmpDiario(startDate, endDate) {
  const client = await _pgPool.connect();
  try {
    const q = `
      SELECT
        data_envio::date AS dia,
        ROUND(AVG(
          CASE
            WHEN hora_envio  ~ '^[0-2]?[0-9]:[0-5][0-9]$'
              AND hora_alerta ~ '^[0-2]?[0-9]:[0-5][0-9]$'
              AND hora_envio::time > hora_alerta::time
            THEN EXTRACT(EPOCH FROM (hora_envio::time - hora_alerta::time)) / 60.0
            ELSE NULL
          END
        ))::int AS tmp_minutos,
        COUNT(*) FILTER (
          WHERE enviado_para IS NOT NULL
            AND enviado_para <> ''
            AND enviado_para <> 'WPP_NAO_ENVIADO'
        ) AS total_enviados
      FROM rts_alertas
      WHERE data_envio::date >= $1::date AND data_envio::date <= $2::date
      GROUP BY data_envio::date
      ORDER BY dia DESC
    `;
    const res = await client.query(q, [startDate, endDate]);
    return res.rows;
  } finally {
    client.release();
  }
}

/**
 * Relatório agrupado por usuário do Command Center (quem atendeu).
 * Retorna: cc_user, cc_email, dia, nome_perfil (contato WPP), total, atendidos, tma_minutos
 */
async function getTmaPorCcUser(startDate, endDate, ccUserFilter) {
  const client = await _pgPool.connect();
  try {
    const params = [startDate, endDate];
    let ccClause = '';
    if (ccUserFilter && ccUserFilter !== 'all') {
      params.push(ccUserFilter);
      ccClause = `AND m.atendido_por_cc = $${params.length}`;
    }

    const q = `
      SELECT
        COALESCE(m.atendido_por_cc, '(não registrado)') AS cc_user,
        m.atendido_por_cc_email AS cc_email,
        m.data_recebimento::date AS dia,
        m.nome_perfil,
        COUNT(*) AS total_solicitacoes,
        COUNT(*) FILTER (WHERE m.foi_atendido = true) AS total_atendidos,
        ROUND(AVG(
          CASE
            WHEN m.foi_atendido = true
              AND m.hora_atendimento IS NOT NULL
              AND m.hora_atendimento <> '0'
              AND m.hora_atendimento ~ '^[0-2]?[0-9]:[0-5][0-9]$'
              AND m.hora_recebimento ~ '^[0-2]?[0-9]:[0-5][0-9]$'
              AND m.hora_atendimento::time > m.hora_recebimento::time
              AND m.hora_recebimento::time >= '08:00'::time
              AND m.hora_recebimento::time <= '17:50'::time
              AND EXTRACT(DOW FROM m.data_recebimento) BETWEEN 1 AND 5
            THEN EXTRACT(EPOCH FROM (
              m.hora_atendimento::time - m.hora_recebimento::time
            )) / 60.0
            ELSE NULL
          END
        ))::int AS tma_minutos
      FROM rts_mensagens m
      WHERE
        m.data_recebimento::date >= $1::date
        AND m.data_recebimento::date <= $2::date
        AND (m.observacao IS NULL OR m.observacao NOT ILIKE '%teste%')
        ${ccClause}
      GROUP BY cc_user, m.atendido_por_cc_email, m.data_recebimento::date, m.nome_perfil
      ORDER BY cc_user, dia DESC, m.nome_perfil
    `;

    const res = await client.query(q, params);
    return res.rows;
  } finally {
    client.release();
  }
}

/** Lista de usuários CC distintos que já atenderam. */
async function getListaCcUsers() {
  const client = await _pgPool.connect();
  try {
    const res = await client.query(
      "SELECT DISTINCT atendido_por_cc FROM rts_mensagens " +
      "WHERE atendido_por_cc IS NOT NULL AND atendido_por_cc <> '' " +
      "ORDER BY atendido_por_cc"
    );
    return res.rows.map((r) => r.atendido_por_cc);
  } finally {
    client.release();
  }
}

/** Lista de nomes_perfil distintos na tabela rts_mensagens. */
async function getListaUsuarios() {
  const client = await _pgPool.connect();
  try {
    const res = await client.query(
      "SELECT DISTINCT nome_perfil FROM rts_mensagens " +
      "WHERE nome_perfil IS NOT NULL AND nome_perfil <> '' " +
      "ORDER BY nome_perfil"
    );
    return res.rows.map((r) => r.nome_perfil);
  } finally {
    client.release();
  }
}

// ── Chat em tempo real (rts_chat — PostgreSQL) ──────────────────────────────

/**
 * Salva uma mensagem de chat (entrada ou saída) na tabela rts_chat.
 *
 * @param {object} msg
 * @param {string} msg.telefone   Telefone do cliente (sem 55)
 * @param {string} msg.direcao    'in' | 'out'
 * @param {string} msg.mensagem   Corpo da mensagem
 * @param {string} msg.remetente  Nome do operador (out) ou perfil WPP (in)
 * @param {string} [msg.remetenteEmail]  Email do operador (out)
 * @param {string} [msg.idMensagemWpp]   wamid retornado pela Meta
 * @param {string} [msg.idSolicitacao]   FK lógica → rts_mensagens.id_mensagem
 * @returns {object} row inserida
 */
async function saveChatMessage(msg) {
  const client = await _pgPool.connect();
  try {
    const res = await client.query(
      `INSERT INTO rts_chat
         (telefone_cliente, direcao, mensagem, remetente, remetente_email,
          id_mensagem_wpp, id_solicitacao)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING *`,
      [
        msg.telefone,
        msg.direcao,
        msg.mensagem,
        msg.remetente || null,
        msg.remetenteEmail || null,
        msg.idMensagemWpp || null,
        msg.idSolicitacao || null,
      ]
    );
    return res.rows[0];
  } finally {
    client.release();
  }
}

/**
 * Retorna o histórico de chat de um telefone, ordenado cronologicamente.
 * Limita a 200 mensagens por padrão.
 *
 * @param {string} telefone
 * @param {number} [limit=200]
 * @returns {Array} mensagens ordenadas por data_hora ASC
 */
async function getChatHistory(telefone, limit = 200) {
  const client = await _pgPool.connect();
  try {
    const res = await client.query(
      `SELECT id, telefone_cliente, direcao, mensagem, remetente,
              remetente_email, id_mensagem_wpp, data_hora, id_solicitacao
       FROM rts_chat
       WHERE telefone_cliente = $1
       ORDER BY data_hora ASC
       LIMIT $2`,
      [telefone, Math.min(limit, 500)]
    );
    return res.rows;
  } finally {
    client.release();
  }
}

/**
 * Retorna o timestamp da última mensagem RECEBIDA (direção 'in') de um telefone.
 * Usado para calcular se a janela de 24h do WhatsApp Business ainda está aberta.
 *
 * @param {string} telefone
 * @returns {Date|null} data_hora da última msg inbound, ou null se não houver
 */
async function getLastInboundTime(telefone) {
  const client = await _pgPool.connect();
  try {
    const res = await client.query(
      `SELECT data_hora FROM rts_chat
       WHERE telefone_cliente = $1 AND direcao = 'in'
       ORDER BY data_hora DESC LIMIT 1`,
      [telefone]
    );
    return res.rows[0] ? res.rows[0].data_hora : null;
  } finally {
    client.release();
  }
}

// ── Exports ───────────────────────────────────────────────────────────────────

module.exports = {
  connect,
  selectTable,
  selectTableWithParams,
  saveMessage,
  updateAssistOnDB,
  saveSubmittedNote,
  findUsuarioByEmail,
  updateUltimoAcesso,
  searchClientes,
  addCliente,
  updateCliente,
  findClienteByNome,
  getRuntimeConfig,
  setRuntimeConfig,
  getLogsAlertas,
  getTmaPorUsuario,
  getTmpDiario,
  getListaUsuarios,
  getTmaPorCcUser,
  getListaCcUsers,
  saveChatMessage,
  getChatHistory,
  getLastInboundTime,
};
