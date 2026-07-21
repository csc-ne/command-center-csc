// =========== COMMAND CENTER CSC ============
// routes/dashboard.js — KPIs e mapa do Dashboard
// =============================================
//
// Fontes de dados (mesma base csc_veneza):
//   - Maquinas comunicando/offline: layer_bronze.opc_equipment + opc_engine_hours
//     (janela de 30 dias para considerar ONLINE)
//   - Alertas criticos (RED): mesma query do RTA (ALERT_COUNTS_TOTAL),
//     somando John Deere + Wirtgen, periodo = hoje
//   - Analises de oleo criticas: mesma query do RCA (DISTRIBUICAO_CRITICIDADES),
//     status CRITICO, periodo = ultimos 30 dias
//   - Geolocalizacao: mesma query do RTA (GEO_ALERTS), com periodo dinamico
//
// NOTA schema: o pool do Command Center usa search_path=command_center,public.
// Por isso as tabelas compartilhadas sao qualificadas explicitamente
// (public.localizacao_maquinas, layer_bronze.*) para nao depender do search_path.

const express = require("express");
const pool    = require("../db");
const { requireSession } = require("../middleware/auth");

const router = express.Router();

// ---------------------------------------------------------------------------
// Maquinas comunicando x offline (frota Veneza — modelos JD + Wirtgen)
// ONLINE  = ultima comunicacao (opc_engine_hours) nos ultimos 30 dias
// OFFLINE = ultima comunicacao ha mais de 30 dias
// SEM_DADOS = nunca comunicou
// ---------------------------------------------------------------------------
const MODELOS_JD = `
  '444G','524K-II','544K-II','624K-II','644K','724K','744L','824L','844L',
  '620G','622G','670G','672G','310L','310K','310 P','700J','750J','850J',
  '130G','160G','200G','210G','250G','350G','470G','870G'
`;

const MODELOS_WIRTGEN = `
  '3411','3412','3414','HC 110','HC 110 P','HC 200 P','W 100 F','W 150 CF','W 150 F',
  'W 200 F','W 100 HR','W 100 R','W 130 Hi','SP 64','SP 94','SUPER 1300','SUPER 1303',
  'SUPER 1400','SUPER 1800-3','SUPER 800','WR 200','WR 240','HD 90K','HD O90V','HP 280'
`;

const MACHINES_COMM_SUMMARY = `
WITH equipamentos AS (
    SELECT
        oe.principal_id,
        oe.serial_number,
        oe.model_name
    FROM layer_bronze.opc_equipment AS oe
    left join public.localizacao_maquinas AS lm on lm.principal_id = oe.principal_id  
    WHERE oe.org_role_in_possession = 'true'
      AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
      AND NULLIF(TRIM(oe.serial_number), '') IS NOT NULL
      and lm.regional IN ('R1', 'R2', 'R3') -- frota comercial (filtra fora os equipamentos de teste/desenvolvimento que nao tem localizacao)
),
-- Ultima comunicacao por maquina em UMA passada (MAX + GROUP BY).
-- Equivalente ao LATERAL ORDER BY report_time DESC LIMIT 1 da query original,
-- mas sem N scans em opc_engine_hours (evita timeout quando nao ha indice
-- composto em (principal_id, report_time)).
ultimas AS (
    SELECT oeh.principal_id, MAX(oeh.report_time) AS report_time
    FROM layer_bronze.opc_engine_hours AS oeh
    WHERE oeh.principal_id IN (SELECT principal_id FROM equipamentos)
    GROUP BY oeh.principal_id
),
status_maquinas AS (
    SELECT
        e.serial_number,
        CASE
            WHEN ult.report_time IS NULL THEN 'SEM_DADOS'
            WHEN ((ult.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo')
                 >= (NOW() AT TIME ZONE 'America/Sao_Paulo') - INTERVAL '60 days'
                THEN 'ONLINE'
            ELSE 'OFFLINE'
        END AS status_comunicacao
    FROM equipamentos AS e
    LEFT JOIN ultimas AS ult ON ult.principal_id = e.principal_id
)
SELECT
    COUNT(*)                                                    AS total,
    COUNT(*) FILTER (WHERE status_comunicacao = 'ONLINE')      AS online,
    COUNT(*) FILTER (WHERE status_comunicacao = 'OFFLINE')     AS offline,
    COUNT(*) FILTER (WHERE status_comunicacao = 'SEM_DADOS')   AS sem_dados
FROM status_maquinas;
`;

// ---------------------------------------------------------------------------
// CTE de alertas — identica ao RTA (queries.js/buildCTE), com tabelas
// qualificadas. Parametros: $1 = date_start, $2 = date_end (YYYY-MM-DD).
// ---------------------------------------------------------------------------
function buildAlertCTE(dateParamStart, dateParamEnd) {
  return `
WITH alert_classified AS (
  SELECT
    oma.id_alert,
    oma.principal_id,
    oma.color,
    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' AS alert_time,
    TO_CHAR((oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY, HH24:MI') AS horario_local,
    oma.three_letter_acronym,
    oma.description AS alert_description,
    oma.latitude,
    oma.longitude,
    om.serial_number,
    om.model_name,
    tccp.a1_nome AS cliente,
    lm.estado,
    lm.cidade,
    lm.mesorregiao,
    lm.regional,
    CASE
      WHEN om.model_name IN (${MODELOS_JD}) THEN 'linha_amarela'
      WHEN om.model_name IN (${MODELOS_WIRTGEN}) THEN 'Wirtgen'
      ELSE 'outros'
    END AS tipo
  FROM layer_bronze.opc_machine_alerts oma
  LEFT JOIN layer_bronze.opc_equipment om ON om.principal_id = oma.principal_id::int
  LEFT JOIN public.localizacao_maquinas lm ON lm.principal_id = om.principal_id
  LEFT JOIN layer_bronze.tb_cliente_chassi_protheus tccp ON tccp.vv1_chassi = om.serial_number
  WHERE oma.alert_time >= (${dateParamStart}::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  ((${dateParamEnd}::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    and lm.regional IN ('R1', 'R2', 'R3') -- frota comercial (filtra fora os equipamentos de teste/desenvolvimento que nao tem localizacao)
)
`;
}

// Total de alertas RED distintos (JD + Wirtgen) — mesma metrica do RTA
// (COUNT(DISTINCT (serial_number, id_alert))) para que o KPI do Command
// Center bata exatamente com os cards do RTA.
const ALERTS_RED_TOTAL = `
${buildAlertCTE("$1", "$2")}
SELECT COALESCE(SUM(total_alertas), 0)::int AS total_red
FROM (
  SELECT COUNT(DISTINCT (serial_number, id_alert)) AS total_alertas
  FROM alert_classified
  WHERE color = 'RED'
    AND tipo <> 'outros'
    AND regional IN ('R1', 'R2', 'R3')
  GROUP BY tipo
) t;
`;

