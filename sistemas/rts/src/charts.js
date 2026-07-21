Chart.register(ChartDataLabels);

let randomColors = generateRandomColors();

let modelChart;
let isCreatingChart = false; // Flag para evitar criações simultâneas do gráfico

// ─── Regra de negócio: horário comercial ──────────────────────────────────────
// Janela operacional do RTS: segunda a sexta, 08:00 às 17:50.
// Estes valores refletem a mesma janela usada no core (business_hours.py) e
// precisam ficar aqui porque os gráficos calculam médias direto do DOM.
const BUSINESS_START_MIN = 8 * 60;        // 08:00 => 480
const BUSINESS_END_MIN   = 17 * 60 + 50;  // 17:50 => 1070

/**
 * Converte "HH:MM" em minutos totais do dia. Aceita string ou array já
 * splitada. Retorna NaN se inválido.
 */
function hhmmToMinutes(value) {
  var parts = Array.isArray(value) ? value : String(value || "").split(":");
  if (parts.length < 2) return NaN;
  var h = parseInt(parts[0], 10);
  var m = parseInt(parts[1], 10);
  if (isNaN(h) || isNaN(m)) return NaN;
  return h * 60 + m;
}

/**
 * Verifica se uma quantidade de minutos do dia está DENTRO do expediente.
 */
function isWithinBusinessHours(minutesOfDay) {
  return (
    typeof minutesOfDay === "number" &&
    !isNaN(minutesOfDay) &&
    minutesOfDay >= BUSINESS_START_MIN &&
    minutesOfDay <= BUSINESS_END_MIN
  );
}

/**
 * Dado um objeto Date, retorna true se for dia útil (segunda a sexta).
 * Usado para excluir registros de sábado/domingo do cálculo de médias.
 */
function isBusinessDay(dateObj) {
  if (!(dateObj instanceof Date) || isNaN(dateObj.getTime())) return false;
  var dow = dateObj.getDay(); // 0=Dom, 1=Seg, ..., 6=Sáb
  return dow >= 1 && dow <= 5;
}

/* Paleta corporativa — nova identidade visual */
const palette = [
  "#F0AB00",  /* novo ouro CSC */
  "#4ade80",  /* verde atendimento */
  "#60a5fa",  /* azul informativo  */
  "#f87171",  /* vermelho alerta   */
  "#fb923c",  /* laranja           */
  "#a78bfa",  /* lilás             */
  "#34d399",  /* verde claro       */
  "#38bdf8",  /* ciano             */
  "#fbbf24",  /* âmbar             */
  "#e879f9",  /* rosa              */
];

function generateRandomColors() {
  /**
   * Math.floor arredonda o número decimal para o menor valor. Ex: 3.8 vira 3.
   * Math.random() pega um número entre 0 e 1
   * 16777215 é máximo de números existentes no RGB. (256 elevado a 3)
   * o toString(16) converte para hexadecimal (ou seja, na base 16)
   */
  let colors = [];
  for (let i = 0; i < 15; i++) {
    let color = "#" + Math.floor(Math.random() * 16777215).toString(16);
    colors.push(color);
  }
  return colors;
}

