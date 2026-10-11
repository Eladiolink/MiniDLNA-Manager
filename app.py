#!/usr/bin/env python3
"""
MiniDLNA Web UI - Backend Application
Provides REST API and web interface to configure, monitor, and control MiniDLNA.
"""

import os
import sys
import re
import socket
import logging
import subprocess
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from flask import Flask, request, jsonify, render_template, abort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("minidlna-webui")

app = Flask(__name__)

# Configuration settings
CONFIG_PATH = os.environ.get("MINIDLNA_CONF", "/etc/minidlna.conf")
BACKUP_PATH = os.environ.get("MINIDLNA_CONF_BAK", "/tmp/minidlna.conf.bak")
SERVICE_NAME = "minidlna"

# Default fallback config template if /etc/minidlna.conf doesn't exist
DEFAULT_CONF_TEMPLATE = """# MiniDLNA Configuration File
# port for HTTP (descriptions, SOAP, media transfer) traffic
port=8200

# network interfaces to serve, comma delimited (8 interfaces max)
#network_interface=

# specify the user account name or uid to run as (commented out for systemd DynamicUser)
#user=minidlna

# set this to the directory you want scanned.
# * media_dir=V,/path/to/videos
# * media_dir=A,/path/to/music
# * media_dir=P,/path/to/pictures
# * media_dir=/path/to/all
media_dir=/var/media

# set this to merge all media_dir base contents into the root container
#merge_media_dirs=no

# set this if you want to customize the name that shows up on your clients
friendly_name=MiniDLNA Server

# set this if you would like to specify the directory where you want MiniDLNA to store its database and album art cache
#db_dir=/var/cache/minidlna

# set this if you would like to specify the directory where you want MiniDLNA to store its log file
#log_dir=/var/log

# log level: off, fatal, error, warn, info, or debug
#log_level=general,artwork,database,inotify,scanner,metadata,http,ssdp,tivo=warn

# list of file names to check for when searching for album art
album_art_names=Cover.jpg/cover.jpg/AlbumArtSmall.jpg/albumartsmall.jpg/AlbumArt.jpg/albumart.jpg/Album.jpg/album.jpg/Folder.jpg/folder.jpg/Thumb.jpg/thumb.jpg

# automatic discovery of new files via inotify
inotify=yes

# TiVo support
enable_tivo=no
tivo_discovery=bonjour

# DLNA strict compliance
strict_dlna=no

# notify interval in seconds
notify_interval=900

# serial and model number
serial=12345678
model_number=1

# root container: . (default), B (Browse Directory), M (Music), V (Video), P (Pictures)
root_container=.

# maximum simultaneous connections
max_connections=50

# allow symlinks pointing outside media_dirs
wide_links=no

# enable subtitle support
enable_subtitles=yes
"""

# ==============================================================================
# Helper Functions
# ==============================================================================

