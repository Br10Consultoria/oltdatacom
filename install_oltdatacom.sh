#!/bin/bash
set -e

# Script de instalação para Debian
# - Atualiza o sistema
# - Instala Docker e docker compose plugin
# - (Opcional) instala TFTP
# - Sobe o container de backup das OLTs Datacom

if [ "$EUID" -ne 0 ]; then
  echo "Por favor, execute como root (sudo su ou sudo ./install_oltdatacom.sh)"
  exit 1
fi

echo "[1/5] Atualizando sistema..."
apt-get update -y
apt-get upgrade -y

echo "[2/5] Instalando Docker e Docker Compose plugin..."
apt-get install -y docker.io docker-compose-plugin

echo "[3/5] (Opcional) Instalando servidor TFTP (tftpd-hpa)..."
apt-get install -y sudo

echo "[4/5] Habilitando e iniciando Docker..."
systemctl enable docker
systemctl start docker

echo "[5/5] Subindo projeto Docker em /home/oltdatacom..."

cd /home/oltdatacom

# Se você for clonar do GitHub, deixe algo assim:
# git clone https://github.com/SEU_USUARIO/SEU_REPO.git .
# e depois rode este script

# Build e subida do container
docker compose build
docker compose up -d

echo "======================================================"
echo "Instalação concluída."
echo "Container 'oltdatacom-backup' em execução."
echo "Backups serão executados todos os dias às 13:00 e 22:00."
echo "Verifique os logs em /home/oltdatacom/logs/backup_datacom.log"
echo "======================================================"