function showChartModels() {
  // Evitar criações simultâneas de gráficos (condição de corrida)
  if (isCreatingChart) {
    console.log("[CHART] Criação de gráfico já em andamento, ignorando chamada duplicada");
    return;
  }

  isCreatingChart = true;

  const chartsContainer = document.querySelector(".above-container");
  if (!chartsContainer) {
    isCreatingChart = false;
    return;
  }

  // Destruir chart anterior se existir
  if (modelChart) {
    try {
      modelChart.destroy();
    } catch (e) {
      console.log("[CHART] Erro ao destruir gráfico anterior:", e.message);
    }
    modelChart = null;
  }

  // Remove elemento anterior se existir
  const existingChartDiv = chartsContainer.querySelector(".chart-models");
  if (existingChartDiv) {
    existingChartDiv.remove();
  }

  const chartModels = `<canvas id="chartByFamily"></canvas>`;
  let newChartElement = document.createElement("div");
  newChartElement.classList.add("chart-models");
  newChartElement.innerHTML = chartModels;

  chartsContainer.prepend(newChartElement); // adiciona no inicio da div

  // Usar pequeno delay para garantir que o DOM foi atualizado corretamente
  setTimeout(function () {
    try {
      const ctx = document.getElementById("chartByFamily");
      if (!ctx) {
        isCreatingChart = false;
        console.log("[CHART] Elemento canvas não encontrado após renderização");
        return;
      } // Verifica se elemento existe

      const pinEl = document.querySelectorAll(".pin");
    var pins = {};
    var pinKeys = [];
    var pinValues = [];

    // Itera sobre o array e conta quantos modelos tem, armazenando no JSON o valor da qtd
    pinEl.forEach((el) => {
      if (chartFilterJD && !isChassiJD(el.innerHTML)) return;
      if (chartFilterWTG && isChassiJD(el.innerHTML)) return;

      // pega o modelo no chassi
      var pin = isChassiJD(el.innerHTML)
        ? el.innerHTML.substring(3, 7)
        : el.innerHTML.substring(4, 8);

      if (pins.hasOwnProperty(pin)) {
        pins[pin]++;
      } else {
        pins[pin] = 1;
      }
    });

    // Adiciona as chaves e os valores numa lista para usar no gráfico
    for (let key in pins) {
      let value = pins[key];
      pinKeys.push(key);
      pinValues.push(value);
    }

    // ordena os valores do maior para o menor
    let sortedData = pinValues.slice().sort((a, b) => b - a);

    // ordena as chaves de acordo com a nova ordem dos valores
    let sortedKeys = pinKeys.slice().sort((a, b) => {
      return sortedData.indexOf(pins[a]) - sortedData.indexOf(pins[b]);
    });

    // recria os arrays com os valores e chaves ordenados
    pinValues = sortedData;
    pinKeys = sortedKeys;

      try {
        modelChart = new Chart(ctx, {
          type: "bar",
          data: {
            labels: pinKeys,
            datasets: [
              {
                label: "Alertas enviados",
                data: pinValues,
                backgroundColor: pinKeys.map((_, i) => palette[i % palette.length]),
                borderColor: pinKeys.map((_, i) => palette[i % palette.length]),
                borderWidth: 0,
                borderRadius: 6,
                borderSkipped: false,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 12, bottom: 8, left: 8, right: 8 } },
            scales: {
              x: {
                ticks: {
                  maxRotation: 35,
                  minRotation: 0,
                  color: "#b0b0b0",
                  font: { size: 12, weight: "500", family: "Inter, sans-serif" },
                },
                grid: { color: "rgba(94,106,113,0.08)", drawBorder: false },
                border: { color: "rgba(94,106,113,0.15)", display: true },
              },
              y: {
                beginAtZero: true,
                grid: { color: "rgba(94,106,113,0.08)", drawBorder: false },
                border: { color: "rgba(94,106,113,0.15)", display: true },
                ticks: {
                  color: "#b0b0b0",
                  font: { size: 12, weight: "500", family: "Inter, sans-serif" },
                  stepSize: 1,
                  padding: 8,
                },
              },
            },
            plugins: {
              title: {
                display: true,
                text: "Estatísticas de Envio de Alertas",
                align: "center",
                font: { size: 15, family: "Inter, sans-serif", weight: "700", lineHeight: 1.4 },
                padding: { top: 8, bottom: 20 },
                color: "#F0AB00",
              },
              legend: { display: false },
              datalabels: {
                anchor: "end",
                align: "top",
                color: "#f0f0f0",
                font: { weight: "700", size: 13, family: "Inter, sans-serif" },
                offset: 4,
                formatter: (val) => val,
              },
              tooltip: {
                backgroundColor: "rgba(30,30,30,0.92)",
                titleColor: "#F0AB00",
                bodyColor: "#f0f0f0",
                borderColor: "rgba(240,171,0,0.3)",
                borderWidth: 1,
                padding: 12,
                titleFont: { size: 13, weight: "bold" },
                bodyFont: { size: 12 },
                callbacks: {
                  label: (ctx) => `  ${ctx.dataset.label}: ${ctx.formattedValue}`,
                },
              },
            },
          },
        });
        console.log("[CHART] Gráfico de modelos criado com sucesso");
      } catch (e) {
        console.error("[CHART] Erro ao criar gráfico de modelos:", e.message);
      }
    } catch (e) {
      console.error("[CHART] Erro durante a criação do gráfico:", e.message);
    } finally {
      isCreatingChart = false;
    }
  }, 100); // Reduzido para 100ms para resposta mais rápida
}