def execute_command(cmd, use_sudo_fallback=True):
    """
    Executes a shell command. If unprivileged execution fails with permission errors,
    attempts with sudo -n if available.
    """
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if res.returncode == 0:
            return True, res.stdout.strip(), ""
        
        # If failed and sudo fallback enabled, try with sudo -n
        if use_sudo_fallback and cmd[0] != "sudo":
            sudo_cmd = ["sudo", "-n"] + cmd
            sudo_res = subprocess.run(sudo_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if sudo_res.returncode == 0:
                return True, sudo_res.stdout.strip(), ""
            return False, sudo_res.stdout.strip(), sudo_res.stderr.strip()
        
        return False, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Comando expirou o tempo limite de execução (timeout)."
    except Exception as e:
        return False, "", str(e)


def is_port_in_use(port, host="127.0.0.1"):
    """Check if a TCP port is in use on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def check_port_conflict(new_port, current_port=None, service_is_active=False):
    """
    Checks if new_port conflicts with another application.
    If service_is_active and new_port == current_port, it is expected to be in use by minidlna.
    """
    try:
        port = int(new_port)
    except (ValueError, TypeError):
        return False, "Porta deve ser um número inteiro válido (1024 - 65535)."

    if not (1024 <= port <= 65535):
        return False, "Porta fora do intervalo permitido para serviços de usuário (1024 - 65535)."

    if service_is_active and current_port is not None and port == int(current_port):
        # Already used by minidlna, so no conflict
        return True, ""

    if is_port_in_use(port):
        return False, f"A porta {port} já está em uso por outro processo no sistema."

    return True, ""


# ==============================================================================
# Configuration Parser & Writer
# ==============================================================================

def read_config():
    """
    Reads and parses the MiniDLNA configuration file.
    Returns:
        dict: parsed configuration values and raw media_dirs list.
    """
    target_path = CONFIG_PATH
    if not os.path.isfile(target_path):
        logger.warning("Config file %s does not exist. Using fallback template.", target_path)
        content = DEFAULT_CONF_TEMPLATE
    else:
        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except PermissionError:
            # Try reading with sudo cat
            success, out, _ = execute_command(["cat", target_path])
            if success:
                content = out
            else:
                logger.error("Failed to read %s. Using default template.", target_path)
                content = DEFAULT_CONF_TEMPLATE

    config_data = {
        "port": "8200",
        "friendly_name": "MiniDLNA Server",
        "media_dirs": [],
        "network_interface": "",
        "user": "",
        "db_dir": "",
        "log_dir": "",
        "log_level": "",
        "album_art_names": "Cover.jpg/cover.jpg/AlbumArtSmall.jpg/albumartsmall.jpg/AlbumArt.jpg/albumart.jpg/Album.jpg/album.jpg/Folder.jpg/folder.jpg/Thumb.jpg/thumb.jpg",
        "inotify": "yes",
        "enable_tivo": "no",
        "tivo_discovery": "bonjour",
        "strict_dlna": "no",
        "presentation_url": "",
        "notify_interval": "900",
        "serial": "12345678",
        "model_number": "1",
        "root_container": ".",
        "max_connections": "50",
        "wide_links": "no",
        "enable_subtitles": "yes",
        "merge_media_dirs": "no",
    }

    media_dirs = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()

        if key == "media_dir":
            # Formats:
            # media_dir=/path
            # media_dir=V,/path
            # media_dir=A,/path
            # media_dir=P,/path
            # media_dir=PV,/path
            dir_type = "ALL"
            dir_path = val
            if "," in val:
                type_prefix, p = val.split(",", 1)
                type_prefix = type_prefix.strip().upper()
                if type_prefix in ["V", "A", "P", "PV"]:
                    dir_type = type_prefix
                    dir_path = p.strip()
            
            exists = os.path.isdir(dir_path)
            media_dirs.append({
                "type": dir_type,
                "path": dir_path,
                "exists": exists
            })
        else:
            if key in config_data:
                config_data[key] = val

    config_data["media_dirs"] = media_dirs
    return config_data


def write_config(data):
    """
    Writes updated configuration to CONFIG_PATH.
    Preserves original structure and comments where possible.
    """
    target_path = CONFIG_PATH

    # Read existing content if exists to preserve comments
    existing_lines = []
    if os.path.isfile(target_path):
        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                existing_lines = f.readlines()
        except PermissionError:
            success, out, _ = execute_command(["cat", target_path])
            if success:
                existing_lines = [l + "\n" for l in out.splitlines()]

    # Make a backup
    try:
        if os.path.isfile(target_path):
            shutil.copy2(target_path, BACKUP_PATH)
    except Exception as e:
        logger.warning("Could not create backup at %s: %s", BACKUP_PATH, e)

    # Clean and extract media_dirs
    raw_media_dirs = data.get("media_dirs", [])
    formatted_media_dirs = []
    for m in raw_media_dirs:
        m_path = m.get("path", "").strip()
        if not m_path:
            continue
        m_type = m.get("type", "ALL").strip().upper()
        if m_type in ["V", "A", "P", "PV"]:
            formatted_media_dirs.append(f"media_dir={m_type},{m_path}")
        else:
            formatted_media_dirs.append(f"media_dir={m_path}")

    # Standard known keys to update
    standard_keys = {
        "port": str(data.get("port", "8200")).strip(),
        "friendly_name": str(data.get("friendly_name", "MiniDLNA Server")).strip(),
        "network_interface": str(data.get("network_interface", "")).strip(),
        "inotify": "yes" if data.get("inotify") in [True, "yes", "on", 1, "1"] else "no",
        "merge_media_dirs": "yes" if data.get("merge_media_dirs") in [True, "yes", "on", 1, "1"] else "no",
        "db_dir": str(data.get("db_dir", "")).strip(),
        "log_dir": str(data.get("log_dir", "")).strip(),
        "log_level": str(data.get("log_level", "")).strip(),
        "album_art_names": str(data.get("album_art_names", "")).strip(),
        "strict_dlna": "yes" if data.get("strict_dlna") in [True, "yes", "on", 1, "1"] else "no",
        "enable_tivo": "yes" if data.get("enable_tivo") in [True, "yes", "on", 1, "1"] else "no",
        "tivo_discovery": str(data.get("tivo_discovery", "bonjour")).strip(),
        "notify_interval": str(data.get("notify_interval", "900")).strip(),
        "serial": str(data.get("serial", "12345678")).strip(),
        "model_number": str(data.get("model_number", "1")).strip(),
        "root_container": str(data.get("root_container", ".")).strip(),
        "max_connections": str(data.get("max_connections", "50")).strip(),
        "wide_links": "yes" if data.get("wide_links") in [True, "yes", "on", 1, "1"] else "no",
        "enable_subtitles": "yes" if data.get("enable_subtitles") in [True, "yes", "on", 1, "1"] else "no",
        "presentation_url": str(data.get("presentation_url", "")).strip(),
    }

    # Handle user directive specifically: if DynamicUser is enabled or user minidlna doesn't exist, comment it
    if "user" in data and data["user"].strip():
        standard_keys["user"] = data["user"].strip()

    updated_keys = set()
    new_lines = []
    media_dirs_inserted = False

    if existing_lines:
        for line in existing_lines:
            stripped = line.strip()

            # Skip existing active media_dir lines; we will insert new ones together
            if stripped.startswith("media_dir=") or stripped.startswith("media_dir ="):
                if not media_dirs_inserted:
                    for md_line in formatted_media_dirs:
                        new_lines.append(f"{md_line}\n")
                    media_dirs_inserted = True
                continue

            # Check if this line defines one of standard keys
            matched_key = None
            if "=" in stripped and not stripped.startswith("#"):
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in standard_keys:
                    matched_key = k

            if matched_key:
                val = standard_keys[matched_key]
                if val:  # only write if non-empty
                    new_lines.append(f"{matched_key}={val}\n")
                else:
                    new_lines.append(f"#{matched_key}=\n")
                updated_keys.add(matched_key)
            else:
                new_lines.append(line)

        # If media_dirs was not inserted yet (e.g., config had no previous media_dir)
        if not media_dirs_inserted:
            new_lines.append("\n# Media Directories\n")
            for md_line in formatted_media_dirs:
                new_lines.append(f"{md_line}\n")

        # Any keys not present in existing file
        for k, v in standard_keys.items():
            if k not in updated_keys and v:
                new_lines.append(f"{k}={v}\n")
    else:
        # Generate clean new file based on template
        new_lines.append("# MiniDLNA Configuration generated by Web UI\n")
        for k, v in standard_keys.items():
            if v:
                new_lines.append(f"{k}={v}\n")
        new_lines.append("\n# Media Directories\n")
        for md_line in formatted_media_dirs:
            new_lines.append(f"{md_line}\n")

    rendered_text = "".join(new_lines)

    # Attempt writing directly
    try:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(rendered_text)
        logger.info("Successfully saved configuration to %s", target_path)
        return True, ""
    except PermissionError:
        logger.info("Direct write to %s failed with PermissionError. Attempting via sudo tee...", target_path)
        # Attempt writing via sudo tee
        try:
            p = subprocess.Popen(["sudo", "-n", "tee", target_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = p.communicate(input=rendered_text, timeout=10)
            if p.returncode == 0:
                logger.info("Successfully wrote config via sudo tee to %s", target_path)
                return True, ""
            return False, f"Falha de permissão ao salvar em {target_path}: {stderr.strip()}"
        except Exception as e:
            return False, f"Erro ao tentar gravar configuração com sudo: {e}"
    except Exception as e:
        return False, f"Erro ao salvar arquivo de configuração: {e}"


# ==============================================================================
# DLNA Web Metrics & Systemd Status
# ==============================================================================

def get_systemd_status():
    """Returns the service state: active, inactive, failed, etc."""
    is_active = False
    status_str = "inactive"
    enabled_str = "unknown"
    pid = None

    # Check is-active
    success, out, _ = execute_command(["systemctl", "is-active", SERVICE_NAME], use_sudo_fallback=False)
    if success:
        status_str = out.strip()
        is_active = (status_str == "active")
    else:
        status_str = out.strip() if out else "inactive"

    # Check is-enabled
    success, out, _ = execute_command(["systemctl", "is-enabled", SERVICE_NAME], use_sudo_fallback=False)
    if success:
        enabled_str = out.strip()
    else:
        enabled_str = out.strip() if out else "disabled"

    # Try getting PID
    success, out, _ = execute_command(["systemctl", "show", SERVICE_NAME, "--property=MainPID"], use_sudo_fallback=False)
    if success and "MainPID=" in out:
        try:
            pid_val = int(out.split("=")[1].strip())
            if pid_val > 0:
                pid = pid_val
        except ValueError:
            pass

    return {
        "active": is_active,
        "status": status_str,
        "enabled": (enabled_str == "enabled"),
        "enabled_raw": enabled_str,
        "pid": pid
    }


def get_minidlna_http_metrics(port):
    """
    Queries MiniDLNA's built-in web endpoint at http://127.0.0.1:{port}/
    Extracts indexed media counts (Audio, Video, Image) and connected clients list.
    """
    url = f"http://127.0.0.1:{port}/"
    metrics = {
        "reachable": False,
        "audio": 0,
        "video": 0,
        "images": 0,
        "total": 0,
        "clients": []
    }

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MiniDLNA-WebUI/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            metrics["reachable"] = True

            # MiniDLNA HTML format typically:
            # <tr><td>Audio files</td><td>123</td></tr>
            # <tr><td>Video files</td><td>45</td></tr>
            # <tr><td>Image files</td><td>678</td></tr>
            audio_m = re.search(r"Audio files</td>\s*<td>(\d+)</td>", html, re.IGNORECASE)
            video_m = re.search(r"Video files</td>\s*<td>(\d+)</td>", html, re.IGNORECASE)
            image_m = re.search(r"Image files</td>\s*<td>(\d+)</td>", html, re.IGNORECASE)

            if audio_m:
                metrics["audio"] = int(audio_m.group(1))
            if video_m:
                metrics["video"] = int(video_m.group(1))
            if image_m:
                metrics["images"] = int(image_m.group(1))

            metrics["total"] = metrics["audio"] + metrics["video"] + metrics["images"]

            # Connected clients table:
            # <tr><td>ID</td><td>Type</td><td>IP Address</td><td>HW Address</td><td>Connections</td></tr>
            # <tr><td>1</td><td>Generic UPnP 1.0</td><td>192.168.1.150</td><td>aa:bb:cc:dd:ee:ff</td><td>1</td></tr>
            client_rows = re.findall(
                r"<tr>\s*<td>(\d+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>(\d+)</td>\s*</tr>",
                html,
                re.IGNORECASE
            )
            for cid, ctype, cip, cmac, cconns in client_rows:
                metrics["clients"].append({
                    "id": cid.strip(),
                    "type": ctype.strip(),
                    "ip": cip.strip(),
                    "mac": cmac.strip(),
                    "connections": int(cconns.strip())
                })
    except Exception as e:
        logger.debug("Could not reach MiniDLNA HTTP interface at %s: %s", url, e)

    return metrics


def get_diagnostics(cfg, metrics=None):
    """
    Checks for common Linux permission and systemd sandbox issues:
    1. ProtectHome active in systemd (blocks /home)
    2. 'Permission denied' in journalctl logs for the current service run
    """
    protect_home = False
    has_permission_denied = False
    denied_paths = []

    success, out, _ = execute_command(["systemctl", "show", SERVICE_NAME, "--property=ProtectHome"], use_sudo_fallback=False)
    if success and "=" in out:
        val = out.split("=", 1)[1].strip().lower()
        # ProtectHome blocks /home if set to yes, true, on, or tmpfs.
        # Values like 'read-only', 'no', 'off', 'false' allow access.
        protect_home = val in ["yes", "true", "on", "tmpfs"]

    # Check journalctl for Permission denied in the current service run
    success, out, _ = execute_command(["journalctl", "-u", SERVICE_NAME, "-b", "-n", "100", "--no-pager"], use_sudo_fallback=False)
    if success and out:
        lines = out.splitlines()
        # Find the start of the most recent service execution
        last_start_idx = 0
        for idx, line in enumerate(lines):
            if "Starting minidlna server" in line or "Started minidlna server" in line or "Starting MiniDLNA" in line:
                last_start_idx = idx

        current_run_lines = lines[last_start_idx:]
        scanned_paths = set()
        raw_denied = []

        for line in current_run_lines:
            sm = re.search(r'Scanning (?:finished: )?([^!]+?)(?: finished|\.\.\.|$)', line)
            if sm:
                scanned_paths.add(sm.group(1).strip())

            if "Permission denied" in line:
                m = re.search(r'Media directory "(?:[A-Z]+,)?([^"]+)" not accessible', line)
                if m:
                    raw_denied.append(m.group(1).strip())
                else:
                    has_permission_denied = True

        # Any path that was denied and not successfully scanned afterwards
        active_denied = [p for p in set(raw_denied) if p not in scanned_paths]
        if active_denied:
            has_permission_denied = True
            denied_paths = active_denied
        elif not any("Permission denied" in l for l in current_run_lines):
            has_permission_denied = False
            denied_paths = []
        else:
            has_permission_denied = len(active_denied) > 0
            denied_paths = active_denied

    # Check if any media_dir is in /home while ProtectHome is actively blocking
    has_home_dirs = any(m.get("path", "").startswith("/home/") for m in cfg.get("media_dirs", []))

    # If media is currently being served and no paths are actively denied, ensure false
    if metrics and metrics.get("total", 0) > 0 and not protect_home and not denied_paths:
        has_permission_denied = False

    return {
        "protect_home": protect_home,
        "has_home_dirs": has_home_dirs,
        "has_permission_denied": has_permission_denied,
        "denied_paths": list(set(denied_paths))
    }


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.route("/")
def index():
    """Serves the main web dashboard."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """
    Returns full status including:
    - systemd service state
    - live indexed media counts
    - connected clients
    - port & friendly_name
    - diagnostics on permissions & ProtectHome
    """
    svc = get_systemd_status()
    cfg = read_config()
    port = int(cfg.get("port", 8200))
    metrics = get_minidlna_http_metrics(port)
    diagnostics = get_diagnostics(cfg, metrics=metrics)

    return jsonify({
        "success": True,
        "service": svc,
        "metrics": metrics,
        "diagnostics": diagnostics,
        "config": {
            "port": port,
            "friendly_name": cfg.get("friendly_name", "MiniDLNA Server"),
            "media_dirs_count": len(cfg.get("media_dirs", []))
        }
    })


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Returns current parsed configuration."""
    cfg = read_config()
    return jsonify({
        "success": True,
        "config": cfg
    })


@app.route("/api/config", methods=["POST"])
def api_post_config():
    """
    Validates and updates configuration file.
    Optionally checks port collision.
    """
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"success": False, "error": "Dados inválidos enviados."}), 400

    cfg_current = read_config()
    svc = get_systemd_status()

    # Port validation & collision check
    new_port = payload.get("port", cfg_current.get("port", 8200))
    is_valid_port, port_msg = check_port_conflict(
        new_port,
        current_port=cfg_current.get("port"),
        service_is_active=svc["active"]
    )
    if not is_valid_port:
        return jsonify({"success": False, "error": port_msg}), 400

    warnings = []
    # Check media directories
    for m in payload.get("media_dirs", []):
        p = m.get("path", "").strip()
        if p and not os.path.exists(p):
            warnings.append(f"A pasta '{p}' não existe atualmente no sistema de arquivos.")

    # Save
    success, err_msg = write_config(payload)
    if not success:
        return jsonify({"success": False, "error": err_msg}), 500

    return jsonify({
        "success": True,
        "message": "Configurações salvas com sucesso!",
        "warnings": warnings
    })


