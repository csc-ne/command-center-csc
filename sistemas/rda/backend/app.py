# =========== RDA - RELATORIOS DE DESEMPENHO AUTOMATICOS ============
# app.py - API Flask para geracao de relatorios PDF
# ===================================================================
#
# Este backend recebe requisicoes do frontend e gera relatorios PDF
# usando o modulo report_0.2.6.5.py (matplotlib, reportlab etc).
#
# Autenticacao: valida cookie rts_token (HMAC-SHA256) compartilhado
# com o RTS, mesmo padrao do RTA.

import os
import sys
import hmac
import hashlib
import json
import base64
import time
import shutil
import tempfile
import traceback
import threading
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # pasta rda/
BACKEND_DIR = Path(__file__).resolve().parent       # pasta rda/backend/
OUTPUT_DIR = BASE_DIR / "relatorios_gerados"
OUTPUT_DIR.mkdir(exist_ok=True)

# Forcar backend nao-interativo do matplotlib
os.environ["MPLBACKEND"] = "Agg"

# O report usa paths relativos - garante que o cwd seja o diretorio rda/
os.chdir(str(BASE_DIR))

# Adicionar diretorio base ao sys.path para imports do kernel/pdf
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# CORS - permite que o frontend (servido por outro container) acesse a API
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# ---------------------------------------------------------------------------
# Tracking de progresso de jobs (em memoria - suficiente para single-worker)
# ---------------------------------------------------------------------------
_jobs = {}
_jobs_lock = threading.Lock()

# Mutex para serializar geração de relatórios.
# O report usa os.chdir() + paths relativos (labels/, fonts/, icons/).
# os.chdir() é process-wide — execução paralela corrupta o CWD.
# Serializar é seguro porque cada relatório já roda em thread separada
# e o gargalo real é I/O (DB queries + PDF rendering), não CPU.
_report_mutex = threading.Lock()

# ---------------------------------------------------------------------------
# Autenticacao — SSO via Command Center
# ---------------------------------------------------------------------------
# O login do RDA e centralizado no Command Center, que emite o cookie
# portal_token (JWT HS256 assinado com PORTAL_JWT_SECRET). Este backend
# apenas valida esse token. A verificacao HS256 e feita manualmente com a
# stdlib (hmac/hashlib/base64) — sem dependencia nova.

_PORTAL_JWT_SECRET   = os.environ.get("PORTAL_JWT_SECRET") or ""
_COMMAND_CENTER_URL  = os.environ.get("COMMAND_CENTER_URL") or ""
_COMMAND_CENTER_PORT = os.environ.get("COMMAND_CENTER_PORT", "4001")
_RDA_PORT = int(os.environ.get("RDA_PORT", "5051"))

# ---------------------------------------------------------------------------
# Batch Mensal — IDs JD para geração automática no dia 01
#
# Fonte preferida: RDA_BATCH_CLIENTES — "Estado|ID|Nome;Estado|ID|Nome;..."
#   Permite agrupar clientes por estado e exibir o nome no front-end.
# Fallback legado: RDA_BATCH_IDS — lista de IDs separada por vírgula.
#   Se RDA_BATCH_CLIENTES estiver definido, RDA_BATCH_IDS é ignorado
#   (fonte única de verdade; evita divergência entre as duas listas).
# ---------------------------------------------------------------------------
_BATCH_CLIENTES_RAW = os.environ.get("RDA_BATCH_CLIENTES", "")
BATCH_CLIENTES = {}  # { "5766479": {"nome": "TOP Engenharia Ltda", "estado": "Salvador"} }
for _entry in _BATCH_CLIENTES_RAW.split(";"):
    _parts = [p.strip() for p in _entry.split("|")]
    if len(_parts) == 3 and _parts[1].isdigit():
        BATCH_CLIENTES[_parts[1]] = {"nome": _parts[2], "estado": _parts[0]}

if BATCH_CLIENTES:
    BATCH_IDS = list(BATCH_CLIENTES.keys())
else:
    _BATCH_IDS_RAW = os.environ.get("RDA_BATCH_IDS", "")
    BATCH_IDS = [x.strip() for x in _BATCH_IDS_RAW.split(",") if x.strip().isdigit()]
    BATCH_CLIENTES = {i: {"nome": "ID " + i, "estado": ""} for i in BATCH_IDS}

