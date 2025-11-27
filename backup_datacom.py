#!/usr/bin/env python3
import telnetlib
import paramiko
import time
import os
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from telegram import Bot

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
LOG_DIR = Path("/home/oltdatacom/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = LOG_DIR / f"backup_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Diretório para salvar backups temporariamente
BACKUP_DIR = Path("/home/oltdatacom/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Configurações do Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Carregar lista de OLTs do ambiente
def load_olts_from_env():
    """Carrega configurações das OLTs das variáveis de ambiente."""
    olts = {}
    
    # Lista de nomes de OLTs esperadas
    olt_names = os.getenv('OLT_NAMES', '').split(',')
    
    if not olt_names or olt_names == ['']:
        logger.error("Variável OLT_NAMES não configurada no .env")
        return {}
    
    for olt_name in olt_names:
        olt_name = olt_name.strip()
        if not olt_name:
            continue
            
        # Buscar credenciais específicas da OLT
        ip = os.getenv(f'OLT_{olt_name}_IP')
        user = os.getenv(f'OLT_{olt_name}_USER')
        password = os.getenv(f'OLT_{olt_name}_PASS')
        
        if not all([ip, user, password]):
            logger.warning(f"OLT {olt_name} está com configuração incompleta no .env. Pulando...")
            continue
        
        olts[olt_name] = {
            'ip': ip,
            'user': user,
            'password': password
        }
        
        logger.debug(f"OLT {olt_name} carregada: IP={ip}, User={user}")
    
    logger.info(f"Total de OLTs carregadas: {len(olts)}")
    return olts


def send_telnet_command(tn, command, wait_time=2):
    """Envia comando via Telnet e retorna a resposta."""
    logger.debug(f"Enviando comando Telnet: {command}")
    tn.write(command.encode('ascii') + b"\n")
    time.sleep(wait_time)
    response = tn.read_very_eager().decode('ascii', errors='ignore')
    logger.debug(f"Resposta Telnet: {response.strip()}")
    return response


def backup_olt_telnet(olt_name, olt_info):
    """Realiza backup via Telnet da OLT Datacom."""
    logger.info(f"=" * 80)
    logger.info(f"Iniciando backup da OLT: {olt_name}")
    logger.info(f"IP: {olt_info['ip']}")
    
    try:
        # Conectar via Telnet
        logger.info(f"Conectando via Telnet em {olt_info['ip']}:23...")
        tn = telnetlib.Telnet(olt_info["ip"], 23, timeout=30)
        
        # Login
        logger.debug("Aguardando prompt de login...")
        tn.read_until(b"login:", timeout=15)
        tn.write(olt_info["user"].encode('ascii') + b"\n")
        
        logger.debug("Aguardando prompt de senha...")
        tn.read_until(b"Password:", timeout=15)
        tn.write(olt_info["password"].encode('ascii') + b"\n")
        
        logger.debug("Aguardando boas-vindas...")
        tn.read_until(b"Welcome to the DmOS CLI", timeout=15)
        logger.info(f"Conexão Telnet estabelecida com sucesso na OLT {olt_name}")
        
        # Entrar no modo de configuração
        logger.debug("Entrando no modo de configuração...")
        send_telnet_command(tn, "config")
        
        # Gerar nome do arquivo
        current_date_time = datetime.now().strftime("%d%m%y_%H%M")
        backup_filename = f"backupolt{olt_name.lower()}{current_date_time}.txt"
        logger.info(f"Nome do arquivo de backup: {backup_filename}")
        
        # Salvar configuração
        logger.info("Executando comando 'save' na OLT...")
        send_telnet_command(tn, f'save {backup_filename}', wait_time=5)
        
        # Aguardar salvamento
        logger.info("Aguardando 30 segundos para conclusão do salvamento...")
        time.sleep(30)
        
        # Sair do modo config
        logger.debug("Saindo do modo de configuração...")
        send_telnet_command(tn, "exit")
        
        # Fechar conexão Telnet
        tn.write(b"exit\n")
        tn.close()
        logger.info(f"Conexão Telnet fechada com {olt_name}")
        
        # Aguardar um pouco antes do SCP
        time.sleep(5)
        
        # Baixar arquivo via SCP
        local_file_path = BACKUP_DIR / backup_filename
        success = download_file_scp(olt_info, backup_filename, local_file_path)
        
        if success:
            logger.info(f"Backup da OLT {olt_name} concluído com sucesso!")
            return local_file_path
        else:
            logger.error(f"Falha ao baixar backup da OLT {olt_name} via SCP")
            return None
            
    except Exception as e:
        logger.error(f"ERRO ao fazer backup da OLT {olt_name}: {e}", exc_info=True)
        return None


def download_file_scp(olt_info, remote_filename, local_path):
    """Baixa arquivo da OLT via SCP."""
    logger.info(f"Iniciando download via SCP: {remote_filename}")
    logger.debug(f"Host: {olt_info['ip']}, User: {olt_info['user']}")
    
    try:
        # Criar cliente SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logger.debug("Conectando via SSH para SCP...")
        ssh.connect(
            hostname=olt_info['ip'],
            username=olt_info['user'],
            password=olt_info['password'],
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )
        
        logger.info("Conexão SSH estabelecida")
        
        # Abrir SFTP
        sftp = ssh.open_sftp()
        logger.debug("Canal SFTP aberto")
        
        # O arquivo fica na raiz do sistema da OLT Datacom
        remote_file = f"/{remote_filename}"
        
        logger.info(f"Baixando arquivo: {remote_file} -> {local_path}")
        sftp.get(remote_file, str(local_path))
        
        sftp.close()
        ssh.close()
        
        logger.info(f"Download concluído com sucesso: {local_path}")
        logger.info(f"Tamanho do arquivo: {local_path.stat().st_size} bytes")
        
        return True
        
    except Exception as e:
        logger.error(f"ERRO ao baixar arquivo via SCP: {e}", exc_info=True)
        return False


async def send_telegram_file(file_path, olt_name):
    """Envia arquivo via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Token ou Chat ID do Telegram não configurados. Pulando envio.")
        return False
    
    logger.info(f"Enviando arquivo para o Telegram: {file_path.name}")
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        caption = f"✅ Backup OLT: {olt_name}\n📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        
        with open(file_path, 'rb') as f:
            await bot.send_document(
                chat_id=TELEGRAM_CHAT_ID,
                document=f,
                caption=caption,
                filename=file_path.name
            )
        
        logger.info(f"Arquivo enviado com sucesso para o Telegram: {file_path.name}")
        return True
        
    except Exception as e:
        logger.error(f"ERRO ao enviar arquivo para o Telegram: {e}", exc_info=True)
        return False


async def send_telegram_message(message):
    """Envia mensagem de texto via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        return True
    except Exception as e:
        logger.error(f"ERRO ao enviar mensagem para o Telegram: {e}", exc_info=True)
        return False


async def run_backups():
    """Executa backup de todas as OLTs."""
    logger.info("=" * 80)
    logger.info("INICIANDO PROCESSO DE BACKUP DE TODAS AS OLTs DATACOM")
    logger.info(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Carregar OLTs do .env
    olts = load_olts_from_env()
    
    if not olts:
        logger.error("Nenhuma OLT foi carregada. Verifique o arquivo .env")
        await send_telegram_message("🚨 ERRO: Nenhuma OLT configurada no .env")
        return
    
    success_count = 0
    failed_count = 0
    failed_olts = []
    
    # Enviar mensagem de início
    await send_telegram_message(f"🔄 Iniciando backup de {len(olts)} OLTs Datacom...")
    
    for olt_name, olt_info in olts.items():
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Processando OLT {success_count + failed_count + 1}/{len(olts)}: {olt_name}")
        
        backup_file = backup_olt_telnet(olt_name, olt_info)
        
        if backup_file and backup_file.exists():
            # Enviar arquivo para o Telegram
            telegram_success = await send_telegram_file(backup_file, olt_name)
            
            if telegram_success:
                success_count += 1
                logger.info(f"✅ Backup da OLT {olt_name} finalizado com sucesso!")
                
                # Remover arquivo local após envio bem-sucedido
                try:
                    backup_file.unlink()
                    logger.debug(f"Arquivo local removido: {backup_file}")
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo local: {e}")
            else:
                failed_count += 1
                failed_olts.append(f"{olt_name} (falha no envio Telegram)")
                logger.error(f"❌ Falha ao enviar backup da OLT {olt_name} para o Telegram")
        else:
            failed_count += 1
            failed_olts.append(olt_name)
            logger.error(f"❌ Falha no backup da OLT {olt_name}")
    
    # Relatório final
    logger.info("\n" + "=" * 80)
    logger.info("RELATÓRIO FINAL DE BACKUPS")
    logger.info("=" * 80)
    logger.info(f"✅ Sucessos: {success_count}/{len(olts)}")
    logger.info(f"❌ Falhas: {failed_count}/{len(olts)}")
    
    if failed_olts:
        logger.info(f"OLTs com falha: {', '.join(failed_olts)}")
    
    logger.info("=" * 80)
    
    # Enviar relatório final via Telegram
    report = f"📊 Relatório de Backup OLTs Datacom\n\n"
    report += f"✅ Sucessos: {success_count}/{len(olts)}\n"
    report += f"❌ Falhas: {failed_count}/{len(olts)}\n"
    
    if failed_olts:
        report += f"\n⚠️ Falhas em:\n" + "\n".join([f"• {olt}" for olt in failed_olts])
    
    report += f"\n\n🕐 Concluído em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    
    await send_telegram_message(report)


def main():
    """Função principal."""
    try:
        asyncio.run(run_backups())
    except Exception as e:
        logger.error(f"ERRO CRÍTICO no processo de backup: {e}", exc_info=True)
        asyncio.run(send_telegram_message(f"🚨 ERRO CRÍTICO no backup de OLTs: {str(e)}"))


if __name__ == "__main__":
    main()
