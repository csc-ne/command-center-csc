let alertsCustomer = [];
let idsAlerts = [];
let lastClick; // Usado para alternar entre detalhes de mensagens de clientes

function startAssist(button) {
    if (!button) return;

    const message = button.closest(".message");
    if (!message) return;

    // Obter ID da mensagem
    const messageId = message.querySelector(".message-id")?.innerHTML;
    if (!messageId) {
        console.error("Erro: ID da mensagem não encontrado");
        return;
    }

    const status = message.querySelector(".treatment-level");
    const currentTime = getTime();

    status.classList.remove("waiting-assistance");
    status.innerHTML = `🟢Atendimento iniciado às <span class="time-assisted">${currentTime}</span>`;

    // Atualiza .hour-assisted para que averageTimeAssist() consiga
    // calcular o tempo médio de atendimento a partir do DOM.
    const hourAssistedEl = message.querySelector(".hour-assisted");
    if (hourAssistedEl) {
        hourAssistedEl.textContent = currentTime;
    }

    // Marca como customer-assisted para que averageTimeAssist() o encontre
    if (!message.classList.contains("customer-assisted")) {
        message.classList.add("customer-assisted");
    }

    button.style.display = "none";
    message.querySelector(".btn-end-assist").classList.remove("hidden");

    message.classList.remove("pulsing");

    // Emitir evento Socket.IO para salvar no BD (inclui usuário CC que iniciou)
    const _cc = window._ccUser || {};
    socket.emit("customerAssisted", {
        id: messageId,
        time: Date.now(),
        ccUserName: _cc.displayName || null,
        ccUserEmail: _cc.email || null
    });

    // Recalcula gauges de tempo médio após marcar atendimento
    if (typeof showAssistTimeChart === 'function') showAssistTimeChart();
    if (typeof showProactivityChart === 'function') showProactivityChart();

    // ── Abre o chat panel para atendimento in-app ──
    const phoneNumber = message.querySelector(".phone-number-customer")?.innerHTML;
    const displayName = message.querySelector(".displayed-name")?.innerHTML;
    if (phoneNumber && typeof openChatPanel === "function") {
        openChatPanel(phoneNumber, messageId, displayName);
    }
}

function endAssist(button) {
    if (!button) return;

    const message = button.closest(".message");
    if (!message) return;

    // Obter ID da mensagem
    const messageId = message.querySelector(".message-id")?.innerHTML;
    if (!messageId) {
        console.error("Erro: ID da mensagem não encontrado");
        return;
    }

    // Obter informações da mensagem para o modal
    const phoneNumber = message.querySelector(".phone-number-customer")?.innerHTML;
    const displayName = message.querySelector(".displayed-name")?.innerHTML;

    // Criar modal de finalização
    const endAssistModal = `
        <div class="floating-window show-floating-window" id="end-assist-modal">
            <div class="details-alert" style="width: 520px; max-height: 80vh;">
                <div class="floating-window-X">
                    <button class="close-X" onclick="closeEndAssistModal()" style="background:none;border:none;cursor:pointer;opacity:0.6;transition:opacity 0.2s;">
                        <svg width="24" height="24" viewBox="0 0 25 24">
                            <line x1="18" y1="6" x2="6" y2="18" stroke="white" stroke-width="2" />
                            <line x1="6" y1="6" x2="18" y2="18" stroke="white" stroke-width="2" />
                        </svg>
                    </button>
                </div>
                <h2>Encerrar Atendimento</h2>
                <div style="padding: 20px; display: flex; flex-direction: column; gap: 16px;">
                    <div>
                        <label style="display: block; margin-bottom: 4px; font-weight: 600; font-size: 0.85rem; color: #787878;">Cliente</label>
                        <p style="margin: 0; color: #f0f0f0;">${displayName}</p>
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 4px; font-weight: 600; font-size: 0.85rem; color: #787878;">Telefone</label>
                        <p style="margin: 0; color: #f0f0f0;">${phoneNumber}</p>
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; font-size: 0.85rem; color: #787878;">Tipo de Finalização</label>
                        <select id="tipo-finalizacao" style="width: 100%; padding: 8px; background: #1a1a1a; border: 1px solid #404040; color: #f0f0f0; border-radius: 4px;">
                            <option value="">Selecione uma opção</option>
                            <option value="Resolvido">Resolvido</option>
                            <option value="Encaminhado">Encaminhado para técnico</option>
                            <option value="Agendado">Agendado para depois</option>
                            <option value="Não_resolvido">Não foi possível resolver</option>
                        </select>
                    </div>

                    <div>
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; font-size: 0.85rem; color: #787878;">Observações (opcional)</label>
                        <textarea id="obs-finalizacao" placeholder="Adicione observações sobre o atendimento..." style="width: 100%; padding: 8px; background: #1a1a1a; border: 1px solid #404040; color: #f0f0f0; border-radius: 4px; min-height: 80px; resize: vertical; font-family: inherit;"></textarea>
                    </div>

                    <div style="display: flex; gap: 10px; margin-top: 10px;">
                        <button onclick="closeEndAssistModal()" style="flex: 1; padding: 10px; background: #404040; color: #f0f0f0; border: 1px solid #505050; border-radius: 4px; cursor: pointer; font-weight: 600;">Cancelar</button>
                        <button onclick="submitEndAssist('${messageId}')" style="flex: 1; padding: 10px; background: #f5c200; color: #111; border: none; border-radius: 4px; cursor: pointer; font-weight: 600;">Confirmar</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Adicionar modal ao DOM
    document.querySelector(".container")?.insertAdjacentHTML("beforeend", endAssistModal);
}

function getTime() {
    // Essa função atualiza a hora atual
    let hoursNow = new Date();
    var hours = hoursNow.getHours().toLocaleString("en-US", { minimumIntegerDigits: 2 });
    var minutes = hoursNow.getMinutes().toLocaleString("en-US", { minimumIntegerDigits: 2 });

    return `${hours}:${minutes}`

}

function closeEndAssistModal() {
    // Fecha o modal de encerramento de atendimento
    const modal = document.getElementById("end-assist-modal");
    if (modal) {
        modal.classList.remove("show-floating-window");
        setTimeout(() => modal.remove(), 300);
    }
}

function submitEndAssist(messageId) {
    // Submete o encerramento de atendimento com observações
    if (!messageId) {
        console.error("Erro: ID da mensagem não encontrado");
        return;
    }

    const tipoFinalizacao = document.getElementById("tipo-finalizacao")?.value;
    const obsFinalizacao = document.getElementById("obs-finalizacao")?.value;

    if (!tipoFinalizacao) {
        alert("Por favor, selecione um tipo de finalização");
        return;
    }

    // Mapear tipo de finalização para o formato esperado pelo servidor
    const serviceTypeMap = {
        "Resolvido": "finished",
        "Encaminhado": "redirect",
        "Agendado": "scheduled",
        "Não_resolvido": "unresolved"
    };

    // Formatar data para o MySQL: YYYY-MM-DD HH:MM:SS (sem T e sem Z)
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const dateTimeFormatted = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;

    // Emitir evento Socket.IO com dados no formato esperado pelo servidor
    const _cc = window._ccUser || {};
    socket.emit("serviceSubmitted", {
        messageId: messageId,
        serviceType: serviceTypeMap[tipoFinalizacao] || "finished",
        dateTimeClicked: dateTimeFormatted,
        redirectService: "default",
        pinMachine: "",
        alertSubject: "",
        noteInput: obsFinalizacao || "",
        ccUserName: _cc.displayName || null,
        ccUserEmail: _cc.email || null
    });

    // Fechar o modal
    closeEndAssistModal();

    // Fecha o chat panel definitivamente (limpa estado + socket)
    if (typeof _closeChatPanelFinal === "function") _closeChatPanelFinal();

    // Atualizar status visual na página
    const messageElement = document.getElementById(messageId)?.closest(".message");
    if (messageElement) {
        const status = messageElement.querySelector(".treatment-level");
        if (status) {
            status.innerHTML = `🔵Atendimento encerrado às ${getTime()}`;
        }
        messageElement.querySelector(".btn-end-assist").style.display = "none";
    }
}

function addElementOnFeed(elem, elemHtml, classHtml, classDivTarget) {
    // Essa função adiciona o elemento HTML no feed da página
    let divFeed = document.querySelector(classDivTarget);
    let newRequest = document.createElement(elemHtml);

    newRequest.classList.add(classHtml);

    // Adiciona o elemento dentro da tag
    newRequest.innerHTML = elem;

    // Adiciona uma classe para efeito configurado no CSS
    newRequest.classList.add("slide-in");

    // Insere o elemento no topo da div
    divFeed.prepend(newRequest);

    // Coloca um efeito de transição da mensagem ao aparecer no feed
    setTimeout(() => newRequest.classList.add("show"), 100);

    return newRequest
};

function updateAmounts(idHTML) {
    // Essa função atualiza as quantidades mostradas na página
    let amountElem = document.querySelector(`#${idHTML}`);
    let amount = parseInt(amountElem.innerHTML);
    amount++;
    amountElem.innerHTML = amount;

}

