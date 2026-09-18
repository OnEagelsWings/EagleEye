from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
import sys
from pathlib import Path
from typing import Iterable

import uvicorn

from eagleeye.bootstrap.runtime_lock import workspace_runtime_lock
from eagleeye_pro.version import BUILD

from .app416 import create_workspace_app416 as create_workspace_app


def _free_port(host: str, preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, preferred))
            return preferred
        except OSError:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])


def _firefox_candidates() -> Iterable[Path]:
    env = os.environ.get("FIREFOX_PATH", "").strip()
    if env:
        yield Path(env)
    found = shutil.which("firefox") or shutil.which("firefox.exe")
    if found:
        yield Path(found)
    if os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                yield Path(base) / "Mozilla Firefox" / "firefox.exe"
        # Microsoft Store and per-user installations can expose Firefox via the
        # WindowsApps alias. The shell can resolve it even when no fixed path exists.
        local = os.environ.get("LOCALAPPDATA")
        if local:
            yield Path(local) / "Microsoft" / "WindowsApps" / "firefox.exe"


def open_local_browser(url: str, preferred: str = "firefox") -> str:
    # Only loopback workspace URLs are accepted by this launcher. Never pass
    # attacker-controlled URLs to an operating-system opener.
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return "unavailable"
    if parsed.scheme != "http" or (parsed.hostname or "").casefold() not in {"127.0.0.1", "localhost", "::1"}:
        return "unavailable"
    if preferred.casefold() == "firefox":
        for candidate in _firefox_candidates():
            if candidate.is_file():
                try:
                    subprocess.Popen([str(candidate), "-new-tab", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                    return "firefox"
                except (OSError, ValueError):
                    # Windows app aliases/stale installations can look like valid files
                    # but still reject process creation. Continue to the next candidate
                    # and ultimately fall back to the system browser instead of letting
                    # the opener thread die silently.
                    continue
    try:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
            return "default"
        command = ["open", url] if sys.platform == "darwin" else ["xdg-open", url]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return "default"
    except (OSError, ValueError):
        return "unavailable"


def _runtime_path(root: Path) -> Path:
    return root / "data" / "runtime_126_0" / "workspace.json"


def _write_runtime(root: Path, *, host: str, port: int) -> Path:
    path = _runtime_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": os.getpid(), "host": host, "port": int(port), "build": BUILD, "started_epoch": int(time.time())}
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(path)
    return path


def _read_running_workspace(root: Path, *, timeout: float = 0.6) -> dict | None:
    path = _runtime_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        host = str(payload.get("host") or "").strip("[]").casefold()
        port = int(payload.get("port") or 0)
        if host not in {"127.0.0.1", "localhost", "::1"} or not 1 <= port <= 65535:
            return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler())
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            health = json.loads(response.read(16 * 1024).decode("utf-8"))
        if not health.get("ok") or str(health.get("build")) != BUILD:
            return None
        return {**payload, "host": "127.0.0.1", "port": port}
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        return None


def _bootstrap_required(root: Path) -> bool:
    """Return the same bootstrap state as Build-146 authentication.

    Build 233 still queried the obsolete ``users_146`` table. On real upgraded
    installations that could disagree with the active authentication schema and
    produce the wrong startup URL. Build 334 reads the canonical Build-146
    tables and fails closed to bootstrap when the database is not ready yet.
    """
    db_path = root / "data" / "eagleeye.db"
    if not db_path.is_file():
        return True
    try:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=1.0)
        try:
            user_row = connection.execute("SELECT COUNT(*) FROM phase15_team_users WHERE active=1").fetchone()
            settings_row = connection.execute("SELECT CASE WHEN COUNT(*)>0 THEN 1 ELSE 0 END FROM phase15_team_users WHERE active=1").fetchone()
            active_users = int(user_row[0]) if user_row else 0
            bootstrap_complete = bool(settings_row and int(settings_row[0]))
            return active_users == 0 or not bootstrap_complete
        finally:
            connection.close()
    except sqlite3.Error:
        return True

def _workspace_url(root: Path, runtime: dict) -> str:
    token_path = root / "data" / "security_364" / "local_session_token"
    token = token_path.read_text(encoding="utf-8").strip() if token_path.is_file() else ""
    base = f"http://127.0.0.1:{int(runtime['port'])}"
    return base + "/security/start?token=" + urllib.parse.quote(token, safe="") if token else base + "/security/login"