@app.route("/api/service/<action>", methods=["POST"])
def api_service_action(action):
    """
    Performs service management actions:
    - start
    - stop
    - restart
    - reindex (forced rescan with minidlnad -R or cache reset)
    - enable
    - disable
    """
    allowed_actions = ["start", "stop", "restart", "reindex", "enable", "disable"]
    if action not in allowed_actions:
        return jsonify({"success": False, "error": f"Ação '{action}' desconhecida."}), 400

    logger.info("Service action requested: %s", action)

    if action in ["start", "stop", "restart", "enable", "disable"]:
        success, stdout, stderr = execute_command(["systemctl", action, SERVICE_NAME])
        if success:
            return jsonify({
                "success": True,
                "message": f"Serviço '{action}' executado com sucesso.",
                "output": stdout
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Erro ao executar '{action}': {stderr or stdout or 'Verifique permissões sudoers.'}"
            }), 500

    elif action == "reindex":
        # Reindex process:
        # 1. Stop service
        # 2. Run forced rescan (minidlnad -R) or clean files.db cache
        # 3. Start service
        out_log = []
        
        # Stop
        s_ok, s_out, s_err = execute_command(["systemctl", "stop", SERVICE_NAME])
        out_log.append(f"systemctl stop: {'OK' if s_ok else s_err}")

        # Rescan via minidlnad -R
        # Check if minidlnad binary is available
        minidlnad_bin = shutil.which("minidlnad") or "/usr/bin/minidlnad" or "/usr/sbin/minidlnad"
        if os.path.exists(minidlnad_bin):
            r_ok, r_out, r_err = execute_command([minidlnad_bin, "-R"])
            out_log.append(f"minidlnad -R: {'OK' if r_ok else (r_err or r_out)}")
        else:
            # Fallback: remove files.db from cache
            cfg = read_config()
            db_dir = cfg.get("db_dir", "/var/cache/minidlna")
            execute_command(["rm", "-f", f"{db_dir}/files.db"])
            out_log.append(f"Removed cache {db_dir}/files.db")

        # Start
        st_ok, st_out, st_err = execute_command(["systemctl", "start", SERVICE_NAME])
        out_log.append(f"systemctl start: {'OK' if st_ok else st_err}")

        if st_ok:
            return jsonify({
                "success": True,
                "message": "Reindexação forçada disparada com sucesso! O MiniDLNA está reconstruindo a biblioteca.",
                "output": "\n".join(out_log)
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Erro ao reiniciar serviço após reindexação: {st_err}",
                "output": "\n".join(out_log)
            }), 500


