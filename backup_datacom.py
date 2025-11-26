import os
import telnetlib
import time
from datetime import datetime
import sys

# ===============================
# Funções auxiliares de log
# ===============================
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()


def send_command(tn, command, wait_time=2):
    """
    Envia comando via Telnet e retorna a resposta.
    """
    log(f"Enviando comando: {command}")
    tn.write(command.encode('ascii') + b"\n")
    time.sleep(wait_time)
    response = tn.read_very_eager().decode('ascii', errors='ignore')
    log(f"Resposta (primeiros 200 chars): {response[:200].replace(chr(10), ' ')}")
    return response


# ===============================
# Carregar configuração via .env
# ===============================

# Lista de OLTs Datacom, separadas por vírgula
# Exemplo no .env:
# DATACOM_OLTS=OURICANGAS,OURICANGUINHA,POP_FORMIGA
datacom_olts_env = os.getenv("DATACOM_OLTS", "").strip()

if not datacom_olts_env:
    log("ERRO: Variável DATACOM_OLTS não definida no .env. Nada a fazer.")
    sys.exit(1)

OLT_NAMES = [name.strip() for name in datacom_olts_env.split(",") if name.strip()]

# IP do servidor TFTP (onde o arquivo será gravado)
TFTP_IP = os.getenv("TFTP_IP", "").strip()
if not TFTP_IP:
    log("ERRO: Variável TFTP_IP não definida no .env.")
    sys.exit(1)


def get_olt_config(name: str):
    """
    Lê as variáveis de ambiente para uma OLT específica.
    Convenção:
      <OLT_NAME>_IP
      <OLT_NAME>_USER
      <OLT_NAME>_PASSWORD
      <OLT_NAME>_PORT (opcional, padrão 23)
    """
    prefix = name.upper()
    ip = os.getenv(f"{prefix}_IP", "").strip()
    user = os.getenv(f"{prefix}_USER", "").strip()
    password = os.getenv(f"{prefix}_PASSWORD", "").strip()
    port = int(os.getenv(f"{prefix}_PORT", "23"))

    if not ip or not user or not password:
        log(f"ERRO: Configuração incompleta para OLT {name}. "
            f"Verifique {prefix}_IP, {prefix}_USER e {prefix}_PASSWORD no .env")
        return None

    return {
        "name": name,
        "ip": ip,
        "user": user,
        "password": password,
        "port": port,
    }


# ===============================
# Função de backup Datacom
# ===============================

def backup_olt_datacom(olt_cfg: dict):
    """
    Executa o backup de uma OLT Datacom via Telnet,
    salva o arquivo localmente na OLT (save <arquivo>)
    e depois copia via TFTP para o servidor configurado.
    """
    olt_name = olt_cfg["name"]
    ip = olt_cfg["ip"]
    user = olt_cfg["user"]
    password = olt_cfg["password"]
    port = olt_cfg["port"]

    try:
        log(f"Conectando à OLT Datacom {olt_name} ({ip}:{port}) via Telnet...")

        tn = telnetlib.Telnet(ip, port, timeout=10)

        # Login
        log("Aguardando 'login:'...")
        tn.read_until(b"login:", timeout=10)
        log(f"Enviando usuário: {user}")
        tn.write(user.encode('ascii') + b"\n")

        log("Aguardando 'Password:'...")
        tn.read_until(b"Password:", timeout=10)
        tn.write(password.encode('ascii') + b"\n")

        # Mensagem de boas-vindas do DmOS
        log("Aguardando 'Welcome to the DmOS CLI'...")
        tn.read_until(b"Welcome to the DmOS CLI", timeout=10)
        log(f"Conexão estabelecida com a OLT {olt_name}")

        # Entrar no modo de configuração
        send_command(tn, "config", wait_time=2)

        # Gerar o nome do arquivo de backup com base na OLT e na data/hora
        current_date_time = datetime.now().strftime("%d%m%y_%H%M")
        backup_filename = f"backupolt_{olt_name.lower()}_{current_date_time}.txt"
        log(f"Nome do arquivo de backup na OLT: {backup_filename}")

        # Comando para salvar o backup na OLT
        send_command(tn, f"save {backup_filename}", wait_time=5)

        # Aguarda para garantir que o arquivo foi salvo
        log("Aguardando 60 segundos para garantir gravação do backup na OLT...")
        time.sleep(60)

        # Enviar o arquivo salvo para o servidor TFTP
        tftp_cmd = f"copy file {backup_filename} tftp://{TFTP_IP}"
        log(f"Enviando arquivo para TFTP: {tftp_cmd}")
        send_command(tn, tftp_cmd, wait_time=10)

        # Aguardar mensagem "Transfer complete."
        try:
            tn.read_until(b"Transfer complete.", timeout=60)
            log(f"Backup da OLT {olt_name} transferido com sucesso para o TFTP {TFTP_IP}.")
        except EOFError:
            log(f"ATENÇÃO: Não foi possível confirmar 'Transfer complete.' para a OLT {olt_name}. "
                f"Verifique manualmente no servidor TFTP.")

        # Sair
        tn.write(b"exit\n")
        tn.close()
        log(f"Backup da OLT {olt_name} concluído.")

    except Exception as e:
        log(f"ERRO ao fazer backup da OLT {olt_name}: {e}")


# ===============================
# Função principal
# ===============================

def run_backups():
    log("=== Iniciando backups de OLTs Datacom ===")

    for name in OLT_NAMES:
        log(f"Processando OLT: {name}")
        cfg = get_olt_config(name)
        if not cfg:
            log(f"Pulando OLT {name} por configuração incompleta.")
            continue
        backup_olt_datacom(cfg)

    log("=== Processo de backup concluído para todas as OLTs configuradas ===")


if __name__ == "__main__":
    run_backups()
