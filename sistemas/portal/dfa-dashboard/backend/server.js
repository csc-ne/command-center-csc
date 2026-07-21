// =========== DFA Dashboard — Backend API ============
// Recebe uploads xlsx, salva no PostgreSQL, expõe API REST
// Upload restrito a usuários autorizados via JWT do portal
// ====================================================

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express = require("express");
const cors    = require("cors");
const crypto  = require("crypto");
const multer  = require("multer");
const XLSX    = require("xlsx");
const pool    = require("./db");
const { mapRow, findHeaderRow, norm } = require("./mapper");

const app    = express();
const PORT   = parseInt(process.env.DFA_BACKEND_PORT || "4012", 10);
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

// JWT secret compartilhado com o portal
const PORTAL_JWT_SECRET = process.env.PORTAL_JWT_SECRET || "";

// Emails autorizados a fazer upload vem de DFA_UPLOAD_ALLOWED_EMAILS (CSV) no .env central (C:\env\.env).
// Se vazio, uploads ficam bloqueados (fail-safe).
const UPLOAD_ALLOWED_EMAILS = (process.env.DFA_UPLOAD_ALLOWED_EMAILS || "")
  .split(",")
  .map(s => s.trim().toLowerCase())
  .filter(Boolean);

app.use(cors());
app.use(express.json());

// ─── JWT validation (mesmo padrão do portal) ────────────────────────────────
function getCookie(req, name) {
  const raw = req.headers.cookie || "";
  for (const part of raw.split(";")) {
    const i = part.indexOf("=");
    if (i > -1 && part.slice(0, i).trim() === name) {
      return decodeURIComponent(part.slice(i + 1).trim());
    }
  }
  return null;
}

function validatePortalToken(token) {
  if (!token || !PORTAL_JWT_SECRET) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [h, p, sig] = parts;
  try {
    const header = JSON.parse(Buffer.from(h, "base64url").toString("utf8"));
    if (!header || header.alg !== "HS256") return null;
    const expected = crypto
      .createHmac("sha256", PORTAL_JWT_SECRET)
      .update(h + "." + p)
      .digest("base64url");
    const sigBuf = Buffer.from(sig);
    const expBuf = Buffer.from(expected);
    if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) return null;
    const payload = JSON.parse(Buffer.from(p, "base64url").toString("utf8"));
    if (!payload.exp || Date.now() / 1000 > payload.exp) return null;
    return payload;
  } catch (_) {
    return null;
  }
}

// Middleware: identifica o usuário (não bloqueia leitura, só popula req.user)
function identifyUser(req, _res, next) {
  const token = getCookie(req, "portal_token");
  req.user = validatePortalToken(token);
  next();
}

// Middleware: exige que o usuário seja um dos autorizados para upload
function requireUploadAuth(req, res, next) {
  if (!PORTAL_JWT_SECRET) {
    req.user = { email: "dev@local", displayName: "Dev Mode" };
    return next();
  }
  const token = getCookie(req, "portal_token");
  const user = validatePortalToken(token);
  if (!user) {
    return res.status(401).json({
      success: false,
      error: "Não autenticado. Faça login no Command Center.",
    });
  }
  const email = (user.email || "").toLowerCase().trim();
  if (!UPLOAD_ALLOWED_EMAILS.includes(email)) {
    return res.status(403).json({
      success: false,
      error: "Você não tem permissão para atualizar as bases. Contate o administrador.",
    });
  }
  req.user = user;
  next();
}

// ─── Health check ────────────────────────────────────────────────────────────
app.get("/healthz", (_req, res) => res.json({ status: "ok", service: "dfa-dashboard-backend" }));