// ─── Renderização de gauges (Chart.js doughnut) ──────────────────────────────
// Mantemos o registro dos charts ativos para podermos destruí-los quando o
// usuário troca filtro ou abre/fecha a tela; sem isso, o Chart.js dispara
// "Canvas is already in use" e o gauge para de atualizar.
const _activeRingCharts = {};

/**
 * Constrói (ou substitui) um gauge em formato de anel 270° dentro de um
 * <div>. O div recebe um <canvas> filho gerenciado por nós.
 *
 * @param {string} containerId   id do <div> hospedeiro (ex.: "gaugeChart")
 * @param {object} cfg           { title, value, max, thresholds, suffix }
 *
 *   thresholds = [ { upTo: 15, color: "#4ade80" }, ... ] — define a cor do
 *   arco preenchido em função do valor (verde/amarelo/laranja/vermelho).
 */
function renderRingGauge(containerId, cfg) {
  var host = document.getElementById(containerId);
  if (!host) return;

  // Destrói chart anterior, se houver. Importante para não vazar canvas.
  if (_activeRingCharts[containerId]) {
    try { _activeRingCharts[containerId].destroy(); } catch (e) { /* ignora */ }
    _activeRingCharts[containerId] = null;
  }

  // Limpa qualquer conteúdo prévio (JSC deixava SVGs aqui antes).
  host.innerHTML = "";
  var canvas = document.createElement("canvas");
  host.appendChild(canvas);

  var maxVal = cfg.max || 60;
  var rawValue = typeof cfg.value === "number" && !isNaN(cfg.value) ? cfg.value : 0;
  var clamped = Math.max(0, Math.min(rawValue, maxVal));
  var overLimit = rawValue > maxVal;

  // Determina cor do arco preenchido conforme thresholds.
  var fillColor = "#4ade80";
  if (Array.isArray(cfg.thresholds)) {
    for (var i = 0; i < cfg.thresholds.length; i++) {
      if (clamped <= cfg.thresholds[i].upTo) {
        fillColor = cfg.thresholds[i].color;
        break;
      }
      fillColor = cfg.thresholds[i].color; // mantém a última se passou de tudo
    }
  }

  // Plugin que escreve o valor + label no centro do anel.
  var centerTextPlugin = {
    id: "centerText_" + containerId,
    afterDraw: function (chart) {
      var ctx = chart.ctx;
      var area = chart.chartArea;
      var cx = (area.left + area.right) / 2;
      // O anel é semi (270°) com rotação para baixo; o "centro visual"
      // fica um pouco abaixo do meio geométrico.
      var cy = area.top + (area.bottom - area.top) * 0.7;

      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      // Valor principal
      ctx.fillStyle = "#f3f4f6";
      ctx.font = "700 34px 'Inter', sans-serif";
      var displayVal = overLimit ? maxVal + "+" : String(clamped);
      ctx.fillText(displayVal, cx, cy - 8);

      // Sufixo (ex.: "min")
      ctx.fillStyle = "#9ca3af";
      ctx.font = "500 12px 'Inter', sans-serif";
      ctx.fillText(cfg.suffix || "min", cx, cy + 18);

      ctx.restore();
    },
  };

  var chart = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      datasets: [
        {
          data: [clamped, Math.max(0, maxVal - clamped)],
          backgroundColor: [fillColor, "rgba(255,255,255,0.06)"],
          borderWidth: 0,
          borderRadius: [10, 0],
          spacing: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "78%",
      rotation: -135,         // começa no canto inferior esquerdo
      circumference: 270,     // arco de 270° (estilo speedometer Tesla)
      animation: { duration: 800, easing: "easeOutCubic" },
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false },
        datalabels: { display: false },
      },
    },
    plugins: [centerTextPlugin],
  });

  _activeRingCharts[containerId] = chart;
}

