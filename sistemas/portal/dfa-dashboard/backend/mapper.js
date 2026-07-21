// =========== DFA Dashboard — XLSX row mapper ============
// Mapeia colunas da planilha DFA para o schema do banco

function norm(v) {
  return (v === undefined || v === null) ? "" : String(v).trim();
}

function upper(v) { return norm(v).toUpperCase(); }

function num(v) {
  if (typeof v === "number") return v;
  let s = norm(v).replace(/R\$|\s/g, "");
  if (s.includes(",") && s.includes("."))
    s = s.replace(/\./g, "").replace(",", ".");
  else if (s.includes(","))
    s = s.replace(",", ".");
  const x = Number(s);
  return isFinite(x) ? x : 0;
}

function pick(o, arr) {
  for (const k of arr) {
    if (o[k] !== undefined && norm(o[k]) !== "") return o[k];
  }
  return "";
}

function excelDate(v) {
  if (!v) return "";
  if (v instanceof Date) return v.toLocaleDateString("pt-BR");
  if (typeof v === "number") {
    const d = new Date(Math.round((v - 25569) * 86400 * 1000));
    return d.toLocaleDateString("pt-BR");
  }
  return String(v);
}

// Mapeamento das colunas do xlsx para o schema do banco
function mapRow(o) {
  const tp = norm(pick(o, ["TP", "tp"]));
  const isServ = tp.toUpperCase().includes("CSCS");
  const isPeca = tp.toUpperCase().includes("CSCP");
  const filial = norm(pick(o, ["FILIAL", "filial"])).padStart(6, "0");

  const serv = num(pick(o, ["SERVIÇO", "SERVICO", "SERVIÇO ", "servico", "serviço"]));
  const pecas = num(pick(o, ["PECAS_TT", "pecas_tt"]));
  const total = num(pick(o, ["VLR_TOTAL", "vlr_total", "TOTAL"]));

  return {
    filial,
    os:             norm(pick(o, ["NRO_OS", "nro_os", "OS"])),
    tp_atend:       norm(pick(o, ["TP_ATEND", "tp_atend"])),
    dt_abert:       excelDate(pick(o, ["DT_ABERT", "dt_abert"])),
    cliente:        norm(pick(o, ["NOME_CLIEN", "nome_clien", "CLIENTE", "cliente"])),
    cidade:         norm(pick(o, ["CIDADE", "cidade"])),
    uf:             upper(pick(o, ["UF", "uf"])),
    marca:          norm(pick(o, ["MARCA", "marca"])),
    modelo:         norm(pick(o, ["MODELO", "modelo"])),
    chassi:         norm(pick(o, ["CHASSI", "chassi"])),
    tp,
    categoria:      isServ ? "Serviço" : isPeca ? "Peças" : tp,
    cod_srv:        norm(pick(o, ["COD_SRV", "cod_srv"])),
    des_srv:        norm(pick(o, ["DES_SRV", "des_srv"])),
    des_item:       norm(pick(o, ["DES_ITEM", "des_item"])),
    qtdade:         num(pick(o, ["QTDADE", "qtdade"])),
    cons_abe:       norm(pick(o, ["CONS_ABE", "cons_abe"])).padStart(6, "0"),
    cons_fec:       norm(pick(o, ["CONS_FEC", "cons_fec", "CONSULTOR_FEC"])).padStart(6, "0"),
    // SERVIÇO = valor individual do serviço (correto para CSCS)
    // VLR_TOTAL = valor individual da linha (correto para CSCP)
    // PECAS_TT = agregado do OS inteiro — NÃO usar como valor da linha
    valor_servico:  isServ ? serv : 0,
    valor_pecas:    isPeca ? total : 0,
    valor_total:    isServ ? serv : isPeca ? total : (total || (serv + pecas)),
    status:         norm(pick(o, ["Status", "status", "STATUS"])),
  };
}

// Detecta a linha de cabeçalho na planilha
function findHeaderRow(ws, XLSX) {
  const ref = ws["!ref"];
  if (!ref) return 0;
  const range = XLSX.utils.decode_range(ref);
  const maxCheck = Math.min(range.e.r, 20);
  // Colunas esperadas na planilha DFA
  const expected = ["FILIAL", "NRO_OS", "TP", "NOME_CLIEN", "COD_SRV", "VLR_TOTAL", "CIDADE", "UF"];
  for (let r = range.s.r; r <= maxCheck; r++) {
    const row = [];
    for (let c = range.s.c; c <= range.e.c; c++) {
      const cell = ws[XLSX.utils.encode_cell({ r, c })];
      row.push(cell ? norm(cell.v) : "");
    }
    const hits = expected.filter((h) => row.includes(h)).length;
    if (hits >= 3) return r;
  }
  return 0;
}

module.exports = { mapRow, findHeaderRow, norm };
