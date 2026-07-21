import sys
import os

# Garante que a raiz do projeto está no sys.path para imports como logs.src.loggers
_RTS_ROOT = os.path.dirname(os.path.abspath(__file__))
if _RTS_ROOT not in sys.path:
    sys.path.insert(0, _RTS_ROOT)

from alerts_api import get_alerts, get_alerts_veneza, get_alerts_from_pg, get_all_alerts_from_pg, get_rts_alerts
from BD_alertas import *
from datetime import date, timedelta, datetime
from whatsapp_api import send_wpp, check_media_id_expiration
from batch_alert_sender import send_pending_alerts
from validators import validate_and_normalize_phone
from token_wpp_manager import WppTokenManager
from business_hours import is_business_hours, describe_window
import time

# Gate dinamico de envio WPP (toggle UI: AUTO / FORCE_ON / FORCE_OFF).
# Importacao lazy/segura: se runtime_config quebrar, fallback para
# is_business_hours() (comportamento legado).
try:
    from runtime_config import should_send_wpp as _gate_wpp_dispatch
except Exception:  # noqa: BLE001
    _gate_wpp_dispatch = None

def _should_dispatch_wpp() -> bool:
    """Retorna True se devemos disparar/capturar alertas agora.

    Combina o toggle do dashboard (runtime_config.wpp_mode) com a janela de
    horario comercial:
      - AUTO       -> respeita is_business_hours()
      - FORCE_ON   -> True (mesmo fora da janela)
      - FORCE_OFF  -> False (mesmo dentro da janela)

    Fallback: se runtime_config indisponivel, cai no comportamento original
    (is_business_hours sem argumento).
    """
    if _gate_wpp_dispatch is not None:
        try:
            return bool(_gate_wpp_dispatch())
        except Exception:  # noqa: BLE001
            pass
    return is_business_hours()

# ────────────────────────────────────────────────────────────
# Modo headless (container Docker): evita importar PySide6 /
# interface.* e substitui AppSignals por stubs que logam via
# logging.  Ativado pela variável de ambiente RTS_HEADLESS=1.
# ────────────────────────────────────────────────────────────
_RTS_HEADLESS = os.environ.get("RTS_HEADLESS") == "1"

# ────────────────────────────────────────────────────────────
# refreshing_token.py usa Selenium + bs4 para clicar no botão
# "Refresh The Access Token" do servidor Flask local (OAuth JD).
# Em modo headless (container), esse fluxo roda no HOST, não
# dentro do container — então substituímos por stubs que:
#   - exp_time()     → retorna datetime distante no futuro
#                      (o if no loop nunca aciona update_token)
#   - update_token() → no-op + log informativo
# O operador continua renovando o token JD manualmente pela GUI
# do host quando necessário.
# ────────────────────────────────────────────────────────────
if not _RTS_HEADLESS:
    from refreshing_token import exp_time, update_token
else:
    import logging as _jd_logging

    _jd_log = _jd_logging.getLogger("rts.jd_token")

    def exp_time():
        # Futuro distante: nunca satisfaz "(expTime - dt) < 1h".
        return datetime(2099, 12, 31, 23, 59, 59)

    def update_token():
        _jd_log.info(
            "[JD-TOKEN] Renovação do token JD é manual em ambiente headless "
            "(execute via GUI no host quando necessário)."
        )

if not _RTS_HEADLESS:
    from PySide6.QtCore import QRunnable, Slot
    from interface.signals.Signals import AppSignals