# Ordem dos estados conforme aparecem no env (para exibição no front)
BATCH_ESTADOS = []
for _c in BATCH_CLIENTES.values():
    if _c["estado"] and _c["estado"] not in BATCH_ESTADOS:
        BATCH_ESTADOS.append(_c["estado"])

BATCH_OUTPUT_DIR = BASE_DIR / "relatorios_mensais"
BATCH_OUTPUT_DIR.mkdir(exist_ok=True)


def _b64url_decode(segment):
    """Decodifica um segmento base64url (sem padding) de um JWT."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def validate_portal_token(token):
    """Valida um JWT HS256 (header.payload.signature) emitido pelo Command Center.
    Retorna o payload decodificado, ou None se invalido/expirado."""
    if not token or not _PORTAL_JWT_SECRET:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig = parts
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        if not header or header.get("alg") != "HS256":
            return None
        expected = base64.urlsafe_b64encode(
            hmac.new(
                _PORTAL_JWT_SECRET.encode(),
                (header_b64 + "." + payload_b64).encode(),
                hashlib.sha256,
            ).digest()
        ).decode().rstrip("=")
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        # jsonwebtoken grava exp em SEGUNDOS (Unix epoch).
        if not payload.get("exp") or time.time() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


def get_command_center_url(req):
    """URL do Command Center; deriva do host da requisicao se nao houver env."""
    if _COMMAND_CENTER_URL:
        return _COMMAND_CENTER_URL
    hostname = req.host.split(":")[0]
    return req.scheme + "://" + hostname + ":" + _COMMAND_CENTER_PORT


# ---------------------------------------------------------------------------
# Import tardio do modulo de relatorios
# ---------------------------------------------------------------------------

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "report_rda",
    str(BACKEND_DIR / "report_0.4.py"),
)
_report_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_report_module)
rda_py_data_movel = _report_module.rda_py_data_movel
rda_py_by_pin     = _report_module.rda_py_by_pin

# ---------------------------------------------------------------------------
# Middleware de autenticacao
# ---------------------------------------------------------------------------


@app.before_request
def check_auth():
    if request.path in ("/healthz", "/health"):
        return None

    token = request.cookies.get("portal_token")
    user = validate_portal_token(token)

    if user:
        request.rda_user = user
        return None

    if request.path.startswith("/api/") or request.path.startswith("/relatorios"):
        return jsonify({"success": False, "error": "Nao autenticado. Faca login no Command Center."}), 401

    return redirect(get_command_center_url(request))


# ---------------------------------------------------------------------------
# Health check (publico - Docker precisa acessar sem auth)
# ---------------------------------------------------------------------------

@app.route("/healthz")
def healthz():
    import datetime
    return jsonify({
        "status": "ok",
        "service": "rda-backend",
        "timestamp": datetime.datetime.now().isoformat(),
    })


# ---------------------------------------------------------------------------
# API: Gerar relatorio (assincrono com tracking de progresso)
# ---------------------------------------------------------------------------

def _run_report_job(job_id, id_jd, data_inicial, data_final, chassi=None):

    def _set_progress(pct, msg=""):
        with _jobs_lock:
            _jobs[job_id]["progress"] = min(int(pct), 100)
            _jobs[job_id]["message"] = msg

    def _progress_monitor(tmpdir, stop_event):
        """Thread auxiliar que monitora arquivos gerados no tmpdir para
        estimar progresso. Um relatório completo gera ~12-16 PDFs parciais
        e ~10+ PNGs de gráficos antes do compilado final."""
        while not stop_event.is_set():
            try:
                pdfs = len(list(Path(tmpdir).glob("*.pdf")))
                pngs = len(list(Path(tmpdir).glob("*.png")))
                # Estimativa: total esperado ~25 artefatos
                total_artefatos = pdfs + pngs
                pct = min(5 + int((total_artefatos / 25) * 85), 90)
                etapas = {
                    (0, 3): "Consultando banco de dados...",
                    (3, 8): "Processando dados...",
                    (8, 15): "Gerando gráficos...",
                    (15, 22): "Montando seções do relatório...",
                    (22, 30): "Compilando PDF final...",
                }
                msg = "Gerando relatório..."
                for (lo, hi), txt in etapas.items():
                    if lo <= total_artefatos < hi:
                        msg = txt
                        break
                if total_artefatos >= 22:
                    msg = "Compilando PDF final..."
                _set_progress(pct, msg)
            except Exception:
                pass
            stop_event.wait(2)

    tmpdir = None
    stop_monitor = threading.Event()
    monitor_thread = None
    _held_mutex = False

    try:
        tmpdir = tempfile.mkdtemp(prefix="rda_work_")

        for asset in ("labels", "fonts", "icons"):
            src_path = str(BASE_DIR / asset)
            dst_path = os.path.join(tmpdir, asset)
            if os.path.isdir(src_path):
                os.symlink(src_path, dst_path)

        # Serializa os.chdir() — process-wide, não thread-safe
        _report_mutex.acquire()
        _held_mutex = True
        os.chdir(tmpdir)

        _set_progress(5, "Consultando banco de dados...")

        # Inicia monitor de progresso
        monitor_thread = threading.Thread(
            target=_progress_monitor, args=(tmpdir, stop_monitor), daemon=True
        )
        monitor_thread.start()

        if chassi:
            pdf_name = rda_py_by_pin(
                chassi=chassi,
                data_inicial=data_inicial,
                data_final=data_final,
            )
        else:
            pdf_name = rda_py_data_movel(
                cliente_id=int(id_jd),
                data_inicial=data_inicial,
                data_final=data_final,
            )

        stop_monitor.set()

        src_file = Path(tmpdir) / pdf_name
        dst_file = OUTPUT_DIR / pdf_name

        if not src_file.exists():
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["message"] = "Erro interno: PDF nao foi gerado."
            return

        _set_progress(95, "Finalizando...")
        shutil.move(str(src_file), str(dst_file))

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = "Relatorio concluido!"
            _jobs[job_id]["result"] = {
                "pdf_url": "/relatorios/" + pdf_name,
                "filename": pdf_name,
                "cached": False,
            }

    except Exception as exc:
        traceback.print_exc()
        stop_monitor.set()
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["message"] = "Erro ao gerar relatorio: " + str(exc)

    finally:
        stop_monitor.set()
        os.chdir(str(BASE_DIR))
        if _held_mutex:
            _report_mutex.release()
        if tmpdir and os.path.isdir(tmpdir):
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


@app.route("/api/gerar-relatorio", methods=["POST"])
def gerar_relatorio():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Corpo da requisicao invalido."}), 400

    chassi    = (data.get("chassi") or "").strip()
    id_jd     = (data.get("id_jd") or "").strip()

    # Modo por chassi: id_jd nao e necessario.
    # Modo por cliente: id_jd e obrigatorio.
    if chassi:
        # Relatorio por chassi — apenas chassi e datas sao necessarios.
        pass
    elif not id_jd or not id_jd.isdigit():
        return jsonify({"message": "Informe o ID JD (numerico) ou o chassi do equipamento."}), 400

    data_inicial = (data.get("data_inicial") or "").strip()
    data_final   = (data.get("data_final") or "").strip()
    if not data_inicial or not data_final:
        return jsonify({"message": "Data inicial e data final sao obrigatorias."}), 400

    try:
        from datetime import datetime
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d")
        dt_fim = datetime.strptime(data_final, "%Y-%m-%d")
        if dt_ini > dt_fim:
            return jsonify({"message": "Data inicial deve ser anterior a data final."}), 400
    except ValueError:
        return jsonify({"message": "Formato de data invalido. Use YYYY-MM-DD."}), 400

    dt_ini_fmt = dt_ini.strftime("%d_%m_%Y")
    dt_fim_fmt = dt_fim.strftime("%d_%m_%Y")

    # Chave de cache diferente para relatorio por chassi vs por cliente
    cache_key = ("pin_" + chassi) if chassi else id_jd
    cached_filename = "relatorio_" + cache_key + "_" + dt_ini_fmt + "_" + dt_fim_fmt + ".pdf"
    cached_path = OUTPUT_DIR / cached_filename

    force_regen = data.get("force", False)

    # Cache TTL: 2 dias (172800 segundos). Apos esse prazo, regenera automaticamente.
    CACHE_TTL_SECONDS = 2 * 24 * 3600

    if cached_path.exists() and not force_regen:
        file_age = time.time() - cached_path.stat().st_mtime
        if file_age < CACHE_TTL_SECONDS:
            return jsonify({
                "pdf_url": "/relatorios/" + cached_filename,
                "filename": cached_filename,
                "cached": True,
            })
        else:
            # Cache expirado — remove e regenera
            try:
                cached_path.unlink()
            except OSError:
                pass

    job_id = str(uuid.uuid4())[:8]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "progress": 0,
            "message": "Iniciando geracao...",
            "result": None,
        }

    t = threading.Thread(
        target=_run_report_job,
        args=(job_id, id_jd, data_inicial, data_final),
        kwargs={"chassi": chassi or None},
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id, "status": "running"})


# ---------------------------------------------------------------------------
# API: Consultar progresso de um job
# ---------------------------------------------------------------------------

@app.route("/api/progresso/<job_id>")
def consultar_progresso(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"message": "Job nao encontrado."}), 404
    return jsonify(job)


# ---------------------------------------------------------------------------
# Servir PDFs gerados
# ---------------------------------------------------------------------------

@app.route("/relatorios/<path:filename>")
def servir_relatorio(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


# ---------------------------------------------------------------------------
# Batch Mensal — geração automática no dia 01
# ---------------------------------------------------------------------------

_batch_state = {
    "status": "idle",        # idle | running | done | error
    "month": None,           # "2026-07" — mês de referência
    "ids": [],               # lista de IDs a processar
    "progress": {},          # { "5766479": { "status": "done"|"running"|"pending"|"error", "progress": 0-100, "message": "...", "pdf_url": "..." } }
    "started_at": None,
    "finished_at": None,
}
_batch_lock = threading.Lock()


def _batch_month_key():
    """Retorna chave do mês atual, ex: '2026-07'."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m")


