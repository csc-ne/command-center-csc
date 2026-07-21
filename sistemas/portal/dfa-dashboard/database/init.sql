-- =========== DFA Dashboard — Dealer Financial Analysis ============
-- Schema para armazenar dados importados dos xlsx
-- ==================================================================

DROP TABLE IF EXISTS import_meta CASCADE;
DROP TABLE IF EXISTS dfa_data CASCADE;

CREATE TABLE dfa_data (
  id              SERIAL PRIMARY KEY,
  filial          TEXT,
  os              TEXT,
  tp_atend        TEXT,
  dt_abert        TEXT,
  cliente         TEXT,
  cidade          TEXT,
  uf              TEXT,
  marca           TEXT,
  modelo          TEXT,
  chassi          TEXT,
  tp              TEXT,
  categoria       TEXT,
  cod_srv         TEXT,
  des_srv         TEXT,
  des_item        TEXT,
  qtdade          NUMERIC(14,4) DEFAULT 0,
  cons_abe        TEXT,
  cons_fec        TEXT,
  valor_servico   NUMERIC(14,2) DEFAULT 0,
  valor_pecas     NUMERIC(14,2) DEFAULT 0,
  valor_total     NUMERIC(14,2) DEFAULT 0,
  status          TEXT,
  imported_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dfa_filial   ON dfa_data(filial);
CREATE INDEX idx_dfa_uf       ON dfa_data(uf);
CREATE INDEX idx_dfa_tp       ON dfa_data(tp);
CREATE INDEX idx_dfa_categoria ON dfa_data(categoria);
CREATE INDEX idx_dfa_cod_srv  ON dfa_data(cod_srv);

CREATE TABLE import_meta (
  id          SERIAL PRIMARY KEY,
  base_type   TEXT NOT NULL,
  row_count   INTEGER NOT NULL DEFAULT 0,
  filename    TEXT,
  imported_at TIMESTAMPTZ DEFAULT NOW()
);
