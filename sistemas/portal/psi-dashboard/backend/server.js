// =========== PSI Dashboard — Backend API ============
// Armazena arquivos xlsx no disco e serve via API REST
// Upload restrito a usuários autorizados via JWT do portal
// Processamento xlsx é feito client-side (SheetJS no browser)
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
const fs      = require("fs");

const app    = express();
const PORT   = parseInt(process.env.PSI_BACKEND_PORT || "4014", 10);
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

// JWT secret compartilhado com o portal
const PORTAL_JWT_SECRET = process.env.PORTAL_JWT_SECRET || "";

// Emails autorizados a fazer upload vem de PSI_UPLOAD_ALLOWED_EMAILS (CSV) no .env central (C:\env\.env).
// Se vazio, uploads ficam bloqueados (fail-safe).
const UPLOAD_ALLOWED_EMAILS = (process.env.PSI_UPLOAD_ALLOWED_EMAILS || "")
  .split(",")
  .map(s => s.trim().toLowerCase())
  .filter(Boolean);

// Tipos de dataset válidos
const VALID_TYPES = ["posvendas", "pecas", "servicos", "campanhas"];

// Diretório de armazenamento dos arquivos
const DATA_DIR = "/app/data";

app.use(cors());
app.use(express.json());

// Garante que o diretório de dados existe
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// ─── Helpers: leitura/escrita de meta.json ──────────────────────────────────
function readMeta() {
  const metaPath = path.join(DATA_DIR, "meta.json");
  if (!fs.existsSync(metaPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(metaPath, "utf8"));
  } catch (_) {
    return {};
  }
}

function writeMeta(meta) {
  const metaPath = path.join(DATA_DIR, "meta.json");
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2), "utf8");
}

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
app.get("/healthz", (_req, res) => res.json({ status: "ok", service: "psi-dashboard-backend" }));

// ─── GET /api/files/:type — retorna o arquivo xlsx armazenado ───────────────
app.get("/api/files/:type", identifyUser, (req, res) => {
  const type = req.params.type;
  if (!VALID_TYPES.includes(type)) {
    return res.status(400).json({ success: false, error: `Tipo inválido: ${type}. Válidos: ${VALID_TYPES.join(", ")}` });
  }

  const filePath = path.join(DATA_DIR, `${type}.xlsx`);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ success: false, error: `Arquivo ${type}.xlsx não encontrado. Faça upload primeiro.` });
  }

  const meta = readMeta();
  const fileMeta = meta[type] || {};
  const filename = fileMeta.name || `${type}.xlsx`;

  res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  fs.createReadStream(filePath).pipe(res);
});

// ─── GET /api/meta — retorna metadados dos arquivos armazenados ─────────────
app.get("/api/meta", identifyUser, (_req, res) => {
  const meta = readMeta();
  res.json({ success: true, meta });
});

// ─── POST /api/upload/:type — recebe xlsx e salva no disco ──────────────────
app.post("/api/upload/:type", requireUploadAuth, upload.single("file"), (req, res) => {
  const type = req.params.type;
  if (!VALID_TYPES.includes(type)) {
    return res.status(400).json({ success: false, error: `Tipo inválido: ${type}. Válidos: ${VALID_TYPES.join(", ")}` });
  }

  if (!req.file) {
    return res.status(400).json({ success: false, error: "Nenhum arquivo enviado." });
  }

  try {
    const filePath = path.join(DATA_DIR, `${type}.xlsx`);
    fs.writeFileSync(filePath, req.file.buffer);

    // Atualiza meta.json
    const meta = readMeta();
    meta[type] = {
      name: req.file.originalname || `${type}.xlsx`,
      size: req.file.size,
      uploaded_at: new Date().toISOString(),
      uploaded_by: req.user ? req.user.email : "desconhecido",
    };
    writeMeta(meta);

    const userEmail = req.user ? req.user.email : "desconhecido";
    console.log(`[PSI-API] Upload ${type}: ${req.file.originalname} (${(req.file.size / 1024).toFixed(1)} KB) por ${userEmail}`);

    res.json({
      success: true,
      type,
      filename: req.file.originalname,
      size: req.file.size,
      message: `Arquivo ${type}.xlsx salvo com sucesso.`,
    });
  } catch (err) {
    console.error("[PSI-API] Upload error:", err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── GET /api/status — retorna quais arquivos existem e permissão de upload ─
app.get("/api/status", identifyUser, (req, res) => {
  const meta = readMeta();

  let canUpload = false;
  if (!PORTAL_JWT_SECRET) {
    canUpload = true;
  } else {
    const userEmail = (req.user && req.user.email || "").toLowerCase().trim();
    canUpload = UPLOAD_ALLOWED_EMAILS.includes(userEmail);
  }

  const files = {};
  for (const type of VALID_TYPES) {
    const filePath = path.join(DATA_DIR, `${type}.xlsx`);
    files[type] = {
      exists: fs.existsSync(filePath),
      ...(meta[type] || {}),
    };
  }

  res.json({
    success: true,
    files,
    canUpload,
  });
});

// ─── Start ───────────────────────────────────────────────────────────────────
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[PSI-BACKEND] Rodando na porta ${PORT}`);
});
