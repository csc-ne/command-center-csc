"""
runtime_config.py
================

Lê configurações dinâmicas (mutáveis em runtime, controladas pela UI do
dashboard) direto do banco MySQL, com cache leve para evitar martelar a
conexão. A motivação é centralizar o "estado vivo" do RTS num único lugar
que tanto o `connection/server.js` (Node) quanto o `rts_core.py` (Python)
podem ler/escrever sem precisar de protocolo extra entre containers.

Configuração suportada hoje:
    wpp_mode  -> "AUTO" | "FORCE_ON" | "FORCE_OFF"
        AUTO       => respeita business_hours.is_business_hours()
        FORCE_ON   => envia WhatsApp ignorando horário comercial
        FORCE_OFF  => bloqueia envio até nova ordem

Tabela:
    runtime_config (
        chave VARCHAR(64) PRIMARY KEY,
        valor VARCHAR(255) NOT NULL,
        atualizado_em DATETIME ON UPDATE CURRENT_TIMESTAMP,
        atualizado_por VARCHAR(255) NULL
    )

A tabela é criada de forma idempotente em `_read_from_db()`. Se o banco
estiver indisponível, caímos silenciosamente para o default ("AUTO") e
loga um warning — o objetivo é nunca derrubar o core por falha em ler
configuração dinâmica.

API pública:
    get_wpp_mode()    -> str   ("AUTO" | "FORCE_ON" | "FORCE_OFF")
    should_send_wpp() -> bool  (combina wpp_mode com business_hours)
    invalidate_cache()         (força próxima leitura ir ao banco)

Uso típico no batch_alert_sender:
    from runtime_config import should_send_wpp, get_wpp_mode
    if not should_send_wpp():
        logger.info(f"[BatchSender] envio bloqueado (mode={get_wpp_mode()})")
        return 0, 0, 0
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from BD_alertas import BancoDados
from business_hours import is_business_hours

log = logging.getLogger(__name__)

# ── Constantes ──────────────────────────────────────────────────────
_TTL_SEC = 5  # cache TTL: leitura ao DB no máximo a cada 5s
_VALID_MODES = ("AUTO", "FORCE_ON", "FORCE_OFF")
_DEFAULT_MODE = "AUTO"

# ── Estado interno ──────────────────────────────────────────────────
_cache = {
    "value": _DEFAULT_MODE,
    "expires_at": 0.0,
}


# ── Helpers privados ────────────────────────────────────────────────
def _ensure_table_and_seed(bd: BancoDados) -> None:
    """Cria a tabela e insere a linha default se não existirem.

    Operações idempotentes: pode ser chamado em todo SELECT sem custo
    apreciável (CREATE IF NOT EXISTS + INSERT ... ON CONFLICT DO NOTHING).
    """
    bd.cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rts_runtime_config (
            chave VARCHAR(64) PRIMARY KEY,
            valor VARCHAR(255) NOT NULL,
            atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_por VARCHAR(255) NULL
        )
        """
    )
    bd.cursor.execute(
        "INSERT INTO rts_runtime_config (chave, valor, atualizado_por) "
        "VALUES ('wpp_mode', %s, 'system') "
        "ON CONFLICT (chave) DO NOTHING",
        (_DEFAULT_MODE,),
    )
    bd.cnx.commit()


def _read_from_db() -> str:
    """Lê wpp_mode do banco. Pode lançar exceção em falha de conexão."""
    bd = BancoDados(nome_tabela="runtime_config")
    bd.conectar()
    try:
        _ensure_table_and_seed(bd)
        bd.cursor.execute(
            "SELECT valor FROM rts_runtime_config WHERE chave = 'wpp_mode' LIMIT 1"
        )
        row = bd.cursor.fetchone()
    finally:
        bd.desconectar()

    if not row or not row[0]:
        return _DEFAULT_MODE

    value = str(row[0]).strip().upper()
    if value not in _VALID_MODES:
        log.warning(
            "[runtime_config] valor inválido em wpp_mode=%r, usando %s",
            value, _DEFAULT_MODE,
        )
        return _DEFAULT_MODE
    return value


# ── API pública ─────────────────────────────────────────────────────
def get_wpp_mode() -> str:
    """Retorna o modo atual de envio WPP, com cache de 5s.

    Em caso de erro lendo o banco, retorna `_DEFAULT_MODE` (AUTO) sem
    lançar — assim, falha de DB nunca paralisa o loop principal.
    """
    now = time.time()
    if now < _cache["expires_at"]:
        return _cache["value"]

    try:
        value = _read_from_db()
    except Exception as e:  # noqa: BLE001 — best-effort
        log.warning(
            "[runtime_config] falha ao ler wpp_mode (%s); usando %s",
            e, _DEFAULT_MODE,
        )
        value = _DEFAULT_MODE

    _cache["value"] = value
    _cache["expires_at"] = now + _TTL_SEC
    return value


def should_send_wpp(now: Optional[float] = None) -> bool:
    """Decide se o RTS deve enviar WhatsApp neste momento.

    Combinação de regras:
        AUTO       -> respeita business_hours.is_business_hours()
        FORCE_ON   -> True  (operador autorizou envio fora do horário)
        FORCE_OFF  -> False (operador pausou envios manualmente)
    """
    mode = get_wpp_mode()
    if mode == "FORCE_ON":
        return True
    if mode == "FORCE_OFF":
        return False
    # AUTO: delega para a janela de expediente configurada via env
    return is_business_hours()


def invalidate_cache() -> None:
    """Força a próxima chamada a `get_wpp_mode()` ir ao banco.

    Útil em testes ou quando o caller acaba de gravar um novo valor e
    quer ler de volta sem aguardar o TTL.
    """
    _cache["expires_at"] = 0.0


# ── Smoke test (rodar diretamente: `python runtime_config.py`) ──────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"wpp_mode atual:  {get_wpp_mode()}")
    print(f"should_send_wpp: {should_send_wpp()}")
