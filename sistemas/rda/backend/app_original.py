# =======================================================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUCOES CONECTADAS - CSC
# RDA - INTERFACE WEB
# =======================================================================

import os
import traceback
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "relatorios_gerados"
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "web" / "templates"),
    static_folder=str(BASE_DIR / "web" / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# ---------------------------------------------------------------------------
# Import tardio do módulo de relatórios (carrega matplotlib, reportlab etc.)
# ---------------------------------------------------------------------------

# Forçar backend não-interativo do matplotlib via env var
# (precisa ser setado ANTES de qualquer import do matplotlib)
os.environ["MPLBACKEND"] = "Agg"

# O report usa paths relativos — garante que o cwd seja o diretório do projeto
os.chdir(str(BASE_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "report_rda",
    str(BASE_DIR / "report_0.2.6.4.py"),
)
_report_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_report_module)

rda_py_data_movel = _report_module.rda_py_data_movel


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Página principal com formulário de geração."""
    return render_template("index.html")


@app.route("/api/gerar-relatorio", methods=["POST"])
def gerar_relatorio():
    """
    Recebe JSON com:
        - id_jd (str, obrigatório): ID numérico do cliente no Operations Center
        - chassi (str, opcional): filtrar por equipamento específico
        - data_inicial (str, obrigatório): formato YYYY-MM-DD
        - data_final (str, obrigatório): formato YYYY-MM-DD

    Retorna JSON com:
        - pdf_url: URL para visualizar/baixar o PDF
        - filename: nome do arquivo
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Corpo da requisição inválido."}), 400

    # --- Validação ---
    id_jd = data.get("id_jd", "").strip()
    if not id_jd or not id_jd.isdigit():
        return jsonify({"message": "ID JD deve ser um número válido."}), 400

    data_inicial = data.get("data_inicial", "").strip()
    data_final = data.get("data_final", "").strip()
    if not data_inicial or not data_final:
        return jsonify({"message": "Data inicial e data final são obrigatórias."}), 400

    # Validar formato de datas
    try:
        from datetime import datetime
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d")
        dt_fim = datetime.strptime(data_final, "%Y-%m-%d")
        if dt_ini > dt_fim:
            return jsonify({"message": "Data inicial deve ser anterior à data final."}), 400
    except ValueError:
        return jsonify({"message": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    chassi = (data.get("chassi") or "").strip() or None
    # TODO: filtro por chassi ainda não implementado nas queries SQL.
    # Quando implementado, passar chassi para rda_py_data_movel.

    # --- Geração ---
    try:
        pdf_path = rda_py_data_movel(
            client_id=int(id_jd),
            data_inicial=data_inicial,
            data_final=data_final,
            output_dir=str(OUTPUT_DIR),
        )

        if not pdf_path or not Path(pdf_path).exists():
            return jsonify({"message": "Erro interno: PDF não foi gerado."}), 500

        filename = Path(pdf_path).name

        return jsonify({
            "pdf_url": f"/relatorios/{filename}",
            "filename": filename,
        })

    except Exception as exc:
        traceback.print_exc()
        return jsonify({
            "message": f"Erro ao gerar relatório: {str(exc)}"
        }), 500


@app.route("/relatorios/<path:filename>")
def servir_relatorio(filename):
    """Serve PDFs gerados para preview e download."""
    return send_from_directory(str(OUTPUT_DIR), filename)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n  RDA - Interface Web")
    print(f"  Diretório base: {BASE_DIR}")
    print(f"  Relatórios em:  {OUTPUT_DIR}")
    print(f"  Acesse: http://localhost:5000\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
