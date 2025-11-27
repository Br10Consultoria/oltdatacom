#!/bin/bash
set -e

# Script de instalação para Debian
# - Atualiza o sistema
# - Instala Docker e Docker Compose
# - Sobe o container de backup das OLTs Datacom

if [ "$EUID" -ne 0 ]; then
  echo "Por favor, execute como root (sudo su ou sudo ./install_oltdatacom.sh)"
  exit 1
fi

echo "[1/5] Atualizando sistema..."
apt-get update -y
apt-get upgrade -y

echo "[2/5] Instalando dependências básicas..."
apt-get install -y ca-certificates curl gnupg lsb-release sudo

echo "[2/5] Adicionando repositório oficial do Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
| tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "[2/5] Atualizando repositórios..."
apt-get update -y

echo "[2/5] Instalando Docker Engine..."
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

echo "[2/5] Instalando Docker Compose plugin..."
if apt-get install -y docker-compose-plugin; then
    echo "Docker Compose plugin instalado com sucesso."
else
    echo "docker-compose-plugin não disponível. Instalando docker-compose manualmente..."
    curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-$(uname -s)-$(uname -m) \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose || true
fi

echo "[3/5] Habilitando e iniciando Docker..."
systemctl enable docker
systemctl start docker

echo "[4/5] Subindo projeto Docker em /home/oltdatacom..."

cd /home/oltdatacom

echo "[5/5] Build e subida do container..."
docker compose build
docker compose up -d

echo "======================================================"
echo "Instalação concluída."
echo "Container 'oltdatacom-backup' em execução."
echo "Backups serão executados todos os dias às 13:00 e 22:00."
echo "Verifique os logs em /home/oltdatacom/logs/backup_datacom.log"
echo "======================================================"