def _batch_period():
    """Retorna (data_inicial, data_final) para o batch: mês anterior inteiro.
    Ex: se hoje é 01/07/2026, retorna ('2026-06-01', '2026-07-01')."""
    from datetime import datetime
    today = datetime.now().replace(day=1)
    # data_final = dia 01 do mês atual
    data_final = today.strftime("%Y-%m-%d")
    # data_inicial = dia 01 do mês anterior
    if today.month == 1:
        data_inicial = today.replace(year=today.year - 1, month=12).strftime("%Y-%m-%d")
    else:
        data_inicial = today.replace(month=today.month - 1).strftime("%Y-%m-%d")
    return data_inicial, data_final


def _batch_marker_path(month_key):
    """Arquivo marcador que indica que o batch de um mês foi concluído."""
    return BATCH_OUTPUT_DIR / ("batch_done_" + month_key + ".marker")


def _batch_already_done(month_key):
    """Verifica se o batch do mês já foi concluído."""
    return _batch_marker_path(month_key).exists()


def _run_batch_reports():
    """Gera relatórios de frota para todos os IDs configurados, um por vez."""
    from datetime import datetime

    month_key = _batch_month_key()
    data_inicial, data_final = _batch_period()

    with _batch_lock:
        _batch_state["status"] = "running"
        _batch_state["month"] = month_key
        _batch_state["ids"] = list(BATCH_IDS)
        _batch_state["started_at"] = datetime.now().isoformat()
        _batch_state["finished_at"] = None
        _batch_state["progress"] = {}
        for id_jd in BATCH_IDS:
            _batch_state["progress"][id_jd] = {
                "status": "pending",
                "progress": 0,
                "message": "Aguardando...",
                "pdf_url": None,
                "filename": None,
            }

    had_errors = False

    def _batch_progress_monitor(id_jd, tmpdir, stop_event):
        """Monitor de progresso por ID — conta artefatos gerados no tmpdir."""
        while not stop_event.is_set():
            try:
                pdfs = len(list(Path(tmpdir).glob("*.pdf")))
                pngs = len(list(Path(tmpdir).glob("*.png")))
                total = pdfs + pngs
                pct = min(5 + int((total / 25) * 85), 90)
                if total < 3:
                    msg = "Consultando banco de dados..."
                elif total < 8:
                    msg = "Processando dados..."
                elif total < 15:
                    msg = "Gerando gráficos..."
                elif total < 22:
                    msg = "Montando seções do relatório..."
                else:
                    msg = "Compilando PDF final..."
                with _batch_lock:
                    _batch_state["progress"][id_jd]["progress"] = pct
                    _batch_state["progress"][id_jd]["message"] = msg
            except Exception:
                pass
            stop_event.wait(2)

    for id_jd in BATCH_IDS:
        with _batch_lock:
            _batch_state["progress"][id_jd]["status"] = "running"
            _batch_state["progress"][id_jd]["progress"] = 5
            _batch_state["progress"][id_jd]["message"] = "Iniciando geração..."

        tmpdir = None
        _held_mutex = False
        stop_monitor = threading.Event()

        try:
            tmpdir = tempfile.mkdtemp(prefix="rda_batch_")

            for asset in ("labels", "fonts", "icons"):
                src_path = str(BASE_DIR / asset)
                dst_path = os.path.join(tmpdir, asset)
                if os.path.isdir(src_path):
                    os.symlink(src_path, dst_path)

            _report_mutex.acquire()
            _held_mutex = True
            os.chdir(tmpdir)

            # Inicia monitor de progresso para este ID
            monitor = threading.Thread(
                target=_batch_progress_monitor,
                args=(id_jd, tmpdir, stop_monitor),
                daemon=True,
            )
            monitor.start()

            pdf_name = rda_py_data_movel(
                cliente_id=int(id_jd),
                data_inicial=data_inicial,
                data_final=data_final,
            )

            stop_monitor.set()

            src_file = Path(tmpdir) / pdf_name
            if not src_file.exists():
                raise FileNotFoundError("PDF não foi gerado: " + pdf_name)

            # Nome final: batch_mensal_<id>_<mes>.pdf
            dt_ini_fmt = data_inicial.replace("-", "_")
            dt_fim_fmt = data_final.replace("-", "_")
            final_name = "batch_mensal_" + id_jd + "_" + dt_ini_fmt + "_" + dt_fim_fmt + ".pdf"
            dst_file = BATCH_OUTPUT_DIR / final_name
            shutil.move(str(src_file), str(dst_file))

            with _batch_lock:
                _batch_state["progress"][id_jd]["status"] = "done"
                _batch_state["progress"][id_jd]["progress"] = 100
                _batch_state["progress"][id_jd]["message"] = "Concluído!"
                _batch_state["progress"][id_jd]["pdf_url"] = "/relatorios-mensais/" + final_name
                _batch_state["progress"][id_jd]["filename"] = final_name

            print("[RDA Batch] Relatório gerado: " + final_name)

        except Exception as exc:
            traceback.print_exc()
            stop_monitor.set()
            had_errors = True
            with _batch_lock:
                _batch_state["progress"][id_jd]["status"] = "error"
                _batch_state["progress"][id_jd]["progress"] = 0
                _batch_state["progress"][id_jd]["message"] = "Erro: " + str(exc)

        finally:
            stop_monitor.set()
            os.chdir(str(BASE_DIR))
            if _held_mutex:
                _report_mutex.release()
            if tmpdir and os.path.isdir(tmpdir):
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception:
                    pass

    # Marcar batch como concluído
    with _batch_lock:
        _batch_state["status"] = "error" if had_errors else "done"
        _batch_state["finished_at"] = datetime.now().isoformat()

    if not had_errors:
        try:
            _batch_marker_path(month_key).write_text(datetime.now().isoformat())
        except Exception:
            pass

    print("[RDA Batch] Batch mensal finalizado. Status: " + _batch_state["status"])


