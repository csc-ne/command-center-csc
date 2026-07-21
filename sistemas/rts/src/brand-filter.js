/**
 * BRAND FILTER — Filtro por John Deere / Wirtgen
 * Filters the feed and amount cards by brand based on chassis data
 */

console.log('[BRAND-FILTER] Script carregado');

// Estado global do filtro
let currentBrandFilter = 'ALL'; // 'ALL', 'JD', 'WTG'

/**
 * Detecta se um chassi é John Deere (começa com "JD")
 */
function isChassiJD(chassis) {
    if (!chassis) return false;
    return chassis.toUpperCase().startsWith('JD');
}

/**
 * Seleciona filtro de marca
 */
function selectBrandFilter(brand) {
    currentBrandFilter = brand;

    // Atualizar select dropdowns (pode haver múltiplos em diferentes páginas)
    const selectDropdowns = document.querySelectorAll('#brand-filter-select');
    selectDropdowns.forEach(dropdown => {
        if (dropdown) {
            dropdown.value = brand;
        }
    });

    console.log('[BRAND-FILTER] Filtro selecionado: ' + brand);

    // Aplicar filtro ao feed (mostra/oculta mensagens)
    applyBrandFilterToFeed();

    // Recalcular stats
    setTimeout(() => {
        recalculateStatsForBrandFilter();
    }, 50);
}

/**
 * Aplica o filtro de marca ao feed (mostra/oculta mensagens)
 */
function applyBrandFilterToFeed() {
    const messages = document.querySelectorAll('.message');

    messages.forEach((msg) => {
        // Procurar pelo chassi na mensagem
        const pinElements = msg.querySelectorAll('.pin');
        let shouldShow = true;

        if (pinElements.length > 0) {
            const chassis = pinElements[0].innerHTML;
            const isJD = isChassiJD(chassis);

            // Aplicar filtro baseado na marca do chassi
            if (currentBrandFilter === 'JD' && !isJD) {
                shouldShow = false; // Ocultar Wirtgen se filtro é JD
            } else if (currentBrandFilter === 'WTG' && isJD) {
                shouldShow = false; // Ocultar JD se filtro é Wirtgen
            }
            // Se currentBrandFilter === 'ALL', shouldShow permanece true
        }

        // Aplicar classe hidden
        if (shouldShow) {
            msg.classList.remove('hidden');
        } else {
            msg.classList.add('hidden');
        }
    });

    console.log('[BRAND-FILTER] Feed filtrado para marca: ' + currentBrandFilter);
}

/**
 * Recalcula as estatísticas baseado no filtro de marca atual
 */
function recalculateStatsForBrandFilter() {
    const messages = document.querySelectorAll('.message');
    let alertCount = 0;
    let supportCount = 0;
    let assistedCount = 0;
    let waitingCount = 0;

    messages.forEach((msg) => {
        const isHidden = msg.classList.contains('hidden');

        // Verificar se a mensagem está visível (não oculta)
        if (!isHidden) {
            // Contar alerts
            if (msg.classList.contains('alert-info')) {
                alertCount++;
            }

            // Contar support requests
            if (msg.classList.contains('customer-needs-help')) {
                supportCount++;
            }

            // Contar waiting
            if (msg.classList.contains('waiting-assistance')) {
                waitingCount++;
            }

            // Contar assisted (status com emoji verde ou azul)
            const statusEl = msg.querySelector('.treatment-level');
            if (statusEl && (statusEl.innerHTML.includes('🟢') || statusEl.innerHTML.includes('🔵'))) {
                assistedCount++;
            }
        }
    });

    // Atualizar elementos KPI
    const alertElem = document.getElementById('number-alert-sended');
    const supportElem = document.getElementById('number-requested-support');
    const assistedElem = document.getElementById('number-customers-assisted');
    const waitingElem = document.getElementById('number-customers-waiting');

    if (alertElem) alertElem.innerHTML = alertCount;
    if (supportElem) supportElem.innerHTML = supportCount;
    if (assistedElem) assistedElem.innerHTML = assistedCount;
    if (waitingElem) waitingElem.innerHTML = waitingCount;

    console.log('[BRAND-FILTER] Stats atualizados - Alertas: ' + alertCount + ', Suporte: ' + supportCount + ', Atendidos: ' + assistedCount + ', Aguardando: ' + waitingCount);
}

/**
 * Inicializa o filtro de marca
 */
function initBrandFilter() {
    console.log('[BRAND-FILTER] Filtro de marca inicializado');

    currentBrandFilter = 'ALL';
    const selectDropdowns = document.querySelectorAll('#brand-filter-select');
    selectDropdowns.forEach(dropdown => {
        if (dropdown) {
            dropdown.value = 'ALL';
        }
    });
}

// Inicializar quando DOM está pronto
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        initBrandFilter();
    }, 100);
});
