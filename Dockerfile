FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    openssh-client \
    telnet \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Criar diretórios
RUN mkdir -p /home/oltdatacom/logs /home/oltdatacom/backups

# Definir diretório de trabalho
WORKDIR /home/oltdatacom

# Copiar arquivo de requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar script e crontab
COPY backup_olt.py .
COPY crontab /etc/cron.d/olt-backup

# Dar permissões ao crontab
RUN chmod 0644 /etc/cron.d/olt-backup && \
    crontab /etc/cron.d/olt-backup

# Criar log do cron
RUN touch /var/log/cron.log

# Script de entrada
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
