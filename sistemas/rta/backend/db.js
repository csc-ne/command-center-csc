// =========== RTA - REAL TIME ALERT ============
// db.js — Pool de conexao PostgreSQL (csc_veneza)
// ================================================

const { Pool } = require("pg");

// Config PG lida do .env central (C:\env\.env). Sem fallbacks para
// credenciais — se algo obrigatorio faltar, o processo sai antes de
// tentar conectar com valores default.
function _req(name) {
  const v = process.env[name];
  if (!v) throw new Error(`[RTA] Variavel de ambiente obrigatoria ausente: ${name} (esperada em C:\\env\\.env)`);
  return v;
}

const pool = new Pool({
  host: _req("RTA_PG_HOST"),
  port: parseInt(process.env.RTA_PG_PORT || "5432", 10),
  database: _req("RTA_PG_DATABASE"),
  user: _req("RTA_PG_USER"),
  password: _req("RTA_PG_PASSWORD"),
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});

pool.on("error", (err) => {
  console.error("[RTA] Erro inesperado no pool PostgreSQL:", err.message);
});

pool.on("connect", () => {
  console.log("[RTA] Nova conexao PostgreSQL estabelecida");
});

module.exports = pool;
