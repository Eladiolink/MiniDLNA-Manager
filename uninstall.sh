#!/usr/bin/env bash
# ==============================================================================
# Script de Desinstalação Completa: MiniDLNA Web UI
# Restaura o sistema para o estado original
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}"
echo "======================================================"
echo "      MiniDLNA Web UI - Desinstalador Completo        "
echo "======================================================"
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERRO] Este script precisa ser executado com privilégios de root (sudo).${NC}"
  echo "Por favor, execute: sudo ./uninstall.sh"
  exit 1
fi

ACTUAL_USER="${SUDO_USER:-$USER}"
if [ "$ACTUAL_USER" = "root" ]; then
  ACTUAL_USER=$(logname 2>/dev/null || echo "")
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Parar e desabilitar serviços systemd
echo -e "\n${BLUE}[1/6] Parando e desabilitando serviços systemd...${NC}"
systemctl stop minidlna-ui.service 2>/dev/null || true
systemctl disable minidlna-ui.service 2>/dev/null || true
systemctl stop minidlna.service 2>/dev/null || true
systemctl disable minidlna.service 2>/dev/null || true

# 2. Remover arquivos de serviço do systemd e overrides
echo -e "\n${BLUE}[2/6] Removendo arquivos de configuração do systemd...${NC}"
if [ -f "/etc/systemd/system/minidlna-ui.service" ]; then
  rm -f "/etc/systemd/system/minidlna-ui.service"
  echo "Removido /etc/systemd/system/minidlna-ui.service"
fi

if [ -d "/etc/systemd/system/minidlna.service.d" ]; then
  rm -rf "/etc/systemd/system/minidlna.service.d"
  echo "Removido diretório /etc/systemd/system/minidlna.service.d"
fi

systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

# 3. Remover regras sudoers
echo -e "\n${BLUE}[3/6] Removendo permissões sudoers...${NC}"
if [ -f "/etc/sudoers.d/dlna-manager" ]; then
  rm -f "/etc/sudoers.d/dlna-manager"
  echo "Removido /etc/sudoers.d/dlna-manager"
fi

# 4. Restaurar permissões do arquivo minidlna.conf e limpar banco de dados
echo -e "\n${BLUE}[4/6] Restaurando permissões de configuração e cache...${NC}"
if [ -f "/etc/minidlna.conf" ]; then
  chown root:root "/etc/minidlna.conf" 2>/dev/null || true
  chmod 644 "/etc/minidlna.conf" 2>/dev/null || true
  echo "Permissões de /etc/minidlna.conf restauradas para root:root (644)."
fi

# Limpar banco de cache do minidlna
rm -f /var/cache/minidlna/files.db 2>/dev/null || true
rm -rf /var/cache/minidlna/art_cache 2>/dev/null || true

# 5. Remover permissões ACL no diretório pessoal do usuário
echo -e "\n${BLUE}[5/6] Removendo regras ACL do usuário...${NC}"
if [ -n "$ACTUAL_USER" ] && [ -d "/home/$ACTUAL_USER" ]; then
  setfacl -x u:minidlna,u:dlna-manager "/home/$ACTUAL_USER" 2>/dev/null || true
  if [ -d "/home/$ACTUAL_USER/Downloads" ]; then
    setfacl -R -x u:minidlna,u:dlna-manager "/home/$ACTUAL_USER/Downloads" 2>/dev/null || true
  fi
  echo "Regras ACL removidas de /home/$ACTUAL_USER."
fi

# Remover usuário do grupo dlna-manager e remover o grupo se desejado
if [ -n "$ACTUAL_USER" ]; then
  gpasswd -d "$ACTUAL_USER" dlna-manager 2>/dev/null || true
fi
if getent group dlna-manager &>/dev/null; then
  groupdel dlna-manager 2>/dev/null || true
  echo "Grupo dlna-manager removido."
fi
if id dlna-manager &>/dev/null; then
  userdel dlna-manager 2>/dev/null || true
fi

# 6. Remover ambiente virtual Python (venv)
echo -e "\n${BLUE}[6/6] Limpando ambiente virtual Python (venv)...${NC}"
if [ -d "$PROJECT_DIR/venv" ]; then
  rm -rf "$PROJECT_DIR/venv"
  echo "Ambiente virtual $PROJECT_DIR/venv removido."
fi
rm -rf "$PROJECT_DIR/__pycache__" 2>/dev/null || true

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}      Desinstalação concluída com sucesso!            ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo "O sistema foi restaurado para o estado limpo original."
echo "Para reinstalar quando desejar, execute: sudo ./install.sh"
echo ""