// Thresholds compartilhados — refletem a SLA percebida do operador:
// até 15 min é excelente, até 30 aceitável, até 45 atenção, acima é crítico.
const GAUGE_THRESHOLDS = [
  { upTo: 15, color: "#22c55e" }, // verde
  { upTo: 30, color: "#facc15" }, // amarelo
  { upTo: 45, color: "#fb923c" }, // laranja
  { upTo: 60, color: "#ef4444" }, // vermelho
];

function showProactivityChart() {
  var averageTime = calculateAverageTime();
  showProactivityChart.lastProactivityTime = averageTime;

  // Garante que o título do bloco esteja consistente com o resto da seção.
  var host = document.getElementById("gaugeChart");
  if (host && host.parentElement && !host.parentElement.querySelector(".gauge-heading")) {
    var heading = document.createElement("div");
    heading.className = "gauge-heading";
    heading.textContent = "Tempo Médio de Proatividade";
    host.parentElement.insertBefore(heading, host);
  }

  renderRingGauge("gaugeChart", {
    value: averageTime,
    max: 60,
    thresholds: GAUGE_THRESHOLDS,
    suffix: "min",
  });
}

/**
 * Calcula o tempo médio de atendimento (em minutos), lendo direto do DOM
 * (.customer-assisted) — mesma estratégia do calculateAverageTime.
 *
 * MUDANÇA estrutural (24-abr-2026):
 *  - ANTES dependia dos arrays globais timesToAnalysisJD/WTG, que só eram
 *    populados por socket.on("msgWaitingAssist") e perdiam todos os
 *    registros históricos sem Chassi ou com Hora_atendimento em formato
 *    inválido. Resultado: o gauge ficava preso em 0 minutos.
 *  - AGORA: percorre os elementos `.customer-assisted` já renderizados,
 *    lê `.hour-request`, `.hour-assisted` e `.date-request`, e aplica os
 *    mesmos filtros de horário comercial / dia útil do calculateAverageTime.
 *  - Bônus: reage automaticamente a filtros de frota (JD/WTG) e de data,
 *    porque opera sobre o que está visível.
 */
function averageTimeAssist() {
  var assistedNodes = document.querySelectorAll(".customer-assisted");
  var arrayDifs = [];

  assistedNodes.forEach(function (node) {
    // Filtros de frota — espelham os do calculateAverageTime.
    var pinEl = node.querySelector(".pin");
    if (chartFilterJD && pinEl && !isChassiJD(pinEl.innerHTML)) return;
    if (chartFilterWTG && pinEl && isChassiJD(pinEl.innerHTML)) return;

    var hourReqEl    = node.querySelector(".hour-request");
    var hourAssistEl = node.querySelector(".hour-assisted");
    var dateReqEl    = node.querySelector(".date-request");
    if (!hourReqEl || !hourAssistEl) return;

    var assistMin = hhmmToMinutes(hourAssistEl.innerHTML);
    var reqMin    = hhmmToMinutes(hourReqEl.innerHTML);

    if (isNaN(assistMin)) return;             // não atendido / dado faltando
    if (!isWithinBusinessHours(reqMin)) return;

    // Filtro por dia útil — date-request vem em DD/MM/YYYY (timeConverter).
    if (dateReqEl) {
      var parts = String(dateReqEl.innerHTML).split("/");
      if (parts.length >= 3) {
        var d  = parseInt(parts[0], 10);
        var mo = parseInt(parts[1], 10);
        var y  = parseInt(parts[2], 10);
        if (!isNaN(d) && !isNaN(mo) && !isNaN(y)) {
          var dt = new Date(y, mo - 1, d);
          if (!isBusinessDay(dt)) return;
        }
      }
    }

    var dif = assistMin - reqMin;
    if (dif < 0) return; // negativo = inconsistência; descartar antes de média
    arrayDifs.push(dif);
  });

  if (arrayDifs.length === 0) return 0;
  var sumDifs = 0;
  arrayDifs.forEach(function (dif) { sumDifs += dif; });
  return Math.round(sumDifs / arrayDifs.length);
}

