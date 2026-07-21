let validationFilterField = true,
  validationSettingsField = true,
  validationChartField = true,
  chartFilterJD = false,
  chartFilterWTG = false,
  sidebarFilterJD = true,  // Novo: filtro da sidebar (começa com JD selecionado)
  sidebarFilterWTG = true, // Novo: filtro da sidebar
  lastClassFiltered;

function formatDate(dt) {
  newDt = dt.split("-");

  return new Date(newDt[0], newDt[1] - 1, newDt[2]);
}

/**
 * Filtro por data da SIDEBAR DE FILTROS (#f-start / #f-end).
 *
 * ANTES: esta função apenas ocultava elementos DOM já renderizados,
 * o que dava a falsa sensação de "filtro quebrado" quando o usuário
 * queria ver datas que não estavam carregadas no feed (ex.: semana anterior).
 *
 * AGORA: envia as datas ao backend via socket (mesmo contrato usado em
 * `submitStartAndEndDates` — evento `changeStartAndEndDates`), fazendo o
 * servidor re-emitir `newEvent` e `msgWaitingAssist` com os dados do período.
 *
 * A validação e a limpeza de KPIs/feed espelham `submitStartAndEndDates` para
 * manter comportamento consistente com o filtro das Configurações.
 */
function filterNotifications() {
  var inputDayStart = document.getElementById("f-start");
  var inputDayEnd = document.getElementById("f-end");

  if (!inputDayStart || !inputDayEnd) return;

  var startDate = formatDate(inputDayStart.value);
  var endDate = formatDate(inputDayEnd.value);

  // Valida: ambas as datas preenchidas e início <= fim.
  if (
    isNaN(startDate) ||
    isNaN(endDate) ||
    Date.parse(startDate) > Date.parse(endDate)
  ) {
    if (!inputDayStart.classList.contains("error"))
      inputDayStart.classList.add("error");
    if (!inputDayEnd.classList.contains("error"))
      inputDayEnd.classList.add("error");
    console.warn("[FILTER] Período inválido:", inputDayStart.value, inputDayEnd.value);
    return;
  }

  inputDayStart.classList.remove("error");
  inputDayEnd.classList.remove("error");

  // Espelha comportamento de submitStartAndEndDates: limpa feed + KPIs,
  // o backend preencherá novamente após responder.
  document.querySelectorAll(".message").forEach((e) => e.remove());

  document.querySelectorAll(".amount-number").forEach((amountDiv) => {
    if (amountDiv.classList.contains("clicked"))
      amountDiv.classList.remove("clicked");
  });

  document.getElementById("number-alert-sended").innerHTML = 0;
  document.getElementById("number-requested-support").innerHTML = 0;
  document.getElementById("number-customers-assisted").innerHTML = 0;
  document.getElementById("number-customers-waiting").innerHTML = 0;

  // Usa o valor original do input (string YYYY-MM-DD), que é o formato
  // que o backend espera em db.selectTable.
  socket.emit("changeStartAndEndDates", inputDayStart.value, inputDayEnd.value);

  // Atualiza o período ativo e rebusca TMA da API para o gauge acompanhar
  window._activeDateRange = { start: inputDayStart.value, end: inputDayEnd.value };
  if (typeof fetchTmaFromAPI === 'function') {
    fetchTmaFromAPI(inputDayStart.value, inputDayEnd.value);
  }
}

