// =========== RTA - REAL TIME ALERT ============
// queries.js — Queries SQL centralizadas
// ================================================
//
// A logica de classificacao de tipo (linha_amarela / Wirtgen / outros)
// fica centralizada aqui como CTE reutilizavel, eliminando a duplicacao
// que existia no Grafana (10+ queries com o mesmo CASE WHEN).
//
// v2: Suporte a filtro de periodo, deduplicacao por maquina, contagem
//     por regional, filtros dinamicos no mapa.

// ---------------------------------------------------------------------------
// CTE reutilizavel: classifica cada alerta por tipo de linha
//
// IMPORTANTE: $1 e $2 (date_start / date_end) sao filtrados DENTRO da CTE
// para que o PostgreSQL reduza o volume ANTES dos JOINs.
// Isso melhora drasticamente a performance em periodos curtos (ex: 1 dia).
//
// TIMEZONE: alert_time eh armazenado em UTC no banco. Convertemos para
// America/Sao_Paulo (BRT/BRST) tanto no SELECT quanto no WHERE para que
// o filtro de data e a exibicao respeitem o horario local.
// ---------------------------------------------------------------------------
function buildCTE(dateParamStart, dateParamEnd) {
  return `
WITH alert_classified AS (
  SELECT
    oma.id_alert,
    oma.principal_id,
    oma.color,
    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' AS alert_time,
    TO_CHAR((oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY, HH24:MI') AS horario_local,
    oma.severity,
    oma.engine_hours,
    oma.three_letter_acronym,
    oma.description AS alert_description,
    oma.latitude,
    oma.longitude,
    om.serial_number,
    om.model_name,
    om.principal_id AS equip_principal_id,
    tccp.a1_nome AS cliente,
    lm.estado,
    lm.cidade,
    lm.mesorregiao,
    lm.regional,
    CASE
      WHEN om.model_name IN (
        '444G','524K-II','544K-II','624K-II','644K','724K','744L','824L','844L',
        '620G','622G','670G','672G','310L','310K','310 P','700J','750J','850J',
        '130G','160G','200G','210G','250G','350G','470G','870G'
      ) THEN 'linha_amarela'
      WHEN om.model_name IN (
        '3411','3412','3414','HC 110','HC 110 P','HC 200 P','W 100 F','W 150 CF','W 150 F',
        'W 200 F','W 100 HR','W 100 R','W 130 Hi','SP 64','SP 94','SUPER 1300','SUPER 1303',
        'SUPER 1400','SUPER 1800-3','SUPER 800','WR 200','WR 240','HD 90K','HD O90V','HP 280'
      ) THEN 'Wirtgen'
      ELSE 'outros'
    END AS tipo
  FROM layer_bronze.opc_machine_alerts oma
  LEFT JOIN layer_bronze.opc_equipment om ON om.principal_id = oma.principal_id::int
  LEFT JOIN localizacao_maquinas lm ON lm.principal_id = om.principal_id
  LEFT JOIN layer_bronze.tb_cliente_chassi_protheus tccp ON tccp.vv1_chassi = om.serial_number
  WHERE oma.alert_time >= (${dateParamStart}::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  ((${dateParamEnd}::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
`;
}

// ---------------------------------------------------------------------------
// Contagem de alertas por cor, tipo E regional (cards de resumo)
// Deduplicacao: conta maquinas distintas (serial_number) por combinacao
// cor+tipo+regional, nao id_alert (evita contar mesmo alerta repetido)
//
// Parametros: $1 = date_start, $2 = date_end
// ---------------------------------------------------------------------------
const ALERT_COUNTS_BY_REGIONAL = `
${buildCTE("$1", "$2")}
SELECT
  color,
  tipo,
  regional,
  COUNT(DISTINCT (serial_number, id_alert)) AS total_alertas
FROM alert_classified
WHERE tipo <> 'outros'
  AND regional IN ('R1', 'R2', 'R3')
GROUP BY color, tipo, regional
ORDER BY tipo, color, regional;
`;

// ---------------------------------------------------------------------------
// Contagem TOTAL por cor e tipo (sem breakdown por regional)
// Parametros: $1 = date_start, $2 = date_end
// ---------------------------------------------------------------------------
const ALERT_COUNTS_TOTAL = `
${buildCTE("$1", "$2")}
SELECT
  color,
  tipo,
  COUNT(DISTINCT (serial_number, id_alert)) AS total_alertas
FROM alert_classified
WHERE tipo <> 'outros'
  AND regional IN ('R1', 'R2', 'R3')
GROUP BY color, tipo
ORDER BY tipo, color;
`;