function updateWaitingAssistNumber() {
    // Essa função pega o número de clientes que estão aguardando atendimento.
    var waitingCustomerEl = document.getElementById("number-customers-waiting");
    waitingCustomerEl.innerHTML = document.getElementsByClassName("waiting-assistance").length;
}

function askingHelp(obj, objAlerts, paramAssisted = false) {
    // Essa função coloca um modelo de solicitação de suporte remoto no feed

    let customerName, dataReceived, timeReceived, messageId, messageBody, phoneNumber, timeAssisted;
    var companyName;

    if (obj.Nome_perfil) {
        customerName = obj.Nome_perfil;
        phoneNumber = obj.Telefone;
        dataReceived = timeConverter(Date.parse(obj.Data_recebimento));
        timeReceived = obj.Hora_Recebimento;
        messageId = obj.Id_mensagem;
        messageBody = obj.Mensagem;
        timeAssisted = obj.Hora_atendimento;
    } else {
        customerName = obj.contact_infos.profile_name;
        phoneNumber = obj.contact_infos.phone_id
        messageId = obj.last_id_msg;
        messageBody = obj.last_message;

        // O timestamp vem como string e em milissegundos.
        // Por isso, precisa multiplicar por 1000 para transformar em segundos.
        var timestamp = parseInt(obj.last_timestamp * 1000);
        var timestampObj = new Date(timestamp);
        var hourTimestamp = timestampObj.getHours().toLocaleString('en-us', { minimumIntegerDigits: 2 });
        var minTimestamp = timestampObj.getMinutes().toLocaleString('en-us', { minimumIntegerDigits: 2 });
        dataReceived = timeConverter(timestamp);
        timeReceived = `${hourTimestamp}:${minTimestamp}`;

    }

    /**
     * Encontra todos os alertas pelo telefone do cliente que entrou em contato e armazena num array.
     * O programa armazena todos os IDS dos alertas numa lista.
     * Isso evita salvar alertas duplicados no "alertsCustomer"
     */
    objAlerts.forEach((alert) => {
        if (alert.ENVIADO_PARA == phoneNumber) {
            if (!idsAlerts.includes(alert.ID)) {
                alertsCustomer.push(alert)
                idsAlerts.push(alert.ID)
            }
            /**
             * Se o telefone corresponder ao número em que foi enviado o alerta, 
             * então o script irá salvar o nome da empresa do chassi que gerou o alerta.
             */
            companyName = alert.CLIENTE;
        }
    });

    var elemAskingHelp = `
        <div class="customer-needs-help">
        <span>👋</span><span class="displayed-name">${customerName}</span>
        <span class="type-message">
        ${messageBody.toUpperCase() == "SOLICITO SUPORTE REMOTO" ? "solicitou suporte remoto." : "mandou uma mensagem"}
        </span>
        <div class="time-of-request">
            <span style="font-size: 10px; margin-left: auto; margin-right: 5px"><strong>Mensagem recebida em:</strong></span>
            <span class="date-request">${dataReceived}</span>
            <span class="hour-request">${timeReceived}</span>
        </div>
        <div class="metadata-customer hidden">
            <span class="message-id hidden" id="${messageId}">${messageId}</span>
            <span class="phone-number-customer hidden">${phoneNumber}</span>
            <span class="message-customer hidden">${messageBody}</span>
            <span class="company-name hidden"> ${companyName == undefined ? "Não identificado" : companyName} </span>
            <!-- Campos abaixo são lidos por charts.js (averageTimeAssist) para
                 calcular o tempo médio de atendimento a partir do DOM, em vez
                 de depender do socket msgWaitingAssist (que era a fonte
                 antiga e perdia dados históricos sem Chassi/Hora_atendimento). -->
            <span class="hour-assisted hidden">${timeAssisted == null || timeAssisted === 0 || timeAssisted === "0" ? "" : timeAssisted}</span>
        </div>
    </div>
    <div class="treatment-status">
        <div class="treatment-level-container">
            <span>Status:</span>
            <span class="treatment-level waiting-assistance">🟡Aguardando atendimento</span>
        </div>
        <div class="treatment-buttons">
            <button type="button" class="btn-start-assist" onclick="startAssist(this)">Iniciar atendimento</button>
            <button type="button" class="btn-end-assist hidden" onclick="endAssist(this)">Encerrar atendimento</button>
            <button type="button" class="btn-info-client" onclick="menuInfoWhatsApp(this)">
                <svg width="25px" height="25px" viewBox="0 0 1024 1024" class="icon" version="1.1"
                    xmlns="http://www.w3.org/2000/svg">
                    <path
                        d="M795.4 749.7c17.2-21.8 27.5-49.3 27.5-79.3 0-70.7-57.3-128-128-128s-128 57.3-128 128c0 29.9 10.3 57.5 27.5 79.3-70.6 36.5-118.9 110.2-118.9 195h73.1c0-80.7 65.6-146.3 146.3-146.3S841.2 864 841.2 944.7h73.1c0-84.7-48.4-158.4-118.9-195zM694.9 615.6c30.2 0 54.9 24.6 54.9 54.9 0 30.2-24.6 54.9-54.9 54.9-30.2 0-54.9-24.6-54.9-54.9 0-30.3 24.6-54.9 54.9-54.9z"
                        fill="white" />
                    <path d="M109.7 73.1v877.8h329.2v-73.2h-256V146.3h658.3V512h73.1V73.1z"
                        fill="white" />
                    <path d="M256 256h512v73.1H256zM256 402.3h365.7v73.1H256zM256 548.6h219.4v73.1H256z"
                        fill="white" />
                </svg>
            </button>
        </div>
    </div>
    `;

    updateAmounts("number-requested-support");

    let askHelpElem;

    // Se o parâmetro for false, significa que o cliente ainda está esperando atendimento
    // Então ele ficará no topo
    if (!paramAssisted) {
        askHelpElem = addElementOnFeed(elemAskingHelp, "article", "message", ".customer-needing-help");
        askHelpElem.classList.add("pulsing");
    } else { // Caso true, o cliente já recebeu atendimento
        askHelpElem = addElementOnFeed(elemAskingHelp, "article", "message", ".all-messages");
        askHelpElem.classList.add("customer-assisted");
        askHelpElem.querySelector(".btn-start-assist").style.display = "none";
        askHelpElem.querySelector(".type-message").innerHTML = "recebeu atendimento";

        var treatmentLevel = askHelpElem.querySelector(".treatment-level");
        treatmentLevel.classList.remove("waiting-assistance");

        if (obj.Tipo_Finalizacao == null || obj.Tipo_Finalizacao == "") {
            // Mostra o botão de encerrar atendimento
            askHelpElem.querySelector(".btn-end-assist").classList.remove("hidden");

            treatmentLevel.innerHTML = `🟢Atendimento iniciado às <span class="time-assisted">${timeAssisted}</span>`;
        } else {
            // Por algum motivo, a data-hora vem 3h a mais. A linha abaixo conserta isso.
            var lux = luxon.DateTime;
            var timeFixed = lux.fromISO(obj.Data_Hora_Finalizacao).setZone("UTC-3");

            var timeFixedHr = timeFixed.toObject().hour.toLocaleString("en-us", { minimumIntegerDigits: 2 });
            var timeFixedMin = timeFixed.toObject().minute.toLocaleString("en-us", { minimumIntegerDigits: 2 });
            treatmentLevel.innerHTML = `🔵Atendimento encerrado em ${timeFixed.toLocaleString()}, às ${timeFixedHr}:${timeFixedMin}`;
        }
    }

    updateWaitingAssistNumber();

}