def _health_ready(port: int, *, timeout: float = 0.35) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler())
        with opener.open(f"http://127.0.0.1:{int(port)}/health", timeout=timeout) as response:
            payload = json.loads(response.read(16 * 1024).decode("utf-8"))
        return bool(payload.get("ok") and str(payload.get("build")) == BUILD)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        return False

def _open_browser_when_ready(root: Path, runtime: dict, browser: str, *, attempts: int = 120, delay: float = 0.25) -> str:
    """Wait for the local HTTP service before opening Firefox.

    The old fixed 1.25-second timer could open a connection-refused page on
    slower Windows machines. We now poll the loopback health endpoint and only
    launch the tab after the correct EagleEye build is reachable.
    """
    port = int(runtime["port"])
    for _ in range(max(1, int(attempts))):
        if _health_ready(port):
            return open_local_browser(_workspace_url(root, runtime), browser)
        time.sleep(max(0.02, float(delay)))
    return "unavailable"


def open_existing_workspace(*, base_dir: str | Path, browser: str = "firefox") -> bool:
    root = Path(base_dir).resolve()
    runtime = _read_running_workspace(root)
    if not runtime:
        return False
    open_local_browser(_workspace_url(root, runtime), browser)
    return True


def serve_workspace(
    *,
    base_dir: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    browser: str = "firefox",
) -> int:
    root = Path(base_dir or Path.cwd()).resolve()
    remote_enabled = os.environ.get("EAGLEEYE_REMOTE_TEAM_ENABLED", "").strip().casefold() in {"1", "true", "yes", "on"}
    if not remote_enabled and host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Local workspace may bind to loopback only; use the explicit Build-364 remote-team profile for network access")
    if not remote_enabled:
        runtime = _read_running_workspace(root)
        if runtime:
            if open_browser:
                open_local_browser(_workspace_url(root, runtime), browser)
            return 0
    try:
        lock_context = workspace_runtime_lock(root, timeout=0.0)
        with lock_context:
            app = create_workspace_app(base_dir=root)
            remote = app.state.context.remote_team_364
            ssl_certfile = None
            ssl_keyfile = None
            scheme = "http"
            if remote_enabled:
                checked = remote.validate_config(load_cert_chain=True)
                if not checked.get("valid"):
                    raise ValueError("Remote-team configuration blocked: " + "; ".join(checked.get("errors") or []))
                cfg = remote.config()
                host = str(cfg["bind_host"])
                env_port = os.environ.get("EAGLEEYE_REMOTE_PORT", "").strip()
                if env_port:
                    port = int(env_port)
                ssl_certfile = str(cfg["tls_cert_path"])
                ssl_keyfile = str(cfg["tls_key_path"])
                open_browser = False
                scheme = "https"
            resolved_port = _free_port(host, int(port))
            runtime_path = _write_runtime(root, host=host, port=resolved_port)
            runtime_info = {"host": host, "port": resolved_port}
            print(f"[EagleEye] Server bereit auf {scheme}://{host}:{resolved_port}", flush=True)
            if remote_enabled:
                print("[EagleEye] Remote-Team-Modus: direktes TLS, explizite Host-/CIDR-Allowlist, Proxy-Header werden nicht vertraut.", flush=True)
            else:
                print("[EagleEye] Browserstart wird nach erfolgreichem Health-Check ausgefuehrt.", flush=True)
            if open_browser:
                opener_thread = threading.Thread(
                    target=_open_browser_when_ready,
                    args=(root, runtime_info, browser),
                    kwargs={"attempts": 120, "delay": 0.25},
                    daemon=True,
                    name="eagleeye-browser-ready-364",
                )
                opener_thread.start()
            config = uvicorn.Config(
                app, host=host, port=resolved_port, log_level="warning", access_log=False,
                proxy_headers=False, ssl_certfile=ssl_certfile, ssl_keyfile=ssl_keyfile,
            )
            server = uvicorn.Server(config)
            try:
                server.run()
            finally:
                runtime_path.unlink(missing_ok=True)
        return 0
    except RuntimeError:
        if remote_enabled:
            raise
        for _ in range(20):
            time.sleep(0.1)
            runtime = _read_running_workspace(root, timeout=0.2)
            if runtime:
                if open_browser:
                    open_local_browser(_workspace_url(root, runtime), browser)
                return 0
        raise
