FROM python:3.11-slim

# Instalar cron
RUN apt-get update && \
    apt-get install -y cron && \
    rm -rf /var/lib/apt/lists/*

# Diretório da aplicação
WORKDIR /app

# Copiar script
COPY backup_datacom.py /app/backup_datacom.py

# Criar log dir
RUN mkdir -p /var/log/oltdatacom

# Crontab: executa o script às 13:00 e 22:00 todos os dias
RUN echo "0 13,22 * * * root python /app/backup_datacom.py >> /var/log/oltdatacom/backup_datacom.log 2>&1" > /etc/cron.d/backup_datacom \
 && chmod 0644 /etc/cron.d/backup_datacom \
 && crontab /etc/cron.d/backup_datacom

# Comando padrão: manter o cron em foreground
CMD ["cron", "-f"]
