FROM python:3.10-slim

RUN apt-get update && apt-get install -y sshpass cron && apt-get clean

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

COPY cronjob /etc/cron.d/backup-cron
RUN chmod 0644 /etc/cron.d/backup-cron && crontab /etc/cron.d/backup-cron
RUN touch /var/log/backup.log

CMD ["cron", "-f"]
