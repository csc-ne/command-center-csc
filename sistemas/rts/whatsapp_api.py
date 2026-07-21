# =========== RTS - REAL TIME SUPPORT ============
# VENEZA EQUIPAMENTOS PESADOS SOCIEDADE ANÔNIMA
# CENTRO DE SOLUÇÕES CONECTADAS - CSC - VENEZA NORDESTE
# JOHN DEERE BRASIL - WIRTGEN
# APLICAÇÃO DESENVOLVIDA POR ROBERT ARAÚJO

import json
import requests
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv, set_key
from alerts_api import retry_request
from requests.exceptions import RequestException, ConnectionError, Timeout
import logging

# ============================================================
# CONFIGURAÇÃO DO .ENV (CAMINHO FIXO)
# ============================================================

import platform as _platform
# .env centralizado em C:\env\.env no host Windows.
# No container Linux, o docker-compose monta esse arquivo em /app/.env.
if _platform.system() == "Windows":
    ENV_PATH = Path(r"C:\env\.env")
else:
    ENV_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / ".env"
_LOGO_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "logo.png"

# Carrega .env na inicialização do módulo
load_dotenv(ENV_PATH)


# ============================================================
# ESCRITA IN-PLACE DO .ENV (compatível com bind-mount Windows/WSL)
# ============================================================
#
# A função set_key() da python-dotenv usa atomic write: grava num
# tempfile e faz os.rename() em cima do .env original. Em bind-mount
# do Docker Desktop (WSL2 → Windows), esse rename SUBSTITUI o inode
# dentro do container, quebrando o link com o arquivo do host. Resultado:
# a escrita "funciona" do ponto de vista do container, mas o .env do
# host nunca é atualizado, e a cada restart o sistema renova de novo.
#
# Esta função reescreve o arquivo IN-PLACE (open "w" no mesmo path,
# preservando o inode), o que garante que a escrita propaga para o host.
# Comportamento externo idêntico ao set_key da python-dotenv para o caso
# de uso aqui (chave=valor sem quotes, sem comentários inline).
def _update_env_inplace(key: str, value: str) -> None:
    """Atualiza chave=valor no .env preservando o inode do arquivo."""
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    new_line = f"{key}={value}\n"
    found = False
    for i, line in enumerate(lines):
        # Compara apenas o prefixo "CHAVE=" (preserva indent/spaces nao deve haver)
        stripped = line.lstrip()
        if stripped.startswith(f"{key}="):
            lines[i] = new_line
            found = True
            break
    if not found:
        # Garante newline antes da nova linha se o arquivo nao termina em \n
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        lines.append(new_line)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _get_token() -> str | None:
    """
    Lê o token WhatsApp SEMPRE do .env no momento da chamada.

    ⚠️ MOTIVO: tok NÃO pode ser uma variável de módulo.
    Quando o usuário atualiza o token no .env com o app em execução
    (via BAT), a variável de módulo fica congelada com o valor antigo.
    Relendo via load_dotenv(override=True) + os.environ.get(),
    o sistema detecta o novo token sem precisar reiniciar.
    """
    load_dotenv(ENV_PATH, override=True)
    return os.environ.get("TKWPP")

# ============================================================
# FUNÇÕES
# ============================================================

