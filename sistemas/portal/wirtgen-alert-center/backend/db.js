'use strict';

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.PGHOST,
  port: Number(process.env.PGPORT || 5432),
  database: process.env.PGDATABASE,
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
  max: Number(process.env.PGPOOL_MAX || 10),
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
  statement_timeout: Number(process.env.PG_STATEMENT_TIMEOUT || 120000)
});

pool.on('error', (error) => console.error('[WAC-DB] Erro no pool PostgreSQL:', error));

module.exports = { pool };