def _batch_scheduler():
    """Thread daemon que verifica a cada hora se é dia 01 e se o batch
    do mês atual ainda não foi executado. Se sim, dispara a geração."""
    while True:
        try:
            from datetime import datetime
            now = datetime.now()
            month_key = now.strftime("%Y-%m")

            if (now.day == 1
                    and BATCH_IDS
                    and not _batch_already_done(month_key)
                    and _batch_state["status"] != "running"):
                print("[RDA Batch] Dia 01 detectado — iniciando batch mensal para " + str(len(BATCH_IDS)) + " IDs.")
                _run_batch_reports()
        except Exception as exc:
            print("[RDA Batch] Erro no scheduler: " + str(exc))
            traceback.print_exc()

        # Verifica a cada 1 hora
        time.sleep(3600)


# ---------------------------------------------------------------------------
# API: Status do batch mensal
# ---------------------------------------------------------------------------

@app.route("/api/batch-mensal/status")
def batch_mensal_status():
    with _batch_lock:
        return jsonify({
            "status": _batch_state["status"],
            "month": _batch_state["month"],
            "ids": _batch_state["ids"],
            "clientes": BATCH_CLIENTES,
            "estados": BATCH_ESTADOS,
            "progress": _batch_state["progress"],
            "started_at": _batch_state["started_at"],
            "finished_at": _batch_state["finished_at"],
        })