function showAssistTimeChart() {
  // Garante que o título do bloco esteja consistente com o resto da seção.
  var host = document.getElementById("assistChart");
  if (host && host.parentElement && !host.parentElement.querySelector(".gauge-heading")) {
    var heading = document.createElement("div");
    heading.className = "gauge-heading";
    heading.textContent = "Tempo Médio de Atendimento";
    host.parentElement.insertBefore(heading, host);
  }

  // Usa valor da API (mais preciso) quando disponível; fallback para DOM.
  var assistTimeValue =
    (typeof showAssistTimeChart._apiValue === "number")
      ? showAssistTimeChart._apiValue
      : averageTimeAssist();

  showAssistTimeChart.lastAssistTime = assistTimeValue;

  renderRingGauge("assistChart", {
    value: assistTimeValue,
    max: 60,
    thresholds: GAUGE_THRESHOLDS,
    suffix: "min",
  });
}

/**
 * Busca TMA via API para o período ativo e atualiza o gauge.
 * Chamado ao carregar a página, ao trocar filtro de datas, e a cada ciclo de refresh.
 * Aceita startDate/endDate opcionais; quando omitidos usa o período filtrado
 * globalmente (window._activeDateRange) ou o mês atual como fallback.
 * Fallback silencioso: mantém o valor DOM caso a API falhe.
 */
function fetchTmaFromAPI(startDate, endDate) {
  var today      = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
  var firstOfMonth = today.slice(0, 7) + "-01";

  // Usa parâmetros explícitos > estado global do filtro > mês atual
  var sd = startDate
    || (window._activeDateRange && window._activeDateRange.start)
    || firstOfMonth;
  var ed = endDate
    || (window._activeDateRange && window._activeDateRange.end)
    || today;

  var params = new URLSearchParams({ startDate: sd, endDate: ed });
  fetch("/api/metrics/tma?" + params.toString())
    .then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); })
    .then(function(json) {
      var rows = json.rows || [];
      if (rows.length === 0) {
        showAssistTimeChart._apiValue = 0;
        showAssistTimeChart();
        // Atualiza painel direito mesmo sem dados (mostra 0/—)
        if (typeof updateStatsPanelTimes === 'function') {
          var proactMin = (typeof calculateAverageTime === 'function') ? calculateAverageTime() : 0;
          updateStatsPanelTimes(proactMin, 0);
        }
        _renderTmaTable(rows);
        return;
      }
      // Média global ponderada: soma(tma * atendidos) / total atendidos
      var totalAtend = 0, somaMin = 0;
      rows.forEach(function(r) {
        var n = parseInt(r.total_atendidos, 10) || 0;
        var m = parseInt(r.tma_minutos,    10);
        if (n > 0 && !isNaN(m) && m > 0) {
          somaMin    += m * n;
          totalAtend += n;
        }
      });
      if (totalAtend === 0) {
        showAssistTimeChart._apiValue = 0;
      } else {
        showAssistTimeChart._apiValue = Math.round(somaMin / totalAtend);
      }
      showAssistTimeChart();

      // Atualiza também o painel de estatísticas do lado direito
      // (proatividade lida do DOM + atendimento da API)
      if (typeof updateStatsPanelTimes === 'function') {
        var proactMin = (typeof calculateAverageTime === 'function') ? calculateAverageTime() : 0;
        updateStatsPanelTimes(proactMin, showAssistTimeChart._apiValue);
      }

      // Renderiza tabela por usuário se o elemento existir
      _renderTmaTable(rows);
    })
    .catch(function() { /* falha silenciosa — DOM-based fica ativo */ });
}

