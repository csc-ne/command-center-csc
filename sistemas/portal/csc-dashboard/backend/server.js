// =========== CSC Dashboard v3 — Backend API ============
// Recebe uploads xlsx, salva no PostgreSQL, expõe API REST
// Upload restrito a usuários autorizados via JWT do portal
// Suporta 3 bases: machine_list, pops, pops_angelo
// =======================================================

const path = require("path");
// .env centralizado em C:\env\.env no host Windows.
// No container Linux, o docker-compose passa via env_file (variaveis ja no env).
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
const { mapBase, findHeaderRow, chooseSheet, detectBase, norm } = require("./mapper");

const app    = express();
const PORT   = parseInt(process.env.CSC_BACKEND_PORT || "4010", 10);
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

const PORTAL_JWT_SECRET = process.env.PORTAL_JWT_SECRET || "";

// Lista de emails autorizados vem de CSC_UPLOAD_ALLOWED_EMAILS (CSV) no .env central (C:\env\.env).
// Se vazio, uploads ficam bloqueados (fail-safe).
const UPLOAD_ALLOWED_EMAILS = (process.env.CSC_UPLOAD_ALLOWED_EMAILS || "")
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

function identifyUser(req, _res, next) {
  const token = getCookie(req, "portal_token");
  req.user = validatePortalToken(token);
  next();
}

function requireUploadAuth(req, res, next) {
  if (!PORTAL_JWT_SECRET) {
    req.user = { email: "dev@local", displayName: "Dev Mode" };
    return next();
  }
  const token = getCookie(req, "portal_token");
  const user = validatePortalToken(token);
  if (!user) {
    return res.status(401).json({ success: false, error: "Não autenticado. Faça login no Command Center." });
  }
  const email = (user.email || "").toLowerCase().trim();
  if (!UPLOAD_ALLOWED_EMAILS.includes(email)) {
    return res.status(403).json({ success: false, error: "Você não tem permissão para atualizar as bases." });
  }
  req.user = user;
  next();
}

// ─── Health check ────────────────────────────────────────────────────────────
app.get("/healthz", (_req, res) => res.json({ status: "ok", service: "csc-dashboard-backend" }));

// ─── Colunas para insert (ordem fixa) ────────────────────────────────────────
const COLS = [
  "serial", "cliente", "filial", "estado", "cidade", "csa", "modelo", "produto",
  "status_comunicacao", "last_call", "lead_qtd", "lead_valor", "pmp_status",
  "garantia_dias", "reconexao",
  "lead_pmp", "lead_preventiva", "lead_garantia_basica", "lead_garantia_estendida",
  "lead_disponibilidade", "lead_reconexao", "lead_reforma", "lead_aor",
  "lead_lamina", "lead_dentes", "lead_rodante", "lead_fps", "lead_plano_manutencao",
  "basic_warranty_type", "basic_warranty_expiration",
  "extended_warranty_type", "extended_warranty_expiration",
  "faixa_vida_estendida",
  "regional", "servicada", "dealer_aor", "transferir_para",
  "lat", "lon", "horimetro", "last_called_group", "filial_localizacao",
];

const VALID_BASES = ["machine_list", "pops", "pops_angelo"];

// ─── Converte row do banco para formato frontend ─────────────────────────────
function toFrontend(row, baseName) {
  return {
    base: baseName,
    serial:             row.serial || "",
    cliente:            row.cliente || "",
    filial:             row.filial || "",
    estado:             row.estado || "",
    cidade:             row.cidade || "",
    csa:                row.csa || "",
    modelo:             row.modelo || "",
    produto:            row.produto || "",
    statusCom:          row.status_comunicacao || "",
    lastCall:           row.last_call || "",
    leadQtd:            parseFloat(row.lead_qtd) || 0,
    valorLead:          parseFloat(row.lead_valor) || 0,
    pmpStatus:          row.pmp_status || "",
    garantiaDias:       row.garantia_dias || "",
    reconexao:          row.reconexao || "",
    leadPreventiva:     isSimFlag(row.lead_preventiva) || isSimFlag(row.lead_pmp),
    leadGarantiaBasica: isSimFlag(row.lead_garantia_basica),
    leadGarantiaEstendida: isSimFlag(row.lead_garantia_estendida),
    leadReconexao:      isSimFlag(row.lead_reconexao),
    leadTransferencia:  isSimFlag(row.lead_aor),
    leadFlags: {
      "PMP":                    row.lead_pmp || "",
      "Preventiva":             row.lead_preventiva || "",
      "Garantia Básica":        row.lead_garantia_basica || "",
      "Garantia Estendida":     row.lead_garantia_estendida || "",
      "Reforma de Componentes": row.lead_reforma || "",
      "Disponibilidade":        row.lead_disponibilidade || "",
      "Reconexão":              row.lead_reconexao || "",
      "Transferência de AOR":   row.lead_aor || "",
      "Lâmina":                 row.lead_lamina || "",
      "Dentes":                 row.lead_dentes || "",
      "Rodante":                row.lead_rodante || "",
      "FPS":                    row.lead_fps || "",
      "Plano de Manutenção":    row.lead_plano_manutencao || "",
    },
    basicWarranty:      row.basic_warranty_expiration || "",
    extendedWarranty:   row.extended_warranty_expiration || "",
    basicWarrantyType:  row.basic_warranty_type || "",
    extendedWarrantyType: row.extended_warranty_type || "",
    faixaVida:          row.faixa_vida_estendida || "",
    regional:           row.regional || "",
    servicada:          row.servicada || "",
    dealerAOR:          row.dealer_aor || "",
    transferirPara:     row.transferir_para || "",
    lat:                parseFloat(row.lat) || 0,
    lon:                parseFloat(row.lon) || 0,
    horimetro:          parseFloat(row.horimetro) || 0,
    lastCalledGroup:    row.last_called_group || "",
    filialLocalizacao:  row.filial_localizacao || "",
  };
}