// Geolocalizacao — identica ao GEO_ALERTS do RTA
const GEO_ALERTS = `
${buildAlertCTE("$1", "$2")}
SELECT DISTINCT ON (serial_number)
  cliente,
  serial_number,
  principal_id,
  longitude,
  latitude,
  three_letter_acronym,
  alert_description,
  color,
  estado,
  cidade,
  mesorregiao,
  regional,
  tipo,
  alert_time,
  horario_local
FROM alert_classified
WHERE regional <> 'FORA'
  AND tipo <> 'outros'
  AND latitude IS NOT NULL AND longitude IS NOT NULL
  AND latitude <> 0 AND longitude <> 0
  AND ($3::text IS NULL OR color = $3)
  AND ($4::text IS NULL OR tipo = $4)
  AND ($5::text IS NULL OR regional = $5)
ORDER BY serial_number, alert_time DESC;
`;

// ---------------------------------------------------------------------------
// Analises de oleo criticas — identica ao RCA (DISTRIBUICAO_CRITICIDADES),
// filtrando somente status CRITICO. $1 = start, $2 = end.
// ---------------------------------------------------------------------------
const ANALISES_CRITICAS = `
SELECT COUNT(*)::int AS total_criticas
FROM layer_bronze.als_s360_resultado_amostra AS asraa
WHERE asraa.data_finalizacao IS NOT NULL
  AND asraa.data_finalizacao >= $1::timestamp
  AND asraa.data_finalizacao < $2::timestamp + INTERVAL '1 day'
  AND asraa.status_amostra = 'CRITICO'
  AND asraa.cliente_nome IN (
    'VENEZA EQUIPAMENTOS PESADOS - SALVADOR BA',
    'VENEZA EQUIPAMENTOS PESADOS - FORTALEZA CE',
    'VENEZA EQUIPAMENTOS PESADOS - PETROLINA PE',
    'VENEZA EQUIPAMENTOS PESADOS - RECIFE PE',
    'VENEZA EQUIPAMENTOS PESADOS - BAYUEX PB'
  );
`;

// ---------------------------------------------------------------------------
// Top 10 maquinas com mais alertas RED — mesma logica do ranking do RTA
// (TOP_MACHINES_BY_COLOR), com cliente e LIMIT no lugar do HAVING.
// Parametros: $1 = date_start, $2 = date_end
// ---------------------------------------------------------------------------
const TOP_RED_MACHINES = `
${buildAlertCTE("$1", "$2")}
SELECT
  ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rank,
  serial_number,
  regional,
  tipo,
  MAX(cliente) AS cliente,
  COUNT(*) AS quantidade_alertas
FROM alert_classified
WHERE color = 'RED'
  AND regional IN ('R1', 'R2', 'R3')
  AND tipo <> 'outros'
GROUP BY serial_number, regional, tipo
ORDER BY quantidade_alertas DESC
LIMIT 50;
`;

