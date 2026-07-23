// =========== Wirtgen Alert Center — Backend API ============
// Consulta layer_bronze do csc_veneza e retorna alertas WIRTGEN/HAMM/CIBER.
// Somente leitura.
// =============================================================

'use strict';

const path = require('path');
// .env centralizado em C:\env\.env no host Windows; dentro do container
// as env vars vem por env_file/environment do docker-compose.
const _envPath = process.platform === 'win32'
  ? 'C:\\env\\.env'
  : path.join(__dirname, '..', '.env');
require('dotenv').config({ path: _envPath });

const express = require('express');
const cors    = require('cors');
const { pool } = require('./db');
const { ALERTAS_QUERY } = require('./queries');

const app  = express();
const PORT = Number(process.env.WAC_BACKEND_PORT || 4016);

app.disable('x-powered-by');
app.use(cors({ origin: process.env.CORS_ORIGIN ? process.env.CORS_ORIGIN.split(',') : true }));
app.use(express.json({ limit: '1mb' }));

app.get('/healthz', (_req, res) => res.json({ status: 'ok', service: 'wirtgen-alert-center-backend' }));

app.get('/api/health', async (_req, res) => {
  try {
    const result = await pool.query('SELECT NOW() AS database_time');
    res.json({ ok: true, databaseTime: result.rows[0].database_time });
  } catch (error) {
    console.error('[WAC-API] health error:', error.message);
    res.status(503).json({ ok: false, error: 'Banco de dados indisponível.' });
  }
});

app.get('/api/alertas', async (_req, res) => {
  const startedAt = Date.now();
  try {
    const result = await pool.query(ALERTAS_QUERY);
    res.set('Cache-Control', 'no-store');
    res.json({
      data: result.rows,
      rowCount: result.rowCount,
      updatedAt: new Date().toISOString(),
      durationMs: Date.now() - startedAt
    });
  } catch (error) {
    console.error('[WAC-API] alertas error:', error.message);
    res.status(500).json({ error: 'Não foi possível consultar os alertas.' });
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[WAC-BACKEND] Rodando na porta ${PORT}`);
});

async function shutdown(signal) {
  console.log(`[WAC-BACKEND] Encerrando por ${signal}...`);
  await pool.end();
  process.exit(0);
}
process.on('SIGINT',  () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
