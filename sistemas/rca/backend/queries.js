// =========== ALS - Analise de Lubrificantes S360 ============
// queries.js — Queries SQL centralizadas
// =============================================================
//
// Migracao (2026-07-10): as queries "essenciais" (TOTAL, criticidades,
// amostras/dia, resultados detalhados) passaram a usar como base a tabela
// layer_bronze.als_resultado_amostra_status_s360 com data_status em fuso
// America/Sao_Paulo e o filtro de posse ativa em opc_equipment
// (org_role_in_possession = 'true'), substituindo o filtro fixo de
// CLIENTES_VENEZA + data_finalizacao. Endpoints de "familia", "cliente",
// "geo-criticos", "criticos" e "canceladas" mantidos como antes.

// ---------------------------------------------------------------------------
// Filtros ainda usados pelas queries herdadas do Grafana original.
// ---------------------------------------------------------------------------
const CLIENTES_VENEZA = `
  'VENEZA EQUIPAMENTOS PESADOS - SALVADOR BA',
  'VENEZA EQUIPAMENTOS PESADOS - FORTALEZA CE',
  'VENEZA EQUIPAMENTOS PESADOS - PETROLINA PE',
  'VENEZA EQUIPAMENTOS PESADOS - RECIFE PE',
  'VENEZA EQUIPAMENTOS PESADOS - BAYUEX PB'
`;

const FAMILIAS_EQUIP = `
  'RETROESCAVADEIRA',
  'CARREGADEIRA',
  'ESCAVADEIRA',
  'MOTONIVELADORA',
  'TRATOR DE ESTEIRA',
  'TRATOR DE ESTEIRA JD'
`;

// ---------------------------------------------------------------------------
// BASE_STATUS_CTE: fonte oficial das novas queries essenciais.
// Traz arass.* + coluna derivada data_resultado (data_status convertida
// para America/Sao_Paulo) e ja filtra por posse ativa em opc_equipment.
// Parametros: $1 = date_start, $2 = date_end
// ---------------------------------------------------------------------------
const BASE_STATUS_CTE = `
WITH primaria AS (
  SELECT
    arass.*,
    arass.data_status AT TIME ZONE 'America/Sao_Paulo' AS data_resultado
  FROM layer_bronze.als_resultado_amostra_status_s360 AS arass
  WHERE arass.data_status IS NOT NULL
),
secundaria AS (
  SELECT
    primaria.*,
    oe.principal_id,
    oe.serial_number,
    oe.model_name,
    oe.organization_id
  FROM primaria
  LEFT JOIN layer_bronze.opc_equipment AS oe
    ON primaria.chassi_serie = oe.serial_number
  WHERE oe.org_role_in_possession = 'true'
)
`;

// ---------------------------------------------------------------------------
// 1. Total de Amostras Registradas (nova fonte)
//    Alias preservado: total_distinto (compat com frontend)
// ---------------------------------------------------------------------------
const TOTAL_AMOSTRAS = `
${BASE_STATUS_CTE}
SELECT COUNT(DISTINCT numero_amostra) AS total_distinto
FROM secundaria
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day';
`;

// ---------------------------------------------------------------------------
// 2. Distribuicao de Criticidades (nova fonte)
//    Aliases preservados: label, value (compat com frontend)
// ---------------------------------------------------------------------------
const DISTRIBUICAO_CRITICIDADES = `
${BASE_STATUS_CTE}
SELECT
  status AS label,
  COUNT(DISTINCT numero_amostra) AS value
FROM secundaria
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day'
  AND status IS NOT NULL
GROUP BY status
ORDER BY value DESC;
`;

// ---------------------------------------------------------------------------
// 3. Contagem de Amostras por dia (nova fonte)
//    Aliases preservados: time, total (compat com frontend)
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_DIA = `
${BASE_STATUS_CTE}
SELECT
  date_trunc('day', data_resultado) AS time,
  COUNT(DISTINCT numero_amostra) AS total
FROM secundaria
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day'
GROUP BY 1
ORDER BY 1;
`;

// ---------------------------------------------------------------------------
// 4. NOVO: Contagem de Amostras por Estado
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_ESTADO = `
${BASE_STATUS_CTE}
, terciaria AS (
  SELECT
    secundaria.*,
    lm.estado
  FROM secundaria
  LEFT JOIN public.localizacao_maquinas AS lm
    ON secundaria.principal_id = lm.principal_id
)
SELECT
  estado,
  COUNT(DISTINCT numero_amostra) AS total_numero_amostra
FROM terciaria
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day'
  AND estado IS NOT NULL
GROUP BY estado
ORDER BY total_numero_amostra DESC;
`;

// ---------------------------------------------------------------------------
// 5. NOVO: Contagem de Amostras por Modelo
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_MODELO = `
${BASE_STATUS_CTE}
SELECT
  model_name,
  COUNT(DISTINCT numero_amostra) AS total_numero_amostra
FROM secundaria
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day'
  AND model_name IS NOT NULL
GROUP BY model_name
ORDER BY total_numero_amostra DESC;
`;

