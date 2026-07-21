# =========== RTS - REAL TIME SUPPORT ============
# GERENCIADOR AUTOMÁTICO DE TOKEN WHATSAPP (META)
# ================================================
#
# Estratégia:
#   1. A cada 30 minutos, verifica o tempo de expiração do TKWPP via
#      endpoint /debug_token da Meta API.
#   2. Se o token expira em menos de 24 horas (ou já expirou), tenta
#      fazer o exchange por um token de longa duração (60 dias).
#      Endpoint: GET /oauth/access_token?grant_type=fb_exchange_token
#   3. Se o exchange funcionar, atualiza TKWPP no .env e em os.environ
#      automaticamente — sem precisar reiniciar o RTS.
#   4. Se o exchange falhar (token já expirado ou sem permissão), loga
#      o erro e emite um sinal de alerta para a interface.
#
# Limitação conhecida:
#   Tokens de usuário gerados no Graph Explorer expiram em ~1-2h.
#   Após o exchange, o novo token dura 60 dias.
#   Após 60 dias, um novo token precisa ser gerado manualmente no Explorer
#   e colocado no .env — o sistema fará o exchange automaticamente.
#
# Integração:
#   Instanciar WppTokenManager e chamar start_background_refresh()
#   logo após o startup do RTS.

import os
import time
import logging
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key

# ============================================================
# CONFIGURAÇÃO
# ============================================================

import platform as _platform
# .env centralizado em C:\env\.env no host Windows.
# No container Linux, o docker-compose monta esse arquivo em /app/.env.
if _platform.system() == "Windows":
    ENV_PATH = Path(r"C:\env\.env")
else:
    ENV_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / ".env"
REFRESH_INTERVAL_SEC = 30 * 60       # 30 minutos entre cada verificação
RENEW_THRESHOLD_HOURS = 24           # Renova se faltar menos de 24h para expirar
META_GRAPH_BASE = "https://graph.facebook.com"


def _load_env():
    """Recarrega o .env e retorna os valores necessários."""
    load_dotenv(ENV_PATH, override=True)
    return {
        "token":      os.environ.get("TKWPP", ""),
        "app_id":     os.environ.get("APP_ID", ""),
        "app_secret": os.environ.get("APP_SECRET", ""),
    }


