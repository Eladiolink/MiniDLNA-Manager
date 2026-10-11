# MiniDLNA Web UI

Uma interface web moderna, segura e responsiva para monitoramento e gerenciamento do **MiniDLNA** (ReadyMedia) no Linux (otimizado para Arch Linux, CachyOS, Ubuntu e Debian).

---

## 🚀 Funcionalidades

- **Visão Geral em Tempo Real:**
  - Status do daemon systemd (`ativo`, `inativo`, `falhou`).
  - Contagem de mídias indexadas (Áudio, Vídeo e Imagens).
  - Tabela com dispositivos clientes UPnP/DLNA conectados na rede (IP, MAC, tipo e conexões ativas).
  - Indicação e verificação da porta HTTP em uso.

- **Gerenciador Interativo de Pastas de Mídia:**
  - Inclusão e exclusão de pastas com seleção de tipo (`Vídeo [V]`, `Áudio [A]`, `Fotos [P]`, `Fotos+Vídeos [PV]` ou `Geral`).
  - Navegador integrado para explorar e selecionar diretórios do sistema.
  - Verificação se os diretórios configurados realmente existem no disco.

- **Configurações Completas do MiniDLNA:**
  - Edição amigável dos parâmetros de `/etc/minidlna.conf` (Nome do servidor, porta, inotify, legendas, directórios de cache/logs, etc.).
  - Validação inteligente contra conflitos de porta ocupada.
  - Backup automático da configuração anterior antes de salvar.

- **Controle Total de Serviço:**
  - Iniciar, reiniciar e parar o serviço com um clique.
  - Habilitar ou desabilitar inicialização automática no boot do sistema (`systemctl enable/disable`).
  - Forçar reindexação completa da biblioteca (`minidlnad -R`).

- **Visualizador de Logs Integrado:**
  - Leitura das últimas linhas via `journalctl` em formato de console/terminal.
  - Filtro em tempo real de logs e botão para copiar para a área de transferência.

---

## 📁 Estrutura de Arquivos

```text
DLNA-UI/
├── app.py                  # Backend Flask e API REST
├── requirements.txt        # Dependências Python (Flask)
├── install.sh              # Script de instalação e configuração automatizada
├── minidlna-ui.service     # Definição do serviço systemd
├── templates/
│   └── index.html          # Interface web moderna em tema escuro
├── static/
│   ├── css/
│   │   └── style.css       # Estilos visuais responsivos
│   └── js/
│       └── main.js         # Lógica assíncrona do frontend
└── test_app.py             # Suíte de testes automatizados
```

---

## 🛠️ Instalação Automatizada

Para instalar as dependências do sistema, configurar as permissões do grupo `dlna-manager`, configurar regras `sudoers` seguras e ativar o serviço systemd:

```bash
sudo ./install.sh
```

Após a execução, o painel estará disponível em:
👉 **[http://127.0.0.1:5050](http://127.0.0.1:5050)**

---

## 💻 Execução Manual / Desenvolvimento

Caso queira executar em modo de desenvolvimento local:

1. Crie o ambiente virtual e instale as dependências:
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

2. Inicie a aplicação:
   ```bash
   ./venv/bin/python app.py
   ```

3. Acesse `http://127.0.0.1:5050` no navegador.

---

```bash
./venv/bin/python test_app.py
```

---

## 🗑️ Desinstalação Completa

Para reverter todas as configurações, remover os serviços systemd, limpar permissões e deixar o sistema no estado limpo original:

```bash
sudo ./uninstall.sh
```
