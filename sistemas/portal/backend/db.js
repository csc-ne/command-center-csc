// =========== COMMAND CENTER CSC ============
// db.js — Pool de conexão PostgreSQL
// =============================================
//
// Conecta no banco de PRODUÇÃO csc_veneza (192.168.0.106:5432) e usa o
// schema dedicado command_center via search_path. 'public' fica no fim do
// search_path para gen_random_uuid() e objetos de catálogo seguirem visíveis.
// Assim as queries das rotas continuam usando nomes não-qualificados
// (users, sessions, ...) sem precisar de alteração.

const { Pool } = require("pg");

const DB_SCHEMA = process.env.DB_SCHEMA || "command_center";

const pool = new Pool({
  host:     process.env.DB_HOST     || "192.168.0.106",
  port:     parseInt(process.env.DB_PORT || "5432", 10),
  database: process.env.DB_NAME     || "csc_veneza",
  user:     process.env.DB_USER     || "henrique",
  password: process.env.DB_PASSWORD || "",
  max:      10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
  options: `-c search_path=${DB_SCHEMA},public`,
});

pool.on("error", (err) => {
  console.error("[DB] Erro inesperado no pool:", err.message);
});

module.exports = pool;