function clearFilters() {
  // Mostrar todas as mensagens escondidas pelos filtros visuais
  const allMessages = document.querySelectorAll(".message");
  allMessages.forEach((element) => {
    if (element.classList.contains("hidden")) {
      element.classList.remove("hidden");
    }
  });

  document.querySelectorAll(".amount-number").forEach((amountDiv) => {
    if (amountDiv.classList.contains("clicked"))
      amountDiv.classList.remove("clicked");
  });

  // Limpa busca por chassi e por cliente (inputs da sidebar de filtros)
  var chassiInput = document.getElementById("f-chassi");
  if (chassiInput) chassiInput.value = "";
  var glassesInput = document.getElementById("glasses");
  if (glassesInput) glassesInput.value = "";

  // Reseta filtro de frota para AMBOS (evita que mensagens fiquem
  // permanentemente escondidas por um filtro de frota anterior)
  sidebarFilterJD = true;
  sidebarFilterWTG = true;
  var fleetSelect = document.getElementById("fleet-select");
  if (fleetSelect) fleetSelect.value = "AMBOS";

  // Limpa inputs de data e erro visual
  var inputDayStart = document.getElementById("f-start");
  var inputDayEnd = document.getElementById("f-end");
  if (inputDayStart) { inputDayStart.value = ""; inputDayStart.classList.remove("error"); }
  if (inputDayEnd) { inputDayEnd.value = ""; inputDayEnd.classList.remove("error"); }

  // Limpa feed + KPIs (backend repreenche apos responder)
  document.querySelectorAll(".message").forEach((e) => e.remove());

  var elAlertSent = document.getElementById("number-alert-sended");
  var elReqSupport = document.getElementById("number-requested-support");
  var elAssist = document.getElementById("number-customers-assisted");
  var elWaiting = document.getElementById("number-customers-waiting");
  if (elAlertSent) elAlertSent.innerHTML = 0;
  if (elReqSupport) elReqSupport.innerHTML = 0;
  if (elAssist) elAssist.innerHTML = 0;
  if (elWaiting) elWaiting.innerHTML = 0;

  // Restaura o estado inicial do servidor: dayInterval = 1 (ultimo dia).
  // IMPORTANTE: usa changeDayInterval em vez de changeStartAndEndDates para
  // manter dayInterval > 0 no servidor — isso garante que o refresh
  // automatico a cada 30s continue funcionando. changeStartAndEndDates
  // setava dayInterval = 0 e matava o refresh, fazendo a pagina ficar
  // permanentemente em branco quando nao havia dados para a data filtrada.
  if (typeof socket !== "undefined" && socket && socket.emit) {
    socket.emit("changeDayInterval", 1);
  }

  // Reseta período ativo e rebusca TMA para o dia atual
  window._activeDateRange = null;
  if (typeof fetchTmaFromAPI === 'function') {
    fetchTmaFromAPI();
  }
}

function submitNewDayInterval() {
  var inputDayInterval = document.getElementById("config-day-interval-input");

  console.log(inputDayInterval.valueAsNumber);

  if (inputDayInterval.valueAsNumber > 0) {
    if (inputDayInterval.classList.contains("error"))
      inputDayInterval.classList.remove("error");
  } else {
    if (!inputDayInterval.classList.contains("error"))
      inputDayInterval.classList.add("error");
    return;
  }

  document.querySelectorAll(".message").forEach((e) => e.remove());

  document.querySelectorAll(".amount-number").forEach((amountDiv) => {
    if (amountDiv.classList.contains("clicked"))
      amountDiv.classList.remove("clicked");
  });

  document.getElementById("number-alert-sended").innerHTML = 0;
  document.getElementById("number-requested-support").innerHTML = 0;
  document.getElementById("number-customers-assisted").innerHTML = 0;
  document.getElementById("number-customers-waiting").innerHTML = 0;

  socket.emit("changeDayInterval", inputDayInterval.valueAsNumber);
}

function submitStartAndEndDates() {
  var inputDayStart = document.getElementById("config-day-start-input");
  var inputDayEnd = document.getElementById("config-day-end-input");

  var startDate = formatDate(
    document.getElementById("config-day-start-input").value
  );
  var endDate = formatDate(
    document.getElementById("config-day-end-input").value
  );

  // Verifica se o input está preenchido e se o startDate é menor do que o endDate
  if (
    Date.parse(startDate) <= Date.parse(endDate) &&
    !(isNaN(startDate) || isNaN(endDate))
  ) {
    if (inputDayStart.classList.contains("error"))
      inputDayStart.classList.remove("error");
    if (inputDayEnd.classList.contains("error"))
      inputDayEnd.classList.remove("error");
  } else {
    if (!inputDayStart.classList.contains("error"))
      inputDayStart.classList.add("error");
    if (!inputDayEnd.classList.contains("error"))
      inputDayEnd.classList.add("error");
    return;
  }

  document.querySelectorAll(".message").forEach((e) => e.remove());

  document.querySelectorAll(".amount-number").forEach((amountDiv) => {
    if (amountDiv.classList.contains("clicked"))
      amountDiv.classList.remove("clicked");
  });

  document.getElementById("number-alert-sended").innerHTML = 0;
  document.getElementById("number-requested-support").innerHTML = 0;
  document.getElementById("number-customers-assisted").innerHTML = 0;
  document.getElementById("number-customers-waiting").innerHTML = 0;

  socket.emit("changeStartAndEndDates", inputDayStart.value, inputDayEnd.value);

  // Atualiza o período ativo e rebusca TMA da API para o gauge acompanhar
  window._activeDateRange = { start: inputDayStart.value, end: inputDayEnd.value };
  if (typeof fetchTmaFromAPI === 'function') {
    fetchTmaFromAPI(inputDayStart.value, inputDayEnd.value);
  }
}

