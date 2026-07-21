# =========================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUÇÕES CONECTADAS - CSC
# RDA - REPORT DE DESEMPENHO AUTOMÁTICO
# DESENVOLVIDO POR THIAGO BARROS - thiago.barros@venezanet.com
# Módulo de Consultas e Resultados no Banco
# =========================================

from kernel.modulo_consulta import BancoService

class Resultados:

    """Módulo de consultas SQL parametrizadas para relatórios operacionais.

    Todas as consultas seguem o padrão:
        sql = "..."
        return self.db.executar(sql, parametros)

    Convenções adotadas
    -------------------
    - Métodos em snake_case padronizados com prefixo `consultar_`.
    - `id_client` representa o identificador do cliente.
    - Quando necessário, `data_inicial` e `data_final` devem ser informadas no
      formato `YYYY-MM-DD`.
    - As consultas usam placeholders `%s` para evitar SQL injection.
    """

    def __init__(self):

        """Armazena a conexão/adapter de banco.

        Parameters
        ----------
        db : object
            Objeto com método `executar(sql, params)`.

        """
        self.db = BancoService()

    def consultar_nome_cliente(self, id_client: int):

        """Retorna o nome do cliente padronizado.

        A consulta remove caracteres especiais e converte o nome para caixa alta.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.

        Returns
        -------
        Any
            Resultado da execução retornado por `self.db.executar`.
        """
        sql = """
       
         SELECT
            regexp_replace(
                upper(unaccent(oo.name)),
                '[^A-Z ]',
                '',
                'g'
            ) AS nome_cliente
        FROM layer_bronze.opc_organizations oo
        WHERE oo.id = %s

        """
        return self.db.executar(sql, (id_client,))

    def consultar_geolocalizacao(self, id_client: int):

        """Retorna a geolocalização dos equipamentos do cliente.

        Busca um registro por chassi com estado, cidade e coordenadas.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.
        """
        sql = """

        SELECT DISTINCT ON (oe.serial_number)
            oe.serial_number AS chassi,
            oe.model_name AS modelo,
            meso.estado AS estado,
            meso.mesorregiao AS cidade,
            COALESCE(meso.latitude::text, 'SEM LATITUDE') AS latitude,
            COALESCE(meso.longitude::text, 'SEM LONGITUDE') AS longitude
        FROM layer_bronze.opc_equipment AS oe
        LEFT JOIN public.localizacao_maquinas AS meso
            ON meso.principal_id = oe.principal_id
        WHERE oe.org_role_in_possession = 'true'
          AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
          AND oe.organization_id = %s
        ORDER BY oe.serial_number

        """
        return self.db.executar(sql, (id_client,))

    def consultar_horimetros(self, id_client: int):

        """Retorna horímetro, status do horímetro e aptidão para revisão.

        A lógica considera a última comunicação do equipamento e a distância,
        em horas, até a próxima verificação de 500 horas.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.
        """
        
        sql = """
        
        WITH base AS (
            SELECT DISTINCT ON (oe.serial_number)
                oe.serial_number AS chassi,
                oe.model_name AS modelo,
                ROUND(oeh.reading_value::numeric, 1) AS horimetro,
                ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo') AS data_comunicacao_raw
            FROM layer_bronze.opc_equipment AS oe
            LEFT JOIN layer_bronze.opc_engine_hours AS oeh
                ON oeh.principal_id = oe.principal_id
            WHERE oe.org_role_in_possession = 'true'
              AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
              AND oe.organization_id = %s
            ORDER BY
                oe.serial_number,
                oeh.report_time DESC NULLS LAST,
                oeh.reading_value DESC NULLS LAST
        ),
        calc AS (
            SELECT
                chassi,
                modelo,
                horimetro,
                data_comunicacao_raw,
                (CEIL(horimetro / 500.0) * 500) AS proxima_verificacao,
                (CEIL(horimetro / 500.0) * 500) - horimetro AS horas_para_verificacao,
                CASE
                    WHEN data_comunicacao_raw IS NOT NULL
                     AND data_comunicacao_raw >= (now() AT TIME ZONE 'America/Sao_Paulo') - INTERVAL '30 days'
                    THEN 'ATUALIZADO'
                    ELSE 'DESATUALIZADO'
                END AS status_horimetro
            FROM base
        )
        SELECT
            chassi,
            modelo,
            horimetro,
            proxima_verificacao,
            horas_para_verificacao,
            status_horimetro,
            CASE
                WHEN horimetro IS NULL THEN 'SEM DADOS'
                WHEN status_horimetro <> 'ATUALIZADO' THEN 'DESCONHECIDO'
                WHEN horas_para_verificacao < 50 THEN 'PARA REVISÃO'
                WHEN horas_para_verificacao BETWEEN 50 AND 100 THEN 'PARA VERIFICAR'
                WHEN horas_para_verificacao > 100 THEN 'EM AGUARDO'
                ELSE NULL
            END AS aptidao_revisao
        FROM calc
        ORDER BY horimetro DESC NULLS LAST
        """
        return self.db.executar(sql, (id_client,))

    def consultar_status_comunicacao(self, id_client: int):

        """Retorna o status de comunicação dos equipamentos.

        Classifica cada equipamento como ONLINE, OFFLINE ou SEM DADOS com base
        na última data de comunicação.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.
        """
       
        sql = """
        
        SELECT DISTINCT ON (oe.serial_number)
            oe.serial_number AS chassi,
            oe.model_name AS modelo,
            to_char(
                ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo'),
                'DD-MM-YYYY'
            ) AS data_comunicacao,
            CASE
                WHEN oeh.report_time IS NULL THEN 'SEM DADOS'
                WHEN ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo')
                     >= (now() AT TIME ZONE 'America/Sao_Paulo') - INTERVAL '30 days'
                    THEN 'ONLINE'
                ELSE 'OFFLINE'
            END AS status_comunicacao
        FROM layer_bronze.opc_equipment AS oe
        LEFT JOIN layer_bronze.opc_engine_hours AS oeh
            ON oeh.principal_id = oe.principal_id
        WHERE oe.org_role_in_possession = 'true'
          AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
          AND oe.organization_id = %s
        ORDER BY oe.serial_number, oeh.report_time DESC NULLS LAST

        """
        return self.db.executar(sql, (id_client,))

    def consultar_utilizacao_frota_diaria(self, id_client: int, data_inicial: str, data_final: str):
        
        """Retorna a utilização diária da frota no período informado.

        A consulta calcula horas ociosas, horas trabalhadas, combustível
        consumido, taxa de consumo e classificação versus referência por modelo.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.

        """
        sql = """
        
        WITH params AS (
            SELECT %s::date AS data_inicio,
                   %s::date AS data_fim
        ),
        equip AS (
            SELECT
                oe.serial_number AS pin,
                oe.type_name,
                oe.isg_type_name
            FROM layer_bronze.opc_equipment oe
            WHERE oe.org_role_in_possession = 'true'
              AND oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
              AND oe.organization_id = %s
        ),
        iso_pre AS (
            SELECT DISTINCT ON (opc.pin)
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time < p.data_inicio
            ORDER BY opc.pin, opc.snapshot_time DESC
        ),
        iso_periodo AS (
            SELECT
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time >= p.data_inicio
              AND opc.snapshot_time < (p.data_fim + INTERVAL '1 day')
        ),
        iso_base AS (
            SELECT * FROM iso_pre
            UNION ALL
            SELECT * FROM iso_periodo
        ),
        calc AS (
            SELECT
                ib.pin,
                REPLACE(ib.model, ' ', '') AS model_clean,
                ib.snapshot_time,
                ib.snapshot_time::date AS data_ref,
                ib.operating_hours,
                ib.idle_hours,
                ib.fuel_consumed,
                LAG(ib.operating_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS op_prev,
                LAG(ib.idle_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS idle_prev,
                LAG(ib.fuel_consumed) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS fuel_prev
            FROM iso_base ib
        ),
        deltas AS (
            SELECT
                c.pin,
                c.model_clean,
                c.data_ref,
                (c.idle_hours - c.idle_prev) AS d_idle,
                ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) AS d_work,
                (c.fuel_consumed - c.fuel_prev) AS d_fuel
            FROM calc c
            JOIN params p ON TRUE
            WHERE c.op_prev IS NOT NULL
              AND c.idle_prev IS NOT NULL
              AND c.fuel_prev IS NOT NULL
              AND c.data_ref BETWEEN p.data_inicio AND p.data_fim
              AND (c.idle_hours - c.idle_prev) >= 0
              AND ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) >= 0
              AND (c.fuel_consumed - c.fuel_prev) >= 0
        ),
        consumo_dia AS (
            SELECT
                pin,
                model_clean,
                data_ref,
                ROUND(SUM(d_idle)::numeric, 2) AS idle_hours,
                ROUND(SUM(d_work)::numeric, 2) AS work_hours,
                ROUND(SUM(d_fuel)::numeric, 2) AS fuel_consumed,
                ROUND(
                    (SUM(d_fuel) / NULLIF(SUM(d_idle) + SUM(d_work), 0))::numeric,
                    2
                ) AS fuel_rate
            FROM deltas
            GROUP BY pin, model_clean, data_ref
        ),
        ref_consumo(model_clean, fuel_rate_reference) AS (
            VALUES
                ('130P', 12::numeric), ('130G', 12::numeric), ('200G', 12::numeric),
                ('210P', 16::numeric), ('210G', 16::numeric), ('250G', 17::numeric),
                ('310P', 5.8::numeric), ('350G', 26::numeric), ('444G', 8::numeric),
                ('524P', 9.5::numeric), ('524K', 9.5::numeric), ('524K-II', 9.5::numeric),
                ('544G', 11::numeric), ('544P', 11::numeric), ('544K', 11::numeric), ('544K-II', 11::numeric),
                ('620P', 15::numeric), ('620G', 15::numeric), ('622G', 15::numeric),
                ('624P', 14::numeric), ('624K', 14::numeric), ('624K-II', 14::numeric),
                ('670P', 16::numeric), ('644P', 17::numeric), ('644K', 17::numeric),
                ('670G', 16::numeric), ('672G', 16::numeric), ('700J-II', 14::numeric),
                ('724P', 17::numeric), ('724K', 17::numeric), ('744P', 25::numeric), ('744K-II', 25::numeric),
                ('750J-II', 16::numeric), ('770P', 17::numeric), ('850J-II', 33::numeric), ('310L', 5.8::numeric),
                ('350P', 26::numeric)
        )
        SELECT
            e.pin,
            cd.model_clean,
            e.type_name,
            e.isg_type_name,
            TO_CHAR(cd.data_ref, 'DD-MM-YYYY') AS data_inicial,
            TO_CHAR(cd.data_ref, 'DD-MM-YYYY') AS data_final,
            COALESCE(cd.idle_hours::text, 'SEM DADOS') AS idle_hours,
            COALESCE(cd.work_hours::text, 'SEM DADOS') AS work_hours,
            COALESCE(cd.fuel_consumed::text, 'SEM DADOS') AS fuel_consumed,
            cd.fuel_rate,
            rc.fuel_rate_reference,
            ROUND((cd.fuel_rate - rc.fuel_rate_reference)::numeric, 2) AS fuel_rate_difference,
            CASE
                WHEN cd.fuel_rate IS NULL OR rc.fuel_rate_reference IS NULL THEN NULL
                WHEN (cd.fuel_rate - rc.fuel_rate_reference) > 0.2 THEN 'HIGH_CONSUMPTION'
                WHEN (cd.fuel_rate - rc.fuel_rate_reference) BETWEEN -2 AND 0.2 THEN 'NORMAL_CONSUMPTION'
                WHEN (cd.fuel_rate - rc.fuel_rate_reference) < -2 THEN 'LOW_CONSUMPTION'
                ELSE NULL
            END AS fuel_use
        FROM equip e
        LEFT JOIN consumo_dia cd
            ON cd.pin = e.pin
        LEFT JOIN ref_consumo rc
            ON rc.model_clean = cd.model_clean
        ORDER BY e.pin, cd.data_ref NULLS LAST

        """
        return self.db.executar(sql, (data_inicial, data_final, id_client))

    def consultar_utilizacao_frota_acumulada(self, id_client: int, data_inicial: str, data_final: str):
       
        """Retorna a utilização acumulada da frota no período informado.

        A consulta consolida o período por equipamento, mantendo a mesma lógica
        de cálculo e comparação com referência de consumo.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.
        """
        sql = """
        
        WITH params AS (
            SELECT %s::date AS data_inicio,
                   %s::date AS data_fim
        ),
        equip AS (
            SELECT
                oe.serial_number AS pin,
                oe.type_name,
                oe.isg_type_name
            FROM layer_bronze.opc_equipment oe
            WHERE oe.org_role_in_possession = 'true'
              AND oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
              AND oe.organization_id = %s
        ),
        iso_pre AS (
            SELECT DISTINCT ON (opc.pin)
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time < p.data_inicio
            ORDER BY opc.pin, opc.snapshot_time DESC
        ),
        iso_periodo AS (
            SELECT
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time >= p.data_inicio
              AND opc.snapshot_time < (p.data_fim + INTERVAL '1 day')
        ),
        iso_base AS (
            SELECT * FROM iso_pre
            UNION ALL
            SELECT * FROM iso_periodo
        ),
        calc AS (
            SELECT
                ib.pin,
                REPLACE(ib.model, ' ', '') AS model_clean,
                ib.snapshot_time,
                ib.snapshot_time::date AS data_ref,
                ib.operating_hours,
                ib.idle_hours,
                ib.fuel_consumed,
                LAG(ib.operating_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS op_prev,
                LAG(ib.idle_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS idle_prev,
                LAG(ib.fuel_consumed) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS fuel_prev
            FROM iso_base ib
        ),
        deltas AS (
            SELECT
                c.pin,
                c.model_clean,
                c.data_ref,
                (c.idle_hours - c.idle_prev) AS d_idle,
                ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) AS d_work,
                (c.fuel_consumed - c.fuel_prev) AS d_fuel
            FROM calc c
            JOIN params p ON TRUE
            WHERE c.op_prev IS NOT NULL
              AND c.idle_prev IS NOT NULL
              AND c.fuel_prev IS NOT NULL
              AND c.data_ref BETWEEN p.data_inicio AND p.data_fim
              AND (c.idle_hours - c.idle_prev) >= 0
              AND ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) >= 0
              AND (c.fuel_consumed - c.fuel_prev) >= 0
        ),
        consumo_periodo AS (
            SELECT
                pin,
                model_clean,
                MIN(data_ref) AS data_inicial,
                MAX(data_ref) AS data_final,
                ROUND(SUM(d_idle)::numeric, 2) AS idle_hours,
                ROUND(SUM(d_work)::numeric, 2) AS work_hours,
                ROUND(SUM(d_fuel)::numeric, 2) AS fuel_consumed,
                ROUND(
                    (SUM(d_fuel) / NULLIF(SUM(d_idle) + SUM(d_work), 0))::numeric,
                    2
                ) AS fuel_rate
            FROM deltas
            GROUP BY pin, model_clean
        ),
        ref_consumo(model_clean, fuel_rate_reference) AS (
            VALUES
                ('130P', 12::numeric), ('130G', 12::numeric), ('200G', 12::numeric),
                ('210P', 16::numeric), ('210G', 16::numeric), ('250G', 17::numeric),
                ('310P', 5.8::numeric), ('350G', 26::numeric), ('444G', 8::numeric),
                ('524P', 9.5::numeric), ('524K', 9.5::numeric), ('524K-II', 9.5::numeric),
                ('544G', 11::numeric), ('544P', 11::numeric), ('544K', 11::numeric), ('544K-II', 11::numeric),
                ('620P', 15::numeric), ('620G', 15::numeric), ('622G', 15::numeric),
                ('624P', 14::numeric), ('624K', 14::numeric), ('624K-II', 14::numeric),
                ('670P', 16::numeric), ('644P', 17::numeric), ('644K', 17::numeric),
                ('670G', 16::numeric), ('672G', 16::numeric), ('700J-II', 14::numeric),
                ('724P', 17::numeric), ('724K', 17::numeric), ('744P', 25::numeric), ('744K-II', 25::numeric),
                ('750J-II', 16::numeric), ('770P', 17::numeric), ('850J-II', 33::numeric), ('350P', 26::numeric)
        )
        SELECT
            e.pin,
            cp.model_clean,
            e.type_name,
            e.isg_type_name,
            TO_CHAR(cp.data_inicial, 'DD-MM-YYYY') AS data_inicial,
            TO_CHAR(cp.data_final, 'DD-MM-YYYY') AS data_final,
            COALESCE(cp.idle_hours::text, 'SEM DADOS') AS idle_hours,
            COALESCE(cp.work_hours::text, 'SEM DADOS') AS work_hours,
            COALESCE(cp.fuel_consumed::text, 'SEM DADOS') AS fuel_consumed,
            cp.fuel_rate,
            rc.fuel_rate_reference,
            ROUND((cp.fuel_rate - rc.fuel_rate_reference)::numeric, 2) AS fuel_rate_difference,
            CASE
                WHEN cp.fuel_rate IS NULL OR rc.fuel_rate_reference IS NULL THEN NULL
                WHEN (cp.fuel_rate - rc.fuel_rate_reference) > 0.2 THEN 'HIGH_CONSUMPTION'
                WHEN (cp.fuel_rate - rc.fuel_rate_reference) BETWEEN -2 AND 0.2 THEN 'NORMAL_CONSUMPTION'
                WHEN (cp.fuel_rate - rc.fuel_rate_reference) < -2 THEN 'LOW_CONSUMPTION'
                ELSE NULL
            END AS fuel_use
        FROM equip e
        LEFT JOIN consumo_periodo cp
            ON cp.pin = e.pin
        LEFT JOIN ref_consumo rc
            ON rc.model_clean = cp.model_clean
        ORDER BY e.pin

        """
        return self.db.executar(sql, (data_inicial, data_final, id_client))

    def consultar_alertas(self, id_client: int, data_inicial: str, data_final: str):
        
        """Retorna os alertas de máquinas do cliente no período informado.

        Parameters
        ----------
        id_client : int
            ID da organização/cliente.
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.
        """
        sql = """
        
        WITH alertas AS (
            SELECT
                al.serial_number,
                al.type_name,
                al.model_name,
                al.organization_id,
                to_char(
                    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
                    'DD-MM-YYYY'
                ) AS alert_data,
                oma.color,
                oma.severity,
                oma.three_letter_acronym,
                oma.suspect_parameter_name,
                oma.failure_mode_indicator,
                UPPER(unaccent(oma.description)) AS description
            FROM layer_bronze.opc_machine_alerts AS oma
            INNER JOIN layer_bronze.opc_equipment AS al
                ON al.principal_id = oma.principal_id
            WHERE al.make_name = 'JOHN DEERE'
        )
        SELECT
            serial_number,
            type_name,
            model_name,
            alert_data,
            color,
            severity,
            three_letter_acronym,
            suspect_parameter_name,
            failure_mode_indicator,
            description
        FROM alertas
        WHERE to_date(alert_data, 'DD-MM-YYYY') BETWEEN %s::date AND %s::date
          AND organization_id = %s
        ORDER BY to_date(alert_data, 'DD-MM-YYYY') DESC

        """
        return self.db.executar(sql, (data_inicial, data_final, id_client))

    def analises_quimicas(self, id_client: int, data_inicial: str, data_final: str):
        """   
        Retorna as análises químicas vinculadas ao cliente informado.
        """ 
        sql = """
            SELECT
                asraa.numero_amostra,
                oe.serial_number AS chassi,
                arass.status,
                asraa.avaliacao,
                asraa.acoes_inspecao,
                TO_CHAR(
                    asraa.data_finalizacao AT TIME ZONE 'America/Sao_Paulo',
                    'DD-MM-YYYY'
                ) AS data_finalizacao_amostra,
                oe.model_name,
                arass.nome_compartimento
            FROM layer_bronze.als_s360_resultado_amostra AS asraa
            INNER JOIN layer_bronze.als_resultado_amostra_status_s360 AS arass
                ON arass.numero_amostra = asraa.numero_amostra
            LEFT JOIN layer_bronze.opc_equipment AS oe
                ON oe.serial_number = arass.chassi_serie
            WHERE oe.organization_id = %s
            AND asraa.data_finalizacao >= %s
            AND asraa.data_finalizacao < %s::date + INTERVAL '1 day'
            ORDER BY asraa.data_finalizacao DESC;
        """

        return self.db.executar(sql, (id_client, data_inicial, data_final))
    
    def consultar_analises_quimicas(self, id_client: int, data_inicial: str, data_final: str):

        """Retorna as análises químicas vinculadas ao principal_id informado.

        Parameters
        ----------
        id_client : int
            Principal ID do equipamento.
        """
        sql = """
        
        SELECT
            oe.serial_number,
            asraa.numero_amostra,
            asraa.status_amostra,
            asraa.avaliacao,
            asraa.tipo_compartimento_nome,
            TO_CHAR(
                asraa.data_finalizacao AT TIME ZONE 'America/Sao_Paulo',
                'DD-MM-YYYY'
            ) AS data_finalizacao
        FROM layer_bronze.als_s360_resultado_amostra AS asraa
        INNER JOIN layer_bronze.opc_equipment AS oe
            ON oe.serial_number = asraa.equipamento_chassi
        WHERE asraa.data_finalizacao IS NOT NULL
        AND oe.principal_id = %s
        AND asraa.data_finalizacao::date BETWEEN %s AND %s
        ORDER BY asraa.data_finalizacao DESC

        """
        return self.db.executar(sql, (id_client, data_inicial, data_final))

    def consultar_garantia(self, id_client: int):
        """Retorna o status de garantia das máquinas do cliente.

        Parameters
        ----------
        id_client : int
            Principal ID da Conta de Usuário.        
        
        
        """

        sql = """
            WITH garantias_base AS (
                SELECT DISTINCT ON (pops.serial_number)
                    pops.serial_number AS pin, 
                    pops.machine_serviced AS maquina_servicada,

                    TO_DATE(pops.basic_warranty_expiration, 'DD-Mon-YY') 
                        AS data_vencimento_garantia_basica,

                    pops.extended_warranty_type AS tipo_garantia_estendida,

                    TO_DATE(pops.extended_warranty_expiration, 'DD-Mon-YY') 
                        AS data_vencimento_garantia_estendida,

                    oe.organization_id

                FROM layer_bronze.pops_base AS pops

                INNER JOIN layer_bronze.opc_equipment AS oe
                    ON oe.serial_number = pops.serial_number

                WHERE 
                    pops.serial_number IS NOT NULL
                    AND pops.basic_warranty_expiration IS NOT NULL
                    AND oe.organization_id = %s

                ORDER BY
                    pops.serial_number,
                    TO_DATE(pops.basic_warranty_expiration, 'DD-Mon-YY') DESC,
                    TO_DATE(pops.extended_warranty_expiration, 'DD-Mon-YY') DESC NULLS LAST
            ),

            calculo AS (
                SELECT
                    *,
                    data_vencimento_garantia_basica - CURRENT_DATE 
                        AS dias_para_vencimento_basica,

                    data_vencimento_garantia_estendida - CURRENT_DATE 
                        AS dias_para_vencimento_estendida
                FROM garantias_base
            )

            SELECT
                pin,
                maquina_servicada,
                organization_id,
                data_vencimento_garantia_basica,
                dias_para_vencimento_basica,

                CASE 
                    WHEN dias_para_vencimento_basica > 30 THEN 'VIGENTE'
                    WHEN dias_para_vencimento_basica BETWEEN 0 AND 30 THEN 'A VENCER'
                    WHEN dias_para_vencimento_basica < 0 THEN 'VENCIDO'
                END AS status_garantia_basica,

                tipo_garantia_estendida,
                data_vencimento_garantia_estendida,
                dias_para_vencimento_estendida,

                CASE 
                    WHEN dias_para_vencimento_estendida > 30 THEN 'VIGENTE'
                    WHEN dias_para_vencimento_estendida BETWEEN 0 AND 30 THEN 'A VENCER'
                    WHEN dias_para_vencimento_estendida < 0 THEN 'VENCIDO'
                    ELSE 'SEM GARANTIA ESTENDIDA'
                END AS status_garantia_estendida

            FROM calculo

            ORDER BY 
                data_vencimento_garantia_basica DESC;
        """

        return self.db.executar(sql, (id_client,))
    
    ##########################################################################################
    # CONSULTAS POR CHASSI -
    ##########################################################################################

    ######################################
    # CONSULTA 1 : Nome do Cliente
    ######################################

    def consultar_nome_cliente_by_pin(self, pin: str):

        """Retorna o nome do cliente padronizado.

        A consulta remove caracteres especiais e converte o nome para caixa alta.

        Parameters
        ----------
        pin : str
            chassi da máquina

        Returns
        -------
        Any
            Resultado da execução retornado por `self.db.executar`.
        """
        sql = """
       
        select 
            regexp_replace(
            upper(unaccent(oo.name)),
            '[^A-Z ]',
            '',
            'g'
        ) AS nome_cliente
        from layer_bronze.opc_equipment oe
        left join layer_bronze.opc_organizations oo
            on oe.organization_id  = oo.id
        where oe.serial_number = %s
        and oe.org_role_in_possession = 'true'

        """
        return self.db.executar(sql, (pin,))   

    ######################################
    # CONSULTA 2 : Geolocalização
    ######################################

    def consultar_geolocalizacao_by_pin(self, pin: str):

        """Retorna a geolocalização do equipamento do cliente.

        Busca um registro por chassi com estado, cidade e coordenadas.

        Parameters
        ----------
        pin : str
            chassi da máquina
        """
        sql = """

        SELECT DISTINCT ON (oe.serial_number)
            oe.serial_number AS chassi,
            oe.model_name AS modelo,
            meso.estado AS estado,
            meso.mesorregiao AS cidade,
            COALESCE(meso.latitude::text, 'SEM LATITUDE') AS latitude,
            COALESCE(meso.longitude::text, 'SEM LONGITUDE') AS longitude
        FROM layer_bronze.opc_equipment AS oe
        LEFT JOIN public.localizacao_maquinas AS meso
            ON meso.principal_id = oe.principal_id
        WHERE oe.org_role_in_possession = 'true'
          AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
          AND oe.serial_number = %s

        """
        return self.db.executar(sql, (pin,))
    
    ######################################
    # CONSULTA 3 : Horímetro
    ######################################

    def consultar_horimetros_by_pin(self, pin: str):

        """Retorna horímetro, status do horímetro e aptidão para revisão.

        A lógica considera a última comunicação do equipamento e a distância,
        em horas, até a próxima verificação de 500 horas.

        Parameters
        ----------
        pin : str
            chassi da máquina
        """
        
        sql = """
        
        WITH base AS (
            SELECT DISTINCT ON (oe.serial_number)
                oe.serial_number AS chassi,
                oe.model_name AS modelo,
                ROUND(oeh.reading_value::numeric, 1) AS horimetro,
                ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo') AS data_comunicacao_raw
            FROM layer_bronze.opc_equipment AS oe
            LEFT JOIN layer_bronze.opc_engine_hours AS oeh
                ON oeh.principal_id = oe.principal_id
            WHERE oe.org_role_in_possession = 'true'
              AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
              AND oe.serial_number = %s
            ORDER BY
                oe.serial_number,
                oeh.report_time DESC NULLS LAST,
                oeh.reading_value DESC NULLS LAST
        ),
        calc AS (
            SELECT
                chassi,
                modelo,
                horimetro,
                data_comunicacao_raw,
                (CEIL(horimetro / 500.0) * 500) AS proxima_verificacao,
                (CEIL(horimetro / 500.0) * 500) - horimetro AS horas_para_verificacao,
                CASE
                    WHEN data_comunicacao_raw IS NOT NULL
                     AND data_comunicacao_raw >= (now() AT TIME ZONE 'America/Sao_Paulo') - INTERVAL '30 days'
                    THEN 'ATUALIZADO'
                    ELSE 'DESATUALIZADO'
                END AS status_horimetro
            FROM base
        )
        SELECT
            chassi,
            modelo,
            horimetro,
            proxima_verificacao,
            horas_para_verificacao,
            status_horimetro,
            CASE
                WHEN horimetro IS NULL THEN 'SEM DADOS'
                WHEN status_horimetro <> 'ATUALIZADO' THEN 'DESCONHECIDO'
                WHEN horas_para_verificacao < 50 THEN 'PARA REVISÃO'
                WHEN horas_para_verificacao BETWEEN 50 AND 100 THEN 'PARA VERIFICAR'
                WHEN horas_para_verificacao > 100 THEN 'EM AGUARDO'
                ELSE NULL
            END AS aptidao_revisao
        FROM calc
        ORDER BY horimetro DESC NULLS LAST
        """
        return self.db.executar(sql, (pin,))

    ######################################
    # CONSULTA 4 : Comunicação
    ######################################

    def consultar_status_comunicacao_by_pin(self, pin: int):

        """Retorna o status de comunicação dos equipamentos.

        Classifica cada equipamento como ONLINE, OFFLINE ou SEM DADOS com base
        na última data de comunicação.

        Parameters
        ----------
        pin : str
            chassi da máquina
        """
       
        sql = """
        
        SELECT DISTINCT ON (oe.serial_number)
            oe.serial_number AS chassi,
            oe.model_name AS modelo,
            to_char(
                ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo'),
                'DD-MM-YYYY'
            ) AS data_comunicacao,
            CASE
                WHEN oeh.report_time IS NULL THEN 'SEM DADOS'
                WHEN ((oeh.report_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo')
                     >= (now() AT TIME ZONE 'America/Sao_Paulo') - INTERVAL '30 days'
                    THEN 'ONLINE'
                ELSE 'OFFLINE'
            END AS status_comunicacao
        FROM layer_bronze.opc_equipment AS oe
        LEFT JOIN layer_bronze.opc_engine_hours AS oeh
            ON oeh.principal_id = oe.principal_id
        WHERE oe.org_role_in_possession = 'true'
          AND oe.isg_type_name IN ('Backhoe', 'Excavator', 'Dozer', 'Loader', 'Motor Grader')
          AND oe.serial_number = %s
        ORDER BY oe.serial_number, oeh.report_time DESC NULLS LAST

        """
        return self.db.executar(sql, (pin,))
    
    #########################################
    # CONSULTA 5 : Utilização Diária da Frota
    #########################################

    def consultar_utilizacao_frota_diaria_by_pin(self, pin: str, data_inicial: str, data_final: str):
        
        """Retorna a utilização diária da frota no período informado.

        A consulta calcula horas ociosas, horas trabalhadas, combustível
        consumido, taxa de consumo e classificação versus referência por modelo.

        Parameters
        ----------
        pin : str
            chassi da máquina
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.

        """
        sql = """
        
        WITH params AS (
            SELECT %s::date AS data_inicio,
                   %s::date AS data_fim
        ),
        equip AS (
            SELECT
                oe.serial_number AS pin,
                oe.type_name,
                oe.isg_type_name
            FROM layer_bronze.opc_equipment oe
            WHERE oe.org_role_in_possession = 'true'
              AND oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
              AND oe.serial_number = %s
        ),
        iso_pre AS (
            SELECT DISTINCT ON (opc.pin)
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time < p.data_inicio
            ORDER BY opc.pin, opc.snapshot_time DESC
        ),
        iso_periodo AS (
            SELECT
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time >= p.data_inicio
              AND opc.snapshot_time < (p.data_fim + INTERVAL '1 day')
        ),
        iso_base AS (
            SELECT * FROM iso_pre
            UNION ALL
            SELECT * FROM iso_periodo
        ),
        calc AS (
            SELECT
                ib.pin,
                REPLACE(ib.model, ' ', '') AS model_clean,
                ib.snapshot_time,
                ib.snapshot_time::date AS data_ref,
                ib.operating_hours,
                ib.idle_hours,
                ib.fuel_consumed,
                LAG(ib.operating_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS op_prev,
                LAG(ib.idle_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS idle_prev,
                LAG(ib.fuel_consumed) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS fuel_prev
            FROM iso_base ib
        ),
        deltas AS (
            SELECT
                c.pin,
                c.model_clean,
                c.data_ref,
                (c.idle_hours - c.idle_prev) AS d_idle,
                ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) AS d_work,
                (c.fuel_consumed - c.fuel_prev) AS d_fuel
            FROM calc c
            JOIN params p ON TRUE
            WHERE c.op_prev IS NOT NULL
              AND c.idle_prev IS NOT NULL
              AND c.fuel_prev IS NOT NULL
              AND c.data_ref BETWEEN p.data_inicio AND p.data_fim
              AND (c.idle_hours - c.idle_prev) >= 0
              AND ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) >= 0
              AND (c.fuel_consumed - c.fuel_prev) >= 0
        ),
        consumo_dia AS (
            SELECT
                pin,
                model_clean,
                data_ref,
                ROUND(SUM(d_idle)::numeric, 2) AS idle_hours,
                ROUND(SUM(d_work)::numeric, 2) AS work_hours,
                ROUND(SUM(d_fuel)::numeric, 2) AS fuel_consumed,
                ROUND(
                    (SUM(d_fuel) / NULLIF(SUM(d_idle) + SUM(d_work), 0))::numeric,
                    2
                ) AS fuel_rate
            FROM deltas
            GROUP BY pin, model_clean, data_ref
        ),
        ref_consumo(model_clean, fuel_rate_reference) AS (
            VALUES
                ('130P', 12::numeric), ('130G', 12::numeric), ('200G', 12::numeric),
                ('210P', 16::numeric), ('210G', 16::numeric), ('250G', 17::numeric),
                ('310P', 5.8::numeric), ('350G', 26::numeric), ('444G', 8::numeric),
                ('524P', 9.5::numeric), ('524K', 9.5::numeric), ('524K-II', 9.5::numeric),
                ('544G', 11::numeric), ('544P', 11::numeric), ('544K', 11::numeric), ('544K-II', 11::numeric),
                ('620P', 15::numeric), ('620G', 15::numeric), ('622G', 15::numeric),
                ('624P', 14::numeric), ('624K', 14::numeric), ('624K-II', 14::numeric),
                ('670P', 16::numeric), ('644P', 17::numeric), ('644K', 17::numeric),
                ('670G', 16::numeric), ('672G', 16::numeric), ('700J-II', 14::numeric),
                ('724P', 17::numeric), ('724K', 17::numeric), ('744P', 25::numeric), ('744K-II', 25::numeric),
                ('750J-II', 16::numeric), ('770P', 17::numeric), ('850J-II', 33::numeric), ('310L', 5.8::numeric),
                ('350P', 26::numeric)
        )
        SELECT
            e.pin,
            cd.model_clean,
            e.type_name,
            e.isg_type_name,
            TO_CHAR(cd.data_ref, 'DD-MM-YYYY') AS data_inicial,
            TO_CHAR(cd.data_ref, 'DD-MM-YYYY') AS data_final,
            COALESCE(cd.idle_hours::text, 'SEM DADOS') AS idle_hours,
            COALESCE(cd.work_hours::text, 'SEM DADOS') AS work_hours,
            COALESCE(cd.fuel_consumed::text, 'SEM DADOS') AS fuel_consumed,
            cd.fuel_rate,
            rc.fuel_rate_reference,
            ROUND((cd.fuel_rate - rc.fuel_rate_reference)::numeric, 2) AS fuel_rate_difference,
            CASE
                WHEN cd.fuel_rate IS NULL OR rc.fuel_rate_reference IS NULL THEN NULL
                WHEN (cd.fuel_rate - rc.fuel_rate_reference) > 0.2 THEN 'HIGH_CONSUMPTION'
                WHEN (cd.fuel_rate - rc.fuel_rate_reference) BETWEEN -2 AND 0.2 THEN 'NORMAL_CONSUMPTION'
                WHEN (cd.fuel_rate - rc.fuel_rate_reference) < -2 THEN 'LOW_CONSUMPTION'
                ELSE NULL
            END AS fuel_use
        FROM equip e
        LEFT JOIN consumo_dia cd
            ON cd.pin = e.pin
        LEFT JOIN ref_consumo rc
            ON rc.model_clean = cd.model_clean
        ORDER BY e.pin, cd.data_ref NULLS LAST

        """
        return self.db.executar(sql, (data_inicial, data_final, pin))
    
    #########################################
    # CONSULTA 6 : Utilização Acumulada da Frota
    #########################################

    def consultar_utilizacao_frota_acumulada_by_pin(self, pin: str, data_inicial: str, data_final: str):
       
        """Retorna a utilização acumulada da frota no período informado.

        A consulta consolida o período por equipamento, mantendo a mesma lógica
        de cálculo e comparação com referência de consumo.

        Parameters
        ----------
        pin : str
            chassi da máquina
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.
        """
        sql = """
        
        WITH params AS (
            SELECT %s::date AS data_inicio,
                   %s::date AS data_fim
        ),
        equip AS (
            SELECT
                oe.serial_number AS pin,
                oe.type_name,
                oe.isg_type_name
            FROM layer_bronze.opc_equipment oe
            WHERE oe.org_role_in_possession = 'true'
              AND oe.isg_type_name IN ('Loader', 'Excavator', 'Dozer', 'Motor Grader', 'Backhoe')
              AND oe.serial_number = %s
        ),
        iso_pre AS (
            SELECT DISTINCT ON (opc.pin)
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time < p.data_inicio
            ORDER BY opc.pin, opc.snapshot_time DESC
        ),
        iso_periodo AS (
            SELECT
                opc.pin,
                opc.model,
                opc.snapshot_time,
                opc.operating_hours,
                opc.idle_hours,
                opc.fuel_consumed
            FROM layer_bronze.opc_iso opc
            JOIN equip e ON e.pin = opc.pin
            JOIN params p ON TRUE
            WHERE opc.snapshot_time >= p.data_inicio
              AND opc.snapshot_time < (p.data_fim + INTERVAL '1 day')
        ),
        iso_base AS (
            SELECT * FROM iso_pre
            UNION ALL
            SELECT * FROM iso_periodo
        ),
        calc AS (
            SELECT
                ib.pin,
                REPLACE(ib.model, ' ', '') AS model_clean,
                ib.snapshot_time,
                ib.snapshot_time::date AS data_ref,
                ib.operating_hours,
                ib.idle_hours,
                ib.fuel_consumed,
                LAG(ib.operating_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS op_prev,
                LAG(ib.idle_hours) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS idle_prev,
                LAG(ib.fuel_consumed) OVER (PARTITION BY ib.pin ORDER BY ib.snapshot_time) AS fuel_prev
            FROM iso_base ib
        ),
        deltas AS (
            SELECT
                c.pin,
                c.model_clean,
                c.data_ref,
                (c.idle_hours - c.idle_prev) AS d_idle,
                ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) AS d_work,
                (c.fuel_consumed - c.fuel_prev) AS d_fuel
            FROM calc c
            JOIN params p ON TRUE
            WHERE c.op_prev IS NOT NULL
              AND c.idle_prev IS NOT NULL
              AND c.fuel_prev IS NOT NULL
              AND c.data_ref BETWEEN p.data_inicio AND p.data_fim
              AND (c.idle_hours - c.idle_prev) >= 0
              AND ((c.operating_hours - c.op_prev) - (c.idle_hours - c.idle_prev)) >= 0
              AND (c.fuel_consumed - c.fuel_prev) >= 0
        ),
        consumo_periodo AS (
            SELECT
                pin,
                model_clean,
                MIN(data_ref) AS data_inicial,
                MAX(data_ref) AS data_final,
                ROUND(SUM(d_idle)::numeric, 2) AS idle_hours,
                ROUND(SUM(d_work)::numeric, 2) AS work_hours,
                ROUND(SUM(d_fuel)::numeric, 2) AS fuel_consumed,
                ROUND(
                    (SUM(d_fuel) / NULLIF(SUM(d_idle) + SUM(d_work), 0))::numeric,
                    2
                ) AS fuel_rate
            FROM deltas
            GROUP BY pin, model_clean
        ),
        ref_consumo(model_clean, fuel_rate_reference) AS (
            VALUES
                ('130P', 12::numeric), ('130G', 12::numeric), ('200G', 12::numeric),
                ('210P', 16::numeric), ('210G', 16::numeric), ('250G', 17::numeric),
                ('310P', 5.8::numeric), ('350G', 26::numeric), ('444G', 8::numeric),
                ('524P', 9.5::numeric), ('524K', 9.5::numeric), ('524K-II', 9.5::numeric),
                ('544G', 11::numeric), ('544P', 11::numeric), ('544K', 11::numeric), ('544K-II', 11::numeric),
                ('620P', 15::numeric), ('620G', 15::numeric), ('622G', 15::numeric),
                ('624P', 14::numeric), ('624K', 14::numeric), ('624K-II', 14::numeric),
                ('670P', 16::numeric), ('644P', 17::numeric), ('644K', 17::numeric),
                ('670G', 16::numeric), ('672G', 16::numeric), ('700J-II', 14::numeric),
                ('724P', 17::numeric), ('724K', 17::numeric), ('744P', 25::numeric), ('744K-II', 25::numeric),
                ('750J-II', 16::numeric), ('770P', 17::numeric), ('850J-II', 33::numeric), ('350P', 26::numeric)
        )
        SELECT
            e.pin,
            cp.model_clean,
            e.type_name,
            e.isg_type_name,
            TO_CHAR(cp.data_inicial, 'DD-MM-YYYY') AS data_inicial,
            TO_CHAR(cp.data_final, 'DD-MM-YYYY') AS data_final,
            COALESCE(cp.idle_hours::text, 'SEM DADOS') AS idle_hours,
            COALESCE(cp.work_hours::text, 'SEM DADOS') AS work_hours,
            COALESCE(cp.fuel_consumed::text, 'SEM DADOS') AS fuel_consumed,
            cp.fuel_rate,
            rc.fuel_rate_reference,
            ROUND((cp.fuel_rate - rc.fuel_rate_reference)::numeric, 2) AS fuel_rate_difference,
            CASE
                WHEN cp.fuel_rate IS NULL OR rc.fuel_rate_reference IS NULL THEN NULL
                WHEN (cp.fuel_rate - rc.fuel_rate_reference) > 0.2 THEN 'HIGH_CONSUMPTION'
                WHEN (cp.fuel_rate - rc.fuel_rate_reference) BETWEEN -2 AND 0.2 THEN 'NORMAL_CONSUMPTION'
                WHEN (cp.fuel_rate - rc.fuel_rate_reference) < -2 THEN 'LOW_CONSUMPTION'
                ELSE NULL
            END AS fuel_use
        FROM equip e
        LEFT JOIN consumo_periodo cp
            ON cp.pin = e.pin
        LEFT JOIN ref_consumo rc
            ON rc.model_clean = cp.model_clean
        ORDER BY e.pin

        """
        return self.db.executar(sql, (data_inicial, data_final, pin))
    
    #########################################
    # CONSULTA 7 : Alertas
    #########################################

    def consultar_alertas_by_pin(self, pin: int, data_inicial: str, data_final: str):
        
        """Retorna os alertas de máquinas do cliente no período informado.

        Parameters
        ----------
        pin : str
            chassi da máquina
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.
        """
        sql = """
        
        WITH alertas AS (
            SELECT
                al.serial_number,
                al.type_name,
                al.model_name,
                al.organization_id,
                to_char(
                    (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
                    'DD-MM-YYYY'
                ) AS alert_data,
                oma.color,
                oma.severity,
                oma.three_letter_acronym,
                oma.suspect_parameter_name,
                oma.failure_mode_indicator,
                UPPER(unaccent(oma.description)) AS description
            FROM layer_bronze.opc_machine_alerts AS oma
            INNER JOIN layer_bronze.opc_equipment AS al
                ON al.principal_id = oma.principal_id
            WHERE al.make_name = 'JOHN DEERE'
        )
        SELECT
            serial_number,
            type_name,
            model_name,
            alert_data,
            color,
            severity,
            three_letter_acronym,
            suspect_parameter_name,
            failure_mode_indicator,
            description
        FROM alertas
        WHERE to_date(alert_data, 'DD-MM-YYYY') BETWEEN %s::date AND %s::date
          AND serial_number = %s
        ORDER BY to_date(alert_data, 'DD-MM-YYYY') DESC

        """
        return self.db.executar(sql, (data_inicial, data_final, pin))
    
    #########################################
    # CONSULTA 8 : Análises Químicas
    #########################################

    def consultar_analises_quimicas_by_pin(self, pin: str, data_inicial: str, data_final: str):
        """   
        Retorna as análises químicas vinculadas ao chassi informado.

        Parameters
        ----------
        pin : str
            Chassi da máquina.
        data_inicial : str
            Data inicial no formato YYYY-MM-DD.
        data_final : str
            Data final no formato YYYY-MM-DD.
        """

        sql = """
            SELECT DISTINCT ON (asraa.numero_amostra)
                asraa.numero_amostra,
                oe.serial_number AS chassi,
                arass.status,
                asraa.avaliacao,
                asraa.acoes_inspecao,
                TO_CHAR(
                    asraa.data_finalizacao AT TIME ZONE 'America/Sao_Paulo',
                    'DD-MM-YYYY'
                ) AS data_finalizacao_amostra,

                oe.model_name,
                arass.nome_compartimento
            FROM layer_bronze.als_s360_resultado_amostra AS asraa
            INNER JOIN layer_bronze.als_resultado_amostra_status_s360 AS arass
                ON arass.numero_amostra = asraa.numero_amostra
            LEFT JOIN layer_bronze.opc_equipment AS oe
                ON oe.serial_number = arass.chassi_serie
            WHERE oe.serial_number = %s
                AND asraa.data_finalizacao >= %s::date
                AND asraa.data_finalizacao < %s::date + INTERVAL '1 day'
            ORDER BY
                asraa.numero_amostra,
                asraa.data_finalizacao DESC;
        """

        return self.db.executar(sql, (pin, data_inicial, data_final))

    #########################################
    # CONSULTA 9 : Garantia
    #########################################

    def consultar_garantia_by_pin(self, pin: str):
            """Retorna o status de garantia das máquinas do cliente.

            Parameters
            ----------
            id_client : int
                Principal ID da Conta de Usuário.        
            """

            sql = """
                WITH garantias_base AS (
                    SELECT DISTINCT ON (pops.serial_number)
                        pops.serial_number AS pin, 
                        pops.machine_serviced AS maquina_servicada,

                        TO_DATE(pops.basic_warranty_expiration, 'DD-Mon-YY') 
                            AS data_vencimento_garantia_basica,

                        pops.extended_warranty_type AS tipo_garantia_estendida,

                        TO_DATE(pops.extended_warranty_expiration, 'DD-Mon-YY') 
                            AS data_vencimento_garantia_estendida,

                        oe.organization_id

                    FROM layer_bronze.pops_base AS pops

                    INNER JOIN layer_bronze.opc_equipment AS oe
                        ON oe.serial_number = pops.serial_number

                    WHERE 
                        pops.serial_number IS NOT NULL
                        AND pops.basic_warranty_expiration IS NOT NULL
                        AND oe.serial_number = %s

                    ORDER BY
                        pops.serial_number,
                        TO_DATE(pops.basic_warranty_expiration, 'DD-Mon-YY') DESC,
                        TO_DATE(pops.extended_warranty_expiration, 'DD-Mon-YY') DESC NULLS LAST
                ),

                calculo AS (
                    SELECT
                        *,
                        data_vencimento_garantia_basica - CURRENT_DATE 
                            AS dias_para_vencimento_basica,

                        data_vencimento_garantia_estendida - CURRENT_DATE 
                            AS dias_para_vencimento_estendida
                    FROM garantias_base
                )

                SELECT
                    pin,
                    maquina_servicada,
                    organization_id,
                    data_vencimento_garantia_basica,
                    dias_para_vencimento_basica,

                    CASE 
                        WHEN dias_para_vencimento_basica > 30 THEN 'VIGENTE'
                        WHEN dias_para_vencimento_basica BETWEEN 0 AND 30 THEN 'A VENCER'
                        WHEN dias_para_vencimento_basica < 0 THEN 'VENCIDO'
                    END AS status_garantia_basica,

                    tipo_garantia_estendida,
                    data_vencimento_garantia_estendida,
                    dias_para_vencimento_estendida,

                    CASE 
                        WHEN dias_para_vencimento_estendida > 30 THEN 'VIGENTE'
                        WHEN dias_para_vencimento_estendida BETWEEN 0 AND 30 THEN 'A VENCER'
                        WHEN dias_para_vencimento_estendida < 0 THEN 'VENCIDO'
                        ELSE 'SEM GARANTIA ESTENDIDA'
                    END AS status_garantia_estendida

                FROM calculo

                ORDER BY 
                    data_vencimento_garantia_basica DESC;
            """

            return self.db.executar(sql, (pin,))
    