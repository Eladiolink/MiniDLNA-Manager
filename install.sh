#!/usr/bin/env bash
# ==============================================================================
# Script de Instalação e Automação: MiniDLNA Web UI
# Compatível com Arch Linux, CachyOS, Ubuntu e Debian
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "======================================================"
echo "         MiniDLNA Web UI - Instalador Automático      "
echo "======================================================"
echo -e "${NC}"

# 1. Verificar privilégios de root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERRO] Este script precisa ser executado com privilégios de superusuário (root ou sudo).${NC}"
  echo "Por favor, execute: sudo ./install.sh"
  exit 1
fi

# Identificar usuário real (não-root)
ACTUAL_USER="${SUDO_USER:-$USER}"
if [ "$ACTUAL_USER" = "root" ]; then
  ACTUAL_USER=$(logname 2>/dev/null || echo "root")
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${GREEN}[INFO] Usuário detectado: ${ACTUAL_USER}${NC}"
echo -e "${GREEN}[INFO] Diretório do projeto: ${PROJECT_DIR}${NC}"

# 2. Detecção e instalação de pacotes do sistema
echo -e "\n${BLUE}[1/5] Detectando distribuição e instalando dependências do sistema...${NC}"

if command -v pacman &>/dev/null; then
  echo "Distribuição baseada em Arch Linux / CachyOS detectada."
  pacman -Sy --needed --noconfirm minidlna python python-pip
elif command -v apt-get &>/dev/null; then
  echo "Distribuição baseada em Debian / Ubuntu detectada."
  apt-get update -y
  apt-get install -y minidlna python3 python3-pip python3-venv
elif command -v dnf &>/dev/null; then
  echo "Distribuição baseada em Fedora / RHEL detectada."
  dnf install -y minidlna python3 python3-pip
else
  echo -e "${YELLOW}[AVISO] Gerenciador de pacotes não identificado. Certifique-se de ter 'minidlna' e 'python3' instalados.${NC}"
fi

# 3. Configuração de usuário do minidlna e permissões
echo -e "\n${BLUE}[2/5] Configurando permissões do sistema e grupo dlna-manager...${NC}"

# Criar grupo dlna-manager se não existir
if ! getent group dlna-manager &>/dev/null; then
  groupadd -r dlna-manager
  echo "Grupo 'dlna-manager' criado."
fi

# Adicionar usuário ao grupo
if [ "$ACTUAL_USER" != "root" ]; then
  usermod -aG dlna-manager "$ACTUAL_USER"
  echo "Usuário '$ACTUAL_USER' adicionado ao grupo 'dlna-manager'."
fi

# Garantir existência do usuário do sistema minidlna (para evitar fatal: Bad user 'minidlna')
if ! id minidlna &>/dev/null; then
  useradd -r -s /usr/bin/nologin -d /var/cache/minidlna minidlna 2>/dev/null || true
  echo "Usuário do sistema 'minidlna' configurado."
fi

# Ajustar permissões do arquivo de configuração
CONF_FILE="/etc/minidlna.conf"
if [ ! -f "$CONF_FILE" ]; then
  if [ -f "$PROJECT_DIR/minidlna.conf" ]; then
    cp "$PROJECT_DIR/minidlna.conf" "$CONF_FILE"
  fi
fi

if [ -f "$CONF_FILE" ]; then
  chown root:dlna-manager "$CONF_FILE"
  chmod 664 "$CONF_FILE"
  echo "Permissões de $CONF_FILE ajustadas (root:dlna-manager, 664)."
fi

# Configurar override do systemd para permitir acesso a /home (ProtectHome=read-only)
echo "Configurando override do systemd para permitir acesso seguro a /home..."
MINIDLNA_DROPIN_DIR="/etc/systemd/system/minidlna.service.d"
mkdir -p "$MINIDLNA_DROPIN_DIR"
cat << 'EOF' > "$MINIDLNA_DROPIN_DIR/override.conf"
[Service]
ProtectHome=read-only
EOF
echo "Override 'ProtectHome=read-only' criado em $MINIDLNA_DROPIN_DIR/override.conf."

# Conceder permissões ACL para travessia no /home do usuário
if [ "$ACTUAL_USER" != "root" ] && [ -d "/home/$ACTUAL_USER" ]; then
  setfacl -m u:minidlna:x "/home/$ACTUAL_USER" 2>/dev/null || true
  if [ -d "/home/$ACTUAL_USER/Downloads" ]; then
    setfacl -m u:minidlna:rx "/home/$ACTUAL_USER/Downloads" 2>/dev/null || true
  fi
  echo "Permissões ACL de travessia concedidas para o usuário minidlna em /home/$ACTUAL_USER."
fi

# 4. Configurar regras sudoers seguras
echo -e "\n${BLUE}[3/5] Configurando regras sudoers (/etc/sudoers.d/dlna-manager)...${NC}"

SUDOERS_FILE="/etc/sudoers.d/dlna-manager"
cat << 'EOF' > "$SUDOERS_FILE"
# Permissões restritas e seguras para gerenciamento do MiniDLNA via Web UI
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl start minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl status minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-enabled minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl enable minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl disable minidlna
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart minidlna-ui
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/systemctl status minidlna-ui
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/minidlnad -R
%dlna-manager ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/minidlna.conf
EOF
chmod 440 "$SUDOERS_FILE"
echo "Arquivo sudoers gerado e protegido com sucesso."

# 5. Criar ambiente virtual e instalar dependências Python
echo -e "\n${BLUE}[4/5] Configurando ambiente virtual Python (venv)...${NC}"

VENV_DIR="$PROJECT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
  su - "$ACTUAL_USER" -c "python3 -m venv '$VENV_DIR'"
fi

# Instalar dependências
su - "$ACTUAL_USER" -c "'$VENV_DIR/bin/pip' install --upgrade pip"
su - "$ACTUAL_USER" -c "'$VENV_DIR/bin/pip' install -r '$PROJECT_DIR/requirements.txt'"
echo "Dependências do Python instaladas com sucesso."

# 6. Criar e registrar serviço systemd para o painel web
echo -e "\n${BLUE}[5/5] Configurando serviço systemd (minidlna-ui.service)...${NC}"

SYSTEMD_SERVICE_FILE="/etc/systemd/system/minidlna-ui.service"
cat << EOF > "$SYSTEMD_SERVICE_FILE"
[Unit]
Description=MiniDLNA Web Management UI
After=network.target minidlna.service
Wants=minidlna.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=dlna-manager
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PORT=5050
Environment=HOST=127.0.0.1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now minidlna.service
systemctl enable --now minidlna-ui.service

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}   Instalação concluída com sucesso!                   ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "O painel web está ativo e rodando como serviço systemd."
echo -e "Acesse pelo seu navegador em: ${YELLOW}http://127.0.0.1:5050/${NC}"
echo -e "Para verificar o status: ${BLUE}systemctl status minidlna-ui${NC}"
echo -e "Para ver os logs do painel: ${BLUE}journalctl -u minidlna-ui -f${NC}"
echo -e "${GREEN}======================================================${NC}\n"