@app.route("/api/logs", methods=["GET"])
def api_logs():
    """
    Returns latest MiniDLNA service logs from journalctl or minidlna.log.
    """
    lines_count = request.args.get("lines", default=100, type=int)
    lines_count = max(10, min(lines_count, 500))

    # Try journalctl first
    success, stdout, stderr = execute_command(
        ["journalctl", "-u", SERVICE_NAME, "-n", str(lines_count), "--no-pager"],
        use_sudo_fallback=False
    )
    
    logs = []
    if success and stdout.strip() and "-- No entries --" not in stdout:
        logs = stdout.splitlines()
    else:
        # Fallback to /var/log/minidlna.log
        cfg = read_config()
        log_dir = cfg.get("log_dir", "/var/log")
        log_file = os.path.join(log_dir, "minidlna.log")
        if os.path.isfile(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    logs = [l.rstrip() for l in all_lines[-lines_count:]]
            except PermissionError:
                f_ok, f_out, _ = execute_command(["tail", "-n", str(lines_count), log_file])
                if f_ok:
                    logs = f_out.splitlines()
        elif stderr:
            logs = [f"Erro ao buscar logs do journalctl: {stderr}"]
        else:
            logs = ["Nenhum registro de log encontrado para o serviço minidlna."]

    return jsonify({
        "success": True,
        "logs": logs
    })


@app.route("/api/browse", methods=["GET"])
def api_browse():
    """
    Allows user to navigate directories when picking media folders.
    Query param: path (default: user home directory or /)
    """
    raw_path = request.args.get("path", "").strip()
    if not raw_path:
        raw_path = os.path.expanduser("~")

    target_path = os.path.abspath(raw_path)
    if not os.path.isdir(target_path):
        target_path = os.path.dirname(target_path)
        if not os.path.isdir(target_path):
            target_path = "/"

    parent_path = os.path.dirname(target_path) if target_path != "/" else "/"

    directories = []
    try:
        with os.scandir(target_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=True):
                        # Filter out common hidden directories unless requested
                        if entry.name.startswith(".") and entry.name not in [".", ".."]:
                            continue
                        directories.append({
                            "name": entry.name,
                            "path": os.path.join(target_path, entry.name)
                        })
                except (PermissionError, OSError):
                    continue
        directories.sort(key=lambda d: d["name"].lower())
    except PermissionError:
        return jsonify({
            "success": False,
            "error": f"Acesso negado ao diretório '{target_path}'."
        }), 403

    return jsonify({
        "success": True,
        "current": target_path,
        "parent": parent_path,
        "directories": directories
    })


# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MiniDLNA Web Management UI")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5050")), help="Port to bind (default: 5050)")
    parser.add_argument("--debug", action="store_true", help="Run Flask in debug mode")
    args = parser.parse_args()

    print(f"======================================================")
    print(f"       MiniDLNA Web UI - Painel de Controle          ")
    print(f"======================================================")
    print(f" * Acesso Web:      http://{args.host}:{args.port}/")
    print(f" * Arquivo Config:  {CONFIG_PATH}")
    print(f" * Serviço:         {SERVICE_NAME}")
    print(f"======================================================\n")

    app.run(host=args.host, port=args.port, debug=args.debug)