function showResources(validation, container, slideIn, slideOut) {
  // Se a validação for falsa, significa que o recurso está visível.
  if (validation) {
    document.querySelector(container).classList.remove(slideOut);
    document.querySelector(container).classList.add(slideIn);
    return (validation = false);
  } else {
    document.querySelector(container).classList.remove(slideIn);
    document.querySelector(container).classList.add(slideOut);
    return (validation = true);
  }
}

function showFilterField() {
  if (!validationSettingsField) showSettingsField();

  validationFilterField = showResources(
    validationFilterField,
    ".right-sidebar-filters",
    "slide-filter",
    "slide-filter-out"
  );
}

function showSettingsField() {
  if (!validationFilterField) showFilterField();

  validationSettingsField = showResources(
    validationSettingsField,
    ".right-sidebar-settings",
    "slide-filter",
    "slide-filter-out"
  );
}

function showCharts() {
  validationChartField = showResources(
    validationChartField,
    ".modal-analysis",
    "slide-charts-in",
    "slide-charts-out"
  );
  setTimeout(() => {
    if (!validationChartField) {
      showChartModels();
      showProactivityChart();
      showLineChart();
      showAssistTimeChart();
    }
  }, 300);
}

function selectChartsFilter(filter) {
  if (filter == "JD") {
    chartFilterJD = !chartFilterJD;
    chartFilterWTG = false;
  } else if (filter == "WTG") {
    chartFilterWTG = !chartFilterWTG;
    chartFilterJD = false;
  }

  if (!chartFilterJD) {
    document.querySelector(".JD").classList.remove("filter-selected");
  } else {
    document.querySelector(".JD").classList.add("filter-selected");
  }

  if (!chartFilterWTG) {
    document.querySelector(".WTG").classList.remove("filter-selected");
  } else {
    document.querySelector(".WTG").classList.add("filter-selected");
  }

  showChartModels();
  showProactivityChart();
  showLineChart();
  showAssistTimeChart();
}

function searchCustomer() {
  var inputSearch = document.getElementById("glasses").value.toUpperCase();
  var displayedNameEl = document.querySelectorAll(".displayed-name");

  displayedNameEl.forEach((el) => {
    let grandPaNode = el.parentNode.parentNode;

    if (!el.innerHTML.includes(inputSearch)) {
      grandPaNode.classList.add("hidden");
    } else {
      grandPaNode.classList.remove("hidden");
    }
  });

  if (inputSearch == "") {
    clearFilters();
  }
}

/**
 * Pesquisa por CHASSI nas mensagens já renderizadas do feed.
 * O chassi é exibido dentro de elementos `.pin` (ver alertSended em script.js
 * e os handlers de `newEvent` em index.html), portanto fazemos a busca
 * case-insensitive nesse texto e escondemos as mensagens que não batem.
 *
 * Quando o campo é esvaziado, chamamos clearFilters() para voltar ao estado
 * original — mesmo padrão usado por searchCustomer.
 */
function searchChassi() {
  var input = document.getElementById("f-chassi");
  if (!input) return;
  var q = input.value.trim().toUpperCase();

  // Campo vazio: restaura visibilidade completa.
  if (q === "") {
    clearFilters();
    return;
  }

  var pinEls = document.querySelectorAll(".pin");
  pinEls.forEach((pinEl) => {
    // Sobe até o nó .message (ancestral comum ao feed).
    var msgEl = pinEl.closest(".message");
    if (!msgEl) return;

    var chassiText = (pinEl.innerHTML || "").toUpperCase();
    if (chassiText.indexOf(q) === -1) {
      msgEl.classList.add("hidden");
    } else {
      msgEl.classList.remove("hidden");
    }
  });
}