function isSimFlag(v) {
  if (!v) return false;
  return ["SIM", "YES", "TRUE", "1", "X"].includes(String(v).trim().toUpperCase());
}

// ─── GET /api/data — retorna todas as bases ──────────────────────────────────
app.get("/api/data", identifyUser, async (req, res) => {
  try {
    const [mlRes, popsRes, paRes, metaRes] = await Promise.all([
      pool.query("SELECT * FROM machine_list ORDER BY id"),
      pool.query("SELECT * FROM pops ORDER BY id"),
      pool.query("SELECT * FROM pops_angelo ORDER BY id").catch(() => ({ rows: [] })),
      pool.query("SELECT * FROM import_meta ORDER BY imported_at DESC LIMIT 10"),
    ]);

    let canUpload = false;
    if (!PORTAL_JWT_SECRET) {
      canUpload = true;
    } else {
      const userEmail = (req.user && req.user.email || "").toLowerCase().trim();
      canUpload = UPLOAD_ALLOWED_EMAILS.includes(userEmail);
    }

    res.json({
      success: true,
      data: [
        ...mlRes.rows.map((r) => toFrontend(r, "Machine List")),
        ...popsRes.rows.map((r) => toFrontend(r, "POPs")),
        ...paRes.rows.map((r) => toFrontend(r, "POPs Angelo")),
      ],
      meta: metaRes.rows,
      canUpload,
    });
  } catch (err) {
    console.error("[CSC-API] GET /api/data error:", err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── POST /api/upload — recebe xlsx, detecta base, truncate+insert ───────────
// Aceita POST /api/upload (auto-detecta) ou POST /api/upload/:base (explícito)
app.post("/api/upload/:base?", requireUploadAuth, upload.single("file"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ success: false, error: "Nenhum arquivo enviado." });
  }

  const fileName = req.file.originalname || "upload.xlsx";
  let baseParam = req.params.base || detectBase(fileName);

  if (!VALID_BASES.includes(baseParam)) {
    return res.status(400).json({ success: false, error: `Base inválida '${baseParam}'. Use: ${VALID_BASES.join(", ")}` });
  }

  const client = await pool.connect();
  try {
    const wb = XLSX.read(req.file.buffer, { type: "buffer", cellDates: true });
    const sheetName = chooseSheet(wb, fileName);

    const ws = wb.Sheets[sheetName];
    if (!ws) {
      return res.status(400).json({ success: false, error: `Aba "${sheetName}" não encontrada.` });
    }

    const headerRow = findHeaderRow(ws, XLSX, baseParam);
    const rows = XLSX.utils.sheet_to_json(ws, { defval: "", range: headerRow, blankrows: false });
    const mapped = rows
      .map((o) => mapBase(o, baseParam))
      .filter(Boolean);

    if (!mapped.length) {
      return res.status(400).json({ success: false, error: "Nenhum registro válido encontrado na planilha." });
    }

    await client.query("BEGIN");
    await client.query(`TRUNCATE TABLE ${baseParam} RESTART IDENTITY`);

    const BATCH = 100;
    for (let i = 0; i < mapped.length; i += BATCH) {
      const batch = mapped.slice(i, i + BATCH);
      const values = [];
      const placeholders = [];
      let idx = 1;
      for (const row of batch) {
        const rowPlaceholders = [];
        for (const col of COLS) {
          values.push(row[col] ?? "");
          rowPlaceholders.push(`$${idx++}`);
        }
        placeholders.push(`(${rowPlaceholders.join(",")})`);
      }
      await client.query(
        `INSERT INTO ${baseParam} (${COLS.join(",")}) VALUES ${placeholders.join(",")}`,
        values
      );
    }

    await client.query(
      "INSERT INTO import_meta (base_type, row_count, filename) VALUES ($1, $2, $3)",
      [baseParam, mapped.length, fileName]
    );

    await client.query("COMMIT");

    const userEmail = req.user ? req.user.email : "desconhecido";
    console.log(`[CSC-API] Upload ${baseParam}: ${mapped.length} registros por ${userEmail}`);
    res.json({
      success: true,
      count: mapped.length,
      base: baseParam,
      sheet: sheetName,
      message: `${mapped.length} registros importados com sucesso em ${baseParam}.`,
    });
  } catch (err) {
    await client.query("ROLLBACK").catch(() => {});
    console.error(`[CSC-API] Upload ${baseParam} error:`, err);
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
  console.log(`[CSC-BACKEND] Rodando na porta ${PORT}`);
});
