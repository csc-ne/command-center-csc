// =========== CSC Dashboard v3 — XLSX row mapper ============
// Mapeamento alinhado com dashboard v3.8.5
// Suporta Machine List, POPs e POPs Angelo
// ============================================================

function norm(v) {
  return (v === undefined || v === null) ? "" : String(v).trim();
}

function upper(v) { return norm(v).toUpperCase(); }

function parseMoney(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  let s = norm(v).replace(/R\$/, "").replace(/\s/g, "");
  if (!s) return 0;
  // BR format: "1.234.567,89" (dots as thousands, comma as decimal)
  if (s.includes(",") && s.includes("."))
    s = s.replace(/\./g, "").replace(",", ".");
  // Only commas: could be BR decimal "1234,56" or US thousands "1,234,567"
  else if (s.includes(",")) {
    // If last comma has exactly 3 digits after and no other commas pattern → US thousands
    const parts = s.split(",");
    const allThousands = parts.length > 1 && parts.slice(1).every(p => p.length === 3);
    if (allThousands && parts.length > 2) {
      // "1,234,567" → US thousands separator
      s = s.replace(/,/g, "");
    } else if (allThousands && parts.length === 2 && parts[0].length <= 3) {
      // "1,234" — ambiguous, but treat as thousands (consistent with XLSX integer formatting)
      s = s.replace(/,/g, "");
    } else {
      // "1234,56" → BR decimal
      s = s.replace(",", ".");
    }
  }
  // Only dots: could be decimal "1234.56" or BR thousands "1.234.567"
  else if (s.includes(".")) {
    const parts = s.split(".");
    // Multiple dots → BR thousands separator (e.g. "1.234.567")
    if (parts.length > 2) {
      s = s.replace(/\./g, "");
    }
    // Single dot: "1.234" — if exactly 3 digits after dot, could be BR thousands
    // But default to decimal (standard JS/XLSX behavior with raw:true)
  }
  const x = Number(s);
  return isFinite(x) ? x : 0;
}

function pick(o, arr) {
  for (const k of arr) {
    if (o[k] !== undefined && o[k] !== null && norm(o[k]) !== "" && norm(o[k]).toLowerCase() !== "nan") return o[k];
  }
  return "";
}

function normalizeBranch(v) {
  let s = upper(v);
  const map = {
    "SAO LUIS": "SÃO LUÍS", "SÃO LUIS": "SÃO LUÍS",
    "MACEIO": "MACEIÓ", "JOAO PESSOA": "JOÃO PESSOA",
  };
  return map[s] || s || "SEM INFORMAÇÃO";
}

function normalizeFaixaVida(v) {
  let s = upper(v);
  if (!s || s === "SEM INFORMAÇÃO" || s === "SEM INFORMACAO" || s === "NAN" || s === "NULL" || s === "NONE") return "Sem informação";
  let m = s.match(/(\d+)/);
  if (m) {
    let n = Number(m[1]);
    if (n >= 11) return "11 ANOS OU MAIS";
    if (n === 1) return "1 ANO";
    return n + " ANOS";
  }
  return s;
}

function translateLastCalledGroup(v) {
  const s = norm(v);
  const map = {
    "Last 15 days": "Últimos 15 dias",
    "16 to 60 days": "16 a 60 dias",
    "61 to 365 days": "61 a 365 dias",
    "365+ days": "Mais de 365 dias",
    "SEM INFORMAÇÃO": "Sem informação",
    "Sem Informação": "Sem informação",
    "": "Sem informação",
  };
  return map[s] || s || "Sem informação";
}

function parseDate(v) {
  if (!v) return "";
  if (typeof v === "number") {
    const d = new Date((v - 25569) * 86400000);
    return isNaN(d) ? "" : d.toISOString().slice(0, 10);
  }
  const d = new Date(v);
  return isNaN(d) ? "" : d.toISOString().slice(0, 10);
}