function filterByAmount(msgElem, classWillFilter, amountClicked) {
  const messages = document.querySelectorAll(msgElem);
  let checkClass;

  // Checa se já foi filtrado. Se ainda não tiver clicado no botão, será filtrado
  if (classWillFilter != lastClassFiltered) {
    /**
     * Se tiver não tiver a classe que será filtrada nas classes da div, o script vai esconder.
     * Isso é para aparecer apenas as divs que contém a classe que deseja filtrar
     */
    messages.forEach((msg) => {
      checkClass = msg.children[0].classList.contains(classWillFilter);
      if (!checkClass) {
        msg.classList.add("hidden");
      } else if (checkClass && msg.classList.contains("hidden")) {
        // Essa condição é para caso alternar o clique dos botões de filtro de quantidades
        msg.classList.remove("hidden");
      }
    });

    // Se já tiver algum filtro "clicado", ele removerá o efeito CSS do último filtro clicado.
    document.querySelectorAll(".amount-number").forEach((amountDiv) => {
      if (amountDiv.classList.contains("clicked"))
        amountDiv.classList.remove("clicked");
    });

    lastClassFiltered = classWillFilter;

    // Coloca uma cor para informar que está "clicado"
    document
      .querySelector(`.${amountClicked}`)
      .children[1].classList.add("clicked");
  } else {
    // Caso já tenha sido clicado, o script vai entender que é preciso retirar o filtro da página
    messages.forEach((msg) => msg.classList.remove("hidden"));
    document
      .querySelector(`.${amountClicked}`)
      .children[1].classList.remove("clicked");

    /**
     * Quando quiser clicar mais de uma vez nos amounts, é preciso que seja null, para não bugar o filtro.
     * Tipo, sem essa linha de código, só é possível filtrar uma vez, porque o lastClassFiltered fica com a última classe filtrada
     * Isso quer dizer que, se precisasse filtrar de novo, não filtraria. Porque pela lógica, ele não filtra se a classe for igual
     * a variável "lastClassFiltered".
     */
    lastClassFiltered = null;
  }
}

function alertFilter() {
  filterByAmount(".message", "alert-info", "alert-sended");
}

function needsHelpFilter() {
  filterByAmount(".message", "customer-needs-help", "requested-support");
}

function isChassiJD(chassi) {
  // 1BZ / 1F9 / 1DW / 1T0 / 1FF

  return (
    chassi.includes("1BZ") ||
    chassi.includes("1F9") ||
    chassi.includes("1DW") ||
    chassi.includes("1T0") ||
    chassi.includes("1FF")
  );
}

function toggleFleetFilter(fleet) {
  // Alternar seleção de frota na sidebar
  if (fleet === "JD") {
    sidebarFilterJD = !sidebarFilterJD;
    // Se desselecionar JD, ativar WTG
    if (!sidebarFilterJD && !sidebarFilterWTG) {
      sidebarFilterWTG = true;
    }
  } else if (fleet === "WTG") {
    sidebarFilterWTG = !sidebarFilterWTG;
    // Se desselecionar WTG, ativar JD
    if (!sidebarFilterJD && !sidebarFilterWTG) {
      sidebarFilterJD = true;
    }
  }

  // Atualizar estilos dos links de filtro
  const jdLink = document.querySelector(".jd-filter-link");
  const wtgLink = document.querySelector(".wtg-filter-link");

  if (jdLink) {
    jdLink.style.color = sidebarFilterJD ? "#F0AB00" : "#787878";
    jdLink.style.opacity = sidebarFilterJD ? "1" : "0.6";
  }

  if (wtgLink) {
    wtgLink.style.color = sidebarFilterWTG ? "#F0AB00" : "#787878";
    wtgLink.style.opacity = sidebarFilterWTG ? "1" : "0.6";
  }

  // Aplicar filtro às mensagens do feed
  applyFleetFilterToFeed();

  // CORREÇÃO: Recalcular os quantitativos dos cards PRIMEIRO
  recalculateStatsForFleetFilter();
}