def check_media_id_expiration(days_before_expiry=3):
    """
    Verifica se o Media ID expira em menos de X dias (default 3).
    Se sim, renova preemptivamente.

    Pode ser chamado no startup do sistema para garantir que o Media ID
    nunca expira enquanto o sistema está rodando.

    Args:
        days_before_expiry: número de dias antes da expiração para renovar

    Returns:
        dict com status da verificação: {"status": "ok" | "renewed", "mediaid": id, "expires": data}
    """

    raw_exp = os.environ.get("MEDIAIDEXP")
    today = datetime.today().date()

    try:
        creation_date = datetime.strptime(raw_exp, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        # Força renovação se não existir ou estiver inválido
        creation_date = today - timedelta(days=30)

    # Media ID válido por 25 dias a partir da criação
    expiry_date = creation_date + timedelta(days=25)
    days_remaining = (expiry_date - today).days

    # Se vai expirar em menos de X dias, renova agora
    if days_remaining <= days_before_expiry:
        logging.info(f"Media ID expira em {days_remaining} dias. Renovando preemptivamente...")
        try:
            newid = post_media_id()
            logging.info(f"Media ID renovado com sucesso. Novo ID: {newid}")
            return {
                "status": "renewed",
                "mediaid": newid,
                "expires": (datetime.today().date() + timedelta(days=25)).strftime("%Y-%m-%d")
            }
        except Exception as e:
            logging.error(f"Erro ao renovar Media ID no startup: {e}")
            # Tenta continuar com ID antigo
            return {
                "status": "renewal_failed",
                "mediaid": os.environ.get("MEDIAIDWPP"),
                "error": str(e)
            }

    return {
        "status": "ok",
        "mediaid": os.environ.get("MEDIAIDWPP"),
        "expires": expiry_date.strftime("%Y-%m-%d"),
        "days_remaining": days_remaining
    }


def get_mediaid():
    """
    Retorna o Media ID atual, verificando se está próximo de expirar.
    Se estiver vencido, faz upload de novo e tenta atualizar o .env.
    Se não conseguir escrever no .env, mantém em memória.

    Esta função é chamada sempre que um alerta precisa ser enviado.
    """

    raw_exp = os.environ.get("MEDIAIDEXP")
    today = datetime.today().date()

    try:
        creation_date = datetime.strptime(raw_exp, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        # força renovação se não existir ou estiver inválido
        creation_date = today - timedelta(days=30)

    # Media ID válido por 25 dias a partir da criação
    expiry_date = creation_date + timedelta(days=25)

    # Se já expirou, renova imediatamente
    if today >= expiry_date:
        logging.warning(f"Media ID expirou em {expiry_date}. Renovando imediatamente...")
        newid = post_media_id()

        # tenta salvar no .env (não derruba o sistema se falhar)
        # Usa _update_env_inplace para compatibilidade com bind-mount WSL/Windows
        try:
            _update_env_inplace("MEDIAIDWPP", str(newid))
        except (PermissionError, OSError) as e:
            logging.warning(f"Nao foi possivel persistir MEDIAIDWPP no .env: {e}")

        # garante uso no processo atual
        os.environ["MEDIAIDWPP"] = str(newid)
        return str(newid)

    return os.environ.get("MEDIAIDWPP")


def _is_media_id_expired_error(response) -> bool:
    """
    Detecta se o erro 400 da Meta é especificamente sobre Media ID expirado/inexistente.
    Erro 131009 com "Media ID ... does not exist or has expired".
    """
    if response.status_code != 400:
        return False
    try:
        body = response.json()
        error = body.get("error", {})
        error_data = error.get("error_data", {})
        details = error_data.get("details", "")
        return error.get("code") == 131009 and "does not exist or has expired" in details
    except Exception:
        return False


def _force_renew_media_id() -> str | None:
    """
    Força renovação do Media ID independentemente da data de expiração calculada.
    Chamado quando a Meta rejeita o ID atual com erro 131009.
    """
    logging.warning("[MediaID] Forçando renovação — Meta rejeitou o ID atual.")
    try:
        newid = post_media_id()
        if newid:
            try:
                _update_env_inplace("MEDIAIDWPP", str(newid))
            except (PermissionError, OSError) as e:
                logging.warning(f"[MediaID] Não foi possível persistir MEDIAIDWPP no .env: {e}")
            os.environ["MEDIAIDWPP"] = str(newid)
            logging.info(f"[MediaID] Renovação forçada concluída. Novo ID: {newid}")
            return str(newid)
    except Exception as e:
        logging.error(f"[MediaID] Falha na renovação forçada: {e}")
    return None


def _sanitize_template_param(val, fallback="N/A"):
    """
    Defense-in-depth: garante que nenhum parâmetro de template chegue à Meta API
    com valor NULL, vazio, ou contendo \\n / \\t / 4+ espaços consecutivos.
    Erros 131008 ("missing text value") e 100 ("new-line/tab characters").
    """
    if not val:
        return fallback
    s = str(val).strip()
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = re.sub(r" {4,}", "   ", s)
    return s or fallback


def send_wpp(tel, cliente, chassi, data_ocorrencia, horimetro, notificacao, _retry_media=False):
    # ── Sanitização defense-in-depth (última barreira antes da API) ──
    cliente = _sanitize_template_param(cliente, "CLIENTE_DESCONHECIDO")
    chassi = _sanitize_template_param(chassi, "N/A")
    data_ocorrencia = _sanitize_template_param(data_ocorrencia, "N/A")
    horimetro = _sanitize_template_param(horimetro, "0")
    notificacao = _sanitize_template_param(notificacao, "ALERTA_SEM_DESCRICAO")

    # Lê o token SEMPRE do .env no momento do envio (não usa variável de módulo)
    # Isso permite que o usuário atualize o token sem reiniciar o sistema.
    tok = _get_token()

    if not tok:
        return {"status": "skipped", "motivo": "TKWPP não configurado no .env"}

    mediaid = get_mediaid()

    phone_id = os.environ.get("PHONE_NUMBER_ID", "103829652641038")
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"

    hdr = {
        "Authorization": f"Bearer {tok}",
        "Content-type": "application/json",
    }

    data_wpp = {
        "messaging_product": "whatsapp",
        "to": f"55{tel}",
        "type": "template",
        "template": {
            "name": "alertas_falhas_img",
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"id": mediaid},
                        }
                    ],
                },
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": f"{cliente}"},
                        {"type": "text", "text": f"{chassi}"},
                        {"type": "text", "text": f"{data_ocorrencia}"},
                        {"type": "text", "text": f"{horimetro}h"},
                        {
                            "type": "text",
                            "text": re.sub(" +", " ", notificacao),
                        },
                    ],
                },
            ],
        },
    }

    try:
        response = requests.post(url, headers=hdr, data=json.dumps(data_wpp))

        # ── Detecção de Media ID expirado (erro 131009) ──
        # Se a Meta rejeita o ID, faz upload de novo e retenta UMA vez.
        # Sem isso, o batch sender entra em loop infinito com 0% de sucesso.
        if _is_media_id_expired_error(response) and not _retry_media:
            logging.warning(
                f"[send_wpp] Media ID {mediaid} rejeitado pela Meta (131009). "
                f"Renovando e retentando..."
            )
            new_id = _force_renew_media_id()
            if new_id:
                return send_wpp(
                    tel, cliente, chassi, data_ocorrencia,
                    horimetro, notificacao, _retry_media=True
                )
            # Se renovação falhou, cai no fluxo normal de erro abaixo

        # Log detalhado para erros 400
        if response.status_code == 400:
            try:
                error_details = response.json()
                logging.error(
                    f"Meta API retornou 400 Bad Request. Detalhes: {json.dumps(error_details, ensure_ascii=False)}"
                )
            except:
                logging.error(f"Meta API retornou 400. Response: {response.text[:500]}")

        response.raise_for_status()
        result = response.json()

        # Verifica se Meta retornou erro na resposta (mesmo com status 200)
        if "error" in result:
            err = result["error"]
            raise ValueError(
                f"WhatsApp API retornou erro: [{err.get('code')}] {err.get('message')}"
            )

        return result

    except (ConnectionError, Timeout) as conn_err:
        logging.warning(f"Conexão falhou, tentando novamente: {conn_err}")
        new_response = retry_request(
            url=url, headers=hdr, data=json.dumps(data_wpp), method="POST"
        )
        if new_response is None:
            logging.error("Requisição falhou após tentativa de retry.")
            raise conn_err

        result = new_response.json()

        # Verifica erro na resposta do retry também
        if "error" in result:
            err = result["error"]
            raise ValueError(
                f"WhatsApp API retornou erro (retry): [{err.get('code')}] {err.get('message')}"
            )

        return result

    except RequestException as req_err:
        logging.error(f"Erro na requisição: {req_err}")
        raise req_err