// ---------------------------------------------------------------------------
// 6. NOVO: Contagem de Amostras por Compartimento
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_COMPARTIMENTO = `
${BASE_STATUS_CTE}
SELECT
  tipo_compartimento_nome,
  COUNT(DISTINCT numero_amostra) AS total_numero_amostra
FROM secundaria
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day'
  AND tipo_compartimento_nome IS NOT NULL
GROUP BY tipo_compartimento_nome
ORDER BY total_numero_amostra DESC;
`;

// ---------------------------------------------------------------------------
// 7. Total de Amostras Por Ponto de Origem (cliente) — HERDADA
//    Mantida como estava (filtro CLIENTES_VENEZA + data_finalizacao).
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_ORIGEM = `
SELECT
  asraa.cliente_nome AS cliente,
  COUNT(DISTINCT asraa.numero_amostra) AS total
FROM layer_bronze.als_s360_resultado_amostra AS asraa
WHERE asraa.data_finalizacao IS NOT NULL
  AND asraa.data_finalizacao >= $1::timestamp
  AND asraa.data_finalizacao < $2::timestamp + INTERVAL '1 day'
  AND asraa.cliente_nome IN (${CLIENTES_VENEZA})
GROUP BY cliente
ORDER BY total DESC;
`;

// ---------------------------------------------------------------------------
// 8. Ultimos Resultados Criticos No Periodo — HERDADA
// ---------------------------------------------------------------------------
const RESULTADOS_CRITICOS = `
SELECT
  asraa.numero_amostra,
  asraa.status_amostra,
  asraa.data_finalizacao,
  asraa.cliente_nome,
  asraa.obra_nome
FROM layer_bronze.als_s360_resultado_amostra AS asraa
WHERE asraa.data_finalizacao IS NOT NULL
  AND asraa.data_finalizacao >= $1::timestamp
  AND asraa.data_finalizacao < $2::timestamp + INTERVAL '1 day'
  AND asraa.status_amostra = 'CRITICO'
  AND asraa.cliente_nome IN (${CLIENTES_VENEZA})
ORDER BY asraa.data_finalizacao DESC;
`;

// ---------------------------------------------------------------------------
// 9. Geolocalizacao dos Ultimos Resultados Criticos — HERDADA
// ---------------------------------------------------------------------------
const GEO_CRITICOS = `
WITH consulta1 AS (
  SELECT
    t1.principal_id,
    t1.latitude,
    t1.longitude,
    t1.cidade,
    t1.estado,
    t2.name AS machine_name
  FROM public.localizacao_maquinas t1
  INNER JOIN layer_bronze.opc_equipment t2
    ON t1.principal_id = t2.principal_id
),
consulta_2 AS (
  SELECT
    j1.principal_id,
    j1.latitude,
    j1.longitude,
    j1.cidade,
    j1.estado,
    j1.machine_name,
    t3.numero_amostra,
    t3.status,
    t3.obra_nome,
    t3.data_status
  FROM consulta1 j1
  INNER JOIN layer_bronze.als_resultado_amostra_status_s360 t3
    ON j1.machine_name = t3.chassi_serie
  WHERE t3.status = 'CRITICO'
    AND t3.data_status >= $1::timestamp
    AND t3.data_status < $2::timestamp + INTERVAL '1 day'
)
SELECT *
FROM consulta_2
ORDER BY principal_id, numero_amostra;
`;

// ---------------------------------------------------------------------------
// 10. Tabela detalhada de resultados no periodo (NOVA FONTE)
//     Colunas retornadas (frontend depende dessa lista):
//       numero_amostra, chassi_serie, status, tipo_compartimento_nome,
//       nome_compartimento, data_resultado (YYYY-MM-DD), model_name,
//       obra, cliente, latitude, longitude, estado, cidade, regional,
//       avaliacao, acoes_inspecao
// ---------------------------------------------------------------------------
const RESULTADOS_PERIODO = `
${BASE_STATUS_CTE}
, terciaria AS (
  SELECT
    secundaria.*,
    lm.latitude,
    lm.longitude,
    lm.estado,
    lm.cidade,
    lm.regional
  FROM secundaria
  LEFT JOIN public.localizacao_maquinas AS lm
    ON secundaria.principal_id = lm.principal_id
),
quarta AS (
  SELECT
    terciaria.*,
    oo.name AS organization_name
  FROM terciaria
  LEFT JOIN layer_bronze.opc_organizations AS oo
    ON terciaria.organization_id = oo.id
),
quinta AS (
  SELECT
    quarta.*,
    asra.avaliacao,
    asra.acoes_inspecao
  FROM quarta
  LEFT JOIN layer_bronze.als_s360_resultado_amostra AS asra
    ON asra.numero_amostra = quarta.numero_amostra
)
SELECT
  numero_amostra,
  chassi_serie,
  status,
  tipo_compartimento_nome,
  nome_compartimento,
  TO_CHAR(data_resultado, 'YYYY-MM-DD') AS data_resultado,
  model_name,
  organization_name AS obra,
  cliente_nome AS cliente,
  latitude,
  longitude,
  estado,
  cidade,
  regional,
  avaliacao,
  acoes_inspecao
FROM quinta
WHERE data_resultado >= $1::timestamp
  AND data_resultado < $2::timestamp + INTERVAL '1 day'
ORDER BY data_resultado DESC;
`;