// ---------------------------------------------------------------------------
// Geolocalizacao de alertas (mapa) — com filtros dinamicos
// Parametros: $1 = date_start, $2 = date_end
//             $3 = color (null = todas), $4 = tipo (null = todos)
//             $5 = regional (null = todas, exceto FORA)
// ---------------------------------------------------------------------------
const GEO_ALERTS = `
${buildCTE("$1", "$2")}
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
// Detalhamento de alertas (tabela completa)
// Parametros: $1 = date_start, $2 = date_end
//             $3 = cor (null = todas), $4 = tipo (null = todos)
//
// INTEGRACAO RTS: cruza com rts_alertas para identificar quais alertas
// do RTA foram enviados pelo RTS via WhatsApp.
//
// Matching (v2 — migracao PG):
//   Primario: rts_alertas.notification_id → opc_notifications_events →
//             serial_number + DATE = opc_machine_alerts (via CTE)
//   Fallback: chassi + data + POSITION substring (alertas sem notification_id)
//
// LEFT JOIN LATERAL retorna dados do envio (data, hora, cliente) quando houver.
// ---------------------------------------------------------------------------
const ALERT_DETAIL = `
${buildCTE("$1", "$2")}
SELECT DISTINCT ON (ac.serial_number, ac.id_alert)
  ac.cliente,
  ac.serial_number AS pin,
  ac.principal_id,
  ac.color,
  ac.tipo,
  ac.id_alert AS id_alerta,
  ac.alert_time,
  ac.horario_local,
  ac.severity,
  ac.engine_hours,
  ac.three_letter_acronym,
  ac.alert_description AS description,
  ac.latitude,
  ac.longitude,
  ac.estado,
  ac.cidade,
  ac.mesorregiao,
  ac.regional,
  CASE WHEN rts.chassi IS NOT NULL THEN true ELSE false END AS enviado_rts,
  CASE WHEN rts.chassi IS NOT NULL
    THEN TO_CHAR(rts.data_envio, 'DD/MM/YYYY') || ' ' || COALESCE(rts.hora_envio, '')
    ELSE NULL
  END AS rts_envio,
  rts.cliente     AS rts_cliente,
  rts.enviado_para AS rts_telefone
FROM alert_classified ac
LEFT JOIN LATERAL (
  SELECT ra.chassi, ra.data_envio, ra.hora_envio, ra.cliente, ra.enviado_para
  FROM rts_alertas ra
  WHERE ra.chassi = ac.serial_number
    AND ra.id_mensagem IS NOT NULL
    AND ra.id_mensagem <> ''
    AND (
      -- Match 1 (direto por ID): notification_id = id_alert.
      -- Pos-migracao PG, o RTS grava oma.id_alert como notification_id.
      (ra.notification_id IS NOT NULL AND ra.notification_id <> ''
       AND ra.notification_id::text = ac.id_alert::text)
      OR
      -- Match 2 (chassi + data): qualquer envio para o mesmo chassi na
      -- mesma data do alerta. Cast explicito ::date para cobrir colunas
      -- VARCHAR ou TIMESTAMP sem depender do datestyle do PG.
      (ra.data_alerta::date = DATE(ac.alert_time))
    )
  ORDER BY ra.data_envio DESC, ra.hora_envio DESC
  LIMIT 1
) rts ON true
WHERE ac.regional <> 'FORA'
  AND ac.tipo <> 'outros'
  AND ($3::text IS NULL OR ac.color = $3)
  AND ($4::text IS NULL OR ac.tipo = $4)
ORDER BY ac.serial_number, ac.id_alert, ac.alert_time DESC;
`;

// ---------------------------------------------------------------------------
// Alertas por dia (grafico de barras)
// Parametros: $1 = date_start, $2 = date_end
// ---------------------------------------------------------------------------
const ALERTS_BY_DAY = `
${buildCTE("$1", "$2")}
SELECT
  TO_CHAR(alert_time, 'DD/MM') AS dia,
  DATE(alert_time) AS dia_order,
  color,
  COUNT(DISTINCT serial_number) AS quantidade_alertas
FROM alert_classified
WHERE regional IN ('R1', 'R2', 'R3')
  AND tipo <> 'outros'
  AND color IN ('BLUE', 'YELLOW', 'RED')
GROUP BY dia, dia_order, color
ORDER BY dia_order, color;
`;

// ---------------------------------------------------------------------------
// Ranking de maquinas com mais alertas (por cor)
// Parametros: $1 = color, $2 = date_start, $3 = date_end
// ---------------------------------------------------------------------------
const TOP_MACHINES_BY_COLOR = `
${buildCTE("$2", "$3")}
SELECT
  ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rank,
  serial_number,
  regional,
  tipo,
  COUNT(*) AS quantidade_alertas
FROM alert_classified
WHERE color = $1
  AND regional IN ('R1', 'R2', 'R3')
  AND tipo <> 'outros'
GROUP BY serial_number, regional, tipo
HAVING COUNT(*) > 20
ORDER BY quantidade_alertas DESC;
`;

module.exports = {
  ALERT_COUNTS_BY_REGIONAL,
  ALERT_COUNTS_TOTAL,
  GEO_ALERTS,
  ALERT_DETAIL,
  ALERTS_BY_DAY,
  TOP_MACHINES_BY_COLOR,
};
