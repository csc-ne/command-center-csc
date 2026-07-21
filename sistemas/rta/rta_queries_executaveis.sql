-- =========================================================================
-- RTA - QUERIES EXECUTÁVEIS PARA TESTE DIRETO NO BANCO
-- =========================================================================
-- Gerado em: 14/06/2026
-- Fonte: backend/queries.js
--
-- INSTRUÇÕES:
--   Substitua as variáveis abaixo antes de rodar:
--     :data_inicio  →  data inicial  (ex: '2026-06-14')
--     :data_fim     →  data final    (ex: '2026-06-14')
--     :cor_filtro   →  cor do alerta (ex: 'RED', ou NULL para todas)
--     :tipo_filtro  →  tipo de linha (ex: 'linha_amarela', ou NULL para todos)
--     :regional_filtro → regional    (ex: 'R1', ou NULL para todas)
--
--   No DBeaver/pgAdmin, use ctrl+H para substituir de uma vez.
--   Ou altere diretamente os valores nas linhas WHERE.
-- =========================================================================


-- =========================================================================
-- 1. CONTAGEM POR COR × TIPO × REGIONAL  (Cards de resumo)
--    Endpoint: GET /api/alerts/counts  →  campo "byRegional"
--    Alimenta: cards de resumo no topo do dashboard
-- =========================================================================

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
  WHERE oma.alert_time >= ('2026-06-14'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  (('2026-06-14'::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
SELECT
  color,
  tipo,
  regional,
  COUNT(DISTINCT serial_number) AS total_alertas
FROM alert_classified
WHERE tipo <> 'outros'
  AND regional IN ('R1', 'R2', 'R3')
GROUP BY color, tipo, regional
ORDER BY tipo, color, regional;


-- =========================================================================
-- 2. CONTAGEM TOTAL POR COR × TIPO  (Totais gerais dos cards)
--    Endpoint: GET /api/alerts/counts  →  campo "totals"
--    Alimenta: totais consolidados nos cards do dashboard
-- =========================================================================

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
  WHERE oma.alert_time >= ('2026-06-14'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  (('2026-06-14'::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
SELECT
  color,
  tipo,
  COUNT(DISTINCT serial_number) AS total_alertas
FROM alert_classified
WHERE tipo <> 'outros'
  AND regional IN ('R1', 'R2', 'R3')
GROUP BY color, tipo
ORDER BY tipo, color;


-- =========================================================================
-- 3. GEOLOCALIZAÇÃO DE ALERTAS  (Mapa Leaflet)
--    Endpoint: GET /api/alerts/geo
--    Alimenta: pins no mapa interativo do dashboard
--    Filtros opcionais: cor, tipo, regional (NULL = sem filtro)
-- =========================================================================

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
  WHERE oma.alert_time >= ('2026-06-14'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  (('2026-06-14'::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
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
  -- Filtros opcionais (remova ou altere conforme necessário):
  -- AND color = 'RED'
  -- AND tipo = 'linha_amarela'
  -- AND regional = 'R1'
ORDER BY serial_number, alert_time DESC;


-- =========================================================================
-- 4. DETALHAMENTO DE ALERTAS  (Tabela principal + tabela RED)
--    Endpoint: GET /api/alerts/detail
--    Alimenta: tabela "Detalhamento de Alertas RED" e tabela completa
--    Inclui cruzamento com rts_alertas (envios WhatsApp do RTS)
--    Filtros opcionais: cor, tipo (NULL = sem filtro)
-- =========================================================================

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
  WHERE oma.alert_time >= ('2026-06-14'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  (('2026-06-14'::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
SELECT DISTINCT ON (ac.serial_number, ac.color)
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
      -- Match 1 (direto): notification_id = id_alert do opc_machine_alerts
      (ra.notification_id IS NOT NULL AND ra.notification_id <> ''
       AND ra.notification_id = ac.id_alert::text)
      OR
      -- Match 2 (chassi+data): notification_id existe mas não bate com id_alert
      (ra.notification_id IS NOT NULL AND ra.notification_id <> ''
       AND ra.data_alerta = DATE(ac.alert_time))
      OR
      -- Match 3 (fallback substring): alertas sem notification_id (pré-migração)
      (COALESCE(ra.notification_id, '') = ''
       AND ra.data_alerta = DATE(ac.alert_time)
       AND (
        POSITION(
          LOWER(LEFT(TRIM(COALESCE(ra.alerta, '')), 30))
          IN LOWER(TRIM(COALESCE(ac.alert_description, '')))
        ) > 0
        OR POSITION(
          LOWER(LEFT(TRIM(COALESCE(ac.alert_description, '')), 30))
          IN LOWER(TRIM(COALESCE(ra.alerta, '')))
        ) > 0
      ))
    )
  ORDER BY ra.data_envio DESC, ra.hora_envio DESC
  LIMIT 1
) rts ON true
WHERE ac.regional <> 'FORA'
  AND ac.tipo <> 'outros'
  -- Filtros opcionais:
  -- AND ac.color = 'RED'
  -- AND ac.tipo = 'linha_amarela'
ORDER BY ac.serial_number, ac.color, ac.alert_time DESC;


-- =========================================================================
-- 5. ALERTAS POR DIA  (Gráfico de barras mensal)
--    Endpoint: GET /api/alerts/monthly
--    Alimenta: gráfico de barras "Abertura Mensal de Alertas"
--    Default no app: início do mês atual até hoje
-- =========================================================================

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
  WHERE oma.alert_time >= ('2026-06-01'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  (('2026-06-14'::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
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


-- =========================================================================
-- 6. RANKING DE MÁQUINAS POR COR  (Top máquinas com mais alertas)
--    Endpoint: GET /api/alerts/ranking?color=RED
--    Alimenta: ranking de máquinas no dashboard
--    Parâmetro: cor (altere 'RED' para YELLOW, BLUE, GRAY conforme necessário)
-- =========================================================================

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
  WHERE oma.alert_time >= ('2026-06-01'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
    AND oma.alert_time <  (('2026-06-14'::timestamp + INTERVAL '1 day') AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
)
SELECT
  ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rank,
  serial_number,
  regional,
  tipo,
  COUNT(*) AS quantidade_alertas
FROM alert_classified
WHERE color = 'RED'                            -- <<< ALTERE A COR AQUI
  AND regional IN ('R1', 'R2', 'R3')
  AND tipo <> 'outros'
GROUP BY serial_number, regional, tipo
HAVING COUNT(*) > 20
ORDER BY quantidade_alertas DESC;


-- =========================================================================
-- REFERÊNCIA RÁPIDA: TABELAS ENVOLVIDAS
-- =========================================================================
--
-- layer_bronze.opc_machine_alerts   → alertas das máquinas (fonte primária)
--   Colunas-chave: id_alert, principal_id, color, alert_time (UTC!),
--                  severity, engine_hours, three_letter_acronym,
--                  description, latitude, longitude
--
-- layer_bronze.opc_equipment        → cadastro de máquinas
--   Colunas-chave: principal_id, serial_number, model_name
--
-- localizacao_maquinas              → geolocalização fixa (estado/cidade/regional)
--   Colunas-chave: principal_id, estado, cidade, mesorregiao, regional
--
-- layer_bronze.tb_cliente_chassi_protheus → vínculo chassi↔cliente (Protheus)
--   Colunas-chave: vv1_chassi, a1_nome
--
-- rts_alertas                       → envios de alerta via WhatsApp (RTS)
--   Colunas-chave: chassi, data_alerta, data_envio, hora_envio,
--                  cliente, enviado_para, id_mensagem, notification_id, alerta
--
-- =========================================================================
-- NOTAS SOBRE TIMEZONE
-- =========================================================================
--
-- alert_time no banco está em UTC.
-- Todas as queries convertem para America/Sao_Paulo (BRT, UTC-3).
--
-- O filtro WHERE usa:
--   oma.alert_time >= ('DATA'::timestamp AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'UTC'
-- Isso converte a data local de entrada para UTC antes de comparar.
--
-- O SELECT usa:
--   (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo'
-- Isso converte o UTC armazenado para horário local na saída.
--
-- =========================================================================