function timeConverter(UNIX_timestamp) {
    var a = new Date(UNIX_timestamp);
    var months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
    var year = a.getFullYear();
    var month = months[a.getMonth()];
    var date = a.getDate().toLocaleString("en-US", { minimumIntegerDigits: 2 });
    var hour = a.getHours();
    var min = a.getMinutes();
    var sec = a.getSeconds();
    var time = `${date}/${month}/${year}`;
    return time;
}

function alertSended(arrDb) {
    // Essa função coloca um modelo de aviso de alerta enviado no feed
    let dt_alert = timeConverter(Date.parse(arrDb.DATA_ALERTA));
    let dt_sended = timeConverter(Date.parse(arrDb.DATA_ENVIO));
    var elemAlertSend = `
        <div class="alert-info">
            <span>🔔Alerta enviado para </span>
            <span class="displayed-name">${arrDb.CLIENTE.toUpperCase()}</span>
            <span class="pin hidden">${arrDb.CHASSI}</span>
            <span class="phone hidden">${arrDb.ENVIADO_PARA}</span>
            <span class="notification-title hidden">${arrDb.ALERTA}</span>
            <span class="identif-number hidden">${arrDb.ID}</span>
            <span class="latitude hidden">${arrDb.LATITUDE}</span>
            <span class="longitude hidden">${arrDb.LONGITUDE}</span>
            <span class="date-time hidden">${dt_alert} ${arrDb.HORA_ALERTA}</span>
            <span class="hours-engine hidden">${arrDb.HORIMETRO}</span>
            <div class="time-of-sending">
                <span style="font-size: 10px; margin-left: auto; margin-right: 5px"><strong>Enviado em:</strong></span>
                <span class="day-sended">${dt_sended}</span>
                <span class="hour-sended">${arrDb.HORA_ENVIO}</span>
            </div>
        </div>
        
        <span class="more-info" onclick="showModal(this)">Clique aqui para ver mais detalhes</span>
    `;

    addElementOnFeed(elemAlertSend, "article", "message", ".all-messages");
    updateAmounts("number-alert-sended");

}