def debug_token(token: str, app_id: str, app_secret: str) -> dict:
    """
    Chama /debug_token para verificar validade e tempo de expiração.

    Retorna dict com:
      - valid (bool)
      - expires_at (int, unix timestamp — 0 se não expirar nunca)
      - error (str | None)
    """
    if not token or not app_id or not app_secret:
        return {"valid": False, "expires_at": 0, "error": "Credenciais ausentes no .env"}

    url = f"{META_GRAPH_BASE}/debug_token"
    params = {
        "input_token": token,
        "access_token": f"{app_id}|{app_secret}",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            return {
                "valid": False,
                "expires_at": 0,
                "error": f"Meta API erro [{err.get('code')}]: {err.get('message')}",
            }

        info = data.get("data", {})
        return {
            "valid": info.get("is_valid", False),
            "expires_at": info.get("expires_at", 0),   # 0 = nunca expira (system user)
            "error": None,
        }

    except requests.RequestException as exc:
        return {"valid": False, "expires_at": 0, "error": str(exc)}


def exchange_for_long_lived_token(short_token: str, app_id: str, app_secret: str) -> str | None:
    """
    Faz o exchange de um token (curto ou longo prazo) por um novo token de
    longa duração (~60 dias).

    Retorna o novo token em caso de sucesso, ou None em caso de falha.
    """
    url = f"{META_GRAPH_BASE}/oauth/access_token"
    params = {
        "grant_type":        "fb_exchange_token",
        "client_id":         app_id,
        "client_secret":     app_secret,
        "fb_exchange_token": short_token,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            logging.error(
                f"[TOKEN-WPP] Exchange falhou — [{err.get('code')}] {err.get('message')}"
            )
            return None

        new_token = data.get("access_token")
        if not new_token:
            logging.error(f"[TOKEN-WPP] Exchange retornou resposta sem 'access_token': {data}")
            return None

        return new_token

    except requests.RequestException as exc:
        logging.error(f"[TOKEN-WPP] Erro de conexão no exchange: {exc}")
        return None


def _save_token_to_env(new_token: str) -> bool:
    """
    Salva o novo token no .env e atualiza os.environ imediatamente.
    Retorna True se conseguiu salvar no arquivo, False caso contrário.
    """
    # Atualiza em memória — vale imediatamente para send_wpp (que usa _get_token)
    os.environ["TKWPP"] = new_token

    # Tenta persistir no arquivo
    try:
        set_key(str(ENV_PATH), "TKWPP", new_token, quote_mode="never")
        logging.info("[TOKEN-WPP] TKWPP atualizado no .env com sucesso.")
        return True
    except PermissionError as e:
        logging.warning(f"[TOKEN-WPP] Não foi possível escrever no .env: {e}. Token válido apenas em memória.")
        return False


# ============================================================
# CLASSE PRINCIPAL
# ============================================================

class WppTokenManager:
    """
    Gerencia a renovação automática do token WhatsApp (TKWPP).

    Uso:
        manager = WppTokenManager(on_alert_callback=minha_funcao)
        manager.start_background_refresh()

    O callback on_alert recebe uma string de mensagem para exibir na interface.
    """

    def __init__(self, on_alert=None):
        """
        on_alert: callable(msg: str) — chamado quando há informação relevante
                  (renovação bem-sucedida, falha, token expirando, etc.)
        """
        self.on_alert = on_alert
        self._stop_event = threading.Event()
        self._thread = None

    def _emit(self, msg: str):
        """Envia mensagem para a interface (se callback configurado) e loga."""
        logging.info(msg)
        if self.on_alert:
            try:
                self.on_alert(msg)
            except Exception:
                pass

    def check_and_renew(self) -> bool:
        """
        Executa um ciclo de verificação e renovação se necessário.

        Retorna True se o token está OK (ou foi renovado com sucesso).
        Retorna False se o token expirou e não foi possível renovar.
        """
        env = _load_env()
        token     = env["token"]
        app_id    = env["app_id"]
        app_secret = env["app_secret"]

        if not token:
            self._emit("[TOKEN-WPP] ⚠️ TKWPP não configurado no .env — nenhuma ação tomada.")
            return False

        # Verifica status do token
        info = debug_token(token, app_id, app_secret)

        if info["error"]:
            self._emit(f"[TOKEN-WPP] ⚠️ Erro ao verificar token: {info['error']}")

        if not info["valid"]:
            self._emit(
                "[TOKEN-WPP] ❌ Token WhatsApp inválido ou expirado!\n"
                "  → Tentando exchange por token de longa duração...\n"
            )
            new_token = exchange_for_long_lived_token(token, app_id, app_secret)
            if new_token:
                _save_token_to_env(new_token)
                self._emit("[TOKEN-WPP] ✅ Token renovado com sucesso (longa duração ~60 dias).")
                return True
            else:
                self._emit(
                    "[TOKEN-WPP] ❌ Não foi possível renovar o token automaticamente.\n"
                    "  → Acesse https://developers.facebook.com/tools/explorer/\n"
                    "    gere um novo token, atualize TKWPP no .env.\n"
                    "    O sistema detectará automaticamente na próxima verificação.\n"
                )
                return False

        # Token válido — verifica proximidade de expiração
        expires_at = info["expires_at"]

        if expires_at == 0:
            # Token do tipo "nunca expira" (system user token)
            self._emit("[TOKEN-WPP] ✅ Token WhatsApp sem data de expiração (system user). OK.")
            return True

        import time as _time
        seconds_remaining = expires_at - int(_time.time())
        hours_remaining = seconds_remaining / 3600

        if hours_remaining < 0:
            # Expirou mas o debug_token ainda disse valid=True (raro)
            hours_remaining = 0

        if hours_remaining <= RENEW_THRESHOLD_HOURS:
            self._emit(
                f"[TOKEN-WPP] ⏳ Token expira em {hours_remaining:.1f}h. Renovando proativamente..."
            )
            new_token = exchange_for_long_lived_token(token, app_id, app_secret)
            if new_token:
                _save_token_to_env(new_token)
                self._emit(f"[TOKEN-WPP] ✅ Token renovado. Novo token válido por ~60 dias.")
                return True
            else:
                self._emit(
                    f"[TOKEN-WPP] ❌ Falha ao renovar token ({hours_remaining:.1f}h restantes).\n"
                    "  → Verifique APP_ID e APP_SECRET no .env.\n"
                )
                return False
        else:
            self._emit(
                f"[TOKEN-WPP] ✅ Token WhatsApp OK. Expira em {hours_remaining:.1f}h (~{hours_remaining/24:.1f} dias)."
            )
            return True

    def _run_loop(self):
        """Loop da thread de background — verifica a cada REFRESH_INTERVAL_SEC."""
        logging.info(f"[TOKEN-WPP] Thread de renovação iniciada (intervalo: {REFRESH_INTERVAL_SEC//60} min).")

        # Verifica imediatamente no startup
        self.check_and_renew()

        while not self._stop_event.is_set():
            # Aguarda 30 minutos (verifica stop_event a cada 30s para resposta rápida)
            for _ in range(REFRESH_INTERVAL_SEC // 30):
                if self._stop_event.is_set():
                    break
                time.sleep(30)

            if not self._stop_event.is_set():
                self.check_and_renew()

        logging.info("[TOKEN-WPP] Thread de renovação encerrada.")

    def start_background_refresh(self):
        """
        Inicia a thread de background para renovação automática.
        Seguro para chamar múltiplas vezes — não cria thread duplicada.
        """
        if self._thread and self._thread.is_alive():
            logging.debug("[TOKEN-WPP] Thread já está em execução.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="WppTokenRefresher",
            daemon=True,  # Encerra junto com o processo principal
        )
        self._thread.start()
        logging.info("[TOKEN-WPP] Renovação automática de token iniciada.")

    def stop(self):
        """Para a thread de renovação de forma segura."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logging.info("[TOKEN-WPP] Renovação automática de token parada.")


# ============================================================
# TESTE LOCAL
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    def console_alert(msg):
        print(msg)

    manager = WppTokenManager(on_alert=console_alert)
    print("Executando verificação única do token...")
    ok = manager.check_and_renew()
    print(f"Resultado: {'OK' if ok else 'FALHA'}")