// Mapeamento unificado — alinhado com standardizeImport do dashboard v3.8.5
function mapBase(o, base) {
  const isPops = base === "pops" || base === "pops_angelo";

  const serial = norm(pick(o, ["Serial Number", "pin_17", "PIN", "ntv_pin"]));
  if (!serial) return null;

  const LEAD_MAP = {
    "PMP":                    ["LEAD - PMP", "LEAD - PMP "],
    "Preventiva":             ["Lead - Preventiva"],
    "Garantia Básica":        ["LEAD-Garantia Básica"],
    "Garantia Estendida":     ["LEAD-Garantia Estendida"],
    "Reforma de Componentes": ["LEAD-Reforma de Componentes"],
    "Disponibilidade":        ["LEAD-Disponibilidade"],
    "Reconexão":              ["LEAD-Reconexão", "Reconexão"],
    "Transferência de AOR":   ["LEAD - Transferência de AOR"],
    "Lâmina":                 ["LEAD-Lâmina"],
    "Dentes":                 ["LEAD-Dentes"],
    "Rodante":                ["LEAD - Rodante"],
    "FPS":                    ["LEAD - FPS"],
    "Plano de Manutenção":    ["LEAD - Plano de Manutenção"],
  };

  const leadFlags = {};
  for (const [cat, cols] of Object.entries(LEAD_MAP)) {
    leadFlags[cat] = norm(pick(o, cols));
  }

  return {
    serial,
    cliente: norm(pick(o, isPops
      ? ["CLIENTE (BASE ENRIQUECIDA)", "Company Name", "Customer Retail", "Cliente"]
      : ["CLIENTE (BASE ENRIQUECIDA)", "Cliente", "Customer Retail", "Organization_name"])) || "Sem informação",
    filial: normalizeBranch(pick(o, isPops
      ? ["Dealer Location", "Last Serviced Location", "Last Serviced Account"]
      : ["Dealer Location", "Dealer", "Filial"])),
    estado: upper(pick(o, ["ESTADO", "State", "Customer State/Province"])) || "SEM INFORMAÇÃO",
    cidade: norm(pick(o, ["City", "Município", "Customer City", "CIDADE"])),
    csa: norm(pick(o, ["CSA ATUAL", "CSA", "RESPONSÁVEL POR FECHAR O ACORDO", "Responsável"])) || "SEM RESPONSÁVEL",
    modelo: norm(pick(o, isPops
      ? ["Model", "MODELO", "Product Line", "decal_model"]
      : ["Model Name", "Model", "Product_Line", "decal_model"])),
    produto: norm(pick(o, ["Product_Line", "Product Line", "Product Family"])),
    status_comunicacao: norm(pick(o, ["Communication Status"])),
    last_call: parseDate(pick(o, ["Last_Call_In", "Last Call In", "Última Comunicação"])),
    lead_qtd: parseMoney(pick(o, ["Total LEAD"])),
    lead_valor: parseMoney(pick(o, ["Valor Total LEAD (R$)", "Total LEAD", "SOMA Potencial de Revenda de Peças Anual", "VALOR ", "brl_total"])),
    pmp_status: norm(pick(o, ["Status de PMP", "LEAD - PMP", "LEAD - PMP "])),
    garantia_dias: norm(pick(o, ["Dias Restantes da Garantia Básica", "Dias Restantes da Garantia Estendida"])),
    reconexao: norm(pick(o, ["LEAD-Reconexão", "Reconexão"])),
    lead_pmp:                 leadFlags["PMP"],
    lead_preventiva:          leadFlags["Preventiva"],
    lead_garantia_basica:     leadFlags["Garantia Básica"],
    lead_garantia_estendida:  leadFlags["Garantia Estendida"],
    lead_disponibilidade:     leadFlags["Disponibilidade"],
    lead_reconexao:           leadFlags["Reconexão"],
    lead_reforma:             leadFlags["Reforma de Componentes"],
    lead_aor:                 leadFlags["Transferência de AOR"],
    lead_lamina:              leadFlags["Lâmina"],
    lead_dentes:              leadFlags["Dentes"],
    lead_rodante:             leadFlags["Rodante"],
    lead_fps:                 leadFlags["FPS"],
    lead_plano_manutencao:    leadFlags["Plano de Manutenção"],
    basic_warranty_type:           norm(pick(o, ["Basic Warranty Type"])),
    basic_warranty_expiration:     parseDate(pick(o, ["Basic Warranty Expiration"])),
    extended_warranty_type:        norm(pick(o, ["Extended Warranty Type"])),
    extended_warranty_expiration:  parseDate(pick(o, ["Extended Warranty Expiration"])),
    faixa_vida_estendida: normalizeFaixaVida(pick(o, ["FAIXA DE VIDA ESTENDIDA", "FAIXA DE VIDA"])),
    regional: norm(pick(o, isPops
      ? ["Regional", "REGIONAL DA EMPRESA", "REGIONAL"]
      : ["REGIONAL", "REGIONAL (All Connections)", "Regional"])) || "SEM INFORMAÇÃO",
    servicada: norm(pick(o, ["Machine Serviced"])),
    dealer_aor: norm(pick(o, ["Dealer por AOR"])) || "SEM INFORMAÇÃO",
    transferir_para: normalizeBranch(pick(o, ["TRANFERIR PARA", "Transferir para"])),
    lat: parseMoney(pick(o, ["LAT", "last_known_lat"])),
    lon: parseMoney(pick(o, ["LONG", "last_known_long"])),
    horimetro: parseMoney(pick(o, ["engn_hours", "Horímetro Atual (Machine List)", "Forecasted Machine Hours", "Work Order Hours Reported", "last_engn_hours"])),
    last_called_group: translateLastCalledGroup(pick(o, ["Last Called Group", "Last Called group"])),
    filial_localizacao: normalizeBranch(pick(o, isPops
      ? ["Filial pela Localização", "CIDADE", "Customer City", "City"]
      : ["Filial pela Localização", "Cidade - API", "City"])),
  };
}

