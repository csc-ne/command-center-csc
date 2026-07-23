'use strict';

const ALERTAS_QUERY = `
WITH alertas AS (
    SELECT
        al.make_name,
        al.serial_number,
        oma.principal_id,
        al.type_name,
        al.model_name,
        TO_CHAR(
            (oma.alert_time AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo',
            'DD-MM-YYYY'
        ) AS alert_time,
        al.organization_id AS machine_id,
        oma.latitude AS latitude_alerta,
        oma.longitude AS longitude_alerta,
        oma.color,
        oma.severity,
        oma.three_letter_acronym,
        oma.suspect_parameter_name,
        oma.failure_mode_indicator,
        UPPER(unaccent(oma.description)) AS description
    FROM layer_bronze.opc_machine_alerts oma
    INNER JOIN layer_bronze.opc_equipment al
        ON al.principal_id = oma.principal_id
    WHERE al.make_name IN ('WIRTGEN', 'HAMM', 'CIBER')
)
SELECT
    al.make_name,
    al.serial_number,
    al.principal_id,
    al.type_name,
    al.model_name,
    al.alert_time,
    al.machine_id,

    /* Prioriza a localização oficial da máquina e usa a posição do alerta
       apenas quando a tabela de localização não possuir coordenadas. */
    COALESCE(lm.latitude, al.latitude_alerta) AS latitude,
    COALESCE(lm.longitude, al.longitude_alerta) AS longitude,

    al.color,
    al.severity,
    al.three_letter_acronym,
    al.suspect_parameter_name,
    al.failure_mode_indicator,
    al.description,
    lm.cidade,
    lm.estado,
    lm.regional
FROM alertas al
INNER JOIN public.localizacao_maquinas lm
    ON al.principal_id = lm.principal_id;
`;

module.exports = { ALERTAS_QUERY };