// ─── GET /api/data — retorna todos os registros DFA ─────────────────────────
app.get("/api/data", identifyUser, async (req, res) => {
  try {
    const [dataRes, metaRes] = await Promise.all([
      pool.query("SELECT * FROM dfa_data ORDER BY id"),
      pool.query("SELECT * FROM import_meta ORDER BY imported_at DESC LIMIT 5"),
    ]);

    // Informa ao frontend se o usuário pode fazer upload
    let canUpload = false;
    if (!PORTAL_JWT_SECRET) {
      canUpload = true;
    } else {
      const userEmail = (req.user && req.user.email || "").toLowerCase().trim();
      canUpload = UPLOAD_ALLOWED_EMAILS.includes(userEmail);
    }

    const rows = dataRes.rows.map((r) => ({
      filial:         r.filial || "",
      os:             r.os || "",
      tp_atend:       r.tp_atend || "",
      dt_abert:       r.dt_abert || "",
      cliente:        r.cliente || "",
      cidade:         r.cidade || "",
      uf:             r.uf || "",
      marca:          r.marca || "",
      modelo:         r.modelo || "",
      chassi:         r.chassi || "",
      tp:             r.tp || "",
      categoria:      r.categoria || "",
      cod_srv:        r.cod_srv || "",
      des_srv:        r.des_srv || "",
      des_item:       r.des_item || "",
      qtdade:         parseFloat(r.qtdade) || 0,
      cons_abe:       r.cons_abe || "",
      cons_fec:       r.cons_fec || "",
      valor_servico:  parseFloat(r.valor_servico) || 0,
      valor_pecas:    parseFloat(r.valor_pecas) || 0,
      valor_total:    parseFloat(r.valor_total) || 0,
      status:         r.status || "",
    }));

    res.json({
      success: true,
      data: rows,
      meta: metaRes.rows,
      canUpload,
    });
  } catch (err) {
    console.error("[DFA-API] GET /api/data error:", err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── POST /api/upload — recebe xlsx e faz truncate+insert ───────────────────
app.post("/api/upload", requireUploadAuth, upload.single("file"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ success: false, error: "Nenhum arquivo enviado." });
  }

  const client = await pool.connect();
  try {
    const wb = XLSX.read(req.file.buffer, { type: "buffer", cellDates: true });
    const sheetName = wb.SheetNames[0];
    const ws = wb.Sheets[sheetName];
    if (!ws) {
      return res.status(400).json({ success: false, error: `Aba "${sheetName}" não encontrada.` });
    }

    const headerRow = findHeaderRow(ws, XLSX);
    const rows = XLSX.utils.sheet_to_json(ws, { defval: "", range: headerRow, raw: false, blankrows: false });
    const mapped = rows
      .map((o) => mapRow(o))
      .filter((r) => r.os || r.cliente || r.filial || r.tp);

    if (!mapped.length) {
      return res.status(400).json({ success: false, error: "Nenhum registro válido encontrado na planilha." });
    }

    const cols = [
      "filial", "os", "tp_atend", "dt_abert", "cliente", "cidade", "uf",
      "marca", "modelo", "chassi", "tp", "categoria", "cod_srv", "des_srv",
      "des_item", "qtdade", "cons_abe", "cons_fec",
      "valor_servico", "valor_pecas", "valor_total", "status",
    ];

    await client.query("BEGIN");
    await client.query("TRUNCATE TABLE dfa_data RESTART IDENTITY");

    const BATCH = 100;
    for (let i = 0; i < mapped.length; i += BATCH) {
      const batch = mapped.slice(i, i + BATCH);
      const values = [];
      const placeholders = [];
      let idx = 1;
      for (const row of batch) {
        const rowPlaceholders = [];
        for (const col of cols) {
          values.push(row[col] ?? "");
          rowPlaceholders.push(`$${idx++}`);
        }
        placeholders.push(`(${rowPlaceholders.join(",")})`);
      }
      await client.query(
        `INSERT INTO dfa_data (${cols.join(",")}) VALUES ${placeholders.join(",")}`,
        values
      );
    }

    await client.query(
      "INSERT INTO import_meta (base_type, row_count, filename) VALUES ($1, $2, $3)",
      ["dfa", mapped.length, req.file.originalname || "upload.xlsx"]
    );

    await client.query("COMMIT");

    const userEmail = req.user ? req.user.email : "desconhecido";
    console.log(`[DFA-API] Upload: ${mapped.length} registros por ${userEmail}`);
    res.json({
      success: true,
      count: mapped.length,
      sheet: sheetName,
      message: `${mapped.length} registros importados com sucesso.`,
    });
  } catch (err) {
    await client.query("ROLLBACK").catch(() => {});
    console.error("[DFA-API] Upload error:", err);
    res.status(500).json({ success: false, error: err.message });
  } finally {
    client.release();
  }
});

// ─── GET /api/meta ───────────────────────────────────────────────────────────
app.get("/api/meta", async (_req, res) => {
  try {
    const result = await pool.query(
      "SELECT base_type, row_count, filename, imported_at FROM import_meta ORDER BY imported_at DESC LIMIT 10"
    );
    res.json({ success: true, meta: result.rows });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── Start ───────────────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[DFA-BACKEND] Rodando na porta ${PORT}`);
});