/** Renderiza tabela de TMA por usuário no elemento #tma-by-user-table (se existir). */
function _renderTmaTable(rows) {
  var container = document.getElementById("tma-by-user-table");
  if (!container) return;
  if (rows.length === 0) {
    container.innerHTML = '<p style="color:#888;font-size:0.78rem;text-align:center;">Sem dados no período.</p>';
    return;
  }
  // Agrupa por usuário (último 30 dias, vários dias por linha)
  var byUser = {};
  rows.forEach(function(r) {
    var u = r.nome_perfil || "—";
    if (!byUser[u]) byUser[u] = { total: 0, soma: 0 };
    var n = parseInt(r.total_atendidos, 10) || 0;
    var m = parseInt(r.tma_minutos,    10);
    if (n > 0 && !isNaN(m) && m > 0) {
      byUser[u].soma  += m * n;
      byUser[u].total += n;
    }
  });
  var html =
    '<table style="width:100%;border-collapse:collapse;font-size:0.76rem;">' +
    '<thead><tr>' +
    '<th style="text-align:left;padding:4px 6px;color:#aaa;font-weight:600;border-bottom:1px solid #333;">Usuário</th>' +
    '<th style="text-align:right;padding:4px 6px;color:#aaa;font-weight:600;border-bottom:1px solid #333;">Atend.</th>' +
    '<th style="text-align:right;padding:4px 6px;color:#aaa;font-weight:600;border-bottom:1px solid #333;">TMA (min)</th>' +
    '</tr></thead><tbody>';
  Object.keys(byUser).sort().forEach(function(u) {
    var d = byUser[u];
    var avg = d.total > 0 ? Math.round(d.soma / d.total) : "—";
    html += '<tr>' +
      '<td style="padding:4px 6px;color:#e0e0e0;">' + u + '</td>' +
      '<td style="padding:4px 6px;color:#bbb;text-align:right;">' + d.total + '</td>' +
      '<td style="padding:4px 6px;color:#F0AB00;font-weight:600;text-align:right;">' + avg + '</td>' +
      '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

// Dispara na carga inicial (aguarda 2s para a página estar pronta e o DOM dos
// alertas já ter sido populado pelo socket "newEvent").
setTimeout(function() {
  fetchTmaFromAPI();
  // Garante que o gauge de proatividade também seja renderizado na carga inicial.
  if (typeof showProactivityChart === 'function') showProactivityChart();
}, 2000);

function calculateAverageTime() {
  /**
   * Pega os horários de envio e de geração do alerta e retorna a diferença
   * em minutos.
   *
   * Regras de negócio aplicadas:
   *  - Só considera alertas do horário comercial (08:00-17:50 Seg-Sex).
   *  - Retorna `null` para registros fora da janela — o chamador FILTRA esses
   *    `null`s antes de calcular a média. ANTES retornava [0,0], o que puxava
   *    a média artificialmente para baixo (pois 0 é um valor válido).
   *  - Rejeita alertas em que a data de detecção e a data de envio divergem
   *    (evita o caso de alerta gerado à noite e enviado no dia seguinte
   *    contaminar a média de proatividade).
   */
  function calculateProactivity(element) {
    var dateTimeNotif = element.querySelector(".date-time").innerHTML;
    var daySended = element.querySelector(".day-sended").innerHTML;
    var hourSended = element.querySelector(".hour-sended").innerHTML;

    var day = stringToArray(daySended, "/");
    var hour = stringToArray(hourSended, ":");
    var dtSended = new Date(day[2], day[1] - 1, day[0], hour[0], hour[1]);

    var dtDtc = stringToArray(dateTimeNotif, " ");
    var dateDtc = stringToArray(dtDtc[0], "/");
    var hourDtc = stringToArray(dtDtc[1], ":");

    // Rejeita se a detecção e o envio não forem no MESMO dia — esse caso costuma
    // ocorrer com alertas emitidos fora de expediente que o core só envia no dia
    // útil seguinte; a diferença deixa de representar "proatividade real".
    if (dtDtc[0] !== daySended) {
      return null;
    }

    // Filtro de expediente: detecção precisa ter caído dentro de 08:00-17:50.
    var notifMinutes = hhmmToMinutes(hourDtc);
    if (!isWithinBusinessHours(notifMinutes)) {
      return null;
    }

    // Só consideramos dias úteis.
    if (!isBusinessDay(dtSended)) {
      return null;
    }

    var dtNotif = new Date(
      dateDtc[2],
      dateDtc[1] - 1,
      dateDtc[0],
      hourDtc[0],
      hourDtc[1]
    );

    // Calcula diferença em minutos de forma direta (sem o cálculo antigo
    // de "hora + minuto" que gerava resultado incorreto quando minSend < minNotif
    // e hrSend-- gerava hora negativa mantida no resultado).
    var difMs = dtSended.getTime() - dtNotif.getTime();
    if (isNaN(difMs) || difMs < 0) return null;

    var difMin = Math.round(difMs / 60000);
    return difMin;
  }

  function stringToArray(str, sep) {
    return str.split(sep);
  }

  /* Pega todos horários de todos os alertas */
  const notif = document.querySelectorAll(".alert-info");
  var allDifTimes = [];

  /* Joga os horários na função para calcular a diferença e armazenar num array */
  notif.forEach((alert) => {
    if (chartFilterJD && !isChassiJD(alert.querySelector(".pin").innerHTML))
      return;
    if (chartFilterWTG && isChassiJD(alert.querySelector(".pin").innerHTML))
      return;

    var dif = calculateProactivity(alert);
    // IMPORTANTE: só empilha se for um número válido. ANTES aceitava [0,0] e
    // contaminava a média.
    if (typeof dif === "number" && !isNaN(dif)) {
      allDifTimes.push(dif);
    }
  });

  // Evita divisão por zero quando não há dados válidos
  if (allDifTimes.length === 0) {
    return 0;
  }

  var sum = 0;
  allDifTimes.forEach((dif) => { sum += dif; });
  return Math.round(sum / allDifTimes.length);
}

// Mantém referência ao chart de linha para destruir antes de recriar.
let _lineChartInstance = null;

function showLineChart() {
  var host = document.getElementById("lineChart");
  if (!host) return;

  // Limpa o div hospedeiro (que historicamente recebia SVG do JSC) e cria
  // um <canvas> filho gerenciado pelo Chart.js.
  if (_lineChartInstance) {
    try { _lineChartInstance.destroy(); } catch (e) { /* ignora */ }
    _lineChartInstance = null;
  }
  host.innerHTML = "";
  var canvas = document.createElement("canvas");
  host.appendChild(canvas);

  var rawPoints = getDataToLineChart("alert-info", "day-sended"); // [[Date, n], ...]
  // Ordena por data para o gráfico ficar cronológico (originalmente vinha
  // pela ordem de inserção no DOM, que segue o feed e nem sempre é monotônica).
  rawPoints.sort(function (a, b) { return a[0].getTime() - b[0].getTime(); });

  var labels = rawPoints.map(function (pt) {
    var d = pt[0];
    var dd = String(d.getDate()).padStart(2, "0");
    var mm = String(d.getMonth() + 1).padStart(2, "0");
    return dd + "/" + mm;
  });
  var values = rawPoints.map(function (pt) { return pt[1]; });

  // Gradiente vertical para preencher sob a linha — combina com o fundo
  // escuro do dashboard e dá profundidade sem ruído visual.
  var ctx = canvas.getContext("2d");
  var gradient = ctx.createLinearGradient(0, 0, 0, 280);
  gradient.addColorStop(0, "rgba(240, 171, 0, 0.35)");
  gradient.addColorStop(1, "rgba(240, 171, 0, 0)");

  _lineChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Alertas enviados",
          data: values,
          borderColor: "#F0AB00",
          borderWidth: 2.5,
          backgroundColor: gradient,
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointBackgroundColor: "#F0AB00",
          pointBorderColor: "#1a1a1a",
          pointBorderWidth: 2,
          pointHoverBorderWidth: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 18, bottom: 8, left: 8, right: 8 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        title: {
          display: true,
          text: "Tempo Médio de Resposta",
          align: "center",
          color: "#F0AB00",
          font: { size: 15, family: "Inter, sans-serif", weight: "700" },
          padding: { top: 4, bottom: 14 },
        },
        legend: {
          display: true,
          position: "top",
          align: "end",
          labels: {
            color: "#cbd5e1",
            font: { size: 12, family: "Inter, sans-serif", weight: "500" },
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            pointStyle: "circle",
          },
        },
        tooltip: {
          backgroundColor: "rgba(20,20,20,0.94)",
          titleColor: "#F0AB00",
          bodyColor: "#f0f0f0",
          borderColor: "rgba(240,171,0,0.3)",
          borderWidth: 1,
          padding: 12,
          titleFont: { size: 13, weight: "bold" },
          bodyFont: { size: 12 },
          displayColors: false,
          callbacks: {
            label: function (ctx) { return "  " + ctx.formattedValue + " alerta(s)"; },
          },
        },
        datalabels: { display: false },
      },
      scales: {
        x: {
          ticks: {
            color: "#94a3b8",
            font: { size: 11, family: "Inter, sans-serif" },
            maxRotation: 0,
            autoSkipPadding: 12,
          },
          grid: { display: false },
          border: { color: "rgba(94,106,113,0.2)" },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: "#94a3b8",
            font: { size: 11, family: "Inter, sans-serif" },
            stepSize: 1,
            padding: 6,
          },
          grid: { color: "rgba(94,106,113,0.08)", drawBorder: false },
          border: { color: "rgba(94,106,113,0.2)" },
        },
      },
    },
  });
}