// ---------------------------------------------------------------------------
// 11. Distribuicao de Amostras por Familia de Equipamento — HERDADA
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_FAMILIA = `
SELECT
  familia_equip_nome AS familia,
  COUNT(DISTINCT numero_amostra) AS total_distintos
FROM layer_bronze.als_s360_resultado_amostra
WHERE data_finalizacao >= $1::timestamp
  AND data_finalizacao < $2::timestamp + INTERVAL '1 day'
  AND familia_equip_nome IN (${FAMILIAS_EQUIP})
GROUP BY familia_equip_nome
ORDER BY total_distintos DESC;
`;

// ---------------------------------------------------------------------------
// 12. Total de Amostras Por Cliente (obra_nome, top 10) — HERDADA
// ---------------------------------------------------------------------------
const AMOSTRAS_POR_CLIENTE = `
SELECT
  obra_nome,
  COUNT(DISTINCT numero_amostra) AS total_distintos
FROM layer_bronze.als_s360_resultado_amostra
WHERE data_finalizacao >= $1::timestamp
  AND data_finalizacao < $2::timestamp + INTERVAL '1 day'
  AND familia_equip_nome IN (${FAMILIAS_EQUIP})
GROUP BY obra_nome
ORDER BY total_distintos DESC
LIMIT 10;
`;

// ---------------------------------------------------------------------------
// 13. Amostras Canceladas e Segregadas (detalhe) — HERDADA
// ---------------------------------------------------------------------------
const AMOSTRAS_CANCELADAS_SEGREGADAS = `
SELECT *
FROM layer_bronze.als_amostras_oleo_s360 aaos
WHERE aaos.situacao IN ('SEGREGADA', 'CANCELADA')
  AND aaos.dt_carga >= $1::timestamp
  AND aaos.dt_carga < $2::timestamp + INTERVAL '1 day'
  AND aaos.cliente_nome IN (
    'VENEZA EQUIPAMENTOS PESADOS - PETROLINA PE',
    'VENEZA EQUIPAMENTOS PESADOS - SALVADOR BA',
    'VENEZA EQUIPAMENTOS PESADOS - RECIFE PE',
    'VENEZA EQUIPAMENTOS PESADOS - FORTALEZA CE',
    'VENEZA EQUIPAMENTOS PESADOS - BAYEUX PB'
  );
`;

// ---------------------------------------------------------------------------
// 14. Total de Amostras Canceladas e Segregadas (agrupado) — HERDADA
// ---------------------------------------------------------------------------
const TOTAL_CANCELADAS_SEGREGADAS = `
SELECT
  aaos.cliente_nome,
  aaos.situacao,
  COUNT(*) AS total_amostras
FROM layer_bronze.als_amostras_oleo_s360 aaos
WHERE aaos.situacao IN ('SEGREGADA', 'CANCELADA')
  AND aaos.dt_carga >= $1::timestamp
  AND aaos.dt_carga < $2::timestamp + INTERVAL '1 day'
  AND aaos.cliente_nome IN (
    'VENEZA EQUIPAMENTOS PESADOS - PETROLINA PE',
    'VENEZA EQUIPAMENTOS PESADOS - SALVADOR BA',
    'VENEZA EQUIPAMENTOS PESADOS - RECIFE PE',
    'VENEZA EQUIPAMENTOS PESADOS - FORTALEZA CE',
    'VENEZA EQUIPAMENTOS PESADOS - BAYEUX PB'
  )
GROUP BY aaos.cliente_nome, aaos.situacao
ORDER BY total_amostras DESC;
`;

module.exports = {
  TOTAL_AMOSTRAS,
  DISTRIBUICAO_CRITICIDADES,
  AMOSTRAS_POR_DIA,
  AMOSTRAS_POR_ESTADO,
  AMOSTRAS_POR_MODELO,
  AMOSTRAS_POR_COMPARTIMENTO,
  AMOSTRAS_POR_FAMILIA,
  AMOSTRAS_POR_ORIGEM,
  RESULTADOS_CRITICOS,
  GEO_CRITICOS,
  RESULTADOS_PERIODO,
  AMOSTRAS_POR_CLIENTE,
  AMOSTRAS_CANCELADAS_SEGREGADAS,
  TOTAL_CANCELADAS_SEGREGADAS,
};
