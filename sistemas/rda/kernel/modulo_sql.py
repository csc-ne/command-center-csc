# =========================================
# VENEZA EQUIPAMENTOS
# CENTRO DE SOLUÇÕES CONECTADAS - CSC
# REPORT AUTOMÁTICO DE DESEMPENHO
# 
# Módulo de Consultas e Resultados no Banco
#  - Análise Química - OK
#  - Análise de Performance - Pendente
#  - Chassis - OK
# =========================================

#MÓDULO OBSOLETO - ARMAZENADO APENAS PARA HISTÓRICO DE VERSÃO


from kernel.modulo_consulta import BancoService

class Resultados:

    def __init__(self):

        self.db = BancoService()
    

    def nome_cliente(self, id_client:int):

        sql = f"""
        select 
            regexp_replace(
                upper(unaccent(oo.name)),
                '[^A-Z ]',
                '',
                'g'
            ) as nome_cliente
        from layer_bronze.opc_organizations oo 
        where oo.id = {id_client};"""  

        return self.db.executar(sql)        

    def lista_frota(self, id_client: int):

        sql = """
            SELECT 
                oe.serial_number AS equipamento_chassi,
                oo.id AS id_organizacao,
                oe.machine_id AS principal_id, 
                oe.type_name,
                oe.isg_type_name,
                oe.model_name,
                UPPER(oo.name) AS name
            FROM layer_bronze.opc_equipment AS oe
            INNER JOIN layer_bronze.opc_organizations AS oo
                ON oe.organization_id = oo.id
            WHERE oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
            AND oe.organization_id = %s;
        """

        return self.db.executar(sql, (id_client,))
    

    def lista_comunicacao(self, id_client: int):

        sql = """
            WITH ultimos_horimetros AS (
                SELECT DISTINCT ON (oe.serial_number)
                    oe.serial_number AS chassi,
                    oe.model_name AS modelo,
                    meso.estado AS estado,
                    meso.mesorregiao AS cidade,
                    meso.latitude AS latitude,
                    meso.longitude AS longitude,

                    ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo') AS data_comunicacao_raw,

                    ROUND(oeh.reading_value::numeric, 1) AS horimetro
                FROM layer_bronze.opc_equipment AS oe
                JOIN layer_bronze.opc_locations_history AS loc
                    ON oe.principal_id = loc.principal_id
                LEFT JOIN layer_bronze.opc_engine_hours AS oeh
                    ON oeh.principal_id = oe.principal_id
                JOIN layer_bronze.opc_organizations AS oo
                    ON oo.id = oe.organization_id
                JOIN public.localizacao_maquinas AS meso
                    ON meso.principal_id = oe.principal_id

                WHERE oe.org_role_in_possession = 'true'
                AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
                AND oe.organization_id = %s

                ORDER BY 
                    oe.serial_number,
                    oeh.reading_value DESC
            )

            SELECT
                chassi,
                modelo,
                estado,
                cidade,
                horimetro,
                latitude,
                longitude,

                to_char(data_comunicacao_raw, 'DD-MM-YYYY') AS data_comunicacao,

                (CEIL(horimetro / 500.0) * 500) AS proxima_verificacao,
                (CEIL(horimetro / 500.0) * 500) - horimetro AS horas_para_verificacao,

                CASE 
                    WHEN data_comunicacao_raw IS NULL THEN 'SEM_DADOS'
                    WHEN data_comunicacao_raw >= (now() AT TIME ZONE 'America/Sao_Paulo') - INTERVAL '30 days'
                        THEN 'ONLINE'
                    ELSE 'OFFLINE'
                END AS status_comunicacao

            FROM ultimos_horimetros
            ORDER BY horimetro DESC;
        """

        return self.db.executar(sql, (id_client,))
    
    def lista_utilizacao(self, id_client:int, data_inicial:str, data_final:str):

        sql = """
            WITH calc AS (
                SELECT
                    opc.id,
                    opc.equipment_id,
                    opc.oem_name,
                    opc.model,
                    opc.pin,
                    opc.snapshot_time,
                    opc.operating_hours,
                    opc.idle_hours,
                    opc.fuel_consumed,
                    (opc.operating_hours - opc.idle_hours) AS work_hours,

                    LAG(opc.operating_hours) OVER (PARTITION BY opc.equipment_id ORDER BY opc.snapshot_time)
                        AS operating_hours_anterior,

                    LAG(opc.idle_hours) OVER (PARTITION BY opc.equipment_id ORDER BY opc.snapshot_time)
                        AS idle_hours_anterior,

                    LAG(opc.fuel_consumed) OVER (PARTITION BY opc.equipment_id ORDER BY opc.snapshot_time)
                        AS fuel_consumed_anterior,

                    LAG(opc.operating_hours - opc.idle_hours) OVER (PARTITION BY opc.equipment_id ORDER BY opc.snapshot_time)
                        AS work_hours_anterior

                FROM layer_bronze.opc_iso AS opc
                WHERE opc.snapshot_time::date BETWEEN DATE %s AND DATE %s
            ),

            deltas AS (
                SELECT
                    oem_name,
                    model,
                    pin,
                    snapshot_time::date AS data,
                    idle_hours - idle_hours_anterior       AS delta_idle_hours,
                    fuel_consumed - fuel_consumed_anterior AS delta_fuel_consumed,
                    work_hours - work_hours_anterior       AS delta_work_hours
                FROM calc
            ),

            final_calc AS (
                SELECT
                    oem_name,
                    model,
                    pin,
                    data,
                    SUM(delta_idle_hours)    AS idle_hours,
                    SUM(delta_work_hours)    AS work_hours,
                    SUM(delta_fuel_consumed) AS fuel_consumed,
                    CASE
                        WHEN (SUM(delta_idle_hours) + SUM(delta_work_hours)) > 0
                        THEN SUM(delta_fuel_consumed) /
                            (SUM(delta_idle_hours) + SUM(delta_work_hours))
                        ELSE NULL
                    END AS fuel_rate
                FROM deltas
                GROUP BY oem_name, model, pin, data
            ),

            equip AS (
                SELECT 
                    oe.serial_number AS equipamento_chassi,
                    oo.id AS id_organizacao,
                    oe.machine_id AS principal_id, 
                    oe.type_name,
                    oe.isg_type_name,
                    oe.model_name,
                    oo.name AS organizacao
                FROM layer_bronze.opc_equipment AS oe
                INNER JOIN layer_bronze.opc_organizations AS oo
                    ON oe.organization_id = oo.id
                WHERE oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
                AND oe.organization_id = %s
            ),

            ref_consumo AS (
                SELECT *
                FROM (
                    VALUES
                        ('130P', 12), 
                        ('130G', 12), 
                        ('200G', 12),
                        ('210P', 16), 
                        ('210G', 16), 
                        ('250G', 17),
                        ('310P', 5.8), 
                        ('350G', 26),
                        ('444G', 8),
                        ('524P', 9.5), 
                        ('524K', 9.5), 
                        ('524K-II', 9.5),
                        ('544G', 11), 
                        ('544P', 11), 
                        ('544K', 11), 
                        ('544K-II', 11),
                        ('620P', 15), 
                        ('620G', 15), 
                        ('622G', 15),
                        ('624P', 14), 
                        ('624K', 14), 
                        ('624K-II', 14),
                        ('670P', 16),
                        ('644P', 17), 
                        ('644K', 17),
                        ('670G', 16), 
                        ('672G', 16),
                        ('700J-II', 14),
                        ('724P', 17), 
                        ('724K', 17),
                        ('744P', 25), 
                        ('744K-II', 25),
                        ('750J-II', 16),
                        ('770P', 17),
                        ('850J-II', 33),
                        ('350P', 26)
                ) AS t(model_clean, fuel_rate_reference)
            )

            SELECT
                fc.*,
                REPLACE(fc.model, ' ', '') AS model_clean,
                rc.fuel_rate_reference,
                (fc.fuel_rate - rc.fuel_rate_reference) AS fuel_rate_difference,

                CASE
                    WHEN (fc.fuel_rate - rc.fuel_rate_reference) > 0.2 THEN 'HIGH_CONSUMPTION'
                    WHEN (fc.fuel_rate - rc.fuel_rate_reference) BETWEEN -2 AND 0.2 THEN 'NORMAL_CONSUMPTION'
                    WHEN (fc.fuel_rate - rc.fuel_rate_reference) < -2 THEN 'LOW_CONSUMPTION'
                    ELSE NULL
                END AS fuel_use,

                e.id_organizacao,
                e.principal_id,
                e.type_name,
                e.isg_type_name,
                e.model_name AS equipamento_modelo,
                e.organizacao

            FROM final_calc AS fc
            LEFT JOIN ref_consumo AS rc
                ON REPLACE(fc.model, ' ', '') = rc.model_clean
            INNER JOIN equip AS e
                ON fc.pin = e.equipamento_chassi
            WHERE 
                fc.work_hours >= 1        
                AND fc.fuel_consumed >= 1   
                AND fc.fuel_rate >= 1
            ORDER BY fc.pin, fc.data;
        """
        return self.db.executar(sql, (data_inicial, data_final, id_client))

    def lista_alertas(self, id_client:int, data_inicial:str, data_final:str):

        sql = """
            WITH alertas AS (
                SELECT
                    al.serial_number,
                    al.make_name,
                    al.type_name,
                    al.model_name,
                    al.organization_id,
                    oma.principal_id,

                    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' AS alert_time_ts,

                    to_char(
                        (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
                        'DD-MM-YYYY'
                    ) AS alert_time,

                    oma.latitude,
                    oma.longitude,
                    oma.color,
                    oma.severity,
                    oma.three_letter_acronym,
                    oma.suspect_parameter_name,
                    oma.failure_mode_indicator,
                    UPPER(unaccent(oma.description)) AS description
                FROM layer_bronze.opc_machine_alerts oma
                INNER JOIN layer_bronze.opc_equipment al
                    ON al.principal_id = oma.principal_id
            )
            SELECT *
            FROM alertas al
            WHERE 
                alert_time_ts::date
                BETWEEN to_date(%s, 'DD-MM-YYYY') AND to_date(%s, 'DD-MM-YYYY')
                AND al.make_name = 'JOHN DEERE'
                AND al.organization_id = %s
            ORDER BY alert_time_ts DESC;
        """
        return self.db.executar(sql, (data_inicial, data_final, id_client))

    def contagem_alertas(self, id_client:int, data_inicial:str, data_final:str):

        sql = """
            WITH alertas AS (
                SELECT
                    al.serial_number,
                    al.make_name,
                    al.type_name,
                    al.model_name,
                    al.organization_id,
                    oma.principal_id,

                    /* Mantém como timestamp */
                    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' AS alert_time,

                    oma.latitude,
                    oma.longitude,
                    oma.color,
                    oma.severity,
                    oma.three_letter_acronym,
                    oma.suspect_parameter_name,
                    oma.failure_mode_indicator,
                    UPPER(unaccent(oma.description)) AS description

                FROM layer_bronze.opc_machine_alerts oma
                INNER JOIN layer_bronze.opc_equipment al
                    ON al.principal_id = oma.principal_id
            )

            SELECT
                severity,
                COUNT(*) AS quantidade,
                to_char(MIN(alert_time), 'DD-MM-YYYY') AS primeira_ocorrencia,
                to_char(MAX(alert_time), 'DD-MM-YYYY') AS ultima_ocorrencia
            FROM alertas
            WHERE 
                alert_time::date BETWEEN %s::date AND %s::date
                AND make_name = 'JOHN DEERE'
                AND organization_id = %s
            GROUP BY severity
            ORDER BY quantidade DESC;
        """

        return self.db.executar(sql, (data_inicial, data_final, id_client))

    def resumo_alertas(self, id_client:int, data_inicial:str, data_final:str):

       sql = f""" WITH alertas AS (
            SELECT
                al.serial_number,
                al.make_name,
                al.type_name,
                al.model_name,
                al.organization_id,
                al.isg_type_name,
                oma.principal_id,
                to_char(
                    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
                    'DD-MM-YYYY'
                ) AS alert_time,
                oma.latitude,
                oma.longitude,
                oma.color,
                oma.severity,
                oma.three_letter_acronym,
                oma.suspect_parameter_name,
                oma.failure_mode_indicator,
                UPPER(unaccent(oma.description)) AS description
            FROM layer_bronze.opc_machine_alerts oma
            INNER JOIN layer_bronze.opc_equipment al
                ON al.principal_id = oma.principal_id
        ),
        alertas_periodo AS (
            SELECT
                *,
                to_date(alert_time, 'DD-MM-YYYY') AS dt_alerta
            FROM alertas
            WHERE to_date(alert_time, 'DD-MM-YYYY')
                BETWEEN to_date('{data_inicial}','DD-MM-YYYY')
                    AND to_date('{data_final}','DD-MM-YYYY')
            AND make_name = 'JOHN DEERE'
            AND isg_type_name in ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
            AND organization_id = {id_client}
        )
        SELECT
            al.serial_number AS chassi,
            COUNT(al.dt_alerta) AS total_alertas,
            COUNT(*) FILTER (WHERE al.severity = 'INFO')     AS qtd_info,
            COUNT(*) FILTER (WHERE al.severity = 'MEDIUM')   AS qtd_medium,
            COUNT(*) FILTER (WHERE al.severity = 'HIGH')     AS qtd_high,
            COUNT(*) FILTER (WHERE al.severity = 'CRITICAL') AS qtd_critical,
            CASE
                WHEN MAX(al.dt_alerta) IS NULL
                    THEN 'Sem alertas enviados no período'
                ELSE to_char(MAX(al.dt_alerta), 'DD-MM-YYYY')
            END AS data_ultimo_alerta
        FROM alertas_periodo al
        GROUP BY al.serial_number
        ORDER BY total_alertas DESC;"""
       
       return self.db.executar(sql)  


    def lista_amostras(self, id_client:int, data_inicial:str, data_final:str):

       sql = f"""
                SELECT DISTINCT
                    asraa.numero_amostra,
                    asraa.status_amostra AS status,

                    to_char(
                        (asraa.data_coleta AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
                        'DD-MM-YYYY'
                    ) AS data_coleta,

                    to_char(
                        (asraa.data_finalizacao AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
                        'DD-MM-YYYY'
                    ) AS data_finalizacao,

                    EXTRACT(
                        DAY FROM (
                            ((asraa.data_finalizacao AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo')
                            -
                            ((asraa.data_coleta AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo')
                        )
                    ) AS tempo_analise,

                    asraa.equipamento_modelo,
                    asraa.compartimento_nome AS compartimento,
                    asraa.equipamento_chassi,
                    oe.id_organizacao,
                    oe.principal_id,
                    oe.type_name,
                    oe.isg_type_name,
                    oe.model_name,
                    oe.org_name

                FROM layer_bronze.als_s360_resultado_amostra AS asraa

                INNER JOIN layer_bronze.als_s360_resultado_amostra_analise AS aaos
                    ON asraa.numero_amostra = aaos.numero_amostra

                INNER JOIN (
                    SELECT 
                        oe.serial_number AS equipamento_chassi,
                        oo.id AS id_organizacao,
                        oe.machine_id AS principal_id, 
                        oe.type_name,
                        oe.isg_type_name,
                        oe.model_name,
                        UPPER(oo.name) AS org_name
                    FROM layer_bronze.opc_equipment AS oe
                    INNER JOIN layer_bronze.opc_organizations AS oo
                        ON oe.organization_id = oo.id
                    WHERE 
                        oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
                        AND oe.org_role_in_possession = 'true'
                ) AS oe
                    ON asraa.equipamento_chassi = oe.equipamento_chassi

                WHERE 
                    asraa.data_finalizacao BETWEEN '{data_inicial}' AND '{data_final}'
                    AND asraa.status_amostra IS NOT NULL
                    AND asraa.familia_equip_nome IN (
                        'RETROESCAVADEIRA',
                        'CARREGADEIRA',
                        'ESCAVADEIRA',
                        'MOTONIVELADORA',
                        'TRATOR DE ESTEIRA',
                        'TRATOR DE ESTEIRA JD'
                    )
                    AND oe.id_organizacao = {id_client}

                ORDER BY 
                    data_finalizacao DESC;"""
       
       return self.db.executar(sql)  
    