@app.route("/api/batch-mensal/trigger", methods=["POST"])
def batch_mensal_trigger():
    """Disparo manual do batch (para testes ou reprocessamento)."""
    if _batch_state["status"] == "running":
        return jsonify({"message": "Batch já está em execução."}), 409

    if not BATCH_IDS:
        return jsonify({"message": "Nenhum ID configurado em RDA_BATCH_IDS."}), 400

    t = threading.Thread(target=_run_batch_reports, daemon=True)
    t.start()
    return jsonify({"message": "Batch mensal iniciado.", "ids": BATCH_IDS})


# ---------------------------------------------------------------------------
# Servir PDFs do batch mensal
# ---------------------------------------------------------------------------

@app.route("/relatorios-mensais/<path:filename>")
def servir_relatorio_mensal(filename):
    return send_from_directory(str(BATCH_OUTPUT_DIR), filename)


# ---------------------------------------------------------------------------
# Limpeza de cache expirado (roda no startup e a cada 6 horas)
# ---------------------------------------------------------------------------

_CACHE_TTL = 2 * 24 * 3600  # 2 dias em segundos


def _cleanup_old_reports():
    """Remove PDFs com mais de 2 dias do diretorio de relatorios."""
    now = time.time()
    removed = 0
    for pdf in OUTPUT_DIR.glob("*.pdf"):
        try:
            if now - pdf.stat().st_mtime > _CACHE_TTL:
                pdf.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        print("[RDA] Cache cleanup: " + str(removed) + " relatorio(s) expirado(s) removido(s).")