function showModal(article) {

    var alertMsg = article.parentNode;
    var customerName = alertMsg.querySelector(".displayed-name").innerHTML;
    var customerChassi = alertMsg.querySelector(".pin").innerHTML;
    var customerDtcChassi = alertMsg.querySelector(".notification-title").innerHTML;
    var customerPhone = alertMsg.querySelector(".phone").innerHTML;
    var latitudeCustomer = alertMsg.querySelector(".latitude").innerHTML;
    var longitudeCustomer = alertMsg.querySelector(".longitude").innerHTML;
    var dateTimeDtc = alertMsg.querySelector(".date-time").innerHTML;
    var hoursEngine = alertMsg.querySelector(".hours-engine").innerHTML;
    var mapCode = `
    <div class="loc-equip">
        <div id="map"></div>
    </div>
    `;

    if (latitudeCustomer == 0 || longitudeCustomer == 0)
        mapCode = `
            <div class="location-none" style="display: flex; align-items: center; justify-content: center; height: 50%;">
                <span>Sem informações de localização</span>
            </div>
        `

    var modalWindow = `
    <div class="details-alert">
        <div class="floating-window-X">
            <button class="close-X" onclick="closeFloatingWindow()">
                <svg width="24" height="24" viewBox="0 0 25 24">
                    <line x1="18" y1="6" x2="6" y2="18" stroke="black" stroke-width="2" />
                    <line x1="6" y1="6" x2="18" y2="18" stroke="black" stroke-width="2" />
                </svg>
            </button>
        </div>
        <h2>Detalhes Adicionais</h2>
        <div class="infos-alert-container">
            <div class="information-alert">
                <div class="name-information details-customer">
                    <div class="company-info">
                        <label>Nome do cliente</label>
                        <p>${customerName}</p>
                    </div>
                    <div class="phone-information">
                        <label>Telefone</label>
                        <p>${customerPhone}</p>
                    </div>
                </div>
                <div class="chassi-information details-customer">
                    <div class="machine-info">
                        <label>Chassi</label>
                        <p>${customerChassi}</p>
                    </div>
                    <div class="machine-hours">
                        <label>Horímetro</label>
                        <p>${hoursEngine}</p>
                    </div>
                    
                </div>
                <div class="dtc-information details-customer">
                    <div class="dtc-details">
                        <label>Detalhes do alerta</label>
                        <p>${customerDtcChassi}</p>
                    </div>
                    <div class="dtc-time-info">
                        <label>Data e hora do alerta</label>
                        <p>${dateTimeDtc}</p>
                    </div>
                </div>
            </div>
            ${mapCode}
        </div>
    </div>
    `;

    addElementOnFeed(modalWindow, "div", "floating-window", ".container")

    floatingWindowDiv = document.querySelector(".floating-window");
    floatingWindowDiv.classList.add("show-floating-window");

    if (document.querySelector("#map")) {
        var map = L.map('map').setView([latitudeCustomer, longitudeCustomer], 13);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(map);

        var marker = L.marker([latitudeCustomer, longitudeCustomer]).addTo(map);
        marker.bindPopup(`<b>${latitudeCustomer}, ${longitudeCustomer}</b>`);
    }
}

function closeFloatingWindow() {
    var floatingWindowDiv = document.querySelector(".floating-window");
    floatingWindowDiv.classList.remove("show-floating-window");
    floatingWindowDiv.remove();

}

function closeDetailsMessage() {
    // Fecha o modal de detalhes da mensagem
    const modal = document.querySelector(".modal-message-details");
    if (modal) {
        modal.classList.remove("show-floating-window");
        setTimeout(() => modal.remove(), 300);
    }
}

