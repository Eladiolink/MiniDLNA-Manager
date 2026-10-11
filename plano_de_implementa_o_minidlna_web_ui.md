# Plano de Implementação: MiniDLNA Web UI

Este documento descreve o plano arquitetural e os passos de implementação para a criação de uma interface web local de gerenciamento do **MiniDLNA** (ReadyMedia) no Linux (com foco inicial em **Arch Linux / CachyOS**, mantendo compatibilidade com Ubuntu/Debian).

---

## 1. Visão Geral da Arquitetura

O projeto adota uma arquitetura cliente-servidor leve executada localmente, garantindo segurança ao restringir o acesso à interface estritamente ao localhost (`127.0.0.1`).

*   **Frontend:** HTML5, CSS3 (com utilitários ou design customizado baseado no tema escuro da interface de referência) e JavaScript Vanilla.
*   **Backend:** Python com **Flask**, responsável por fornecer as rotas da API REST, ler/escrever arquivos de configuração com privilégios adequados e interagir com o sistema operacional.
*   **Gerenciamento de Serviços:** Integração nativa com o **systemd** via comandos de terminal (`systemctl`).
*   **Permissões de Execução (Segurança):** Uso de arquivos de configuração específicos ou regras `sudoers` restritas para que o backend Flask possa alterar `/etc/minidlna.conf` e controlar o serviço sem requerer privilégios de root na aplicação inteira.

---

## 2. Estrutura de Diretórios do Projeto

```text
minidlna-webui/
├── app.py                  # Aplicação principal Flask (Backend)
├── requirements.txt        # Dependências do Python (Flask, etc.)
├── install.sh              # Script de automação da instalação no Arch/CachyOS
├── minidlna-ui.service     # Arquivo de serviço systemd para o painel
├── static/
│   ├── css/
│   │   └── style.css       # Estilos customizados (tema escuro, cards, ícones)
│   └── js/
│       └── main.js         # Lógica do frontend (fetch API, atualização em tempo real)
└── templates/
    └── index.html          # Template HTML principal (Painel e subseções)
```

---

## 3. Especificações por Módulo

### 3.1. Backend (Python / Flask)
*   **Leitura e Escrita de Configuração (`/etc/minidlna.conf`):**
    *   Parser em Python para extrair parâmetros cruciais como `port=8200`, `media_dir=...`, e `friendly_name`.
    *   Validação de portas para mitigar o problema de porta ocupada (verificação de disponibilidade de socket antes de aplicar a nova porta).
*   **Rotas da API:**
    *   `GET /api/status`: Retorna o estado do serviço systemd (`active`, `inactive`), contagem de arquivos indexados e conexões ativas.
    *   `POST /api/config`: Salva as alterações de configuração e manipula o arquivo `/etc/minidlna.conf`.
    *   `POST /api/service/<action>`: Executa ações (`start`, `stop`, `restart`, `reindex`) acionando o MiniDLNA com a flag `-R` para reindexação forçada.
    *   `GET /api/logs`: Lê as últimas linhas do log do MiniDLNA (via `journalctl -u minidlna`).

### 3.2. Frontend (HTML/CSS/JS)
*   **Layout Base:** Inspirado no painel de controle escuro da imagem de referência, dividindo a tela em:
    *   Barra de navegação lateral (Início, Pastas de mídia, Configurações, Logs, Status, Controle).
    *   Painel central dinâmico com cartões informativos (Status do serviço, Arquivos indexados, Dispositivos conectados, Porta HTTP).
    *   Seção de gerenciamento de pastas de mídia com opção de inclusão/remoção interativa.
    *   Bloco de terminal/logs recentes e botões de controle de serviço (Iniciar, Reiniciar, Parar, Habilitar na inicialização).

---

## 4. Plano de Passos para Execução (Roadmap)

### Passo 1: Configuração do Ambiente e Dependências
1. Garantir que o `minidlna` (ou `minidlna-git` no AUR) esteja instalado no Arch Linux/CachyOS.
2. Instalar o Python e criar um ambiente virtual (`venv`) para o Flask.

### Passo 2: Desenvolvimento do Backend (`app.py`)
1. Implementar as rotas de manipulação do arquivo de configuração `/etc/minidlna.conf`.
2. Criar a interface de comunicação com o `systemctl` usando o módulo `subprocess` do Python.
3. Adicionar tratamento robusto de erros para portas em uso.

### Passo 3: Criação da Interface Gráfica (`index.html` e `style.css`)
1. Desenvolver o layout responsivo em tema escuro conforme a identidade visual planejada.
2. Integrar o JavaScript assíncrono (`fetch`) para carregar o status do servidor e atualizar os logs em tempo real sem recarregar a página.

### Passo 4: Automação e Instalação (`install.sh`)
1. Criar um script shell de instalação automatizada que:
   * Instala as dependências do sistema.
   * Configura permissões para edição segura do arquivo de configuração.
   * Cria e habilita o serviço systemd dedicado para a interface web rodando na porta local designada.
```

---

Espero que este plano estruture perfeitamente o desenvolvimento do seu painel de controle para o MiniDLNA! Você gostaria de começar gerando o código do backend (`app.py`) ou prefere focar primeiro no template HTML/CSS?