def post_media_id():
    """
    Faz upload da mídia e retorna o ID.
    Atualiza MEDIAIDEXP no .env se possível.
    """
    tok = _get_token()

    phone_id = os.environ.get("PHONE_NUMBER_ID", "103829652641038")
    url = f"https://graph.facebook.com/v15.0/{phone_id}/media"

    hdr = {
        "Authorization": f"Bearer {tok}",
    }

    # Usa caminho absoluto para evitar problemas com diretório de trabalho
    if not _LOGO_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de logo não encontrado: {_LOGO_PATH}\n"
            "Certifique-se de que logo.png está na raiz do projeto RTS."
        )

    fl = {
        "file": ("logo.png", open(str(_LOGO_PATH), "rb"), "image/png"),
        "type": "image/png",
        "messaging_product": (None, "WHATSAPP"),
    }

    raw = requests.post(url, headers=hdr, files=fl)
    response = json.loads(raw.text)

    # A API retorna {"error": {...}} quando o token é inválido ou a requisição falha
    if "error" in response:
        err = response["error"]
        raise ValueError(
            f"WhatsApp API recusou o upload da mídia: [{err.get('code')}] {err.get('message')}"
        )

    if "id" not in response:
        raise ValueError(
            f"WhatsApp API retornou resposta inesperada (sem 'id'): {raw.text[:300]}"
        )

    today_str = datetime.today().date().strftime("%Y-%m-%d")

    # tenta salvar no .env
    try:
        _update_env_inplace("MEDIAIDEXP", today_str)
    except PermissionError:
        pass

    # garante valor no processo atual
    os.environ["MEDIAIDEXP"] = today_str

    return response["id"]


def get_media_file(id_media):
    """Baixa o arquivo de mídia."""
    tok = _get_token()

    url_media_content = f"https://graph.facebook.com/v15.0/{id_media}/"

    headers = {
        "Authorization": f"Bearer {tok}",
    }

    try:
        resp = requests.get(url_media_content, headers=headers).json()
        url_media = resp["url"]
        mime_type = resp["mime_type"]
    except KeyError:
        raise RuntimeError("Não foi possível fazer o download da mídia.")

    if "audio" in mime_type:
        ext = ".mp3"
    elif "image" in mime_type:
        ext = ".png"
    else:
        raise TypeError("Tipo de arquivo incompatível.")

    media_file_bin = requests.get(url_media, headers=headers).content

    with open(f"{id_media}{ext}", "wb") as media_file:
        media_file.write(media_file_bin)


# ============================================================
# TESTE LOCAL
# ============================================================

if __name__ == "__main__":
    data = datetime(2023, 2, 7).date()
    alerta = (
        "RED     TCU 522444.01    Charge pressure low  -  Troubleshooting required."
    )
    envio = send_wpp(
        81992885875,
        "Veneza Projeto",
        "1BZ310LAAND006227",
        data.strftime("%d/%m/%Y"),
        "221",
        alerta,
    )
    print(envio)