function menuInfoWhatsApp(button) {
    if (!button) return;

    const messageDiv = button.closest(".message");
    if (!messageDiv) return;

    let companyName = "Não identificado";
    const phoneCustomer = messageDiv.querySelector(".phone-number-customer").innerHTML;
    const messageBody = messageDiv.querySelector(".message-customer").innerHTML;
    const profileName = messageDiv.querySelector(".displayed-name").innerHTML;
    const wppMsgId = messageDiv.querySelector(".message-id").innerHTML;

    alertsCustomer.forEach((alert) => {
        if (alert.ENVIADO_PARA == phoneCustomer) {
            companyName = alert.CLIENTE;
        }
    });

    // Fecha modal anterior se existir
    const existingModal = document.querySelector(".modal-message-details");
    if (existingModal) {
        existingModal.remove();
    }

    // Cria modal popup
    const modalHtml = `
        <div class="floating-window modal-message-details show-floating-window">
            <div class="details-alert" style="width: 520px; max-height: 80vh;">
                <div class="floating-window-X">
                    <button class="close-X" onclick="closeDetailsMessage()" style="background:none;border:none;cursor:pointer;opacity:0.6;transition:opacity 0.2s;">
                        <svg width="24" height="24" viewBox="0 0 25 24">
                            <line x1="18" y1="6" x2="6" y2="18" stroke="white" stroke-width="2" />
                            <line x1="6" y1="6" x2="18" y2="18" stroke="white" stroke-width="2" />
                        </svg>
                    </button>
                </div>
                <h2>Detalhes da Mensagem</h2>
                <div class="infos-alert-container">
                    <div class="field-infos-customers">
                        <label>Nome</label>
                        <p>${profileName}</p>
                        <label>Telefone</label>
                        <p>${phoneCustomer}</p>
                        <label>Mensagem Enviada</label>
                        <p>${messageBody}</p>
                        <label>Empresa</label>
                        <p>${companyName}</p>
                    </div>
                    <div class="alerts-customer-field">
                        <label>Alertas Enviados</label>
                        <div class="container-alerts-customer" style="max-height:200px;overflow-y:auto;"></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.querySelector(".container").insertAdjacentHTML("beforeend", modalHtml);

    // Adiciona os alertas
    alertsCustomer.forEach((alert) => {
        if (alert.ENVIADO_PARA == phoneCustomer) {
            const containerCustomerAlerts = document.querySelector(".modal-message-details .container-alerts-customer");
            const alertElem = `
                <div class="alert-machine" style="width:95%;margin:6px auto;">
                    <div class="alert-details">
                        <div class="alert-title">
                            <span class="alert-text" title="${alert.ALERTA}">${alert.ALERTA}</span>
                        </div>
                        <div style="font-size:0.72rem;color:#b0b0b0;margin-top:4px;">
                            <strong>${alert.CHASSI}</strong> | ${timeConverter(Date.parse(alert.DATA_ALERTA))} ${alert.HORA_ALERTA}
                        </div>
                    </div>
                </div>
            `;
            containerCustomerAlerts.insertAdjacentHTML("beforeend", alertElem);
        }
    });
}


// ═══════════════════════════════════════════════════════════════════
// TOGGLE ENVIO WPP — sidebar Configurações
// Endpoints: GET /api/config/wpp-mode  e  POST /api/config/wpp-mode
// Modos suportados pelo backend: 'AUTO' | 'FORCE_ON' | 'FORCE_OFF'
// AUTO       -> respeita business_hours (08h-17h50 Seg-Sex)
// FORCE_ON   -> envia sempre (ignora horário)
// FORCE_OFF  -> bloqueia envio até nova ordem
// ═══════════════════════════════════════════════════════════════════

const _WPP_MODE_LABELS = {
  AUTO:      "Automático",
  FORCE_ON:  "Sempre ligado",
  FORCE_OFF: "Pausado",
};

async function loadWppMode() {
  const statusEl = document.getElementById("wpp-mode-status");
  const wppBlock = document.querySelector(".wpp-mode-block");
  // O divider "Envio WhatsApp" é o .settings-divider imediatamente antes de .wpp-mode-block
  const wppDivider = wppBlock ? wppBlock.previousElementSibling : null;

  try {
    const resp = await fetch("/api/config/wpp-mode", { credentials: "same-origin" });

    // 403 = usuário não é admin -> esconde seção inteira
    if (resp.status === 403) {
      if (wppBlock)   wppBlock.style.display = "none";
      if (wppDivider) wppDivider.style.display = "none";
      return;
    }

    if (!resp.ok) {
      if (statusEl) statusEl.textContent = "Não foi possível carregar o modo atual";
      return;
    }
    const data = await resp.json();
    if (data && data.mode) {
      _updateWppModeUI(data.mode, data.updated_by, data.updated_at);
    }
  } catch (e) {
    console.warn("[wpp-mode] erro ao carregar:", e);
    if (statusEl) statusEl.textContent = "Erro ao carregar modo (offline?)";
  }
}

async function setWppMode(mode) {
  const allowed = ["AUTO", "FORCE_ON", "FORCE_OFF"];
  if (!allowed.includes(mode)) return;

  // Trava UI durante a chamada para evitar duplo-clique
  const buttons = document.querySelectorAll(".wpp-mode-btn");
  buttons.forEach(b => b.disabled = true);

  try {
    const resp = await fetch("/api/config/wpp-mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ mode }),
    });

    if (!resp.ok) {
      let msg = resp.statusText;
      try { msg = (await resp.json()).error || msg; } catch (_) { /* noop */ }
      alert(`Falha ao alterar modo: ${msg}`);
      return;
    }

    const data = await resp.json();
    _updateWppModeUI(data.mode, "(você)", new Date().toISOString());
  } catch (e) {
    alert(`Erro ao alterar modo: ${e.message}`);
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

function _updateWppModeUI(mode, who, updatedAt) {
  // 1) marca botão ativo
  document.querySelectorAll(".wpp-mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });

  // 2) atualiza linha de status
  const statusEl = document.getElementById("wpp-mode-status");
  if (!statusEl) return;

  const label = _WPP_MODE_LABELS[mode] || mode;
  let timeStr = "";
  if (updatedAt) {
    try {
      const d = new Date(updatedAt);
      if (!isNaN(d.getTime())) {
        timeStr = ` <span class="wpp-mode-by">· ${d.toLocaleString("pt-BR")}</span>`;
      }
    } catch (_) { /* noop */ }
  }
  const byStr = who ? ` <span class="wpp-mode-by">por ${who}</span>` : "";
  statusEl.innerHTML = `Modo atual: <strong>${label}</strong>${byStr}${timeStr}`;
}

// Boot — carrega o modo assim que o DOM tiver pronto
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadWppMode);
} else {
  loadWppMode();
}

// ============================================================
// LOGS MODAL — Configuracoes -> Ver Logs
// ============================================================
//
// 3 abas: Alertas (DB), Envios WPP (DB filtrado), Sistema (file).
// Endpoints (ver connection/server.js):
//   GET /api/logs/alertas?limit=50&filter=all|enviados|pendentes
//   GET /api/logs/envios?limit=50
//   GET /api/logs/sistema?lines=200&level=ALL|INFO|WARNING|ERROR
//
// Estado: aba ativa fica em _LOGS_STATE.activeTab
// ============================================================

const _LOGS_STATE = { activeTab: "alertas" };

function openLogsModal() {
  const m = document.getElementById("logs-modal");
  if (!m) return;
  m.style.display = "flex";
  switchLogTab(_LOGS_STATE.activeTab);
}

function closeLogsModal() {
  const m = document.getElementById("logs-modal");
  if (m) m.style.display = "none";
}

function closeLogsModalIfBackdrop(ev) {
  if (ev && ev.target && ev.target.id === "logs-modal") closeLogsModal();
}

function switchLogTab(tab) {
  _LOGS_STATE.activeTab = tab;
  // Tabs visuais
  document.querySelectorAll(".logs-tab").forEach((b) => {
    b.classList.toggle("logs-tab-active", b.dataset.tab === tab);
  });
  // Toolbars (so 1 visivel por vez)
  ["alertas", "envios", "sistema"].forEach((t) => {
    const tb = document.getElementById("logs-toolbar-" + t);
    if (tb) tb.style.display = t === tab ? "flex" : "none";
    const pn = document.getElementById("logs-pane-" + t);
    if (pn) pn.style.display = t === tab ? "block" : "none";
  });
  // Carrega dados
  if (tab === "alertas") loadLogsAlertas();
  else if (tab === "envios") loadLogsEnvios();
  else if (tab === "sistema") loadLogsSistema();
}

function refreshActiveLogTab() {
  switchLogTab(_LOGS_STATE.activeTab);
}

// ----- Helpers de render -----
function _logsEscapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _logsFormatDate(d) {
  if (!d) return "—";
  // Vem como "2026-04-25T..." ou "2026-04-25"
  const s = String(d).slice(0, 10);
  const parts = s.split("-");
  if (parts.length === 3) return parts[2] + "/" + parts[1] + "/" + parts[0];
  return s;
}

function _logsFormatHora(h) {
  if (!h) return "—";
  // Vem como "14:30:00" ou objeto
  return String(h).slice(0, 5);
}

function _logsRenderTableAlertas(alertas) {
  if (!alertas || !alertas.length) {
    return '<div class="logs-empty">Nenhum alerta encontrado.</div>';
  }
  let html = '<table class="logs-table"><thead><tr>';
  html += "<th>ID</th><th>Cliente</th><th>Chassi</th><th>Alerta</th><th>Data/Hora</th><th>Status</th>";
  html += "</tr></thead><tbody>";
  for (const a of alertas) {
    const pill =
      a.status === "enviado"  ? '<span class="logs-pill logs-pill-enviado">ENVIADO</span>' :
      a.status === "falha"    ? '<span class="logs-pill logs-pill-falha">FALHA</span>' :
                                '<span class="logs-pill logs-pill-pendente">PENDENTE</span>';
    html += "<tr>";
    html += '<td class="col-id">' + _logsEscapeHtml(a.id) + "</td>";
    html += "<td>" + _logsEscapeHtml(a.cliente) + "</td>";
    html += '<td class="col-chassi">' + _logsEscapeHtml(a.chassi) + "</td>";
    html += "<td>" + _logsEscapeHtml(a.alerta) + "</td>";
    html += '<td class="col-data">' + _logsFormatDate(a.data) + " " + _logsFormatHora(a.hora) + "</td>";
    html += "<td>" + pill + "</td>";
    html += "</tr>";
  }
  html += "</tbody></table>";
  return html;
}

function _logsRenderTableEnvios(envios) {
  if (!envios || !envios.length) {
    return '<div class="logs-empty">Nenhum envio registrado.</div>';
  }
  let html = '<table class="logs-table"><thead><tr>';
  html += "<th>ID</th><th>Cliente</th><th>Chassi</th><th>Telefone</th><th>Data/Hora</th><th>Msg ID</th>";
  html += "</tr></thead><tbody>";
  for (const a of envios) {
    html += "<tr>";
    html += '<td class="col-id">' + _logsEscapeHtml(a.id) + "</td>";
    html += "<td>" + _logsEscapeHtml(a.cliente) + "</td>";
    html += '<td class="col-chassi">' + _logsEscapeHtml(a.chassi) + "</td>";
    html += "<td>" + _logsEscapeHtml(a.enviado_para) + "</td>";
    html += '<td class="col-data">' + _logsFormatDate(a.data) + " " + _logsFormatHora(a.hora) + "</td>";
    html += '<td class="col-msgid" title="' + _logsEscapeHtml(a.msg_id || "") + '">' + _logsEscapeHtml(a.msg_id || "—") + "</td>";
    html += "</tr>";
  }
  html += "</tbody></table>";
  return html;
}

function _logsRenderSistema(lines) {
  if (!lines || !lines.length) {
    return '<div class="logs-empty">Sem entradas de log.</div>';
  }
  let html = '<pre class="logs-system-pre">';
  for (const l of lines) {
    let cls = "logs-system-line";
    if (l.includes("[ERROR]")) cls += " lvl-ERROR";
    else if (l.includes("[WARNING]")) cls += " lvl-WARNING";
    else if (l.includes("[INFO]")) cls += " lvl-INFO";
    html += '<span class="' + cls + '">' + _logsEscapeHtml(l) + "</span>";
  }
  html += "</pre>";
  return html;
}

// ----- Loaders (chamadas REST) -----
async function loadLogsAlertas() {
  const pane = document.getElementById("logs-pane-alertas");
  const status = document.getElementById("logs-status-alertas");
  const filter = (document.getElementById("logs-filter-alertas") || {}).value || "all";
  const limit = (document.getElementById("logs-limit-alertas") || {}).value || 50;
  if (!pane) return;
  pane.innerHTML = '<div class="logs-loading">Carregando…</div>';
  try {
    const r = await fetch("/api/logs/alertas?filter=" + encodeURIComponent(filter) + "&limit=" + encodeURIComponent(limit), { credentials: "include" });
    if (!r.ok) {
      const t = await r.text();
      throw new Error("HTTP " + r.status + ": " + t.slice(0, 200));
    }
    const data = await r.json();
    pane.innerHTML = _logsRenderTableAlertas(data.alertas);
    if (status) status.textContent = (data.count || 0) + " registro(s) — filtro: " + (data.filter || "all");
  } catch (e) {
    pane.innerHTML = '<div class="logs-error">Erro ao carregar alertas: ' + _logsEscapeHtml(e.message) + "</div>";
    if (status) status.textContent = "erro";
  }
}

async function loadLogsEnvios() {
  const pane = document.getElementById("logs-pane-envios");
  const status = document.getElementById("logs-status-envios");
  const limit = (document.getElementById("logs-limit-envios") || {}).value || 50;
  if (!pane) return;
  pane.innerHTML = '<div class="logs-loading">Carregando…</div>';
  try {
    const r = await fetch("/api/logs/envios?limit=" + encodeURIComponent(limit), { credentials: "include" });
    if (!r.ok) {
      const t = await r.text();
      throw new Error("HTTP " + r.status + ": " + t.slice(0, 200));
    }
    const data = await r.json();
    pane.innerHTML = _logsRenderTableEnvios(data.envios);
    if (status) status.textContent = (data.count || 0) + " envio(s)";
  } catch (e) {
    pane.innerHTML = '<div class="logs-error">Erro ao carregar envios: ' + _logsEscapeHtml(e.message) + "</div>";
    if (status) status.textContent = "erro";
  }
}

async function loadLogsSistema() {
  const pane = document.getElementById("logs-pane-sistema");
  const status = document.getElementById("logs-status-sistema");
  const level = (document.getElementById("logs-level-sistema") || {}).value || "ALL";
  const lines = (document.getElementById("logs-lines-sistema") || {}).value || 200;
  if (!pane) return;
  pane.innerHTML = '<div class="logs-loading">Carregando…</div>';
  try {
    const r = await fetch("/api/logs/sistema?level=" + encodeURIComponent(level) + "&lines=" + encodeURIComponent(lines), { credentials: "include" });
    if (!r.ok) {
      const t = await r.text();
      throw new Error("HTTP " + r.status + ": " + t.slice(0, 200));
    }
    const data = await r.json();
    pane.innerHTML = _logsRenderSistema(data.lines);
    if (status) {
      const note = data.note ? " (" + data.note + ")" : "";
      status.textContent = (data.count || 0) + " linha(s) — nivel: " + (data.level || "ALL") + note;
    }
    // Auto scroll para o final (logs mais recentes)
    pane.scrollTop = pane.scrollHeight;
  } catch (e) {
    pane.innerHTML = '<div class="logs-error">Erro ao carregar log do sistema: ' + _logsEscapeHtml(e.message) + "</div>";
    if (status) status.textContent = "erro";
  }
}

// Tecla ESC fecha o modal
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") {
    const m = document.getElementById("logs-modal");
    if (m && m.style.display !== "none") closeLogsModal();
    // ESC também fecha o chat panel
    const cp = document.getElementById("chat-panel");
    if (cp && cp.classList.contains("chat-panel-open")) closeChatPanel();
  }
});

// ============================================================
// CHAT IN-APP — Atendimento via WhatsApp direto pelo RTS
// ============================================================
//
// Fluxo:
//   1. Operador clica "Iniciar Atendimento" → startAssist() abre chat
//   2. Chat carrega histórico (GET /api/chat/history/:tel)
//   3. Operador envia mensagem (POST /api/chat/send)
//   4. Mensagens recebidas chegam via Socket.IO "chatMessage"
//   5. Ao encerrar, endAssist() fecha o chat
//
// A janela de 24h da WhatsApp Business API é verificada:
//   - No carregamento do histórico (backend calcula windowOpen)
//   - No envio (backend retorna 422 WINDOW_EXPIRED se expirou)
//   - No frontend (timer visual mostrando tempo restante)
// ============================================================

const _chatState = {
  telefone: null,
  idSolicitacao: null,
  profileName: null,
  windowOpen: false,
  windowExpiresAt: null,
  _timerInterval: null,
  _minimized: false,
  _unread: 0,
};

/**
 * Abre o chat panel para um cliente.
 * Chamado após startAssist() marcar o atendimento.
 */
async function openChatPanel(telefone, idSolicitacao, profileName) {
  // Se já está minimizado para o MESMO telefone, apenas reabre
  if (_chatState._minimized && _chatState.telefone === telefone) {
    _restoreChatPanel();
    return;
  }

  _chatState.telefone = telefone;
  _chatState.idSolicitacao = idSolicitacao;
  _chatState.profileName = profileName || telefone;
  _chatState._minimized = false;
  _chatState._unread = 0;

  const panel = document.getElementById("chat-panel");
  if (!panel) return;

  // Atualiza header do chat
  const nameEl = document.getElementById("chat-client-name");
  const phoneEl = document.getElementById("chat-client-phone");
  if (nameEl) nameEl.textContent = _chatState.profileName;
  if (phoneEl) phoneEl.textContent = telefone;

  // Limpa mensagens anteriores
  const body = document.getElementById("chat-messages");
  if (body) body.innerHTML = '<div class="chat-loading">Carregando histórico…</div>';

  // Abre painel
  panel.classList.add("chat-panel-open");
  _hideChatFab();

  // Notifica o socket para receber mensagens deste telefone
  socket.emit("chatOpen", { telefone });

  // Carrega histórico
  try {
    const resp = await fetch(`/api/chat/history/${encodeURIComponent(telefone)}`, {
      credentials: "same-origin",
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();

    _chatState.windowOpen = data.windowOpen;
    _chatState.windowExpiresAt = data.windowExpiresAt;
    _updateChatWindowStatus();

    // Renderiza mensagens
    if (body) {
      body.innerHTML = "";
      if (data.messages && data.messages.length > 0) {
        data.messages.forEach((m) => _appendChatBubble(m));
      } else {
        body.innerHTML = '<div class="chat-empty">Nenhuma mensagem ainda. A conversa será iniciada quando você enviar a primeira mensagem.</div>';
      }
      body.scrollTop = body.scrollHeight;
    }
  } catch (err) {
    console.error("[chat] Erro ao carregar histórico:", err);
    if (body) body.innerHTML = '<div class="chat-error">Erro ao carregar histórico.</div>';
  }

  // Foco no input
  const input = document.getElementById("chat-input");
  if (input) input.focus();
}

/**
 * Minimiza o chat panel (X ou ESC).
 * O estado é preservado, o socket continua recebendo mensagens,
 * e um botão flutuante (FAB) aparece para reabrir.
 */
function closeChatPanel() {
  if (!_chatState.telefone) return; // nada aberto

  const panel = document.getElementById("chat-panel");
  if (panel) panel.classList.remove("chat-panel-open");

  _chatState._minimized = true;
  _chatState._unread = 0;
  // NÃO emite chatClose — socket continua roteando mensagens
  _showChatFab();
}

/**
 * Restaura o chat minimizado (clique no FAB).
 * Não recarrega histórico — as mensagens já estão no DOM.
 */
function _restoreChatPanel() {
  const panel = document.getElementById("chat-panel");
  if (!panel) return;

  panel.classList.add("chat-panel-open");
  _chatState._minimized = false;
  _chatState._unread = 0;
  _hideChatFab();

  // Scroll até o final para mostrar mensagens novas
  const body = document.getElementById("chat-messages");
  if (body) body.scrollTop = body.scrollHeight;

  const input = document.getElementById("chat-input");
  if (input) input.focus();
}

/**
 * Fecha o chat DE VERDADE — chamado apenas por submitEndAssist().
 * Limpa estado, encerra subscription do socket.
 */
function _closeChatPanelFinal() {
  const panel = document.getElementById("chat-panel");
  if (panel) panel.classList.remove("chat-panel-open");

  socket.emit("chatClose");

  _chatState.telefone = null;
  _chatState.idSolicitacao = null;
  _chatState.profileName = null;
  _chatState._minimized = false;
  _chatState._unread = 0;
  if (_chatState._timerInterval) {
    clearInterval(_chatState._timerInterval);
    _chatState._timerInterval = null;
  }
  _hideChatFab();
}

/** Mostra o FAB (botão flutuante) de chat minimizado */
function _showChatFab() {
  let fab = document.getElementById("chat-fab");
  if (!fab) {
    fab = document.createElement("button");
    fab.id = "chat-fab";
    fab.className = "chat-fab";
    fab.title = "Reabrir chat";
    fab.onclick = function () { _restoreChatPanel(); };
    fab.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <span id="chat-fab-badge" class="chat-fab-badge" style="display:none;">0</span>
    `;
    document.body.appendChild(fab);
  }
  fab.style.display = "flex";
  _updateChatFabBadge();
}

