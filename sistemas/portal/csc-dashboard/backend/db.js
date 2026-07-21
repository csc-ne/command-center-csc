// =========== CSC Dashboard — DB connection ============
const { Pool } = require("pg");

const pool = new Pool({
  host:     process.env.CSC_DB_HOST     || "csc-db",
  port:     parseInt(process.env.CSC_DB_PORT || "5432", 10),
  database: process.env.CSC_DB_NAME     || "csc_dashboard",
  user:     process.env.CSC_DB_USER     || "csc",
  password: process.env.CSC_DB_PASSWORD || "csc_secret",
});

pool.on("error", (err) => {
  console.error("[CSC-DB] Pool error:", err.message);
});

module.exports = pool;
