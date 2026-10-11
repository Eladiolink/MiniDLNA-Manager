/**
 * MiniDLNA Web UI - Frontend Application Logic
 * Handles real-time polling, REST API communication, folder management, and UI events.
 */

document.addEventListener("DOMContentLoaded", () => {
  // ==========================================================================
  // Global State
  // ==========================================================================
  let configData = null;
  let foldersList = [];
  let pollIntervalId = null;
  let currentBrowserPath = "/";
  let activeTab = "dashboard";
  let permissionWarningDismissed = false;

  // ==========================================================================
  // DOM Elements
  // ==========================================================================
  // Nav & Tabs
  const navItems = document.querySelectorAll(".nav-item");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const pageTitle = document.getElementById("page-title");
  const topbarServerName = document.getElementById("topbar-server-name");
  const navFoldersCount = document.getElementById("nav-folders-count");

  // Status Indicators
  const sidebarStatusDot = document.getElementById("sidebar-status-dot");
  const sidebarStatusText = document.getElementById("sidebar-status-text");
  const sidebarPortPreview = document.getElementById("sidebar-port-preview");

  // Metrics
  const metricServiceStatus = document.getElementById("metric-service-status");
  const metricBootStatus = document.getElementById("metric-boot-status");
  const metricPidSubtext = document.getElementById("metric-pid-subtext");
  const metricPort = document.getElementById("metric-port");
  const metricPortLink = document.getElementById("metric-port-link");
  const metricAudioCount = document.getElementById("metric-audio-count");
  const metricVideoCount = document.getElementById("metric-video-count");
  const metricImageCount = document.getElementById("metric-image-count");
  const metricClientsCount = document.getElementById("metric-clients-count");

  // Tables & Mini-panels
  const clientCountBadge = document.getElementById("client-count-badge");
  const clientsTableBody = document.getElementById("clients-table-body");
  const miniFoldersList = document.getElementById("mini-folders-list");
  const miniTerminalPreview = document.getElementById("mini-terminal-preview");

  // Folders UI
  const btnOpenAddFolder = document.getElementById("btn-open-add-folder");
  const addFolderBox = document.getElementById("add-folder-box");
  const newFolderPath = document.getElementById("new-folder-path");
  const newFolderType = document.getElementById("new-folder-type");
  const btnBrowseFolder = document.getElementById("btn-browse-folder");
  const btnCancelAddFolder = document.getElementById("btn-cancel-add-folder");
  const btnConfirmAddFolder = document.getElementById("btn-confirm-add-folder");
  const foldersContainer = document.getElementById("folders-container");
  const btnSaveFolders = document.getElementById("btn-save-folders");
  const btnSaveAndReindexFolders = document.getElementById("btn-save-and-reindex-folders");

  // Settings UI
  const settingsForm = document.getElementById("settings-form");

  // Service Controls
  const ctrlBtnStart = document.getElementById("ctrl-btn-start");
  const ctrlBtnRestart = document.getElementById("ctrl-btn-restart");
  const ctrlBtnStop = document.getElementById("ctrl-btn-stop");
  const ctrlBtnReindex = document.getElementById("ctrl-btn-reindex");
  const ctrlBtnEnable = document.getElementById("ctrl-btn-enable");
  const ctrlBtnDisable = document.getElementById("ctrl-btn-disable");
  const controlOutputText = document.getElementById("control-output-text");

  // Sidebar Quick Controls
  const quickBtnStart = document.getElementById("quick-btn-start");
  const quickBtnRestart = document.getElementById("quick-btn-restart");
  const quickBtnStop = document.getElementById("quick-btn-stop");

  // Logs UI
  const terminalLogOutput = document.getElementById("terminal-log-output");
  const logFilterInput = document.getElementById("log-filter-input");
  const btnRefreshLogs = document.getElementById("btn-refresh-logs");
  const btnCopyLogs = document.getElementById("btn-copy-logs");

  // Browser Modal
  const folderBrowserModal = document.getElementById("folder-browser-modal");
  const btnCloseBrowser = document.getElementById("btn-close-browser");
  const btnCancelBrowser = document.getElementById("btn-cancel-browser");
  const btnBrowserUp = document.getElementById("btn-browser-up");
  const btnSelectCurrentDir = document.getElementById("btn-select-current-dir");
  const browserCurrentPath = document.getElementById("browser-current-path");
  const browserDirsList = document.getElementById("browser-dirs-list");

  // Refresh controls
  const autoRefreshCheck = document.getElementById("auto-refresh-check");
  const btnManualRefresh = document.getElementById("btn-manual-refresh");
  const toastContainer = document.getElementById("toast-container");

  // ==========================================================================
  // Navigation & Tab Switching
  // ==========================================================================
  const tabTitles = {
    dashboard: "Visão Geral",
    folders: "Pastas de Mídia",
    settings: "Configurações",
    control: "Controle de Serviço",
    logs: "Logs do Sistema"
  };

  function switchTab(tabId) {
    if (!tabTitles[tabId]) return;
    activeTab = tabId;

    navItems.forEach(item => {
      item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
    });

    tabPanes.forEach(pane => {
      pane.classList.toggle("active", pane.id === `tab-${tabId}`);
    });

    pageTitle.textContent = tabTitles[tabId];
    window.location.hash = tabId;

    if (tabId === "logs") {
      fetchLogs();
    }
  }

  navItems.forEach(item => {
    item.addEventListener("click", e => {
      e.preventDefault();
      const tab = item.getAttribute("data-tab");
      switchTab(tab);
    });
  });

  document.querySelectorAll("[data-tab-switch]").forEach(link => {
    link.addEventListener("click", e => {
      e.preventDefault();
      const target = link.getAttribute("data-tab-switch");
      switchTab(target);
    });
  });

  // Handle URL hash on load
  const initialHash = window.location.hash.replace("#", "");
  if (initialHash && tabTitles[initialHash]) {
    switchTab(initialHash);
  }

  // ==========================================================================
  // Toast Notifications
  // ==========================================================================
  function showToast(message, type = "info", duration = 4000) {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let iconSvg = "";
    if (type === "success") {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" class="text-success"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    } else if (type === "error") {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" class="text-danger"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else if (type === "warning") {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" class="text-warning"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
    } else {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" class="text-info"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `
      ${iconSvg}
      <div style="flex: 1; word-break: break-word;">${message}</div>
    `;

    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ==========================================================================
  // Status API & Data Rendering
  // ==========================================================================
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.success) {
        updateStatusUI(data);
      }
    } catch (err) {
      console.warn("Erro ao buscar status:", err);
      sidebarStatusDot.className = "status-dot inactive";
      sidebarStatusText.textContent = "Servidor Offline";
    }
  }

  function updateStatusUI(data) {
    const svc = data.service || {};
    const metrics = data.metrics || {};
    const cfg = data.config || {};

    const isActive = !!svc.active;
    const statusText = svc.status || "inactive";

    // Sidebar indicator
    sidebarStatusDot.className = `status-dot ${isActive ? "active" : "inactive"}`;
    sidebarStatusText.textContent = isActive ? "MiniDLNA Ativo" : "MiniDLNA Parado";

    // Port display
    const port = cfg.port || 8200;
    sidebarPortPreview.textContent = `127.0.0.1:${port}`;
    metricPort.textContent = port;
    metricPortLink.href = `http://127.0.0.1:${port}/`;

    // Server name
    topbarServerName.textContent = cfg.friendly_name || "MiniDLNA Server";

    // Metric Service Card
    metricServiceStatus.textContent = isActive ? "Ativo" : (statusText === "failed" ? "Falhou" : "Inativo");
    metricServiceStatus.className = `card-value status-text ${isActive ? "active" : "inactive"}`;

    metricBootStatus.textContent = svc.enabled ? "Boot: Habilitado" : "Boot: Desabilitado";
    metricBootStatus.style.color = svc.enabled ? "var(--success)" : "var(--text-dim)";

    metricPidSubtext.textContent = svc.pid ? `PID: ${svc.pid}` : "PID: Inativo";

    // Media counts
    metricAudioCount.textContent = (metrics.audio || 0).toLocaleString();
    metricVideoCount.textContent = (metrics.video || 0).toLocaleString();
    metricImageCount.textContent = (metrics.images || 0).toLocaleString();
    metricClientsCount.textContent = (metrics.clients ? metrics.clients.length : 0);

    // Connected clients table
    renderClientsTable(metrics.clients || []);

    // Permission diagnostics check
    const diag = data.diagnostics || {};
    const warningBox = document.getElementById("permission-warning-box");
    const warningText = document.getElementById("permission-warning-text");

    if (warningBox) {
      const hasIssue = Boolean(diag.has_permission_denied || (diag.protect_home && diag.has_home_dirs));
      if (!hasIssue) {
        warningBox.style.display = "none";
        permissionWarningDismissed = false;
      } else if (!permissionWarningDismissed) {
        warningBox.style.display = "block";
        if (diag.denied_paths && diag.denied_paths.length > 0) {
          warningText.innerHTML = `O MiniDLNA não conseguiu acessar a pasta: <code>${diag.denied_paths.map(escapeHtml).join(", ")}</code> [Permission denied]. O systemd bloqueia o <code>/home</code> por padrão (<code>ProtectHome=yes</code>) e faltam permissões no sistema de arquivos.`;
        }
      } else {
        warningBox.style.display = "none";
      }
    }

    // Quick control buttons state
    if (quickBtnStart) quickBtnStart.disabled = isActive;
    if (quickBtnStop) quickBtnStop.disabled = !isActive;
    if (ctrlBtnStart) ctrlBtnStart.disabled = isActive;
    if (ctrlBtnStop) ctrlBtnStop.disabled = !isActive;
  }

  function renderClientsTable(clients) {
    clientCountBadge.textContent = `${clients.length} conectado${clients.length === 1 ? "" : "s"}`;

    if (!clients || clients.length === 0) {
      clientsTableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="5">Nenhum cliente DLNA conectado no momento.</td>
        </tr>
      `;
      return;
    }

    clientsTableBody.innerHTML = clients.map(c => `
      <tr>
        <td><strong>#${c.id}</strong></td>
        <td><span class="badge" style="background: rgba(14,165,233,0.1); color: var(--primary);">${escapeHtml(c.type)}</span></td>
        <td><code>${escapeHtml(c.ip)}</code></td>
        <td><code>${escapeHtml(c.mac)}</code></td>
        <td><span class="badge">${c.connections} conexões</span></td>
      </tr>
    `).join("");
  }

  // ==========================================================================
  // Configuration API & Form Handling
  // ==========================================================================
  async function fetchConfig() {
    try {
      const res = await fetch("/api/config");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.success && data.config) {
        configData = data.config;
        foldersList = (data.config.media_dirs || []).map(f => ({ ...f }));
        renderFolders();
        populateSettingsForm(data.config);
      }
    } catch (err) {
      console.error("Erro ao carregar configurações:", err);
      showToast("Não foi possível carregar as configurações do arquivo.", "error");
    }
  }

  function populateSettingsForm(cfg) {
    if (!cfg) return;

    // Inputs
    setInputValue("cfg-friendly_name", cfg.friendly_name || "");
    setInputValue("cfg-port", cfg.port || "8200");
    setInputValue("cfg-network_interface", cfg.network_interface || "");
    setInputValue("cfg-presentation_url", cfg.presentation_url || "");
    setInputValue("cfg-db_dir", cfg.db_dir || "");
    setInputValue("cfg-log_dir", cfg.log_dir || "");
    setInputValue("cfg-album_art_names", cfg.album_art_names || "");
    setInputValue("cfg-root_container", cfg.root_container || ".");
    setInputValue("cfg-max_connections", cfg.max_connections || "50");
    setInputValue("cfg-notify_interval", cfg.notify_interval || "900");
    setInputValue("cfg-log_level", cfg.log_level || "");

    // Checkboxes
    setCheckboxValue("cfg-inotify", cfg.inotify === "yes");
    setCheckboxValue("cfg-merge_media_dirs", cfg.merge_media_dirs === "yes");
    setCheckboxValue("cfg-enable_subtitles", cfg.enable_subtitles === "yes");
    setCheckboxValue("cfg-wide_links", cfg.wide_links === "yes");
    setCheckboxValue("cfg-strict_dlna", cfg.strict_dlna === "yes");
    setCheckboxValue("cfg-enable_tivo", cfg.enable_tivo === "yes");
  }

  function setInputValue(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }

  function setCheckboxValue(id, val) {
    const el = document.getElementById(id);
    if (el) el.checked = !!val;
  }

  // ==========================================================================
  // Media Folders Management
  // ==========================================================================
  function renderFolders() {
    navFoldersCount.textContent = foldersList.length;

    // Render in Folders Tab
    if (foldersList.length === 0) {
      foldersContainer.innerHTML = `
        <div class="empty-state-sm" style="text-align: center; padding: 2.5rem; color: var(--text-dim);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="36" height="36" style="margin-bottom: 0.5rem; opacity: 0.5;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
          <p>Nenhuma pasta de mídia configurada ainda.</p>
          <p style="font-size: 0.8rem; margin-top: 0.25rem;">Clique no botão "Adicionar Pasta" acima para começar.</p>
        </div>
      `;
    } else {
      foldersContainer.innerHTML = foldersList.map((folder, index) => {
        const typeBadge = getTypeBadge(folder.type);
        const exists = folder.exists !== false;

        return `
          <div class="folder-card">
            <div class="folder-info">
              ${typeBadge}
              <div class="folder-path-wrap">
                <span class="folder-path-text">${escapeHtml(folder.path)}</span>
                <span class="folder-status-indicator ${exists ? "exists" : "missing"}">
                  ${exists ? "✓ Pasta acessível no disco" : "⚠ Atenção: pasta não encontrada no sistema"}
                </span>
              </div>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" onclick="removeFolder(${index})" title="Remover pasta">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" class="text-danger"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              <span>Remover</span>
            </button>
          </div>
        `;
      }).join("");
    }

    // Render in Mini-folders dashboard summary
    if (foldersList.length === 0) {
      miniFoldersList.innerHTML = `<div class="empty-state-sm">Nenhuma pasta cadastrada.</div>`;
    } else {
      miniFoldersList.innerHTML = foldersList.slice(0, 4).map(f => `
        <div class="mini-folder-item">
          <span class="mini-folder-path">${escapeHtml(f.path)}</span>
          ${getTypeBadge(f.type)}
        </div>
      `).join("");
    }
  }

  function getTypeBadge(type) {
    const t = (type || "ALL").toUpperCase();
    if (t === "V") return `<span class="type-pill type-v">Vídeos (V)</span>`;
    if (t === "A") return `<span class="type-pill type-a">Músicas (A)</span>`;
    if (t === "P") return `<span class="type-pill type-p">Fotos (P)</span>`;
    if (t === "PV") return `<span class="type-pill type-pv">Fotos e Vídeos (PV)</span>`;
    return `<span class="type-pill type-all">Geral</span>`;
  }

  window.removeFolder = function(index) {
    if (index >= 0 && index < foldersList.length) {
      const removed = foldersList.splice(index, 1);
      renderFolders();
      showToast(`Pasta '${removed[0].path}' removida da lista. Lembre-se de salvar!`, "warning");
    }
  };

  btnOpenAddFolder.addEventListener("click", () => {
    addFolderBox.style.display = addFolderBox.style.display === "none" ? "block" : "none";
    if (addFolderBox.style.display === "block") {
      newFolderPath.focus();
    }
  });

  btnCancelAddFolder.addEventListener("click", () => {
    addFolderBox.style.display = "none";
    newFolderPath.value = "";
  });

  btnConfirmAddFolder.addEventListener("click", () => {
    const path = newFolderPath.value.trim();
    const type = newFolderType.value;

    if (!path) {
      showToast("Informe o caminho da pasta.", "warning");
      newFolderPath.focus();
      return;
    }

    // Check duplicate
    if (foldersList.some(f => f.path === path)) {
      showToast("Este caminho já está na lista de pastas.", "warning");
      return;
    }

    foldersList.push({
      path: path,
      type: type,
      exists: true
    });

    renderFolders();
    newFolderPath.value = "";
    addFolderBox.style.display = "none";
    showToast("Pasta adicionada! Clique em 'Salvar Configuração de Pastas' para confirmar.", "success");
  });

  async function saveFoldersConfig(forceReindex = false) {
    if (!configData) configData = {};
    const payload = {
      ...configData,
      media_dirs: foldersList
    };

    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        showToast("Configuração de pastas salva com sucesso!", "success");
        if (data.warnings && data.warnings.length > 0) {
          data.warnings.forEach(w => showToast(w, "warning", 6000));
        }

        if (forceReindex) {
          executeServiceAction("reindex");
        } else {
          // Offer to restart service
          executeServiceAction("restart");
        }
        fetchStatus();
      } else {
        showToast(data.error || "Erro ao salvar pastas.", "error");
      }
    } catch (err) {
      showToast(`Erro de conexão ao salvar: ${err.message}`, "error");
    }
  }

  btnSaveFolders.addEventListener("click", () => saveFoldersConfig(false));
  btnSaveAndReindexFolders.addEventListener("click", () => saveFoldersConfig(true));

  // ==========================================================================
  // Settings Form Submit
  // ==========================================================================
  settingsForm.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      friendly_name: document.getElementById("cfg-friendly_name").value.trim(),
      port: parseInt(document.getElementById("cfg-port").value, 10) || 8200,
      network_interface: document.getElementById("cfg-network_interface").value.trim(),
      presentation_url: document.getElementById("cfg-presentation_url").value.trim(),
      db_dir: document.getElementById("cfg-db_dir").value.trim(),
      log_dir: document.getElementById("cfg-log_dir").value.trim(),
      album_art_names: document.getElementById("cfg-album_art_names").value.trim(),
      root_container: document.getElementById("cfg-root_container").value,
      max_connections: parseInt(document.getElementById("cfg-max_connections").value, 10) || 50,
      notify_interval: parseInt(document.getElementById("cfg-notify_interval").value, 10) || 900,
      log_level: document.getElementById("cfg-log_level").value.trim(),
      inotify: document.getElementById("cfg-inotify").checked ? "yes" : "no",
      merge_media_dirs: document.getElementById("cfg-merge_media_dirs").checked ? "yes" : "no",
      enable_subtitles: document.getElementById("cfg-enable_subtitles").checked ? "yes" : "no",
      wide_links: document.getElementById("cfg-wide_links").checked ? "yes" : "no",
      strict_dlna: document.getElementById("cfg-strict_dlna").checked ? "yes" : "no",
      enable_tivo: document.getElementById("cfg-enable_tivo").checked ? "yes" : "no",
      media_dirs: foldersList
    };

    const submitBtn = document.getElementById("btn-submit-settings");
    submitBtn.disabled = true;
    submitBtn.textContent = "Gravando...";

    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        showToast("Configurações salvas no arquivo com sucesso!", "success");
        if (data.warnings && data.warnings.length > 0) {
          data.warnings.forEach(w => showToast(w, "warning", 6000));
        }
        configData = payload;
        // Prompt restart
        executeServiceAction("restart");
      } else {
        showToast(data.error || "Erro ao salvar configurações.", "error");
      }
    } catch (err) {
      showToast(`Falha na requisição: ${err.message}`, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
          <polyline points="17 21 17 13 7 13 7 21"></polyline>
          <polyline points="7 3 7 8 15 8"></polyline>
        </svg>
        <span>Salvar Configurações</span>
      `;
    }
  });

  // ==========================================================================
  // Service Control Execution
  // ==========================================================================
  async function executeServiceAction(action) {
    const actionNames = {
      start: "Iniciar",
      stop: "Parar",
      restart: "Reiniciar",
      reindex: "Reindexar biblioteca",
      enable: "Habilitar no boot",
      disable: "Desabilitar no boot"
    };

    sidebarStatusDot.className = "status-dot transitioning";
    sidebarStatusText.textContent = `${actionNames[action] || action}...`;

    if (controlOutputText) {
      controlOutputText.textContent = `[${new Date().toLocaleTimeString()}] Executando: systemctl ${action} minidlna...`;
    }

    try {
      const res = await fetch(`/api/service/${action}`, { method: "POST" });
      const data = await res.json();

      if (data.success) {
        showToast(data.message || `Ação '${action}' concluída com sucesso!`, "success");
        if (controlOutputText) {
          controlOutputText.textContent = `[${new Date().toLocaleTimeString()}] SUCESSO:\n${data.output || "Comando executado sem retorno textual."}`;
        }
      } else {
        showToast(data.error || `Erro ao executar ação '${action}'.`, "error");
        if (controlOutputText) {
          controlOutputText.textContent = `[${new Date().toLocaleTimeString()}] ERRO:\n${data.error || ""}\n${data.output || ""}`;
        }
      }
    } catch (err) {
      showToast(`Falha de comunicação: ${err.message}`, "error");
      if (controlOutputText) {
        controlOutputText.textContent = `[${new Date().toLocaleTimeString()}] FALHA DE REDE: ${err.message}`;
      }
    } finally {
      setTimeout(fetchStatus, 1000);
      setTimeout(fetchLogs, 1500);
    }
  }

  // Connect action buttons
  if (ctrlBtnStart) ctrlBtnStart.addEventListener("click", () => executeServiceAction("start"));
  if (ctrlBtnRestart) ctrlBtnRestart.addEventListener("click", () => executeServiceAction("restart"));
  if (ctrlBtnStop) ctrlBtnStop.addEventListener("click", () => executeServiceAction("stop"));
  if (ctrlBtnReindex) ctrlBtnReindex.addEventListener("click", () => executeServiceAction("reindex"));
  if (ctrlBtnEnable) ctrlBtnEnable.addEventListener("click", () => executeServiceAction("enable"));
  if (ctrlBtnDisable) ctrlBtnDisable.addEventListener("click", () => executeServiceAction("disable"));

  if (quickBtnStart) quickBtnStart.addEventListener("click", () => executeServiceAction("start"));
  if (quickBtnRestart) quickBtnRestart.addEventListener("click", () => executeServiceAction("restart"));
  if (quickBtnStop) quickBtnStop.addEventListener("click", () => executeServiceAction("stop"));

  // ==========================================================================
  // Logs Viewer
  // ==========================================================================
  let cachedLogs = [];

  async function fetchLogs() {
    try {
      const res = await fetch("/api/logs?lines=120");
      if (!res.ok) return;
      const data = await res.json();

      if (data.success && data.logs) {
        cachedLogs = data.logs;
        renderLogs();
      }
    } catch (err) {
      console.warn("Erro ao buscar logs:", err);
    }
  }

  function renderLogs() {
    const filter = (logFilterInput ? logFilterInput.value : "").trim().toLowerCase();
    const filtered = filter ? cachedLogs.filter(line => line.toLowerCase().includes(filter)) : cachedLogs;

    // Mini terminal in dashboard (last 10 lines)
    if (miniTerminalPreview) {
      const recent = cachedLogs.slice(-8);
      miniTerminalPreview.textContent = recent.length ? recent.join("\n") : "Sem logs recentes.";
      miniTerminalPreview.scrollTop = miniTerminalPreview.scrollHeight;
    }

    // Full terminal
    if (terminalLogOutput) {
      if (filtered.length === 0) {
        terminalLogOutput.textContent = filter ? `Nenhum registro correspondente ao filtro "${filter}".` : "Nenhum log disponível.";
      } else {
        terminalLogOutput.textContent = filtered.join("\n");
      }
      const fullBody = document.getElementById("full-terminal-body");
      if (fullBody) fullBody.scrollTop = fullBody.scrollHeight;
    }
  }

  if (logFilterInput) {
    logFilterInput.addEventListener("input", renderLogs);
  }

  if (btnRefreshLogs) {
    btnRefreshLogs.addEventListener("click", () => {
      fetchLogs();
      showToast("Logs atualizados.", "info", 1500);
    });
  }

  if (btnCopyLogs) {
    btnCopyLogs.addEventListener("click", async () => {
      const text = cachedLogs.join("\n");
      try {
        await navigator.clipboard.writeText(text);
        showToast("Logs copiados para a área de transferência!", "success");
      } catch {
        showToast("Não foi possível copiar automaticamente.", "warning");
      }
    });
  }

  // ==========================================================================
  // Directory Browser Modal
  // ==========================================================================
  async function loadDirectory(path) {
    try {
      browserDirsList.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--text-dim);">Carregando diretórios...</div>`;
      const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
      const data = await res.json();

      if (data.success) {
        currentBrowserPath = data.current;
        browserCurrentPath.textContent = data.current;

        btnBrowserUp.disabled = (data.current === "/" || data.current === data.parent);
        btnBrowserUp.onclick = () => loadDirectory(data.parent);

        if (!data.directories || data.directories.length === 0) {
          browserDirsList.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--text-dim);">Nenhum subdiretório acessível nesta pasta.</div>`;
          return;
        }

        browserDirsList.innerHTML = data.directories.map(d => `
          <div class="browser-item" data-path="${escapeHtml(d.path)}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            <span>${escapeHtml(d.name)}</span>
          </div>
        `).join("");

        // Attach double-click and single click
        browserDirsList.querySelectorAll(".browser-item").forEach(item => {
          const itemPath = item.getAttribute("data-path");
          item.addEventListener("dblclick", () => loadDirectory(itemPath));
          item.addEventListener("click", () => {
            browserDirsList.querySelectorAll(".browser-item").forEach(i => i.style.background = "");
            item.style.background = "var(--bg-card-hover)";
            currentBrowserPath = itemPath;
            browserCurrentPath.textContent = itemPath;
          });
        });
      } else {
        showToast(data.error || "Erro ao listar diretório.", "error");
      }
    } catch (err) {
      showToast(`Erro ao carregar diretório: ${err.message}`, "error");
    }
  }

  btnBrowseFolder.addEventListener("click", () => {
    folderBrowserModal.style.display = "flex";
    const initial = newFolderPath.value.trim() || "/home";
    loadDirectory(initial);
  });

  function closeBrowserModal() {
    folderBrowserModal.style.display = "none";
  }

  btnCloseBrowser.addEventListener("click", closeBrowserModal);
  btnCancelBrowser.addEventListener("click", closeBrowserModal);

  btnSelectCurrentDir.addEventListener("click", () => {
    newFolderPath.value = currentBrowserPath;
    closeBrowserModal();
  });

  // ==========================================================================
  // Auto-Refresh & Polling Loop
  // ==========================================================================
  function setupPolling() {
    if (pollIntervalId) clearInterval(pollIntervalId);

    if (autoRefreshCheck.checked) {
      pollIntervalId = setInterval(() => {
        fetchStatus();
        if (activeTab === "logs") {
          fetchLogs();
        }
      }, 4000);
    }
  }

  autoRefreshCheck.addEventListener("change", setupPolling);

  btnManualRefresh.addEventListener("click", () => {
    fetchStatus();
    fetchConfig();
    fetchLogs();
    showToast("Dados atualizados.", "info", 1500);
  });

  const btnDismissWarning = document.getElementById("btn-dismiss-permission-warning");
  if (btnDismissWarning) {
    btnDismissWarning.addEventListener("click", () => {
      permissionWarningDismissed = true;
      const warningBox = document.getElementById("permission-warning-box");
      if (warningBox) warningBox.style.display = "none";
    });
  }

  // ==========================================================================
  // Utilities
  // ==========================================================================
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ==========================================================================
  // Initial Boot
  // ==========================================================================
  fetchStatus();
  fetchConfig();
  fetchLogs();
  setupPolling();
});