/** Esconde o FAB */
function _hideChatFab() {
  const fab = document.getElementById("chat-fab");
  if (fab) fab.style.display = "none";
}

/** Atualiza badge de não lidas no FAB */
function _updateChatFabBadge() {
  const badge = document.getElementById("chat-fab-badge");
  if (!badge) return;
  if (_chatState._unread > 0) {
    badge.textContent = _chatState._unread > 99 ? "99+" : _chatState._unread;
    badge.style.display = "flex";
  } else {
    badge.style.display = "none";
  }
}

/** Envia mensagem de texto via chat */
async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  if (!input || !input.value.trim()) return;
  if (!_chatState.telefone) return;

  const mensagem = input.value.trim();
  input.value = "";

  // Desabilita botão durante envio
  if (sendBtn) sendBtn.disabled = true;

  try {
    const resp = await fetch("/api/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        telefone: _chatState.telefone,
        mensagem,
        idSolicitacao: _chatState.idSolicitacao,
      }),
    });

    const data = await resp.json();

    if (!resp.ok) {
      if (data.code === "WINDOW_EXPIRED") {
        _chatState.windowOpen = false;
        _updateChatWindowStatus();
        _showChatError("Janela de 24h expirada. Aguarde o cliente enviar nova mensagem.");
      } else {
        _showChatError(data.error || "Erro ao enviar mensagem.");
      }
      // Devolve o texto ao input para o usuário não perder
      input.value = mensagem;
      return;
    }

    // Mensagem enviada com sucesso — a bolha será adicionada via chatMessage do Socket.IO
  } catch (err) {
    console.error("[chat] Erro ao enviar:", err);
    _showChatError("Erro de conexão ao enviar mensagem.");
    input.value = mensagem;
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    input.focus();
  }
}

