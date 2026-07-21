"""
Gera connection/serviceAccount.json a partir das variaveis FIREBASE_*
do .env central (C:\\env\\.env).

Motivo: a chave privada Firebase antes ficava hardcoded neste script.
Agora ela mora no .env central e este script apenas monta o JSON.

Uso:
    python create_sa.py

Rode uma vez apos qualquer rotacao da chave. O container do rts-dashboard
faz bind-mount de connection/serviceAccount.json, entao basta rodar isto
antes do `docker compose up -d --build`.
"""

import json
import os
import platform
import sys
from dotenv import load_dotenv

# .env centralizado em C:\env\.env no host Windows.
_ENV_PATH = r"C:\env\.env" if platform.system() == "Windows" else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)


def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        sys.stderr.write(
            f"[create_sa] Variavel obrigatoria ausente: {name}\n"
            f"[create_sa] Esperada em {_ENV_PATH}\n"
        )
        sys.exit(1)
    return v


# private_key vem com "\n" literais (formato JSON escapado). Restaura os newlines reais.
private_key = _require("FIREBASE_PRIVATE_KEY").replace("\\n", "\n")

data = {
    "type": "service_account",
    "project_id": _require("FIREBASE_PROJECT_ID"),
    "private_key_id": _require("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": private_key,
    "client_email": _require("FIREBASE_CLIENT_EMAIL"),
    "client_id": _require("FIREBASE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{_require('FIREBASE_CLIENT_EMAIL').replace('@', '%40')}",
    "universe_domain": "googleapis.com",
}

here = os.path.dirname(os.path.abspath(__file__))
dest = os.path.join(here, "connection", "serviceAccount.json")

os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"serviceAccount.json criado em: {dest}")
