#!/usr/bin/env python3
# =========== RTS - REAL TIME SUPPORT ============
# ENTRYPOINT HEADLESS (CONTAINER)
# ================================================
#
# Este é o ponto de entrada do container rts-core.
# Roda o MessageShooter (loop de monitoramento de alertas) SEM PySide6,
# SEM janela Qt, SEM dependência da interface gráfica.
#
# Diferenças em relação a `python interface/app.py`:
#   - não importa nada de interface/ nem de PySide6
#   - todos os "signals.info_to_textbox.emit(...)" caem em logging
#   - RTS está sempre "ON" (sem botão de ligar/desligar)
#   - não há timeout de inatividade que mata o processo
#
# Execução manual (fora do container):
#   RTS_HEADLESS=1 python rts_core.py
#
# Execução dentro do container: CMD do Dockerfile.core já cuida disso.

import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ────────────────────────────────────────────────────────────
# 1) Força modo headless ANTES de qualquer import do projeto
#    (o main.py checa essa variável para decidir se importa
#    PySide6 ou usa stubs).
# ────────────────────────────────────────────────────────────
os.environ["RTS_HEADLESS"] = "1"

# ────────────────────────────────────────────────────────────
# 2) Carrega .env ANTES de importar BD_alertas.
#    BD_alertas.ConnectionBD lê credenciais como *atributos de classe*,
#    que são avaliados no momento do import. Se .env ainda não estiver
#    carregado, `host` e `user` ficam None e nenhuma conexão abre.
# ────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
except ImportError:
    sys.stderr.write("python-dotenv não instalado. Abortando.\n")
    sys.exit(1)

# .env centralizado em C:\env\.env no host Windows.
# No container Linux, o docker-compose monta esse arquivo em /app/.env
# (equivalente a Path(__file__).resolve().parent / ".env" quando o script está em /app/).
import platform as _platform
if _platform.system() == "Windows":
    ENV_PATH = Path(r"C:\env\.env")
else:
    ENV_PATH = Path(__file__).resolve().parent / ".env"

if not ENV_PATH.exists():
    sys.stderr.write(
        f"[rts-core] .env não encontrado em {ENV_PATH}. "
        "Monte o arquivo como volume no docker-compose ou crie C:\\env\\.env no host.\n"
    )
    sys.exit(2)

load_dotenv(ENV_PATH, override=False)

# ────────────────────────────────────────────────────────────
# 3) Configura logging para stdout (docker logs captura)
# ────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("RTS_LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_LEVEL_ENUM = getattr(logging, LOG_LEVEL, logging.INFO)

# stdout handler (mantem comportamento atual: docker logs continua funcionando)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
_handlers = [_stdout_handler]

# File handler rotativo: dashboard le esse arquivo via /api/logs/sistema.
# Path: /app/logs/output/rts-core.log (NAO em /app/logs porque /app/logs eh
# um package Python do projeto, com __init__.py e subdiretorios src/output/).
# Rotacao: 5MB x 5 arquivos = ~25MB max em disco.
# Falha silenciosa: se o diretorio nao existir/for read-only, segue so com stdout.
try:
    from logging.handlers import RotatingFileHandler
    _LOG_DIR = "/app/logs/output"
    os.makedirs(_LOG_DIR, exist_ok=True)
    _file_handler = RotatingFileHandler(
        os.path.join(_LOG_DIR, "rts-core.log"),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8",
    )
    _file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    _handlers.append(_file_handler)
except Exception as _e:  # noqa: BLE001 — best effort
    print(f"[rts.core] Aviso: nao foi possivel abrir file handler: {_e}", file=sys.stderr)

logging.basicConfig(
    level=_LOG_LEVEL_ENUM,
    handlers=_handlers,
    force=True,  # garante que handlers sobrescrevam config previa
)
log = logging.getLogger("rts.core")

# ────────────────────────────────────────────────────────────
# 4) Imports do projeto (agora seguros — .env carregado + flag setada)
# ────────────────────────────────────────────────────────────
try:
    from main import MessageShooter  # noqa: E402
    from business_hours import describe_window, is_business_hours  # noqa: E402
except Exception as e:
    log.exception("Falha ao importar módulos do projeto: %s", e)
    sys.exit(3)