else:
    import logging as _logging

    _hlog = _logging.getLogger("rts.signal")

    class QRunnable:  # stub mínimo: MessageShooter herda e chama super().__init__
        def __init__(self):
            pass

    def Slot(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

    class _LogSignal:
        """Substitui pyqtSignal em headless — redireciona emit() para logging."""
        def __init__(self, name: str, level: int = _logging.INFO):
            self._name = name
            self._level = level

        def emit(self, *args):
            if not args:
                return
            payload = args[0]
            try:
                msg = str(payload).strip()
            except Exception:
                msg = repr(payload)
            if msg:
                _hlog.log(self._level, f"[{self._name}] {msg}")

        def connect(self, *a, **kw):
            # Ninguém conecta em headless; mantido por compatibilidade.
            pass

    class AppSignals:
        """Stub de sinais em headless — sem Qt."""
        def __init__(self):
            self.info_to_textbox = _LogSignal("info")
            self.error_signal = _LogSignal("error", _logging.ERROR)
            self.time_to_update = _LogSignal("tick", _logging.DEBUG)
            self.inactivity_detected = _LogSignal("inactivity")
            self.authenticate = _LogSignal("auth")
            self.dashboard_health = _LogSignal("dash")
            # Em headless, o RTS está sempre "ligado"; não há botão.
            self.status_rts = "ON"

from logs.src.loggers import Logger

logger = Logger()

# ────────────────────────────────────────────────────────────
# Gerenciador de token WhatsApp — iniciado uma única vez aqui,
# em escopo de módulo, para que a thread de renovação a cada
# 30 min funcione independentemente do MessageShooter estar
# ligado ou desligado.
# ────────────────────────────────────────────────────────────
_wpp_token_manager = WppTokenManager(
    on_alert=lambda msg: logger.info_logger(msg)
)
_wpp_token_manager.start_background_refresh()


class MessageShooter(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = AppSignals()

        # Atualiza o callback do gerenciador de token para também emitir
        # mensagens na interface gráfica (textbox do RTS).
        # O manager já está rodando em background; apenas atualiza o alvo.
        def _token_ui_alert(msg: str):
            logger.info_logger(msg)
            try:
                self.signals.info_to_textbox.emit(msg + "\n")
            except RuntimeError:
                pass  # Interface ainda não pronta ou já fechada

        _wpp_token_manager.on_alert = _token_ui_alert

    def check_status(self):
        self.signals.info_to_textbox.emit("RTS Desligado\n")

        c = 0
        while self.signals.status_rts == "OFF":
            print("Aguardando clique do botão")
            
            # O usuário tem 10min para religar o RTS
            # Caso contrário, será considerado inatividade
            if c == 600:
                self.signals.inactivity_detected.emit(True)
                exit()

            time.sleep(5)
            c += 5
        
        self.signals.info_to_textbox.emit("RTS Ligado")
            

    @Slot()
    def run(self):
        try:
            # ========== VERIFICAÇÃO DE STARTUP ==========
            # Verifica se Media ID está próximo de expirar
            # Se faltam menos de 3 dias, renova preemptivamente
            media_check = check_media_id_expiration(days_before_expiry=3)
            if media_check["status"] == "renewed":
                logger.info_logger(f"RTS Startup: Media ID renovado. Expira em: {media_check['expires']}")
                self.signals.info_to_textbox.emit(
                    f"✅ Media ID renovado no startup\nExpira em: {media_check['expires']}\n\n"
                )
            elif media_check["status"] == "renewal_failed":
                logger.error_logger(Exception(f"RTS Startup: Falha ao renovar Media ID. Continuando com ID anterior."))
                self.signals.info_to_textbox.emit(
                    f"⚠️ Falha ao renovar Media ID, continuando com ID anterior\n\n"
                )
            else:
                logger.info_logger(f"RTS Startup: Media ID OK. Dias restantes: {media_check.get('days_remaining', '?')}")

            # Log único da janela configurada (ajuda a confirmar no boot do container)
            self.signals.info_to_textbox.emit(
                f"Janela de expediente ativa: {describe_window()}\n"
            )

            while True:
                # Essa declaração interrompe o loop ao apertar no botão
                # da interface gráfica (ignorado em modo headless)
                if self.signals.status_rts == "OFF":
                    self.check_status()

                dt_hoje = date.today()
                dt_completa = datetime.today()
                expTime = exp_time()

                # Renovação do token JD roda 24/7 — não depende da janela
                # de expediente. (Token WPP é cuidado por WppTokenManager
                # em thread daemon separada.)
                if (expTime - dt_completa) < timedelta(hours=1):
                    update_token()

                # ──────────────────────────────────────────────────────
                # Janela de expediente (08:00–17:50 Seg–Sex por padrão)
                # Fora da janela: estrutura continua online, tokens são
                # renovados, MAS nenhum alerta é disparado e o batch
                # sender não é acionado.
                # Não damos `break` — o processo continua vivo para
                # retomar automaticamente no próximo dia útil.
                # ──────────────────────────────────────────────────────
                # NB: usa _should_dispatch_wpp() (combina is_business_hours
                # com toggle dashboard wpp_mode) para que FORCE_ON sobreponha
                # janela de expediente. Em AUTO, comportamento legado preserva.
                self.signals.info_to_textbox.emit(
                    f"[GATE-CHECK] Verificando gate WPP ({dt_completa.strftime('%d/%m %H:%M')})...\n"
                )
                if not _should_dispatch_wpp():
                    self.signals.info_to_textbox.emit(
                        f"[EXPEDIENTE] Fora do horário ({dt_completa.strftime('%d/%m %H:%M %a')}). "
                        f"Aguardando 60s. Tokens continuam sendo renovados.\n"
                    )
                    time.sleep(60)
                    continue

                self.signals.info_to_textbox.emit("[CICLO] Iniciando novo ciclo de captura...\n")

                self.bd = BancoDados(nome_tabela="Alertas")

                # ── Query unificada: busca todos os alertas RED prontos
                # para envio em UMA query (opc_machine_alerts + joins).
                # Já traz cliente, telefone, chassi, modelo, localização.
                _t_start = time.time()
                alertas_rts = get_rts_alerts()
                _t_elapsed = time.time() - _t_start
                self.signals.info_to_textbox.emit(
                    f"[CICLO] {len(alertas_rts)} alertas RED carregados em {_t_elapsed:.1f}s\n"
                )

                if not alertas_rts:
                    self.signals.info_to_textbox.emit(
                        "[CICLO] Nenhum alerta RED no período. Aguardando próximo ciclo.\n"
                    )

                for alerta in alertas_rts:
                    # Interrompe o loop ao apertar no botão da interface
                    if self.signals.status_rts == "OFF":
                        self.check_status()

                    # Re-check do gate WPP — permite que "Pausado" do
                    # dashboard interrompa o ciclo rapidamente.
                    if not _should_dispatch_wpp():
                        self.signals.info_to_textbox.emit(
                            "[GATE] Envio interrompido (toggle = Pausado).\n"
                        )
                        break

                    dtc = alerta["Alerta"]
                    chassi = alerta["Chassi"]
                    data = alerta["Data"]
                    hora = alerta["Hora"]
                    horimetro = alerta["Horimetro"]
                    latitude = alerta["Latitude"]
                    longitude = alerta["Longitude"]
                    nome_cliente = alerta["cliente"]
                    telefone = alerta["telefone"]
                    id_alert = alerta["id_alert"]
                    color_id = alerta["color_id"]
                    severity = alerta["severity"]
                    machine_model = alerta["machine_model"]
                    organization_id = alerta["organization_id"]

                    self.signals.info_to_textbox.emit(
                        f'Cliente: {nome_cliente} | {chassi[:15]} | {dtc[:50]}\n'
                    )

                    # ── Dedup diário: (chassi + alerta) já enviado hoje? ──
                    # Comparação feita no banco via CURRENT_DATE::date para
                    # evitar falso-negativo quando data_envio é TIMESTAMP
                    # (psycopg2 retornaria datetime, não date, quebrando ==).
                    ja_enviou_hoje = self.bd.consultar_hoje(chassi, dtc)

                    if ja_enviou_hoje:
                        self.signals.info_to_textbox.emit(
                            f"[DEDUP] {nome_cliente} / {chassi[:15]} — "
                            f"alerta já enviado hoje, pulando.\n"
                        )
                    else:
                        self.send_alert(
                            organization_id or 0,
                            nome_cliente,
                            chassi,
                            data,
                            hora,
                            horimetro,
                            dtc,
                            latitude,
                            longitude,
                            dt_hoje,
                            notification_id=id_alert,
                            color_id=color_id,
                            severity=severity,
                            three_letter_acronym=None,
                            machine_model=machine_model,
                        )

                # Temporizador + Batch sender
                # Intervalo reduzido: 60s entre ciclos (antes 300s) para
                # minimizar latência entre detecção e envio do alerta.
                _CYCLE_WAIT = 60
                for i in range(_CYCLE_WAIT):
                    if self.signals.status_rts == "OFF":
                        self.check_status()

                    # Batch sender roda uma vez no fim do intervalo (a cada ~60s)
                    if i == _CYCLE_WAIT - 1:
                        # Guard: se cruzou o fim do expediente durante a espera,
                        # não acionar o batch sender.
                        # Usa _should_dispatch_wpp() para respeitar override
                        # FORCE_ON/FORCE_OFF do dashboard.
                        if not _should_dispatch_wpp():
                            self.signals.info_to_textbox.emit(
                                "[BATCH] Pulado — fora do horário (ou WPP em FORCE_OFF).\n"
                            )
                        else:
                            try:
                                total, sucesso, falha = send_pending_alerts()
                                if sucesso > 0:
                                    self.signals.info_to_textbox.emit(
                                        f"\n[BATCH] ✅ {sucesso}/{total} alertas enviados via batch sender\n"
                                    )
                            except Exception as batch_err:
                                logger.error_logger(f"Erro no batch sender: {batch_err}")

                    # Manda informação para a interface
                    self.signals.time_to_update.emit(_CYCLE_WAIT - i)

                    time.sleep(1)

        except RuntimeError as err:
            # RuntimeError: Signal source has been deleted
            # Ocorre quando a janela é fechada enquanto a thread ainda está rodando.
            # Encerra silenciosamente sem gerar log de erro.
            return

        except Exception as err:
            # Armazena no log
            logger.error_logger(err)

            try:
                self.signals.error_signal.emit("Ocorreu um erro com o monitoramento de alertas do RTS. Consulte o log.")
            except RuntimeError:
                pass  # Janela já foi fechada — ignora
            

    def send_alert(
        self,
        client_id,
        customer,
        machine,
        dt,
        hour,
        hoursMeter,
        notification,
        lat,
        lng,
        delivered_date,
        # Novos campos migração PG
        notification_id=None,
        color_id=None,
        severity=None,
        three_letter_acronym=None,
        machine_model=None,
    ):

        shipping_hour = datetime.now().time().strftime("%H:%M")

        # Pega o telefone do cliente (usando parametrized query para segurança)
        try:
            # NOTA: Refatorar executar_DQL para aceitar parâmetros seria ideal
            # Temporariamente usando format string com int conversion (mais seguro que direto)
            phone_result = self.bd.executar_DQL(
                'SELECT telefone FROM rts_contatos WHERE jdlink_id = %s',
                (str(int(client_id)),)
            )
            if not phone_result:
                self.signals.info_to_textbox.emit(
                    f"\n[ERRO] Cliente {customer} (ID: {client_id}) não encontrado na tabela contatos\n"
                )
                return
            phone = phone_result[0][0]
        except Exception as db_err:
            logger.error_logger(f"Erro ao buscar telefone do cliente {customer}: {db_err}")
            self.signals.info_to_textbox.emit(
                f"\n[ERRO] Falha ao buscar telefone do cliente {customer}\n"
            )
            return

        # Validar e normalizar telefone (usando validador centralizado)
        phone_clean, is_valid_phone = validate_and_normalize_phone(phone)

        if is_valid_phone:
            # Tenta enviar WhatsApp — erros são isolados para não parar o monitoramento
            wa_id = "WPP_NAO_ENVIADO"
            msg_id = "WPP_NAO_ENVIADO"
            try:
                shipping = send_wpp(
                    phone_clean,
                    customer,
                    machine,
                    f'{dt.strftime("%d/%m/%Y")} as {hour}',
                    hoursMeter,
                    notification,
                )
                if shipping.get("status") == "skipped":
                    # Token WhatsApp não configurado — alerta registrado no BD sem envio
                    self.signals.info_to_textbox.emit(
                        f"\n[WPP] Alerta de {customer} registrado sem envio WhatsApp (TKWPP não configurado)\n"
                    )
                elif "error" in shipping:
                    # API retornou erro
                    erro = shipping.get("error", {})
                    code = erro.get('code')
                    msg_erro = f"[{code}] {erro.get('message')}"
                    logger.error_logger(Exception(f"WhatsApp API Error para {customer}: {msg_erro}"))
                    self.signals.info_to_textbox.emit(
                        f"\n[WPP] ❌ Erro ao enviar para {customer}: {msg_erro}\n"
                    )
                else:
                    # Sucesso!
                    wa_id = shipping["contacts"][0]["wa_id"]
                    msg_id = shipping["messages"][0]["id"]
                    self.signals.info_to_textbox.emit(f"\n[WPP] ✅ Alerta enviado para {customer}\n")
                    self.signals.info_to_textbox.emit(f"wa_id: {wa_id}, msg_id: {msg_id}\n")
            except Exception as wpp_err:
                err_str = str(wpp_err)
                logger.error_logger(wpp_err)
                # Mensagem específica para 401 (token inválido/expirado)
                if "401" in err_str:
                    self.signals.info_to_textbox.emit(
                        f"\n[WPP] ❌ Token WhatsApp inválido ou expirado!\n"
                        f"  → Atualize TKWPP no arquivo .env e aguarde o próximo ciclo.\n"
                    )
                else:
                    self.signals.info_to_textbox.emit(
                        f"\n[WPP] ❌ Erro ao enviar alerta para {customer}: {err_str}\n"
                    )

            # Inclusão no BD — sempre executa, independente do WhatsApp
            self.bd.incluir(
                machine,
                customer,
                notification,
                dt,
                hour,
                shipping_hour,
                lat,
                lng,
                wa_id,
                msg_id,
                hoursMeter,
                delivered_date,
                notification_id=notification_id,
                color_id=color_id,
                severity=severity,
                three_letter_acronym=three_letter_acronym,
                machine_model=machine_model,
            )

        else:
            # Telefone inválido — registro no BD com status de erro
            logger.error_logger(f"Telefone inválido para {customer}: {phone_clean} ({len(phone_clean)} dígitos)")
            self.signals.info_to_textbox.emit(
                f"\n[WPP] ⚠️ Telefone inválido para {customer}: {phone_clean}\n"
            )
            self.bd.incluir(
                machine,
                customer,
                notification,
                dt,
                hour,
                shipping_hour,
                lat,
                lng,
                "TELEFONE_INVALIDO",
                "TELEFONE_INVALIDO",
                hoursMeter,
                delivered_date,
                notification_id=notification_id,
                color_id=color_id,
                severity=severity,
                three_letter_acronym=three_letter_acronym,
                machine_model=machine_model,
            )