def _periodic_cleanup():
    """Thread daemon que limpa cache a cada 6 horas."""
    while True:
        time.sleep(6 * 3600)
        _cleanup_old_reports()


# ---------------------------------------------------------------------------
# Startup — inicialização que roda tanto via gunicorn quanto via python direto
# ---------------------------------------------------------------------------

def _init_app():
    """Inicializa threads daemon (cleanup, batch scheduler) e restaura estado.
    Chamada uma vez no import do módulo — funciona com gunicorn e execução direta."""

    # Limpar cache expirado no boot
    _cleanup_old_reports()

    # Thread de limpeza periodica (a cada 6h)
    t_cleanup = threading.Thread(target=_periodic_cleanup, daemon=True)
    t_cleanup.start()

    # Thread do scheduler de batch mensal (verifica a cada 1h se é dia 01)
    if BATCH_IDS:
        print("[RDA] Batch mensal: " + str(len(BATCH_IDS)) + " IDs configurados")
        # Carregar estado de batches anteriores do mês atual (se existir marker)
        _cur_month = _batch_month_key()
        if _batch_already_done(_cur_month):
            # Reconstruir estado dos PDFs existentes para exibição no frontend
            _data_ini, _data_fim = _batch_period()
            _dt_ini_fmt = _data_ini.replace("-", "_")
            _dt_fim_fmt = _data_fim.replace("-", "_")
            _batch_state["status"] = "done"
            _batch_state["month"] = _cur_month
            _batch_state["ids"] = list(BATCH_IDS)
            _batch_state["progress"] = {}
            for _bid in BATCH_IDS:
                _fname = "batch_mensal_" + _bid + "_" + _dt_ini_fmt + "_" + _dt_fim_fmt + ".pdf"
                _fpath = BATCH_OUTPUT_DIR / _fname
                if _fpath.exists():
                    _batch_state["progress"][_bid] = {
                        "status": "done",
                        "progress": 100,
                        "message": "Concluído!",
                        "pdf_url": "/relatorios-mensais/" + _fname,
                        "filename": _fname,
                    }
                else:
                    _batch_state["progress"][_bid] = {
                        "status": "error",
                        "progress": 0,
                        "message": "PDF não encontrado",
                        "pdf_url": None,
                        "filename": None,
                    }
            print("[RDA] Batch do mes " + _cur_month + " ja concluido — estado restaurado.")
        t_batch = threading.Thread(target=_batch_scheduler, daemon=True)
        t_batch.start()
    else:
        print("[RDA] Batch mensal: nenhum ID configurado (RDA_BATCH_IDS vazio)")


# Executa no import (gunicorn carrega o módulo uma vez por worker)
_init_app()


if __name__ == "__main__":
    port = _RDA_PORT
    print("\n  RDA - Backend API")
    print("  Diretorio base: " + str(BASE_DIR))
    print("  Relatorios em:  " + str(OUTPUT_DIR))
    print("  Porta: " + str(port))
    print("  Acesse: http://localhost:" + str(port) + "\n")

    app.run(host="0.0.0.0", port=port, debug=False)