function findHeaderRow(ws, XLSX, base) {
  const ref = ws["!ref"];
  if (!ref) return 0;
  const range = XLSX.utils.decode_range(ref);
  const maxCheck = Math.min(range.e.r, 20);
  const expected = base === "machine_list"
    ? ["PIN", "Organization_name", "Model Name", "Communication Status", "Serial Number"]
    : ["Serial Number", "Dealer Location", "Model", "Valor Total LEAD (R$)", "Dealer Account Number", "CLIENTE (BASE ENRIQUECIDA)"];
  for (let r = range.s.r; r <= maxCheck; r++) {
    const row = [];
    for (let c = range.s.c; c <= range.e.c; c++) {
      const cell = ws[XLSX.utils.encode_cell({ r, c })];
      row.push(cell ? norm(cell.v) : "");
    }
    const hits = expected.filter((h) => row.includes(h)).length;
    if (hits >= 2) return r;
  }
  return 0;
}

function chooseSheet(wb, fileName) {
  const lower = String(fileName || "").toLowerCase();
  if (lower.includes("angelo") && wb.SheetNames.includes("Export")) return "Export";
  if (lower.includes("pop") && wb.SheetNames.includes("Pops - NOVO - BASE")) return "Pops - NOVO - BASE";
  if (lower.includes("pop") && wb.SheetNames.includes("Pops - BASE")) return "Pops - BASE";
  if (wb.SheetNames.includes("Export")) return "Export";
  return wb.SheetNames[0];
}

function detectBase(fileName) {
  const lower = String(fileName || "").toLowerCase();
  if (lower.includes("angelo")) return "pops_angelo";
  if (lower.includes("pop")) return "pops";
  return "machine_list";
}

module.exports = { mapBase, findHeaderRow, chooseSheet, detectBase, norm };
