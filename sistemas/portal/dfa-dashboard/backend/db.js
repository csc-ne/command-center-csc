// =========== DFA Dashboard — DB connection ============
const { Pool } = require("pg");

const pool = new Pool({
  host:     process.env.DFA_DB_HOST     || "dfa-db",
  port:     parseInt(process.env.DFA_DB_PORT || "5432", 10),
  database: process.env.DFA_DB_NAME     || "dfa_dashboard",
  user:     process.env.DFA_DB_USER     || "dfa",
  password: process.env.DFA_DB_PASSWORD || "dfa_secret",
});

pool.on("error", (err) => {
  console.error("[DFA-DB] Pool error:", err.message);
});

module.exports = pool;
