#!/usr/bin/env bash
# =========== RTS - REAL TIME SUPPORT ============
# install-vm.sh — bootstrap de VM Ubuntu 22.04+ para rodar RTS no Docker
# ================================================
#
# Requer sudo / root. Idempotente: pode rodar múltiplas vezes.
#
# O que faz:
#   1. atualiza apt
#   2. instala docker-ce + docker-compose-plugin oficiais
#   3. habilita serviço docker no boot
#   4. adiciona o usuário atual ao grupo docker (login/logout depois)
#   5. ajusta timezone para America/Recife
#   6. instala utilitários auxiliares (curl, netcat, jq, python3)
#   7. valida que os arquivos do projeto estão na VM
#
# Uso:
#   sudo bash install-vm.sh

set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
    echo "Este script precisa rodar como root. Use: sudo bash install-vm.sh"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"

echo "============================================================"
echo "RTS install-vm — $(date)"
echo "Usuário alvo (será adicionado ao grupo docker): $REAL_USER"
echo "============================================================"

# ---- 1. apt update ----
echo "[1/7] apt update..."
apt-get update -y

# ---- 2. Pré-requisitos ----
echo "[2/7] Instalando pré-requisitos..."
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    netcat-openbsd \
    jq \
    python3 \
    python3-pip \
    git

# ---- 3. Docker CE + compose plugin ----
if ! command -v docker >/dev/null 2>&1; then
    echo "[3/7] Instalando Docker CE..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    echo "[3/7] Docker já instalado — pulando."
fi

# ---- 4. habilitar e iniciar docker ----
echo "[4/7] Habilitando serviço docker..."
systemctl enable docker
systemctl start docker

# ---- 5. adicionar usuário ao grupo docker ----
if ! id -nG "$REAL_USER" | grep -qw docker; then
    echo "[5/7] Adicionando $REAL_USER ao grupo docker..."
    usermod -aG docker "$REAL_USER"
    echo "      >>> Faça logout/login (ou 'newgrp docker') para aplicar. <<<"
else
    echo "[5/7] $REAL_USER já está no grupo docker."
fi

# ---- 6. timezone ----
echo "[6/7] Ajustando timezone para America/Recife..."
timedatectl set-timezone America/Recife || true
ok_tz="$(timedatectl show -p Timezone --value)"
echo "      Timezone atual: $ok_tz"

# ---- 7. validação ----
echo "[7/7] Validando instalação..."
docker --version
docker compose version
echo ""
echo "============================================================"
echo "Instalação concluída."
echo ""
echo "Próximos passos:"
echo "  1. Clone o repositório em /opt/rts  (ou ajuste o path no systemd)"
echo "       sudo mkdir -p /opt && sudo chown $REAL_USER:$REAL_USER /opt"
echo "       cd /opt && git clone <url-do-repo> rts"
echo "  2. Copie o template de env:"
echo "       cp /opt/rts/docker/.env.example /opt/rts/.env"
echo "       # edite /opt/rts/.env com os segredos reais (chmod 600)"
echo "  3. Coloque o serviceAccount.json em /opt/rts/connection/"
echo "  4. Rode preflight:"
echo "       bash /opt/rts/docker/scripts/preflight.sh"
echo "  5. Build + up:"
echo "       bash /opt/rts/docker/scripts/build.sh"
echo "       bash /opt/rts/docker/scripts/up.sh"
echo "  6. (Opcional) Instalar systemd unit para auto-start no boot:"
echo "       sudo cp /opt/rts/docker/systemd/rts.service /etc/systemd/system/"
echo "       sudo systemctl daemon-reload"
echo "       sudo systemctl enable --now rts.service"
echo "============================================================"
