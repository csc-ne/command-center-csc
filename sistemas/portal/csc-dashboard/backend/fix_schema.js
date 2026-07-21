const p = require('./db');
const fix = `
DROP TABLE IF EXISTS import_meta CASCADE;
DROP TABLE IF EXISTS machine_list CASCADE;
DROP TABLE IF EXISTS pops CASCADE;

CREATE TABLE machine_list (
  id SERIAL PRIMARY KEY, serial TEXT, cliente TEXT, filial TEXT, estado TEXT, cidade TEXT, csa TEXT, modelo TEXT, produto TEXT, status_comunicacao TEXT, last_call TEXT, lead_qtd NUMERIC(14,2) DEFAULT 0, lead_valor NUMERIC(14,2) DEFAULT 0, pmp_status TEXT, garantia_dias TEXT, reconexao TEXT, lead_pmp TEXT, lead_preventiva TEXT, lead_garantia_basica TEXT, lead_garantia_estendida TEXT, lead_disponibilidade TEXT, lead_reconexao TEXT, lead_reforma TEXT, lead_aor TEXT, lead_lamina TEXT, lead_dentes TEXT, lead_rodante TEXT, lead_fps TEXT, lead_plano_manutencao TEXT, basic_warranty_type TEXT, basic_warranty_expiration TEXT, extended_warranty_type TEXT, extended_warranty_expiration TEXT, imported_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pops (
  id SERIAL PRIMARY KEY, serial TEXT, cliente TEXT, filial TEXT, estado TEXT, cidade TEXT, csa TEXT, modelo TEXT, produto TEXT, status_comunicacao TEXT, last_call TEXT, lead_qtd NUMERIC(14,2) DEFAULT 0, lead_valor NUMERIC(14,2) DEFAULT 0, pmp_status TEXT, garantia_dias TEXT, reconexao TEXT, lead_pmp TEXT, lead_preventiva TEXT, lead_garantia_basica TEXT, lead_garantia_estendida TEXT, lead_disponibilidade TEXT, lead_reconexao TEXT, lead_reforma TEXT, lead_aor TEXT, lead_lamina TEXT, lead_dentes TEXT, lead_rodante TEXT, lead_fps TEXT, lead_plano_manutencao TEXT, basic_warranty_type TEXT, basic_warranty_expiration TEXT, extended_warranty_type TEXT, extended_warranty_expiration TEXT, imported_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE import_meta (
  id SERIAL PRIMARY KEY, base_type TEXT NOT NULL, row_count INTEGER DEFAULT 0, filename TEXT, imported_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ml_serial ON machine_list(serial);
CREATE INDEX idx_ml_filial ON machine_list(filial);
CREATE INDEX idx_ml_estado ON machine_list(estado);
CREATE INDEX idx_ml_csa ON machine_list(csa);
CREATE INDEX idx_pops_serial ON pops(serial);
CREATE INDEX idx_pops_filial ON pops(filial);
CREATE INDEX idx_pops_estado ON pops(estado);
CREATE INDEX idx_pops_csa ON pops(csa);
`;
p.query(fix).then(function() {
  console.log("Schema corrigido com sucesso - todas as colunas agora sao TEXT");
  return p.query("SELECT column_name,data_type FROM information_schema.columns WHERE table_name='machine_list' AND data_type='character varying'");
}).then(function(r) {
  console.log("VARCHARs restantes:", r.rows.length === 0 ? "NENHUM (OK)" : r.rows);
  process.exit();
}).catch(function(e) {
  console.error("Erro:", e.message);
  process.exit(1);
});
