"""
jd_token_manager.py
===================

Gerenciador de access_token da John Deere para o modo headless do RTS.

Substitui o servidor Flask local (JohnDeereAPI.py) que rodava no host com
Selenium. No container, esse Flask nao existe, entao precisamos fazer o
refresh OAuth direto via Python.

Fluxo:
  1. Le `clientId` / `clientSecret` do .env
  2. Le `refreshToken` do `.token_cache.json` (escrito pelo JohnDeereAPI.py
     quando o operador faz o login OAuth inicial pela GUI no host)
  3. Faz POST no token_endpoint da John Deere com grant_type=refresh_token
  4. Recebe novo `access_token` (curto prazo, ~1h) e novo `refresh_token`
     (~1 ano - John Deere rotaciona)
  5. Salva o novo refresh_token de volta no .token_cache.json (rotacao)
  6. Cacheia o access_token em memoria com expires_at; renova preemptivamente
     quando faltar < 5min para expirar

API publica:
  get_access_token() -> str    : chamada principal usada por alerts_api.py
  refresh_now()      -> dict   : forca um refresh imediato (debug)
  get_status()       -> dict   : telemetria para tela de Logs / /status

Pre-requisitos no .env:
  clientId       = <App key da John Deere>
  clientSecret   = <App secret>

Pre-requisitos no .token_cache.json (criado uma unica vez pelo login GUI):
  refreshToken   = <refresh token de 43 chars>

Quando o refresh_token nao e mais valido (revogado / expirado por inatividade
> 1 ano), get_access_token() levanta JdTokenError e o operador precisa
relogar pela GUI no host UMA VEZ para regerar o cache.

Thread-safety: get_access_token() pode ser chamado de multiplas threads.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("rts.jd_token")

# ── Constantes ──────────────────────────────────────────────────────
_WELL_KNOWN = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/.well-known/oauth-authorization-server"
_SCOPES = "ag1 ag2 ag3 eq1 eq2 org1 org2 files offline_access"
_REDIRECT_URI = "http://127.0.0.1:5000/callback"  # mesmo do JohnDeereAPI.py

# 5 min antes de expirar, ja renova preemptivamente
_REFRESH_MARGIN_SEC = 300

_ROOT = Path(__file__).resolve().parent
_TOKEN_CACHE_PATH = _ROOT / ".token_cache.json"


# ── Excecao publica ─────────────────────────────────────────────────
class JdTokenError(Exception):
    """Falha ao obter access_token. Refresh token pode estar invalido."""


# ── Estado interno ──────────────────────────────────────────────────
_state = {
    "access_token": None,        # str | None
    "expires_at": 0.0,           # epoch
    "last_refresh_at": None,     # datetime
    "last_error": None,          # str | None
    "refresh_count": 0,
}
_lock = threading.Lock()
_token_endpoint_cache = None  # cache do token_endpoint resolvido via well-known


# ── Helpers privados ────────────────────────────────────────────────
def _resolve_token_endpoint() -> str:
    """Descobre o token_endpoint via well-known (com cache em memoria)."""
    global _token_endpoint_cache
    if _token_endpoint_cache:
        return _token_endpoint_cache
    try:
        resp = requests.get(_WELL_KNOWN, timeout=10)
        resp.raise_for_status()
        meta = resp.json()
        ep = meta.get("token_endpoint")
        if not ep:
            raise JdTokenError("well-known sem token_endpoint")
        _token_endpoint_cache = ep
        log.info("[JD-TOKEN] token_endpoint resolvido: %s", ep)
        return ep
    except Exception as e:
        raise JdTokenError(f"Falha ao resolver well-known JD: {e}") from e


def _load_refresh_token() -> str:
    """Le o refresh_token do cache em disco. Levanta se nao existe/invalido."""
    if not _TOKEN_CACHE_PATH.exists():
        raise JdTokenError(
            f"Token cache nao existe em {_TOKEN_CACHE_PATH}. "
            "Faca login OAuth inicial pela GUI no host (interface/johndeere)."
        )
    try:
        with open(_TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception as e:
        raise JdTokenError(f"Token cache corrompido: {e}") from e

    rt = cache.get("refreshToken")
    if not rt or not isinstance(rt, str) or len(rt) < 10:
        raise JdTokenError("refreshToken ausente ou invalido no cache")
    return rt


def _save_refresh_token(new_rt: str) -> None:
    """Persiste o novo refresh_token (rotacao). Escrita in-place para ser
    compativel com bind-mount WSL/Windows (mesmo problema do .env)."""
    payload = {
        "refreshToken": new_rt,
        "savedAt": datetime.now().isoformat(),
    }
    try:
        # Escrita in-place: abre em "w" no mesmo path. Preserva inode.
        with open(_TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:  # noqa: BLE001
        log.warning("[JD-TOKEN] Nao foi possivel salvar novo refresh_token: %s", e)


def _do_refresh() -> dict:
    """Executa o POST de refresh. Retorna dict do JSON de resposta.

    Sucesso => atualiza _state e salva novo refresh_token.
    Falha   => levanta JdTokenError com detalhe.
    """
    client_id = os.environ.get("clientId")
    client_secret = os.environ.get("clientSecret")
    if not client_id or not client_secret:
        raise JdTokenError("clientId/clientSecret ausentes no .env")

    refresh_token = _load_refresh_token()
    token_endpoint = _resolve_token_endpoint()

    import base64
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "grant_type": "refresh_token",
        "redirect_uri": _REDIRECT_URI,
        "refresh_token": refresh_token,
        "scope": _SCOPES,
    }

    try:
        resp = requests.post(token_endpoint, data=payload, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise JdTokenError(f"Erro de rede no refresh: {e}") from e

    if resp.status_code != 200:
        raise JdTokenError(
            f"Refresh falhou ({resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    new_access = data.get("access_token")
    new_refresh = data.get("refresh_token")
    expires_in = int(data.get("expires_in", 3600))
    if not new_access:
        raise JdTokenError("Resposta sem access_token")

    now = time.time()
    _state["access_token"] = new_access
    _state["expires_at"] = now + expires_in
    _state["last_refresh_at"] = datetime.now()
    _state["last_error"] = None
    _state["refresh_count"] += 1

    if new_refresh and new_refresh != refresh_token:
        # JD rotaciona o refresh_token a cada uso — persiste o novo
        _save_refresh_token(new_refresh)
        log.info("[JD-TOKEN] refresh_token rotacionado e persistido")

    log.info(
        "[JD-TOKEN] access_token renovado (expira em %ds, refresh #%d)",
        expires_in, _state["refresh_count"],
    )
    return data


# ── API publica ─────────────────────────────────────────────────────
def get_access_token() -> str:
    """Retorna um access_token JD valido. Renova se necessario.

    Thread-safe. Em caso de falha, levanta JdTokenError.
    """
    with _lock:
        now = time.time()
        # Cache em memoria valido?
        if _state["access_token"] and now < _state["expires_at"] - _REFRESH_MARGIN_SEC:
            return _state["access_token"]
        # Renovar
        try:
            _do_refresh()
        except JdTokenError as e:
            _state["last_error"] = str(e)
            log.error("[JD-TOKEN] Falha ao renovar: %s", e)
            # Se ainda temos um token nao-totalmente-vencido, devolvemos ele
            if _state["access_token"] and now < _state["expires_at"]:
                log.warning("[JD-TOKEN] Usando access_token previo ainda valido")
                return _state["access_token"]
            raise
        return _state["access_token"]


def refresh_now() -> dict:
    """Forca um refresh imediato (util para debug/manutencao)."""
    with _lock:
        return _do_refresh()


def get_status() -> dict:
    """Telemetria para o /status do rts-core ou Tela de Logs."""
    now = time.time()
    return {
        "has_token": bool(_state["access_token"]),
        "expires_in_sec": max(0, int(_state["expires_at"] - now)) if _state["access_token"] else 0,
        "last_refresh_at": _state["last_refresh_at"].isoformat() if _state["last_refresh_at"] else None,
        "refresh_count": _state["refresh_count"],
        "last_error": _state["last_error"],
        "cache_file_exists": _TOKEN_CACHE_PATH.exists(),
    }


# ── Smoke test (rodar diretamente: `python jd_token_manager.py`) ────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        tk = get_access_token()
        print(f"OK: access_token len={len(tk)} prefix={tk[:12]}...")
        print(f"Status: {json.dumps(get_status(), indent=2)}")
    except JdTokenError as e:
        print(f"FAIL: {e}")
        raise SystemExit(1)