# ────────────────────────────────────────────────────────────
# 5) Estado compartilhado (consultado pelo endpoint /status)
# ────────────────────────────────────────────────────────────
_STATE = {
    "started_at": time.time(),
    "last_loop": None,
    "last_error": None,
}


class _StatusHandler(BaseHTTPRequestHandler):
    """Endpoint HTTP mínimo para a GUI (ou qualquer cliente) verificar status."""

    def do_GET(self):
        import json

        if self.path in ("/status", "/"):
            payload = {
                "status": "ON",
                "headless": True,
                "is_business_hours": is_business_hours(),
                "business_window": describe_window(),
                "started_at": _STATE["started_at"],
                "last_loop": _STATE["last_loop"],
                "last_error": _STATE["last_error"],
                "uptime_sec": int(time.time() - _STATE["started_at"]),
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):  # silencia logs do BaseHTTPRequestHandler
        return


def _start_status_server():
    port = int(os.environ.get("RTS_STATUS_PORT", "5001"))
    try:
        server = HTTPServer(("0.0.0.0", port), _StatusHandler)
    except OSError as e:
        log.warning("Não foi possível abrir porta de status %s: %s", port, e)
        return
    log.info("Status HTTP escutando em 0.0.0.0:%s (/status, /healthz)", port)
    server.serve_forever()


# ────────────────────────────────────────────────────────────
# 6) Sinalização de shutdown (docker stop envia SIGTERM)
# ────────────────────────────────────────────────────────────
_shutdown = threading.Event()


def _handle_signal(signum, _frame):
    log.info("Sinal %s recebido — encerrando rts-core.", signum)
    _shutdown.set()
    # sys.exit encerra o processo e o MessageShooter (thread filha) morre junto
    sys.exit(0)


for _sig in (signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, _handle_signal)
    except (ValueError, OSError):
        # Em Windows SIGTERM pode não estar disponível; seguimos sem.
        pass


# ────────────────────────────────────────────────────────────
# 7) Main
# ────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("RTS-CORE (headless) iniciando...")
    log.info("Janela de expediente: %s", describe_window())
    log.info("Timezone do processo: %s", time.tzname)
    log.info("ENV path: %s", ENV_PATH)
    log.info("=" * 60)

    # Sobe endpoint de status em thread separada (daemon = morre com o processo)
    threading.Thread(target=_start_status_server, daemon=True, name="rts-status").start()

    # MessageShooter foi desenhado como QRunnable. Em modo GUI, quando run()
    # termina (por exceção ou return normal), o usuário pode clicar "Ligar"
    # de novo e um novo QRunnable é criado. Em headless não há ninguém para
    # reiniciar — por isso envelopamos run() em um loop resiliente.
    #
    # Motivação concreta: se TKWPP expira, MessageShooter.run() captura o
    # erro e retorna; o processo morreria e o Docker reiniciaria em loop.
    # Com o wrapper, o container fica vivo, loga o erro, espera RETRY_SEC
    # e reinstancia o shooter — dando tempo para o operador atualizar o
    # token no .env sem precisar recriar o container.
    RETRY_SEC = int(os.environ.get("RTS_RETRY_SEC", "30"))
    attempt = 0
    while not _shutdown.is_set():
        attempt += 1
        log.info("MessageShooter: tentativa #%d iniciando.", attempt)
        try:
            shooter = MessageShooter()
            shooter.run()
            # run() retornou sem exceção — isso só deveria acontecer em GUI
            # quando o usuário fecha a janela. Em headless tratamos como
            # "loop terminou cedo demais" e reiniciamos.
            log.warning(
                "MessageShooter.run() retornou normalmente. "
                "Reagendando em %ss (attempt #%d).",
                RETRY_SEC, attempt,
            )
        except Exception as e:  # noqa: BLE001 — propositalmente broad
            log.exception(
                "MessageShooter.run() terminou com exceção: %s. "
                "Reagendando em %ss (attempt #%d).",
                e, RETRY_SEC, attempt,
            )
            _STATE["last_error"] = f"attempt {attempt}: {e}"

        if _shutdown.is_set():
            break
        # Espera com checagem periódica de shutdown para SIGTERM responder rápido
        _shutdown.wait(timeout=RETRY_SEC)


    log.info("RTS-CORE encerrando (shutdown sinalizado).")


if __name__ == "__main__":
    main()
