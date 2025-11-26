import os
import telnetlib
import time
import datetime
import subprocess
from dotenv import load_dotenv
import requests

# Diretórios
BACKUP_DIR = "/app/backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Carrega variáveis do .env
load_dotenv()

OLTS = os.getenv("OLTS", "")
TELNET_PORT = int(os.getenv("TELNET_PORT", 23))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

today = datetime.datetime.now().strftime("%d%m%Y")

def send_telegram_message(message, file_path=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")

    if file_path:
        try:
            url_doc = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': TELEGRAM_CHAT_ID}
                requests.post(url_doc, files=files, data=data)
        except Exception as e:
            print(f"Erro ao enviar arquivo: {e}")

def backup_olt(ip, tipo, username, password):
    try:
        print(f"Conectando na OLT {ip} via Telnet...")
        tn = telnetlib.Telnet(ip, TELNET_PORT, timeout=10)

        tn.read_until(b"Username:")
        tn.write(username.encode('ascii') + b"\n")
        tn.read_until(b"Password:")
        tn.write(password.encode('ascii') + b"\n")

        time.sleep(1)
        tn.write(b"enable\n")
        tn.write(b"configure terminal\n")

        filename = f"bkup_{ip.replace('.', '_')}_{today}.cfg"
        tn.write(f"show running-config | save overwrite {filename}\n".encode('ascii'))
        time.sleep(3)
        tn.write(b"exit\n")
        tn.write(b"exit\n")

        print(f"Arquivo salvo na OLT: {filename}")

        local_path = os.path.join(BACKUP_DIR, filename)
        scp_cmd = (
            f"sshpass -p {password} scp -P 22 "
            f"{username}@{ip}:{filename} {local_path}"
        )

        print("Baixando arquivo via SCP...")
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print("Backup baixado com sucesso.")
            send_telegram_message(f"✅ Backup da OLT {ip} concluído!", file_path=local_path)
        else:
            raise Exception(result.stderr)

    except Exception as e:
        send_telegram_message(f"❌ Falha ao fazer backup da OLT {ip}: {e}")

def main():
    for olt in OLTS.split(";"):
        try:
            ip, tipo, user, passwd = olt.strip().split(",")
            if tipo.lower() == "datacom":
                backup_olt(ip, tipo, user, passwd)
        except ValueError:
            print(f"Erro no formato da linha: {olt}")
            continue

if __name__ == "__main__":
    main()