// ---------------------------------------------------------------------------
// Helpers de data (mesmo padrao do RTA: YYYY-MM-DD)
// ---------------------------------------------------------------------------
// Data local do servidor (TZ=America/Recife no Docker).
// NÃO usar toISOString() que retorna UTC — às 21h BRT seria dia seguinte.
function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function daysAgoStr(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
// Subtrai N dias de uma data YYYY-MM-DD (ancora no "hoje" do navegador)
function daysAgoFrom(dateStr, days) {
  const d = new Date(dateStr + "T12:00:00Z"); // meio-dia UTC evita rollover de fuso
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
function safeDate(value, fallback) {
  return (typeof value === "string" && DATE_RE.test(value)) ? value : fallback;
}

// Caches em memoria (politica definida com o usuario):
//   - Frota (maquinas comunicando/nao comunicando): 24h — janela de 30 dias,
//     muda lentamente; query mais pesada do dashboard.
//   - Analises de oleo criticas: 24h — amostras finalizadas mudam pouco no dia.
//   - Alertas RED: SEM cache — o frontend atualiza a cada 5 min via
//     /alerts-red (mesmo intervalo de refresh do RTA).
const _TTL_24H_MS = 24 * 60 * 60 * 1000;

let _machinesCache = { at: 0, row: null };
let _machinesInflight = null; // mutex: reutiliza a Promise em andamento
async function getMachinesSummary() {
  const now = Date.now();
  if (_machinesCache.row && now - _machinesCache.at < _TTL_24H_MS) {
    return _machinesCache.row;
  }
  // Se já existe uma query em andamento, reutiliza a mesma Promise
  // em vez de disparar outra execução concorrente.
  if (_machinesInflight) return _machinesInflight;
  _machinesInflight = (async () => {
    const client = await pool.connect();
    try {
      // 5 min — query com DISTINCT ON em opc_engine_hours pode levar 3-300s
      await client.query("SET statement_timeout = '300000'");
      const { rows } = await client.query(MACHINES_COMM_SUMMARY);
      await client.query("SET statement_timeout = '0'"); // reset para o pool
      _machinesCache = { at: Date.now(), row: rows[0] || {} };
      return _machinesCache.row;
    } finally {
      client.release();
      _machinesInflight = null;
    }
  })();
  return _machinesInflight;
}

// Cache por periodo (a chave muda quando o "hoje" do navegador vira o dia,
// entao na pratica expira na virada do dia mesmo antes das 24h).
let _analisesCache = { at: 0, key: "", value: null };
async function getAnalisesCriticas(start30, today) {
  const now = Date.now();
  const key = start30 + "|" + today;
  if (_analisesCache.value !== null && _analisesCache.key === key && now - _analisesCache.at < _TTL_24H_MS) {
    return _analisesCache.value;
  }
  const { rows } = await pool.query(ANALISES_CRITICAS, [start30, today]);
  const value = rows[0] ? rows[0].total_criticas : 0;
  _analisesCache = { at: now, key, value };
  return value;
}

// ─── GET /api/dashboard/summary ──────────────────────────────────────────────
// KPIs do topo: maquinas comunicando/offline, alertas RED (hoje),
// analises de oleo criticas (30 dias)
router.get("/summary", requireSession, async (req, res) => {
  try {
    // "Hoje" vem do navegador (igual ao RTA, que monta start/end no cliente).
    // Evita divergencia se o relogio/timezone do servidor diferir do usuario.
    const today = safeDate(req.query.today, todayStr());
    // Janela "30 dias" identica aos presets do RCA/RTA: hoje - 29 dias
    // (30 dias INCLUSIVE). Com -30 o resultado divergia do card do RCA.
    const start30 = daysAgoFrom(today, 29);

    // allSettled + log de duracao: uma query lenta/quebrada nao derruba o
    // endpoint inteiro (antes, qualquer falha estourava o timeout do proxy
    // e o navegador recebia ERR_EMPTY_RESPONSE).
    const t0 = Date.now();
    const timed = (label, promise) => promise.then((r) => {
      console.log(`[DASHBOARD] ${label}: ${Date.now() - t0}ms`);
      return r;
    });
    const [machines, alertsRed, analises] = await Promise.allSettled([
      timed("machines", getMachinesSummary()),
      timed("alertsRed", pool.query(ALERTS_RED_TOTAL, [today, today])),
      timed("analises", getAnalisesCriticas(start30, today)),
    ]);
    for (const [label, r] of [["machines", machines], ["alertsRed", alertsRed], ["analises", analises]]) {
      if (r.status === "rejected") console.error(`[DASHBOARD] /summary ${label} FALHOU:`, r.reason && r.reason.message);
    }

    const m = (machines.status === "fulfilled" && machines.value) || {};
    const red = alertsRed.status === "fulfilled" && alertsRed.value.rows[0]
      ? alertsRed.value.rows[0].total_red : null;
    const crit = analises.status === "fulfilled" ? analises.value : null;
    return res.json({
      success: true,
      machines: {
        total:     parseInt(m.total, 10)     || 0,
        online:    parseInt(m.online, 10)    || 0,
        offline:   parseInt(m.offline, 10)   || 0,
        semDados:  parseInt(m.sem_dados, 10) || 0,
      },
      alertasRed: red,
      analisesCriticas: crit,
      periods: {
        alertas:  { start: today, end: today },
        analises: { start: start30, end: today },
      },
    });
  } catch (err) {
    console.error("[DASHBOARD] Erro em /summary:", err.message);
    return res.status(500).json({ success: false, error: "Erro ao carregar KPIs." });
  }
});

// ─── GET /api/dashboard/alerts-red ───────────────────────────────────────────
// Somente o card Alertas Criticos (RED, hoje) — SEM cache. Chamado pelo
// frontend a cada 5 min (mesmo intervalo de refresh do RTA).
router.get("/alerts-red", requireSession, async (req, res) => {
  try {
    const today = safeDate(req.query.today, todayStr());
    const { rows } = await pool.query(ALERTS_RED_TOTAL, [today, today]);
    return res.json({ success: true, alertasRed: rows[0] ? rows[0].total_red : 0, period: { start: today, end: today } });
  } catch (err) {
    console.error("[DASHBOARD] Erro em /alerts-red:", err.message);
    return res.status(500).json({ success: false, error: "Erro ao carregar alertas." });
  }
});

// ─── GET /api/dashboard/top-red ──────────────────────────────────────────────
// Top maquinas com mais alertas RED nos ultimos 30 dias (mesma logica do
// ranking do RTA). Retorna ate 50 para permitir filtro no frontend;
// o frontend exibe as 10 primeiras.
router.get("/top-red", requireSession, async (req, res) => {
  try {
    const today = safeDate(req.query.today, todayStr());
    const start30 = daysAgoFrom(today, 29);
    const { rows } = await pool.query(TOP_RED_MACHINES, [start30, today]);
    return res.json({ success: true, count: rows.length, machines: rows, period: { start: start30, end: today } });
  } catch (err) {
    console.error("[DASHBOARD] Erro em /top-red:", err.message);
    return res.status(500).json({ success: false, error: "Erro ao carregar ranking." });
  }
});

// ─── GET /api/dashboard/geo ──────────────────────────────────────────────────
// Mapa operacional — mesma query/filtros do RTA + periodo dinamico
// ?start=YYYY-MM-DD&end=YYYY-MM-DD&color=&tipo=&regional=
router.get("/geo", requireSession, async (req, res) => {
  try {
    const today = todayStr();
    const start = safeDate(req.query.start, today);
    const end   = safeDate(req.query.end, today);
    const color    = req.query.color    || null;
    const tipo     = req.query.tipo     || null;
    const regional = req.query.regional || null;

    const { rows } = await pool.query(GEO_ALERTS, [start, end, color, tipo, regional]);
    return res.json({ success: true, count: rows.length, alerts: rows, period: { start, end } });
  } catch (err) {
    console.error("[DASHBOARD] Erro em /geo:", err.message);
    return res.status(500).json({ success: false, error: "Erro ao carregar geolocalizacao." });
  }
});

// ---------------------------------------------------------------------------
// JD Protect — status de ciclo de manutencao por maquina
// Retorna contagem por status_alerta_ciclo (EXPIRADO, CRÍTICO, MÉDIO, LEVE, OK, ...)
// ---------------------------------------------------------------------------
const JD_PROTECT_STATUS = `
WITH jd_base AS (
    SELECT DISTINCT
        jp.chassi,
        jp.cliente,
        jp.tipo_de_plano,
        jp.ciclo,
        jp.valor,
        jp.data_lancamento_svap,
        NULLIF(jp.horimetro_atual::text, '')::numeric AS horimetro_jd_protect,
        NULLIF(
            substring(jp.ciclo FROM '-\\s*([0-9]+)'),
            ''
        )::numeric AS ciclo_limite_horas
    FROM grarantia.jd_protect jp
),
equipamento_base AS (
    SELECT
        oe.serial_number,
        oe.principal_id
    FROM layer_bronze.opc_equipment oe
    INNER JOIN jd_base jp
        ON jp.chassi = oe.serial_number
    WHERE oe.org_role_in_possession = 'true'
),
equipamento_com_horimetro AS (
    SELECT
        eb.serial_number,
        eb.principal_id,
        uh.reading_value,
        uh.report_time
    FROM equipamento_base eb
    LEFT JOIN LATERAL (
        SELECT
            oeh.reading_value,
            oeh.report_time
        FROM layer_bronze.opc_engine_hours oeh
        WHERE oeh.principal_id = eb.principal_id
        ORDER BY oeh.report_time DESC
        LIMIT 1
    ) uh ON TRUE
),
equipamento AS (
    SELECT DISTINCT ON (serial_number)
        serial_number,
        principal_id,
        reading_value,
        report_time
    FROM equipamento_com_horimetro
    ORDER BY
        serial_number,
        CASE WHEN report_time IS NOT NULL THEN 1 ELSE 0 END DESC,
        report_time DESC NULLS LAST,
        principal_id
),
base AS (
    SELECT
        jp.chassi,
        jp.cliente,
        jp.tipo_de_plano,
        jp.ciclo,
        jp.valor,
        jp.data_lancamento_svap,
        eq.principal_id,
        eq.reading_value AS horimetro_opc,
        jp.horimetro_jd_protect,
        COALESCE(
            eq.reading_value,
            jp.horimetro_jd_protect,
            0
        ) AS horimetro_atual,
        CASE
            WHEN eq.reading_value IS NOT NULL THEN 'OPC_ENGINE_HOURS'
            WHEN jp.horimetro_jd_protect IS NOT NULL THEN 'JD_PROTECT'
            ELSE 'SEM_DADOS'
        END AS fonte_horimetro,
        eq.report_time AS data_ultimo_horimetro,
        jp.ciclo_limite_horas
    FROM jd_base jp
    LEFT JOIN equipamento eq
        ON eq.serial_number = jp.chassi
),
calculo AS (
    SELECT
        b.*,
        CASE
            WHEN b.fonte_horimetro = 'SEM_DADOS' THEN NULL
            WHEN b.ciclo_limite_horas IS NULL THEN NULL
            WHEN b.horimetro_atual > b.ciclo_limite_horas THEN b.ciclo_limite_horas
            ELSE LEAST(
                b.ciclo_limite_horas,
                CASE
                    WHEN b.horimetro_atual <= 0 THEN 500
                    ELSE CEIL(b.horimetro_atual / 500.0) * 500
                END
            )
        END AS proximo_ciclo_horas
    FROM base b
),
final AS (
    SELECT
        c.*,
        CASE
            WHEN c.fonte_horimetro = 'SEM_DADOS' THEN NULL
            WHEN c.ciclo_limite_horas IS NULL THEN NULL
            WHEN c.horimetro_atual > c.ciclo_limite_horas THEN 0
            ELSE c.proximo_ciclo_horas - c.horimetro_atual
        END AS horas_faltantes_para_ciclo,
        CASE
            WHEN c.fonte_horimetro = 'SEM_DADOS' THEN 'SEM DADOS'
            WHEN c.ciclo_limite_horas IS NULL THEN 'CICLO INVÁLIDO'
            WHEN c.horimetro_atual > c.ciclo_limite_horas THEN 'EXPIRADO'
            WHEN c.proximo_ciclo_horas - c.horimetro_atual <= 100 THEN 'CRÍTICO'
            WHEN c.proximo_ciclo_horas - c.horimetro_atual BETWEEN 101 AND 250 THEN 'MÉDIO'
            WHEN c.proximo_ciclo_horas - c.horimetro_atual BETWEEN 251 AND 300 THEN 'LEVE'
            ELSE 'OK'
        END AS status_alerta_ciclo
    FROM calculo c
)
SELECT
    status_alerta_ciclo,
    COUNT(*) AS quantidade
FROM final
GROUP BY status_alerta_ciclo
ORDER BY
    CASE status_alerta_ciclo
        WHEN 'EXPIRADO' THEN 1
        WHEN 'CRÍTICO' THEN 2
        WHEN 'MÉDIO' THEN 3
        WHEN 'LEVE' THEN 4
        WHEN 'OK' THEN 5
        WHEN 'SEM DADOS' THEN 6
        WHEN 'CICLO INVÁLIDO' THEN 7
        ELSE 8
    END;
`;

// ---------------------------------------------------------------------------
// Garantia — status de garantia basica + estendida por maquina
// Retorna rows individuais (chassi, tipo_garantia, status_final_garantia)
// Agregacao e dedup de chassis feitas no handler JS
// ---------------------------------------------------------------------------
const GARANTIA_STATUS = `
WITH base AS (
    SELECT
        TRIM(serial_number) AS chassi,
        COALESCE(NULLIF(TRIM(basic_warranty_type), ''), 'BASIC WARRANTY') AS basic_warranty_type,
        basic_warranty_expiration AS data_expiracao_garantia_basica,
        NULLIF(TRIM(extended_warranty_type), '') AS extended_warranty_type,
        extended_warranty_expiration AS data_expiracao_garantia_estendida,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(serial_number)
            ORDER BY
                GREATEST(
                    COALESCE(extended_warranty_expiration, DATE '1900-01-01'),
                    COALESCE(basic_warranty_expiration, DATE '1900-01-01')
                ) DESC
        ) AS rn
    FROM grarantia.pops_base
    WHERE NULLIF(TRIM(serial_number), '') IS NOT NULL
),
base_filtrada AS (
    SELECT * FROM base WHERE rn = 1
),
plus_care AS (
    SELECT DISTINCT ON (TRIM(chassi))
        TRIM(chassi) AS chassi,
        COALESCE(
            NULLIF(
                REGEXP_REPLACE(horas_do_plano::text, '[^0-9]', '', 'g'),
                ''
            )::numeric,
            0
        ) AS horas_do_plano
    FROM grarantia.power_gard_plus_care
    WHERE NULLIF(TRIM(chassi), '') IS NOT NULL
    ORDER BY
        TRIM(chassi),
        COALESCE(
            NULLIF(
                REGEXP_REPLACE(horas_do_plano::text, '[^0-9]', '', 'g'),
                ''
            )::numeric,
            0
        ) DESC
),
equipamento_base AS (
    SELECT DISTINCT ON (TRIM(oe.serial_number))
        TRIM(oe.serial_number) AS chassi,
        oe.principal_id
    FROM layer_bronze.opc_equipment oe
    INNER JOIN base_filtrada bf
        ON bf.chassi = TRIM(oe.serial_number)
    WHERE oe.org_role_in_possession = 'true'
      AND NULLIF(TRIM(oe.serial_number), '') IS NOT NULL
    ORDER BY TRIM(oe.serial_number), oe.principal_id
),
equipamento_horimetro AS (
    SELECT
        eb.chassi,
        eb.principal_id,
        uh.reading_value::numeric AS horimetro_atual,
        uh.report_time AS data_ultimo_horimetro
    FROM equipamento_base eb
    LEFT JOIN LATERAL (
        SELECT oeh.reading_value, oeh.report_time
        FROM layer_bronze.opc_engine_hours oeh
        WHERE oeh.principal_id = eb.principal_id
        ORDER BY oeh.report_time DESC
        LIMIT 1
    ) uh ON TRUE
),
garantias AS (
    SELECT
        b.chassi,
        g.tipo_garantia,
        g.tipo_garantia_descricao,
        g.data_expiracao,
        CASE
            WHEN g.tipo_garantia = 'ESTENDIDA' THEN COALESCE(pc.horas_do_plano, 0)
            ELSE NULL
        END AS horas_do_plano,
        eh.horimetro_atual,
        eh.data_ultimo_horimetro,
        CASE
            WHEN eh.horimetro_atual IS NOT NULL THEN 'OPC_ENGINE_HOURS'
            ELSE 'SEM_DADOS'
        END AS fonte_horimetro
    FROM base_filtrada b
    LEFT JOIN plus_care pc ON pc.chassi = b.chassi
    LEFT JOIN equipamento_horimetro eh ON eh.chassi = b.chassi
    CROSS JOIN LATERAL (
        VALUES
            ('BASICA', b.basic_warranty_type, b.data_expiracao_garantia_basica),
            ('ESTENDIDA', b.extended_warranty_type, b.data_expiracao_garantia_estendida)
    ) AS g(tipo_garantia, tipo_garantia_descricao, data_expiracao)
    WHERE g.tipo_garantia = 'BASICA'
       OR (g.tipo_garantia = 'ESTENDIDA' AND g.tipo_garantia_descricao IS NOT NULL)
),
calculo AS (
    SELECT
        g.*,
        g.data_expiracao - CURRENT_DATE AS dias_restantes,
        CASE
            WHEN g.tipo_garantia = 'ESTENDIDA'
             AND COALESCE(g.horas_do_plano, 0) > 0
             AND g.horimetro_atual IS NOT NULL
                THEN g.horas_do_plano - g.horimetro_atual
            ELSE NULL
        END AS horas_restantes,
        CASE
            WHEN g.data_expiracao IS NULL THEN 'SEM DATA'
            WHEN g.data_expiracao < CURRENT_DATE THEN 'VENCIDO'
            WHEN g.data_expiracao - CURRENT_DATE BETWEEN 0 AND 30 THEN 'CRITICO'
            WHEN g.data_expiracao - CURRENT_DATE BETWEEN 31 AND 60 THEN 'MEDIO'
            WHEN g.data_expiracao - CURRENT_DATE BETWEEN 61 AND 90 THEN 'BAIXA'
            WHEN g.data_expiracao - CURRENT_DATE > 90 THEN 'OK'
        END AS status_data,
        CASE
            WHEN g.tipo_garantia = 'BASICA' THEN 'NAO APLICA'
            WHEN COALESCE(g.horas_do_plano, 0) <= 0 THEN 'SEM HORAS DO PLANO'
            WHEN g.horimetro_atual IS NULL THEN 'SEM DADOS'
            WHEN g.horas_do_plano - g.horimetro_atual <= 0 THEN 'VENCIDO'
            WHEN g.horas_do_plano - g.horimetro_atual BETWEEN 1 AND 100 THEN 'CRITICO'
            WHEN g.horas_do_plano - g.horimetro_atual BETWEEN 101 AND 250 THEN 'MEDIO'
            WHEN g.horas_do_plano - g.horimetro_atual BETWEEN 251 AND 300 THEN 'BAIXA'
            WHEN g.horas_do_plano - g.horimetro_atual > 300 THEN 'OK'
        END AS status_horimetro
    FROM garantias g
),
resultado AS (
    SELECT
        c.*,
        CASE
            WHEN c.status_data = 'VENCIDO' OR c.status_horimetro = 'VENCIDO' THEN 'VENCIDO'
            WHEN c.status_data = 'CRITICO' OR c.status_horimetro = 'CRITICO' THEN 'CRITICO'
            WHEN c.status_data = 'MEDIO' OR c.status_horimetro = 'MEDIO' THEN 'MEDIO'
            WHEN c.status_data = 'BAIXA' OR c.status_horimetro = 'BAIXA' THEN 'BAIXA'
            WHEN c.status_data = 'SEM DATA' THEN 'SEM DATA'
            WHEN c.tipo_garantia = 'ESTENDIDA' AND c.status_horimetro = 'SEM HORAS DO PLANO' THEN 'SEM HORAS DO PLANO'
            WHEN c.tipo_garantia = 'ESTENDIDA' AND c.status_horimetro = 'SEM DADOS' THEN 'SEM DADOS'
            ELSE 'OK'
        END AS status_final_garantia
    FROM calculo c
)
SELECT chassi, tipo_garantia, status_final_garantia
FROM resultado;
`;

// Cache 24h para JD Protect e Garantia (dados mudam lentamente)
let _jdProtectCache = { at: 0, value: null };
let _garantiaCache  = { at: 0, value: null };

async function getJdProtectStatus() {
  const now = Date.now();
  if (_jdProtectCache.value && now - _jdProtectCache.at < _TTL_24H_MS) {
    return _jdProtectCache.value;
  }
  const { rows } = await pool.query(JD_PROTECT_STATUS);
  _jdProtectCache = { at: now, value: rows };
  return rows;
}

async function getGarantiaStatus() {
  const now = Date.now();
  if (_garantiaCache.value && now - _garantiaCache.at < _TTL_24H_MS) {
    return _garantiaCache.value;
  }
  const { rows } = await pool.query(GARANTIA_STATUS);
  _garantiaCache = { at: now, value: rows };
  return rows;
}

// ─── GET /api/dashboard/maintenance ─────────────────────────────────────────
// KPIs de JD Protect (ciclo manutencao) + Garantia (basica/estendida)
router.get("/maintenance", requireSession, async (req, res) => {
  try {
    const t0 = Date.now();
    const [jdResult, garantiaResult] = await Promise.allSettled([
      getJdProtectStatus(),
      getGarantiaStatus(),
    ]);
    for (const [label, r] of [["jdProtect", jdResult], ["garantia", garantiaResult]]) {
      if (r.status === "rejected") console.error(`[DASHBOARD] /maintenance ${label} FALHOU:`, r.reason && r.reason.message);
    }
    console.log(`[DASHBOARD] maintenance: ${Date.now() - t0}ms`);

    const jdProtect = jdResult.status === "fulfilled" ? jdResult.value : [];
    const garantia  = garantiaResult.status === "fulfilled" ? garantiaResult.value : [];

    // Mapear JD Protect para objeto { EXPIRADO: N, CRITICO: N, MEDIO: N, LEVE: N, ... }
    const jdMap = {};
    jdProtect.forEach(r => { jdMap[r.status_alerta_ciclo] = parseInt(r.quantidade, 10); });

    // Agregar Garantia no JS: contagem por tipo + status E distinct chassis por status
    const garantiaMap = { BASICA: {}, ESTENDIDA: {} };
    const _distinctSets = {};  // status -> Set(chassi)
    garantia.forEach(r => {
      const tipo = r.tipo_garantia || "BASICA";
      const status = r.status_final_garantia;
      if (!garantiaMap[tipo]) garantiaMap[tipo] = {};
      garantiaMap[tipo][status] = (garantiaMap[tipo][status] || 0) + 1;
      if (!_distinctSets[status]) _distinctSets[status] = new Set();
      _distinctSets[status].add(r.chassi);
    });
    const garantiaDistinct = {};
    for (const [status, s] of Object.entries(_distinctSets)) {
      garantiaDistinct[status] = s.size;
    }

    return res.json({
      success: true,
      jdProtect: jdMap,
      garantia: garantiaMap,
      garantiaDistinct,
    });
  } catch (err) {
    console.error("[DASHBOARD] Erro em /maintenance:", err.message);
    return res.status(500).json({ success: false, error: "Erro ao carregar dados de manutencao/garantia." });
  }
});

// ---------------------------------------------------------------------------
// JD Protect — detalhamento por maquina (ciclo de manutencao)
// Retorna chassi, cliente, plano, horimetro, horas faltantes, status etc.
// ---------------------------------------------------------------------------
const JD_PROTECT_DETAIL = `
WITH ultimo_horimetro AS (
    SELECT DISTINCT ON (oeh.principal_id)
        oeh.principal_id,
        oeh.reading_value,
        oeh.reading_unit,
        oeh.report_time
    FROM layer_bronze.opc_engine_hours oeh
    ORDER BY oeh.principal_id, oeh.report_time DESC
),
equipamento AS (
    SELECT DISTINCT ON (oe.serial_number)
        oe.serial_number,
        oe.principal_id,
        uh.reading_value,
        uh.report_time
    FROM layer_bronze.opc_equipment oe
    LEFT JOIN ultimo_horimetro uh ON uh.principal_id = oe.principal_id
    WHERE oe.org_role_in_possession = 'true'
    ORDER BY oe.serial_number,
        CASE WHEN uh.report_time IS NOT NULL THEN 1 ELSE 0 END DESC,
        uh.report_time DESC NULLS LAST, oe.principal_id
),
jd_base AS (
    SELECT DISTINCT
        jp.chassi, jp.cliente, jp.tipo_de_plano, jp.ciclo, jp.valor,
        jp.data_lancamento_svap,
        NULLIF(jp.horimetro_atual::text, '')::numeric AS horimetro_jd_protect
    FROM grarantia.jd_protect jp
),
base AS (
    SELECT
        jp.chassi, jp.cliente, jp.tipo_de_plano, jp.ciclo, jp.valor,
        jp.data_lancamento_svap, eq.principal_id,
        eq.reading_value AS horimetro_opc, jp.horimetro_jd_protect,
        COALESCE(eq.reading_value, jp.horimetro_jd_protect, 0) AS horimetro_atual,
        CASE
            WHEN eq.reading_value IS NOT NULL THEN 'OPC_ENGINE_HOURS'
            WHEN jp.horimetro_jd_protect IS NOT NULL THEN 'JD_PROTECT'
            ELSE 'SEM_DADOS'
        END AS fonte_horimetro,
        eq.report_time AS data_ultimo_horimetro,
        NULLIF(substring(jp.ciclo FROM '-\\s*([0-9]+)'), '')::numeric AS ciclo_limite_horas
    FROM jd_base jp
    LEFT JOIN equipamento eq ON eq.serial_number = jp.chassi
),
calculo AS (
    SELECT b.*,
        CASE
            WHEN b.fonte_horimetro = 'SEM_DADOS' THEN NULL
            WHEN b.ciclo_limite_horas IS NULL THEN NULL
            WHEN b.horimetro_atual > b.ciclo_limite_horas THEN b.ciclo_limite_horas
            ELSE LEAST(b.ciclo_limite_horas,
                CASE WHEN b.horimetro_atual <= 0 THEN 500
                     ELSE CEIL(b.horimetro_atual / 500.0) * 500 END)
        END AS proximo_ciclo_horas
    FROM base b
),
final AS (
    SELECT c.*,
        CASE
            WHEN c.fonte_horimetro = 'SEM_DADOS' THEN NULL
            WHEN c.ciclo_limite_horas IS NULL THEN NULL
            WHEN c.horimetro_atual > c.ciclo_limite_horas THEN 0
            ELSE c.proximo_ciclo_horas - c.horimetro_atual
        END AS horas_faltantes_para_ciclo,
        CASE
            WHEN c.fonte_horimetro = 'SEM_DADOS' THEN 'SEM DADOS'
            WHEN c.ciclo_limite_horas IS NULL THEN 'CICLO INVÁLIDO'
            WHEN c.horimetro_atual > c.ciclo_limite_horas THEN 'EXPIRADO'
            WHEN c.proximo_ciclo_horas - c.horimetro_atual <= 100 THEN 'CRÍTICO'
            WHEN c.proximo_ciclo_horas - c.horimetro_atual BETWEEN 101 AND 250 THEN 'MÉDIO'
            WHEN c.proximo_ciclo_horas - c.horimetro_atual BETWEEN 251 AND 300 THEN 'LEVE'
            ELSE 'OK'
        END AS status_alerta_ciclo
    FROM calculo c
)
SELECT chassi, cliente, tipo_de_plano, ciclo, valor, data_lancamento_svap,
    horimetro_atual, fonte_horimetro, data_ultimo_horimetro,
    ciclo_limite_horas, proximo_ciclo_horas, horas_faltantes_para_ciclo,
    status_alerta_ciclo
FROM final
ORDER BY chassi, horimetro_atual;
`;

// ---------------------------------------------------------------------------
// Garantia — detalhamento por maquina (basica + estendida)
// Retorna chassi, tipo garantia, horimetro, datas expiracao, status etc.
// ---------------------------------------------------------------------------
const GARANTIA_DETAIL = `
WITH base AS (
    SELECT
        TRIM(serial_number) AS chassi,
        COALESCE(NULLIF(TRIM(basic_warranty_type), ''), 'BASIC WARRANTY') AS basic_warranty_type,
        basic_warranty_expiration AS data_expiracao_garantia_basica,
        NULLIF(TRIM(extended_warranty_type), '') AS extended_warranty_type,
        extended_warranty_expiration AS data_expiracao_garantia_estendida,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(serial_number)
            ORDER BY GREATEST(
                COALESCE(extended_warranty_expiration, DATE '1900-01-01'),
                COALESCE(basic_warranty_expiration, DATE '1900-01-01')
            ) DESC
        ) AS rn
    FROM grarantia.pops_base
    WHERE NULLIF(TRIM(serial_number), '') IS NOT NULL
),
base_filtrada AS (
    SELECT * FROM base WHERE rn = 1
),
plus_care AS (
    SELECT DISTINCT ON (TRIM(chassi))
        TRIM(chassi) AS chassi,
        COALESCE(NULLIF(REGEXP_REPLACE(horas_do_plano::text, '[^0-9]', '', 'g'), '')::numeric, 0) AS horas_do_plano
    FROM grarantia.power_gard_plus_care
    WHERE NULLIF(TRIM(chassi), '') IS NOT NULL
    ORDER BY TRIM(chassi),
        COALESCE(NULLIF(REGEXP_REPLACE(horas_do_plano::text, '[^0-9]', '', 'g'), '')::numeric, 0) DESC
),
equipamento_base AS (
    SELECT DISTINCT ON (TRIM(oe.serial_number))
        TRIM(oe.serial_number) AS chassi, oe.principal_id
    FROM layer_bronze.opc_equipment oe
    INNER JOIN base_filtrada bf ON bf.chassi = TRIM(oe.serial_number)
    WHERE oe.org_role_in_possession = 'true'
      AND NULLIF(TRIM(oe.serial_number), '') IS NOT NULL
    ORDER BY TRIM(oe.serial_number), oe.principal_id
),
equipamento_horimetro AS (
    SELECT eb.chassi, eb.principal_id,
        uh.reading_value::numeric AS horimetro_atual,
        uh.report_time AS data_ultimo_horimetro
    FROM equipamento_base eb
    LEFT JOIN LATERAL (
        SELECT oeh.reading_value, oeh.report_time
        FROM layer_bronze.opc_engine_hours oeh
        WHERE oeh.principal_id = eb.principal_id
        ORDER BY oeh.report_time DESC LIMIT 1
    ) uh ON TRUE
),
resultado AS (
    SELECT
        b.chassi,
        COALESCE(pc.horas_do_plano, 0) AS horas_do_plano,
        eh.horimetro_atual,
        CASE WHEN eh.horimetro_atual IS NOT NULL THEN 'OPC_ENGINE_HOURS' ELSE 'SEM_DADOS' END AS fonte_horimetro,
        eh.data_ultimo_horimetro,
        CASE
            WHEN b.extended_warranty_type IS NULL THEN NULL
            WHEN COALESCE(pc.horas_do_plano, 0) <= 0 THEN NULL
            WHEN eh.horimetro_atual IS NULL THEN NULL
            ELSE COALESCE(pc.horas_do_plano, 0) - eh.horimetro_atual
        END AS horas_restantes_garantia_estendida,
        CASE
            WHEN b.extended_warranty_type IS NULL THEN 'SEM GARANTIA ESTENDIDA'
            WHEN COALESCE(pc.horas_do_plano, 0) <= 0 THEN 'SEM HORAS DO PLANO'
            WHEN eh.horimetro_atual IS NULL THEN 'SEM DADOS'
            WHEN COALESCE(pc.horas_do_plano, 0) - eh.horimetro_atual <= 0 THEN 'VENCIDO'
            WHEN COALESCE(pc.horas_do_plano, 0) - eh.horimetro_atual BETWEEN 1 AND 100 THEN 'CRITICO'
            WHEN COALESCE(pc.horas_do_plano, 0) - eh.horimetro_atual BETWEEN 101 AND 250 THEN 'MEDIO'
            WHEN COALESCE(pc.horas_do_plano, 0) - eh.horimetro_atual BETWEEN 251 AND 300 THEN 'OK'
            ELSE 'ACIMA DE 300 HORAS'
        END AS status_garantia_estendida_horimetro,
        CASE
            WHEN b.extended_warranty_type IS NOT NULL THEN
                b.basic_warranty_type || ' \\ EXTENDED WARRANTY (' || b.extended_warranty_type || ')'
            ELSE b.basic_warranty_type
        END AS garantias_presentes,
        b.data_expiracao_garantia_basica,
        b.data_expiracao_garantia_basica - CURRENT_DATE AS dias_restantes_garantia_basica,
        CASE
            WHEN b.data_expiracao_garantia_basica IS NULL THEN 'SEM DATA'
            WHEN b.data_expiracao_garantia_basica < CURRENT_DATE THEN 'VENCIDA'
            WHEN b.data_expiracao_garantia_basica - CURRENT_DATE BETWEEN 0 AND 30 THEN 'CRITICO'
            WHEN b.data_expiracao_garantia_basica - CURRENT_DATE BETWEEN 31 AND 60 THEN 'MEDIO'
            WHEN b.data_expiracao_garantia_basica - CURRENT_DATE BETWEEN 61 AND 90 THEN 'BAIXA'
            WHEN b.data_expiracao_garantia_basica - CURRENT_DATE > 90 THEN 'ACIMA DE 90 DIAS'
        END AS status_garantia_basica,
        b.data_expiracao_garantia_estendida,
        b.data_expiracao_garantia_estendida - CURRENT_DATE AS dias_restantes_garantia_estendida,
        CASE
            WHEN b.extended_warranty_type IS NULL THEN 'SEM GARANTIA ESTENDIDA'
            WHEN b.data_expiracao_garantia_estendida IS NULL THEN 'SEM DATA'
            WHEN b.data_expiracao_garantia_estendida < CURRENT_DATE THEN 'VENCIDA'
            WHEN b.data_expiracao_garantia_estendida - CURRENT_DATE BETWEEN 0 AND 30 THEN 'CRITICO'
            WHEN b.data_expiracao_garantia_estendida - CURRENT_DATE BETWEEN 31 AND 60 THEN 'MEDIO'
            WHEN b.data_expiracao_garantia_estendida - CURRENT_DATE BETWEEN 61 AND 90 THEN 'BAIXA'
            WHEN b.data_expiracao_garantia_estendida - CURRENT_DATE > 90 THEN 'ACIMA DE 90 DIAS'
        END AS status_garantia_estendida_data
    FROM base_filtrada b
    LEFT JOIN plus_care pc ON pc.chassi = b.chassi
    LEFT JOIN equipamento_horimetro eh ON eh.chassi = b.chassi
)
SELECT * FROM resultado ORDER BY chassi;
`;

// ---------------------------------------------------------------------------
// Cache + inflight protection + circuit breaker para detail queries.
//
// Cada cache guarda:
//   - at:         quando o cache foi populado com sucesso
//   - rows:       ultimo resultado bem-sucedido (preservado mesmo se refresh falhar)
//   - lastFailAt: quando a ultima tentativa falhou (0 = nunca falhou)
//
// Fluxo:
//   1. Cache fresco (<24h) -> retorna direto
//   2. Refresh em andamento -> retorna a mesma promise
//   3. Falhou nos ultimos 10 min -> circuit-break: retorna rows velhas (ou [])
//      SEM disparar nova query (evita loop de tentativas de 15 min falhando)
//   4. Caso contrario -> dispara refresh
// ---------------------------------------------------------------------------
const _CIRCUIT_BREAK_MS = 10 * 60 * 1000;   // 10 min sem re-tentar apos falha
const _JD_STMT_TIMEOUT_MS = 900000;         // 15 min (query pesada com opc_engine_hours)
const _GAR_STMT_TIMEOUT_MS = 300000;        // 5 min

let _jdProtectDetailCache = { at: 0, rows: null, lastFailAt: 0 };
let _jdProtectDetailInflight = null;

async function _refreshJdProtectDetail() {
  const client = await pool.connect();
  try {
    await client.query(`SET statement_timeout = '${_JD_STMT_TIMEOUT_MS}'`);
    const t0 = Date.now();
    const { rows } = await client.query(JD_PROTECT_DETAIL);
    console.log(`[DASHBOARD] jdprotect-detail refresh OK em ${Date.now() - t0}ms, ${rows.length} rows`);
    _jdProtectDetailCache = { at: Date.now(), rows, lastFailAt: 0 };
    return rows;
  } catch (err) {
    _jdProtectDetailCache = { ..._jdProtectDetailCache, lastFailAt: Date.now() };
    console.error(`[DASHBOARD] jdprotect-detail refresh FALHOU: ${err.message}`);
    throw err;
  } finally {
    try { await client.query("SET statement_timeout = '0'"); } catch (_) {}
    client.release();
    _jdProtectDetailInflight = null;
  }
}

async function getJdProtectDetail() {
  const now = Date.now();
  if (_jdProtectDetailCache.rows && now - _jdProtectDetailCache.at < _TTL_24H_MS) {
    return _jdProtectDetailCache.rows;
  }
  if (_jdProtectDetailInflight) return _jdProtectDetailInflight;
  if (_jdProtectDetailCache.lastFailAt && now - _jdProtectDetailCache.lastFailAt < _CIRCUIT_BREAK_MS) {
    const secsAgo = Math.floor((now - _jdProtectDetailCache.lastFailAt) / 1000);
    console.warn(`[DASHBOARD] jdprotect-detail em circuit-break (falhou ha ${secsAgo}s). Retornando cache velho (${(_jdProtectDetailCache.rows || []).length} rows).`);
    return _jdProtectDetailCache.rows || [];
  }
  _jdProtectDetailInflight = _refreshJdProtectDetail();
  return _jdProtectDetailInflight;
}

let _garantiaDetailCache = { at: 0, rows: null, lastFailAt: 0 };
let _garantiaDetailInflight = null;

async function _refreshGarantiaDetail() {
  const client = await pool.connect();
  try {
    await client.query(`SET statement_timeout = '${_GAR_STMT_TIMEOUT_MS}'`);
    const t0 = Date.now();
    const { rows } = await client.query(GARANTIA_DETAIL);
    console.log(`[DASHBOARD] garantia-detail refresh OK em ${Date.now() - t0}ms, ${rows.length} rows`);
    _garantiaDetailCache = { at: Date.now(), rows, lastFailAt: 0 };
    return rows;
  } catch (err) {
    _garantiaDetailCache = { ..._garantiaDetailCache, lastFailAt: Date.now() };
    console.error(`[DASHBOARD] garantia-detail refresh FALHOU: ${err.message}`);
    throw err;
  } finally {
    try { await client.query("SET statement_timeout = '0'"); } catch (_) {}
    client.release();
    _garantiaDetailInflight = null;
  }
}

async function getGarantiaDetail() {
  const now = Date.now();
  if (_garantiaDetailCache.rows && now - _garantiaDetailCache.at < _TTL_24H_MS) {
    return _garantiaDetailCache.rows;
  }
  if (_garantiaDetailInflight) return _garantiaDetailInflight;
  if (_garantiaDetailCache.lastFailAt && now - _garantiaDetailCache.lastFailAt < _CIRCUIT_BREAK_MS) {
    const secsAgo = Math.floor((now - _garantiaDetailCache.lastFailAt) / 1000);
    console.warn(`[DASHBOARD] garantia-detail em circuit-break (falhou ha ${secsAgo}s). Retornando cache velho (${(_garantiaDetailCache.rows || []).length} rows).`);
    return _garantiaDetailCache.rows || [];
  }
  _garantiaDetailInflight = _refreshGarantiaDetail();
  return _garantiaDetailInflight;
}

// ─── GET /api/dashboard/maintenance-detail ──────────────────────────────────
// Detalhamento por maquina: ?type=jdprotect ou ?type=garantia
// Se o cache esta sendo aquecido (inflight), retorna warming:true com rows
// vazias em vez de bloquear — o proxy mataria a conexao antes da query terminar.
router.get("/maintenance-detail", requireSession, async (req, res) => {
  try {
    const type = (req.query.type || "").toLowerCase();
    if (type !== "jdprotect" && type !== "garantia") {
      return res.status(400).json({ success: false, error: "Parametro type deve ser 'jdprotect' ou 'garantia'." });
    }

    // Verificar se já tem cache pronto
    const cache = type === "jdprotect" ? _jdProtectDetailCache : _garantiaDetailCache;
    const inflight = type === "jdprotect" ? _jdProtectDetailInflight : _garantiaDetailInflight;

    if (cache.rows && Date.now() - cache.at < _TTL_24H_MS) {
      // Cache valido — retorna imediatamente
      console.log(`[DASHBOARD] maintenance-detail(${type}): 0ms (cache), ${cache.rows.length} rows`);
      return res.json({ success: true, type, rows: cache.rows });
    }

    if (inflight) {
      // Query em andamento (warming) — nao bloquear, retornar vazio com flag
      console.log(`[DASHBOARD] maintenance-detail(${type}): warming em andamento, retornando vazio`);
      return res.json({ success: true, type, rows: [], warming: true });
    }

    // Nenhum cache nem inflight — executar agora.
    // getXDetail() ja aplica circuit breaker; se falhou recentemente, retorna
    // cache velho SEM disparar nova query pesada. Se lancar, retorna warming
    // vazio para o frontend nao ver 500 e continuar o polling.
    const t0 = Date.now();
    try {
      const rows = type === "jdprotect"
        ? await getJdProtectDetail()
        : await getGarantiaDetail();
      console.log(`[DASHBOARD] maintenance-detail(${type}): ${Date.now() - t0}ms, ${rows.length} rows`);
      return res.json({ success: true, type, rows });
    } catch (queryErr) {
      // Query falhou (timeout ou erro de schema). Nao propaga 500: o frontend
      // tem retry automatico e trava no console se recebe erro HTTP.
      console.error(`[DASHBOARD] maintenance-detail(${type}) query FALHOU: ${queryErr.message}`);
      const fallback = type === "jdprotect"
        ? (_jdProtectDetailCache.rows || [])
        : (_garantiaDetailCache.rows || []);
      return res.json({
        success: true, type, rows: fallback,
        stale: fallback.length > 0,
        warming: fallback.length === 0,
      });
    }
  } catch (err) {
    console.error("[DASHBOARD] Erro em /maintenance-detail:", err.message);
    return res.status(500).json({ success: false, error: "Erro ao carregar detalhamento." });
  }
});

// ---------------------------------------------------------------------------
// Cache warming — executa as queries pesadas em background logo apos o boot.
// Isso evita que a primeira requisicao HTTP sofra timeout no proxy enquanto
// a query de machines roda (3-60s+ dependendo da carga do banco).
// ---------------------------------------------------------------------------
setTimeout(() => {
  console.log("[DASHBOARD] Warming cache: machines...");
  getMachinesSummary()
    .then((row) => console.log(`[DASHBOARD] Warming machines OK: ${row.total || 0} maquinas`))
    .catch((err) => console.error("[DASHBOARD] Warming machines FALHOU:", err.message));

  console.log("[DASHBOARD] Warming cache: jdprotect-detail...");
  getJdProtectDetail()
    .then((rows) => console.log(`[DASHBOARD] Warming jdprotect-detail OK: ${rows.length} rows`))
    .catch((err) => console.error("[DASHBOARD] Warming jdprotect-detail FALHOU:", err.message));

  console.log("[DASHBOARD] Warming cache: garantia-detail...");
  getGarantiaDetail()
    .then((rows) => console.log(`[DASHBOARD] Warming garantia-detail OK: ${rows.length} rows`))
    .catch((err) => console.error("[DASHBOARD] Warming garantia-detail FALHOU:", err.message));
}, 2000); // 2s de delay para o pool de DB estabilizar

module.exports = router;
