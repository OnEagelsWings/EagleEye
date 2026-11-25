"""Legenden-Browser: je Legende ein eigenes, dauerhaftes Browserprofil – verschlüsselt im Vault, nur über Tor/Proxy.

* Das Profil (Cookies, Anmeldungen, gespeicherte Passwörter) liegt als verschlüsseltes Archiv im Vault
  (``files/persona-browser/<id>.zip.enc``). Nur solange das Fenster offen ist, liegt es entpackt in einem
  temporären Ordner; beim Schließen wird es wieder verschlüsselt und der Ordner gelöscht.
* Das Fenster startet nur mit einem Anonymisierungs-Ausgang der Legende (``--proxy-server``). Lokale
  Namensauflösung ist gesperrt (kein DNS-Leck), WebRTC nur über den Proxy (kein IP-Leck), QUIC aus.
* Sperren des Vaults oder Schließen des Netzes beendet alle Legendenfenster.

Grenze (ehrlich): Bildschirmgröße, Schriftarten und Grafikkarte bleiben die Ihres Rechners – ein geübter
Gegner kann Browser daran wiedererkennen (Fingerprinting). Für höchste Anforderungen: Tor Browser oder eine
eigene virtuelle Maschine je Legende.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from urllib.parse import urlsplit

#: Ordner im Profil, die nur Zwischenspeicher sind – werden nicht mitgesichert (klein und schnell)
SKIP_DIRS = {"Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache", "GraphiteDawnCache", "DawnCache", "Crashpad", "BrowserMetrics",
             "CacheStorage", "ScriptCache", "component_crx_cache", "Safe Browsing", "OptimizationGuidePredictionModels", "segmentation_platform"}
MAX_ARCHIVE = 400 * 1024 * 1024


class BrowserError(RuntimeError):
    pass


def find_chromium() -> str | None:
    """Chromium-Browser für Vault- und Legendenfenster (Edge, Chrome, Brave, Chromium)."""
    candidates = []
    for base in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", ""), os.environ.get("LOCALAPPDATA", "")):
        if base:
            candidates += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                           os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                           os.path.join(base, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")]
    candidates += ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    candidates += [shutil.which(n) or "" for n in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser", "brave-browser")]
    env = os.environ.get("EAGLEEYE_VAULT_BROWSER", "")
    return next((c for c in [env] + candidates if c and os.path.isfile(c)), None)


def browser_args(profile_dir: str, proxy_url: str, title: str, lang: str = "de-DE") -> list[str]:
    parts = urlsplit(proxy_url)
    if parts.scheme not in {"http", "https", "socks5"} or not parts.hostname or not parts.port:
        raise BrowserError("Der Ausgang der Legende braucht eine Proxy-Adresse wie http://127.0.0.1:9080 (Tor HTTPTunnelPort).")
    if parts.username or parts.password:
        raise BrowserError("Proxys mit Anmeldung kann der Browser nicht automatisch nutzen. Bitte einen Ausgang ohne Zugangsdaten "
                           "(z. B. Tor) oder eine lokale Weiterleitung verwenden.")
    proxy = f"{parts.scheme}://{parts.hostname}:{parts.port}"
    return [f"--user-data-dir={profile_dir}", f"--proxy-server={proxy}",
            # keine lokale Namensauflösung: alles läuft über den Proxy (Ausnahme nur der Proxy selbst)
            f"--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE {parts.hostname}",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--disable-quic", f"--lang={lang}", "--no-first-run", "--no-default-browser-check", "--disable-sync",
            "--disable-background-networking", "--disable-component-update", "--disable-default-apps", "--disable-domain-reliability",
            "--metrics-recording-only", "--password-store=basic", f"--window-name={title}",
            "--disable-features=Translate,AutofillServerCommunication,OptimizationHints,MediaRouter,InterestFeedContentSuggestions",
            "about:blank"]


def _safe_extract(data: bytes, target: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts:
                continue
            dest = target.joinpath(*name.parts)
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)


def _archive(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f in {"SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"}:
                    continue
                path = Path(root) / f
                try:
                    z.write(path, path.relative_to(folder).as_posix())
                except OSError:
                    continue
    return buf.getvalue()


class PersonaBrowsers:
    def __init__(self, store_dir: Path, vault, browser: Callable[[], str | None], launcher: Callable[[list[str]], Any] | None = None):
        self.store_dir = Path(store_dir)
        self.vault = vault
        self.browser = browser
        self.launcher = launcher or (lambda cmd: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))  # noqa: S603
        self.running: dict[int, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _archive_path(self, pid: int) -> Path:
        return self.store_dir / f"{int(pid)}.zip.enc"

    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"persona_id": pid, "codename": r["codename"], "started": r["started"], "egress": r["egress"]} for pid, r in self.running.items()]

    def open(self, persona: dict[str, Any], proxy_url: str, egress_name: str) -> dict[str, Any]:
        pid = int(persona["id"])
        with self._lock:
            if pid in self.running:
                raise BrowserError("Das Fenster dieser Legende ist schon offen.")
        exe = self.browser()
        if not exe:
            raise BrowserError("Kein Edge/Chrome/Brave gefunden – der Legenden-Browser braucht einen Chromium-Browser.")
        tmp = Path(tempfile.mkdtemp(prefix="eagleeye-legende-"))
        archive = self._archive_path(pid)
        try:
            if archive.is_file():
                _safe_extract(self.vault.decrypt(archive.read_bytes()), tmp)
            cmd = [exe] + browser_args(str(tmp), proxy_url, f"Legende {persona['codename']}")
            proc = self.launcher(cmd)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        entry = {"proc": proc, "dir": tmp, "started": time.time(), "codename": persona["codename"], "egress": egress_name, "done": threading.Event()}
        with self._lock:
            self.running[pid] = entry
        threading.Thread(target=self._watch, args=(pid,), name=f"legende-{pid}", daemon=True).start()
        return {"persona_id": pid, "codename": persona["codename"], "egress": egress_name, "restored": archive.is_file()}

    def _watch(self, pid: int) -> None:
        entry = self.running[pid]
        try:
            entry["proc"].wait()
            time.sleep(0.5)  # Browser schreibt beim Beenden noch Dateien
            data = _archive(entry["dir"])
            if len(data) > MAX_ARCHIVE:
                raise BrowserError("Profil zu groß")
            self.store_dir.mkdir(parents=True, exist_ok=True)
            target = self._archive_path(pid)
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(self.vault.encrypt(data))
            os.replace(tmp, target)
        except Exception:  # noqa: BLE001 - Profil bleibt dann beim alten Stand; der temporäre Ordner wird trotzdem gelöscht
            pass
        finally:
            shutil.rmtree(entry["dir"], ignore_errors=True)
            with self._lock:
                self.running.pop(pid, None)
            entry["done"].set()

    def close(self, pid: int, wait: float = 15.0) -> bool:
        with self._lock:
            entry = self.running.get(int(pid))
        if not entry:
            return False
        proc = entry["proc"]
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        if not entry["done"].wait(wait):
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            entry["done"].wait(wait)
        return True

    def close_all(self) -> int:
        pids = [r["persona_id"] for r in self.status()]
        for pid in pids:
            self.close(pid)
        return len(pids)

    def delete_profile(self, pid: int) -> None:
        self.close(pid)
        self._archive_path(pid).unlink(missing_ok=True)


__all__ = ["PersonaBrowsers", "BrowserError", "browser_args"]