function getDataToLineChart(messageClass, dateClass) {
  const elements = document.querySelectorAll(`.${messageClass}`); // Pega todas as mensagens
  var elementAmounts = {};
  let dateAlert, dateToObj;

  // console.log("Chassis - Alertas por dia")

  elements.forEach((alert) => {
    dateAlert = alert.querySelector(`.${dateClass}`).innerHTML.split("/"); // Pega a data de cada mensagem

    dateToObj = `${dateAlert[2]}-${dateAlert[1]}-${dateAlert[0]}T12:00:00.000Z`; // Coloca no formato ISO

    if (chartFilterJD && !isChassiJD(alert.querySelector(".pin").innerHTML))
      return;
    if (chartFilterWTG && isChassiJD(alert.querySelector(".pin").innerHTML))
      return;

    // Adiciona ao objeto a contagem de mensagens separadas por datas
    if (elementAmounts[dateToObj] == null) {
      elementAmounts[dateToObj] = 1;
    } else {
      elementAmounts[dateToObj]++;
    }
  });

  /**
   * Faz a adição a um array para ficar no formato em que o gráfico aceita.
   * Ex: [[new Date(2023, 03, 31), 10], [new Date(2023, 04, 04), 15]]
   * O new Date dentro do "map" é para transformar a string "dateToObj" em um object
   */
  return Object.keys(elementAmounts).map((dt) => [
    new Date(dt),
    elementAmounts[dt],
  ]);
}
