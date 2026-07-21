-- =========== COMMAND CENTER CSC 3.0 — Machine List + POPs + POPs Angelo ============
-- Schema para armazenar dados importados dos xlsx
-- Usa TEXT em todas as colunas de texto para evitar truncamento
-- v3: campos adicionais para dashboard v3.8.5
-- ==================================================================================

DROP TABLE IF EXISTS import_meta CASCADE;
DROP TABLE IF EXISTS machine_list CASCADE;
DROP TABLE IF EXISTS pops CASCADE;
DROP TABLE IF EXISTS pops_angelo CASCADE;

CREATE TABLE machine_list (
  id                          SERIAL PRIMARY KEY,
  serial                      TEXT,
  cliente                     TEXT,
  filial                      TEXT,
  estado                      TEXT,
  cidade                      TEXT,
  csa                         TEXT,
  modelo                      TEXT,
  produto                     TEXT,
  status_comunicacao          TEXT,
  last_call                   TEXT,
  lead_qtd                    NUMERIC(14,2) DEFAULT 0,
  lead_valor                  NUMERIC(14,2) DEFAULT 0,
  pmp_status                  TEXT,
  garantia_dias               TEXT,
  reconexao                   TEXT,
  lead_pmp                    TEXT,
  lead_preventiva             TEXT,
  lead_garantia_basica        TEXT,
  lead_garantia_estendida     TEXT,
  lead_disponibilidade        TEXT,
  lead_reconexao              TEXT,
  lead_reforma                TEXT,
  lead_aor                    TEXT,
  lead_lamina                 TEXT,
  lead_dentes                 TEXT,
  lead_rodante                TEXT,
  lead_fps                    TEXT,
  lead_plano_manutencao       TEXT,
  basic_warranty_type         TEXT,
  basic_warranty_expiration   TEXT,
  extended_warranty_type      TEXT,
  extended_warranty_expiration TEXT,
  faixa_vida_estendida        TEXT,
  -- v3 fields
  regional                    TEXT,
  servicada                   TEXT,
  dealer_aor                  TEXT,
  transferir_para             TEXT,
  lat                         NUMERIC(12,7) DEFAULT 0,
  lon                         NUMERIC(12,7) DEFAULT 0,
  horimetro                   NUMERIC(14,2) DEFAULT 0,
  last_called_group           TEXT,
  filial_localizacao          TEXT,
  imported_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pops (
  id                          SERIAL PRIMARY KEY,
  serial                      TEXT,
  cliente                     TEXT,
  filial                      TEXT,
  estado                      TEXT,
  cidade                      TEXT,
  csa                         TEXT,
  modelo                      TEXT,
  produto                     TEXT,
  status_comunicacao          TEXT,
  last_call                   TEXT,
  lead_qtd                    NUMERIC(14,2) DEFAULT 0,
  lead_valor                  NUMERIC(14,2) DEFAULT 0,
  pmp_status                  TEXT,
  garantia_dias               TEXT,
  reconexao                   TEXT,
  lead_pmp                    TEXT,
  lead_preventiva             TEXT,
  lead_garantia_basica        TEXT,
  lead_garantia_estendida     TEXT,
  lead_disponibilidade        TEXT,
  lead_reconexao              TEXT,
  lead_reforma                TEXT,
  lead_aor                    TEXT,
  lead_lamina                 TEXT,
  lead_dentes                 TEXT,
  lead_rodante                TEXT,
  lead_fps                    TEXT,
  lead_plano_manutencao       TEXT,
  basic_warranty_type         TEXT,
  basic_warranty_expiration   TEXT,
  extended_warranty_type      TEXT,
  extended_warranty_expiration TEXT,
  faixa_vida_estendida        TEXT,
  -- v3 fields
  regional                    TEXT,
  servicada                   TEXT,
  dealer_aor                  TEXT,
  transferir_para             TEXT,
  lat                         NUMERIC(12,7) DEFAULT 0,
  lon                         NUMERIC(12,7) DEFAULT 0,
  horimetro                   NUMERIC(14,2) DEFAULT 0,
  last_called_group           TEXT,
  filial_localizacao          TEXT,
  imported_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pops_angelo (
  id                          SERIAL PRIMARY KEY,
  serial                      TEXT,
  cliente                     TEXT,
  filial                      TEXT,
  estado                      TEXT,
  cidade                      TEXT,
  csa                         TEXT,
  modelo                      TEXT,
  produto                     TEXT,
  status_comunicacao          TEXT,
  last_call                   TEXT,
  lead_qtd                    NUMERIC(14,2) DEFAULT 0,
  lead_valor                  NUMERIC(14,2) DEFAULT 0,
  pmp_status                  TEXT,
  garantia_dias               TEXT,
  reconexao                   TEXT,
  lead_pmp                    TEXT,
  lead_preventiva             TEXT,
  lead_garantia_basica        TEXT,
  lead_garantia_estendida     TEXT,
  lead_disponibilidade        TEXT,
  lead_reconexao              TEXT,
  lead_reforma                TEXT,
  lead_aor                    TEXT,
  lead_lamina                 TEXT,
  lead_dentes                 TEXT,
  lead_rodante                TEXT,
  lead_fps                    TEXT,
  lead_plano_manutencao       TEXT,
  basic_warranty_type         TEXT,
  basic_warranty_expiration   TEXT,
  extended_warranty_type      TEXT,
  extended_warranty_expiration TEXT,
  faixa_vida_estendida        TEXT,
  -- v3 fields
  regional                    TEXT,
  servicada                   TEXT,
  dealer_aor                  TEXT,
  transferir_para             TEXT,
  lat                         NUMERIC(12,7) DEFAULT 0,
  lon                         NUMERIC(12,7) DEFAULT 0,
  horimetro                   NUMERIC(14,2) DEFAULT 0,
  last_called_group           TEXT,
  filial_localizacao          TEXT,
  imported_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ml_serial     ON machine_list(serial);
CREATE INDEX idx_ml_filial     ON machine_list(filial);
CREATE INDEX idx_ml_estado     ON machine_list(estado);
CREATE INDEX idx_ml_csa        ON machine_list(csa);
CREATE INDEX idx_ml_regional   ON machine_list(regional);

CREATE INDEX idx_pops_serial   ON pops(serial);
CREATE INDEX idx_pops_filial   ON pops(filial);
CREATE INDEX idx_pops_estado   ON pops(estado);
CREATE INDEX idx_pops_csa      ON pops(csa);
CREATE INDEX idx_pops_regional ON pops(regional);

CREATE INDEX idx_pa_serial     ON pops_angelo(serial);
CREATE INDEX idx_pa_filial     ON pops_angelo(filial);
CREATE INDEX idx_pa_estado     ON pops_angelo(estado);
CREATE INDEX idx_pa_csa        ON pops_angelo(csa);
CREATE INDEX idx_pa_regional   ON pops_angelo(regional);

CREATE TABLE import_meta (
  id          SERIAL PRIMARY KEY,
  base_type   TEXT NOT NULL,
  row_count   INTEGER NOT NULL DEFAULT 0,
  filename    TEXT,
  imported_at TIMESTAMPTZ DEFAULT NOW()
);
