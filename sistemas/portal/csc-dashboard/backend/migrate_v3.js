// =========== CSC Dashboard — Migration v3 ============
// Adiciona colunas novas para o dashboard v3.8.5
// Cria tabela pops_angelo
// Idempotente: pode rodar múltiplas vezes sem erro
// =====================================================

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });
const pool = require("./db");

const MIGRATION = `
-- Novas colunas em machine_list
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS regional TEXT;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS servicada TEXT;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS dealer_aor TEXT;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS transferir_para TEXT;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS lat NUMERIC(12,7) DEFAULT 0;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS lon NUMERIC(12,7) DEFAULT 0;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS horimetro NUMERIC(14,2) DEFAULT 0;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS last_called_group TEXT;
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS filial_localizacao TEXT;

-- Novas colunas em pops
ALTER TABLE pops ADD COLUMN IF NOT EXISTS regional TEXT;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS servicada TEXT;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS dealer_aor TEXT;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS transferir_para TEXT;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS lat NUMERIC(12,7) DEFAULT 0;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS lon NUMERIC(12,7) DEFAULT 0;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS horimetro NUMERIC(14,2) DEFAULT 0;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS last_called_group TEXT;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS filial_localizacao TEXT;

-- Tabela pops_angelo (mesma estrutura de pops)
CREATE TABLE IF NOT EXISTS pops_angelo (
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

CREATE INDEX IF NOT EXISTS idx_pops_angelo_serial ON pops_angelo(serial);
CREATE INDEX IF NOT EXISTS idx_pops_angelo_filial ON pops_angelo(filial);
CREATE INDEX IF NOT EXISTS idx_pops_angelo_estado ON pops_angelo(estado);
CREATE INDEX IF NOT EXISTS idx_pops_angelo_csa    ON pops_angelo(csa);

-- Índices nas novas colunas
CREATE INDEX IF NOT EXISTS idx_ml_regional ON machine_list(regional);
CREATE INDEX IF NOT EXISTS idx_pops_regional ON pops(regional);
CREATE INDEX IF NOT EXISTS idx_pops_angelo_regional ON pops_angelo(regional);
`;

async function run() {
  try {
    await pool.query(MIGRATION);
    console.log("[MIGRATION v3] Sucesso — colunas e tabela pops_angelo criados.");
    process.exit(0);
  } catch (err) {
    console.error("[MIGRATION v3] Erro:", err.message);
    process.exit(1);
  }
}

run();