function onFleetFilterChange(filterValue) {
  // Nova função para o dropdown de filtros
  console.log("[FILTER] Filtro de frota selecionado: " + filterValue);

  if (filterValue === "JD") {
    // Apenas John Deere
    sidebarFilterJD = true;
    sidebarFilterWTG = false;
  } else if (filterValue === "WTG") {
    // Apenas Wirtgen
    sidebarFilterJD = false;
    sidebarFilterWTG = true;
  } else if (filterValue === "AMBOS") {
    // Ambas as frotas
    sidebarFilterJD = true;
    sidebarFilterWTG = true;
  }

  // Aplicar filtro às mensagens do feed
  applyFleetFilterToFeed();

  // Recalcular os quantitativos dos cards
  recalculateStatsForFleetFilter();

  // Se os gráficos estiverem visíveis, atualizar também
  const modalAnalysis = document.querySelector(".modal-analysis");
  if (modalAnalysis && !modalAnalysis.classList.contains("slide-charts-out")) {
    // Os gráficos estão visíveis, então atualizar
    if (typeof showChartModels === 'function') {
      showChartModels();
    }
    if (typeof showProactivityChart === 'function') {
      showProactivityChart();
    }
    if (typeof showLineChart === 'function') {
      showLineChart();
    }
    if (typeof showAssistTimeChart === 'function') {
      showAssistTimeChart();
    }
  }
}

function applyFleetFilterToFeed() {
  // Filtrar mensagens do feed por frota
  const messages = document.querySelectorAll(".message");

  messages.forEach((msg) => {
    const pinElements = msg.querySelectorAll(".pin");
    let shouldShow = true;

    if (pinElements.length > 0) {
      const pin = pinElements[0].innerHTML;
      const isJD = isChassiJD(pin);

      if (isJD && !sidebarFilterJD) {
        shouldShow = false; // Ocultar JD se não selecionado
      } else if (!isJD && !sidebarFilterWTG) {
        shouldShow = false; // Ocultar WTG se não selecionado
      }
    }

    if (shouldShow) {
      msg.classList.remove("hidden");
    } else {
      msg.classList.add("hidden");
    }
  });
}

function recalculateStatsForFleetFilter() {
  // Recalcular métricas baseado nas mensagens visíveis após filtro de frota.
  //
  // CORREÇÃO: As classes alert-info, customer-needs-help e customer-assisted
  // ficam no PRIMEIRO FILHO de .message (não no .message em si).
  // A classe waiting-assistance fica em .treatment-level (span interno).
  const allMessages = document.querySelectorAll(".message");
  let alertCount = 0;
  let supportCount = 0;
  let assistedCount = 0;
  let waitingCount = 0;

  allMessages.forEach((msg) => {
    if (msg.classList.contains("hidden")) return;

    const firstChild = msg.children[0];
    if (!firstChild) return;

    // Contar alertas — primeiro filho tem classe alert-info
    if (firstChild.classList.contains("alert-info")) {
      alertCount++;
    }

    // Contar solicitações de suporte — primeiro filho tem customer-needs-help
    if (firstChild.classList.contains("customer-needs-help")) {
      supportCount++;
    }

    // Contar aguardando — span .treatment-level com classe waiting-assistance
    const treatmentEl = msg.querySelector(".treatment-level");
    if (treatmentEl && treatmentEl.classList.contains("waiting-assistance")) {
      waitingCount++;
    }

    // Contar atendidos — primeiro filho com customer-assisted (marcado pelo askingHelp)
    if (firstChild.classList.contains("customer-assisted")) {
      assistedCount++;
    }
  });

  // Atualizar elementos KPI
  const alertElem = document.getElementById("number-alert-sended");
  const supportElem = document.getElementById("number-requested-support");
  const assistedElem = document.getElementById("number-customers-assisted");
  const waitingElem = document.getElementById("number-customers-waiting");

  if (alertElem) alertElem.innerHTML = alertCount;
  if (supportElem) supportElem.innerHTML = supportCount;
  if (assistedElem) assistedElem.innerHTML = assistedCount;
  if (waitingElem) waitingElem.innerHTML = waitingCount;

  console.log("[FILTER] Estatísticas recalculadas - Alertas: " + alertCount + ", Suporte: " + supportCount + ", Atendido: " + assistedCount + ", Aguardando: " + waitingCount);
}
