#!/usr/bin/env python3
"""
force_renew_media.py
====================

Forca a renovacao do Media ID do WhatsApp imediatamente, ignorando
a checagem de expiracao do `check_media_id_expiration()`.

Uso (dentro do container):
    docker exec rts-core python /app/force_renew_media.py

O que faz:
    1. Carrega o .env (TKWPP, PHONE_NUMBER_ID etc.)
    2. Chama post_media_id() -> upload do logo.png pra Meta -> retorna ID novo
    3. post_media_id() ja chama _update_env_inplace("MEDIAIDEXP", hoje)
    4. Sobrescreve MEDIAIDWPP no .env via _update_env_inplace
    5. Imprime o ID novo e o caminho do .env atualizado

Saida esperada (sucesso):
    [force_renew] Token OK: EAA...
    [force_renew] Novo Media ID: 1234567890
    [force_renew] MEDIAIDWPP / MEDIAIDEXP gravados em /app/.env
    [force_renew] Confira no host: Get-Content .env | Select-String MEDIAID
"""

import logging
import os
import sys

# Logging legivel no terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from whatsapp_api import post_media_id, _update_env_inplace, _get_token, ENV_PATH


def main() -> int:
    tok = _get_token()
    if not tok:
        print("[force_renew] ERRO: TKWPP nao configurado no .env", file=sys.stderr)
        return 1
    print(f"[force_renew] Token OK: {tok[:12]}...")

    try:
        new_id = post_media_id()
    except Exception as e:
        print(f"[force_renew] ERRO ao fazer upload: {e}", file=sys.stderr)
        return 2

    if not new_id:
        print("[force_renew] ERRO: post_media_id() retornou vazio", file=sys.stderr)
        return 3

    # Persistir MEDIAIDWPP via mesmo helper (post_media_id ja gravou MEDIAIDEXP)
    try:
        _update_env_inplace("MEDIAIDWPP", str(new_id))
        os.environ["MEDIAIDWPP"] = str(new_id)
    except Exception as e:
        print(
            f"[force_renew] AVISO: Media ID {new_id} gerado mas nao foi possivel "
            f"gravar no .env: {e}",
            file=sys.stderr,
        )
        return 4

    print(f"[force_renew] Novo Media ID: {new_id}")
    print(f"[force_renew] MEDIAIDWPP / MEDIAIDEXP gravados em {ENV_PATH}")
    print("[force_renew] Confira no host:")
    print('             Get-Content .env | Select-String "MEDIAID"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
