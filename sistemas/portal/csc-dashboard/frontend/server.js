// =========== CSC Dashboard v3 — Frontend Server ============
// Serve o dashboard HTML com dados via API (sem JSON inline)
// Proxy /api → backend
// Template: template.html (o HTML v3.8.9 original)
// ===========================================================

const path = require("path");
const fs   = require("fs");
// .env centralizado em C:\env\.env no host Windows.
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });

const express = require("express");
const http    = require("http");

const app  = express();
const PORT = parseInt(process.env.CSC_FRONTEND_PORT || "4011", 10);
const BACKEND_URL = process.env.CSC_BACKEND_URL || "http://csc-backend:4010";
const backendParsed = new URL(BACKEND_URL);

// ─── Prepara o HTML servido (strip DATA + inject API boot) ───────────────────
let SERVED_HTML = "";

function prepareHTML() {
  const templatePath = path.join(__dirname, "template.html");
  if (!fs.existsSync(templatePath)) {
    console.error("[CSC-FRONTEND] ERRO: template.html não encontrado em", templatePath);
    console.error("[CSC-FRONTEND] Copie o dashboard_csc_v3_8_9_topo_botoes_corrigidos.html para", templatePath);
    SERVED_HTML = "<html><body><h1>template.html não encontrado</h1><p>Copie o arquivo HTML do dashboard v3.8.9 para a pasta frontend/ como template.html</p></body></html>";
    return;
  }

  let html = fs.readFileSync(templatePath, "utf8");

  // 1. Replace inline DATA script with empty array
  html = html.replace(
    /<script\s+id=["']DATA["']\s+type=["']application\/json["']>[\s\S]*?<\/script>/i,
    '<script id="DATA" type="application/json">[]</script>'
  );

  // 2. Remove hardcoded base-load-title script (dates will come from API)
  html = html.replace(
    /<script\s+id=["']base-load-title-v3-js["']>[\s\S]*?<\/script>/i,
    "<!-- base-load-title removed: dates come from API -->"
  );

  // 3. Replace the client-side import handler (dfa-top-controls-js) with API-backed version
  html = html.replace(
    /<script\s+id=["']dfa-top-controls-js["']>[\s\S]*?<\/script>/i,
    `<script id="dfa-top-controls-js">
${API_IMPORT_SCRIPT}
</script>`
  );

  // 4. Suppress the initial fillFilters/applyFilters call (data is empty at this point;
  //    the API boot script will call them after fetching data from the server)
  html = html.replace(
    /fillFilters\(\);applyFilters\(\);(window\.addEventListener)/,
    '/* fillFilters/applyFilters deferred to API boot */ $1'
  );
  // Fallback: also try with space variations
  html = html.replace(
    /fillFilters\(\)\s*;\s*applyFilters\(\)\s*;/,
    '/* deferred to API boot */'
  );

  // 5. NaN guard for line() is injected via API_BOOT_SCRIPT (runtime override — regex unreliable on minified HTML)

  // 6. Inject API boot script before </body>
  html = html.replace(
    "</body>",
    `<script id="api-boot-js">
${API_BOOT_SCRIPT}
</script>
</body>`
  );

  SERVED_HTML = html;
  console.log("[CSC-FRONTEND] Template preparado com sucesso");
}

// ─── Script injetado: boot de dados via API ──────────────────────────────────
const API_BOOT_SCRIPT = `
(function(){
  // Override line() to guard against NaN when total=0 (division by zero in SVG charts)
  if(typeof line === 'function'){
    var _origLine = line;
    window.line = function(id){
      try{
        var el = document.getElementById(id);
        if(!el) return;
        if(typeof metrics === 'function'){
          var m = metrics();
          if(!m || !m.total){
            el.innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px">Sem dados</div>';
            return;
          }
        }
        return _origLine.apply(this, arguments);
      }catch(e){
        console.warn('[CSC] line() error for', id, e);
      }
    };
  }

  const loadingEl = document.getElementById('importStatus');
  function showLoading(msg){
    if(!loadingEl)return;
    loadingEl.textContent = msg;
    loadingEl.classList.add('show');
  }
  function hideLoading(){
    if(!loadingEl)return;
    loadingEl.classList.remove('show');
  }
  function showStatus(msg, duration){
    if(!loadingEl)return;
    loadingEl.textContent = msg;
    loadingEl.classList.add('show');
    clearTimeout(window.__importStatusTimer);
    window.__importStatusTimer = setTimeout(function(){ loadingEl.classList.remove('show'); }, duration||4200);
  }

  showLoading('Carregando dados do servidor...');

  fetch('/api/data', {credentials:'include'})
    .then(function(r){ return r.json(); })
    .then(function(resp){
      if(!resp.success){
        showStatus('Erro ao carregar dados: '+(resp.error||'desconhecido'), 8000);
        return;
      }
      // Populate RAW (global) and re-render
      if(typeof RAW !== 'undefined'){
        RAW.length = 0;
        resp.data.forEach(function(r){ RAW.push(r); });
      }
      if(typeof DATA !== 'undefined'){
        DATA.length = 0;
        resp.data.forEach(function(r){ DATA.push(r); });
      }

      // Update load timestamps from meta
      if(resp.meta && resp.meta.length > 0){
        var latest = resp.meta[0];
        var dt = new Date(latest.imported_at);
        var label = dt.toLocaleDateString('pt-BR')+' '+dt.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
        if(typeof BASE_LOAD_TEXT !== 'undefined') BASE_LOAD_TEXT = 'Última carga da base: '+label;
        var upd = document.getElementById('lastUpdate');
        if(upd) upd.textContent = label;
      }

      // Toggle upload buttons visibility based on permission
      var uploadBtns = document.querySelectorAll('.import-machine,.import-pops,.import-angelo');
      uploadBtns.forEach(function(btn){
        btn.style.display = resp.canUpload ? '' : 'none';
      });

      if(typeof fillFilters === 'function') fillFilters();
      if(typeof applyFilters === 'function') applyFilters();

      var count = resp.data.length;
      showStatus(count.toLocaleString('pt-BR')+' registros carregados do servidor.', 3000);
    })
    .catch(function(err){
      showStatus('Falha ao conectar ao servidor: '+err.message, 8000);
      console.error('[CSC] API load error:', err);
    });
})();
`;

// ─── Script injetado: import handlers via API ────────────────────────────────
const API_IMPORT_SCRIPT = `
(function(){
  function showStatus(msg, duration){
    var el=document.getElementById('importStatus');
    if(!el)return;
    el.textContent=msg;
    el.classList.add('show');
    clearTimeout(window.__importStatusTimer);
    window.__importStatusTimer=setTimeout(function(){el.classList.remove('show');}, duration||4200);
  }

  function reloadData(){
    return fetch('/api/data',{credentials:'include'})
      .then(function(r){return r.json();})
      .then(function(resp){
        if(!resp.success) throw new Error(resp.error||'Erro ao recarregar');
        if(typeof RAW!=='undefined'){
          RAW.length=0;
          resp.data.forEach(function(r){RAW.push(r);});
        }
        if(typeof DATA!=='undefined'){
          DATA.length=0;
          resp.data.forEach(function(r){DATA.push(r);});
        }
        if(resp.meta&&resp.meta.length>0){
          var latest=resp.meta[0];
          var dt=new Date(latest.imported_at);
          var label=dt.toLocaleDateString('pt-BR')+' '+dt.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
          if(typeof BASE_LOAD_TEXT!=='undefined')BASE_LOAD_TEXT='Última carga da base: '+label;
          var upd=document.getElementById('lastUpdate');
          if(upd)upd.textContent=label;
          var sub=document.getElementById('pageSubtitle');
          if(sub&&typeof titles!=='undefined'&&typeof PAGE!=='undefined'&&titles[PAGE])
            sub.textContent=BASE_LOAD_TEXT+' • '+titles[PAGE][1];
        }
        if(typeof fillFilters==='function')fillFilters();
        if(typeof applyFilters==='function')applyFilters();
        return resp;
      });
  }

  async function uploadBase(file, baseName, apiBase){
    if(!file)return;
    showStatus('Enviando '+baseName+'...', 60000);
    var formData=new FormData();
    formData.append('file', file);

    try{
      var resp=await fetch('/api/upload/'+apiBase,{
        method:'POST',
        credentials:'include',
        body:formData
      });
      var json=await resp.json();
      if(!resp.ok||!json.success){
        showStatus('Erro no upload '+baseName+': '+(json.error||'desconhecido'), 6000);
        return;
      }
      showStatus(baseName+': '+json.count.toLocaleString('pt-BR')+' registros importados. Recarregando...', 2000);
      await reloadData();
      showStatus(baseName+': '+json.count.toLocaleString('pt-BR')+' registros importados com sucesso.', 4000);
    }catch(err){
      showStatus('Falha no upload '+baseName+': '+err.message, 6000);
    }
  }

  var bases=[
    {btn:'btnImportMachine', input:'fileImportMachine', label:'Machine List', api:'machine_list'},
    {btn:'btnImportPops',    input:'fileImportPops',    label:'POPs',         api:'pops'},
    {btn:'btnImportAngelo',  input:'fileImportAngelo',  label:'POPs Angelo',  api:'pops_angelo'}
  ];

  bases.forEach(function(cfg){
    var btn=document.getElementById(cfg.btn);
    var input=document.getElementById(cfg.input);
    if(btn&&input){
      btn.onclick=function(){input.click();};
      input.onchange=async function(e){
        var file=e.target.files&&e.target.files[0];
        await uploadBase(file, cfg.label, cfg.api);
        input.value='';
      };
    }
  });

  // Botões de controle
  var btnAplicar=document.getElementById('btnAplicar');
  if(btnAplicar)btnAplicar.onclick=function(){if(typeof applyFilters==='function')applyFilters();};
  var btnLimpar=document.getElementById('btnLimpar');
  if(btnLimpar)btnLimpar.onclick=function(){
    document.querySelectorAll('.filters select,.filters input').forEach(function(el){el.value='';});
    if(window.CHART_FILTER!==undefined)CHART_FILTER=null;
    if(typeof applyFilters==='function')applyFilters();
  };
  var btnPdf=document.getElementById('btnPdf');
  if(btnPdf&&typeof window.exportPdfDfaLayout==='function'){
    btnPdf.onclick=window.exportPdfDfaLayout;
  }else if(btnPdf){
    btnPdf.onclick=function(){
      var ov=document.getElementById('pdfExportOverlay');
      if(ov)ov.classList.add('show');
      setTimeout(function(){if(ov)ov.classList.remove('show');window.print();},500);
    };
  }
  var btnExcel=document.getElementById('btnExcel');
  if(btnExcel)btnExcel.onclick=function(){
    if(window.XLSX){
      var ws=XLSX.utils.json_to_sheet(typeof rows==='function'?rows():DATA);
      var wb=XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb,ws,'Dashboard CSC');
      XLSX.writeFile(wb,'dashboard_csc_filtrado.xlsx');
    }else if(typeof exportCSV==='function'){
      exportCSV();
    }
  };
  var btnFull=document.getElementById('btnFullscreen');
  if(btnFull)btnFull.onclick=function(){
    if(!document.fullscreenElement)document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen();
    else document.exitFullscreen&&document.exitFullscreen();
  };
})();
`;

// ─── Manual proxy /api → backend (sem dependência de http-proxy-middleware) ──
app.use("/api", (req, res) => {
  const targetPath = "/api" + (req.url || "");
  const options = {
    hostname: backendParsed.hostname,
    port:     backendParsed.port || 4010,
    path:     targetPath,
    method:   req.method,
    headers:  { ...req.headers, host: backendParsed.host },
    timeout:  120000,
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on("error", (err) => {
    console.error("[CSC-PROXY] Erro:", err.message);
    if (!res.headersSent) {
      res.status(502).json({ success: false, error: "Backend indisponível: " + err.message });
    }
  });

  proxyReq.on("timeout", () => {
    proxyReq.destroy();
    if (!res.headersSent) {
      res.status(504).json({ success: false, error: "Backend timeout" });
    }
  });

  req.pipe(proxyReq, { end: true });
});

// Health check
app.get("/healthz", (_req, res) => res.json({ status: "ok", service: "csc-dashboard-frontend" }));

// Dashboard HTML (template processado)
app.get("/", (_req, res) => {
  res.type("html").send(SERVED_HTML);
});

// Arquivos estáticos (CSS, JS, imagens — caso existam)
app.use(express.static(path.join(__dirname), {
  maxAge: "1h",
  etag: true,
  index: false,  // Não servir index.html estático — usamos a rota /
}));

// SPA fallback
app.get("*", (_req, res) => {
  res.type("html").send(SERVED_HTML);
});

// ─── Start ───────────────────────────────────────────────────────────────────
prepareHTML();

// Watch template.html for changes (hot reload)
const templatePath = path.join(__dirname, "template.html");
if (fs.existsSync(templatePath)) {
  fs.watch(templatePath, { persistent: false }, () => {
    console.log("[CSC-FRONTEND] template.html alterado, recarregando...");
    setTimeout(prepareHTML, 200);
  });
}

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[CSC-FRONTEND] Rodando na porta ${PORT}`);
  console.log(`[CSC-FRONTEND] Proxy /api → ${BACKEND_URL}`);
});