/** Adiciona uma bolha de mensagem no chat */
function _appendChatBubble(msg) {
  const body = document.getElementById("chat-messages");
  if (!body) return;

  // Remove placeholder de "nenhuma mensagem" se existir
  const empty = body.querySelector(".chat-empty");
  if (empty) empty.remove();

  const isOut = msg.direcao === "out";
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble chat-bubble-${isOut ? "out" : "in"}`;

  const time = msg.data_hora
    ? new Date(msg.data_hora).toLocaleString("pt-BR", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })
    : "";

  const sender = isOut
    ? (msg.remetente || "Operador")
    : (msg.remetente || "Cliente");

  bubble.innerHTML = `
    <div class="chat-bubble-sender">${_chatEscape(sender)}</div>
    <div class="chat-bubble-text">${_chatEscape(msg.mensagem)}</div>
    <div class="chat-bubble-time">${time}</div>
  `;

  body.appendChild(bubble);
  body.scrollTop = body.scrollHeight;
}

/** Escape HTML para prevenir XSS no chat */
function _chatEscape(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/** Mostra erro temporário no chat */
function _showChatError(msg) {
  const body = document.getElementById("chat-messages");
  if (!body) return;
  const el = document.createElement("div");
  el.className = "chat-error-inline";
  el.textContent = msg;
  body.appendChild(el);
  body.scrollTop = body.scrollHeight;
  setTimeout(() => el.remove(), 8000);
}

/** Atualiza indicador de janela de 24h */
function _updateChatWindowStatus() {
  const statusEl = document.getElementById("chat-window-status");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");

  if (!statusEl) return;

  if (_chatState._timerInterval) {
    clearInterval(_chatState._timerInterval);
    _chatState._timerInterval = null;
  }

  if (!_chatState.windowOpen) {
    statusEl.innerHTML = '<span class="chat-window-expired">Janela de 24h expirada — aguarde nova mensagem do cliente</span>';
    statusEl.className = "chat-window-status chat-window-closed";
    if (input) input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    return;
  }

  if (input) input.disabled = false;
  if (sendBtn) sendBtn.disabled = false;

  // Timer countdown
  function updateTimer() {
    if (!_chatState.windowExpiresAt) return;
    const remaining = new Date(_chatState.windowExpiresAt).getTime() - Date.now();
    if (remaining <= 0) {
      _chatState.windowOpen = false;
      _updateChatWindowStatus();
      return;
    }
    const hours = Math.floor(remaining / (1000 * 60 * 60));
    const mins = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
    statusEl.innerHTML = `<span class="chat-window-open">Janela aberta — ${hours}h ${mins}min restantes</span>`;
    statusEl.className = "chat-window-status chat-window-open-status";
  }

  updateTimer();
  _chatState._timerInterval = setInterval(updateTimer, 30000); // atualiza a cada 30s
}

// ── Socket.IO listener para chat está no index.html (inline script),
// porque o `socket` é declarado lá via `const socket = io()`.
// As funções _appendChatBubble e _updateChatWindowStatus acima são
// chamadas pelo listener no index.html.
