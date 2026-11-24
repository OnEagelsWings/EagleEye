"""Page image ("Seitenbild") of a public address, taken with the locally installed Edge or Chrome.

The browser runs headless with a fresh, throw-away profile. All of its traffic goes through a
small proxy in this process that only connects to public addresses on ports 80 and 443: the
proxy resolves the name itself, checks every address and connects to the checked address, so
a page cannot send the browser into the office network (also not by DNS rebinding). WebRTC
and QUIC are switched off because they would bypass the proxy.

Only hosts the page itself asks for are let through: every request of the page is paused in the
browser (DevTools "Fetch"), its host is admitted, then the request continues. Background
connections of the browser (update, sign-in, safe browsing) are therefore refused.

No extra Python package and no browser download is needed: the browser is controlled through
its DevTools protocol over a minimal WebSocket client.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import secrets
import selectors
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from .webcapture import CaptureError, public_addresses

WIDTH = 1366
VIEW_HEIGHT = 900
MAX_HEIGHT = 12000
MAX_PNG = 30 * 1024 * 1024
MAX_TRAFFIC = 80 * 1024 * 1024
MAX_CONNECTIONS = 400
LOAD_TIMEOUT = 25.0
SETTLE = 1.5
_ONE_AT_A_TIME = threading.Lock()
WAITED_EVENTS = {"Page.loadEventFired"}
EXTRA_ARGS: list[str] = []  # test hook (e.g. CI machines without a usable browser sandbox)


class ImageError(RuntimeError):
    """Readable German reason why no page image was taken."""


# ---------------------------------------------------------------- browser discovery

def browser_candidates() -> list[str]:
    paths = []
    if sys.platform.startswith("win"):
        for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA")):
            if base:
                paths += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                          os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    elif sys.platform == "darwin":
        paths += ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for name in ("msedge", "microsoft-edge", "microsoft-edge-stable", "google-chrome", "google-chrome-stable",
                 "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            paths.append(found)
    return list(dict.fromkeys(paths))


def browser_name(path: str) -> str:
    stem = Path(str(path)).stem.lower()
    if "edge" in stem:
        return "Microsoft Edge"
    if "chromium" in stem:
        return "Chromium"
    if "chrome" in stem:
        return "Google Chrome" if "google" in str(path).lower() else "Chrome"
    return Path(str(path)).name


def find_browser(configured: str = "") -> str | None:
    configured = str(configured or "").strip().strip('"')
    if configured:
        return configured if os.path.isfile(configured) else None
    return next((p for p in browser_candidates() if os.path.isfile(p)), None)


# ---------------------------------------------------------------- filtering proxy

def default_check(host: str) -> list[str]:
    """Public addresses of host, or CaptureError. Same rules as the WARC capture."""
    host = host.strip("[]").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost", ".onion")):
        raise CaptureError("interne Adresse")
    return public_addresses(host)


class FilterProxy:
    """HTTP proxy on 127.0.0.1 that only connects to checked public addresses."""

    def __init__(self, *, check=default_check, ports=(80, 443), max_traffic=MAX_TRAFFIC,
                 max_connections=MAX_CONNECTIONS, timeout=15.0, admit=None):
        self.check, self.ports, self.timeout, self.admit = check, ports, timeout, admit
        self.background: set[str] = set()
        self.max_traffic, self.max_connections = max_traffic, max_connections
        self.hosts: set[str] = set()
        self.blocked: list[str] = []
        self.traffic = 0
        self.connections = 0
        self._lock = threading.Lock()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(64)
        self.port = self._server.getsockname()[1]
        self._closed = False
        self._thread = threading.Thread(target=self._accept, name="eagleeye-pageimage-proxy", daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._closed = True
        try:
            self._server.close()
        except OSError:
            pass

    def _accept(self):
        while not self._closed:
            try:
                client, _ = self._server.accept()
            except OSError:
                return
            with self._lock:
                self.connections += 1
                too_many = self.connections > self.max_connections
            if too_many:
                self._refuse(client, "zu viele Verbindungen")
                continue
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _block(self, what: str):
        with self._lock:
            if len(self.blocked) < 200:
                self.blocked.append(what[:200])

    @staticmethod
    def _refuse(client, reason: str):
        try:
            body = ("EagleEye: " + reason).encode("utf-8")
            client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n"
                           b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        except OSError:
            pass
        finally:
            client.close()

    def _open(self, host: str, port: int):
        name = host.strip("[]").lower()
        if self.admit is not None and not self.admit(name):
            with self._lock:
                self.background.add(host.lower())
            raise CaptureError("nicht von der Seite angefordert")
        if self.ports and port not in self.ports:
            raise CaptureError("Port nicht erlaubt")
        addresses = self.check(host)
        last = None
        for address in addresses:
            try:
                upstream = socket.create_connection((address, port), timeout=self.timeout)
                with self._lock:
                    self.hosts.add(host.lower())
                return upstream
            except OSError as exc:
                last = exc
        raise CaptureError("nicht erreichbar" if last else "keine Adresse")

    def _handle(self, client):
        upstream = None
        try:
            client.settimeout(self.timeout)
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = client.recv(8192)
                if not chunk:
                    client.close()
                    return
                head += chunk
                if len(head) > 32768:
                    raise CaptureError("Anfragekopf zu groß")
            head, rest = head.split(b"\r\n\r\n", 1)
            lines = head.decode("latin-1").split("\r\n")
            method, target, version = lines[0].split(" ", 2)
            if method.upper() == "CONNECT":
                host, _, port = target.rpartition(":")
                if not host or not port.isdigit():
                    raise CaptureError("ungültiges Ziel")
                try:
                    upstream = self._open(host, int(port))
                except CaptureError as exc:
                    if host.lower() not in self.background:
                        self._block(target + " (" + str(exc) + ")")
                    raise
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                first = rest
            else:
                parts = urlsplit(target)
                if parts.scheme != "http" or not parts.hostname:
                    raise CaptureError("nur http und https")
                try:
                    upstream = self._open(parts.hostname, parts.port or 80)
                except CaptureError as exc:
                    if parts.hostname.lower() not in self.background:
                        self._block(parts.hostname + (f":{parts.port}" if parts.port else "") + " (" + str(exc) + ")")
                    raise
                path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
                keep = [line for line in lines[1:] if line.split(":", 1)[0].strip().lower()
                        not in ("proxy-connection", "connection", "keep-alive", "proxy-authorization")]
                first = (f"{method} {path} {version}\r\n" + "\r\n".join(keep) + "\r\nConnection: close\r\n\r\n").encode("latin-1") + rest
            self._relay(client, upstream, first)
        except (CaptureError, ValueError) as exc:
            self._refuse(client, str(exc))
        except OSError:
            client.close()
        finally:
            if upstream is not None:
                upstream.close()

    def _relay(self, client, upstream, first: bytes):
        if first:
            upstream.sendall(first)
        selector = selectors.DefaultSelector()
        selector.register(client, selectors.EVENT_READ, upstream)
        selector.register(upstream, selectors.EVENT_READ, client)
        try:
            while not self._closed:
                events = selector.select(timeout=self.timeout)
                if not events:
                    return
                for key, _ in events:
                    data = key.fileobj.recv(65536)
                    if not data:
                        return
                    with self._lock:
                        self.traffic += len(data)
                        over = self.traffic > self.max_traffic
                    if over:
                        self._block("Datenmenge überschritten")
                        return
                    key.data.sendall(data)
        finally:
            selector.close()
            client.close()


# ---------------------------------------------------------------- DevTools over WebSocket

class _WebSocket:
    def __init__(self, url: str, timeout: float):
        parts = urlsplit(url)
        if parts.hostname != "127.0.0.1":
            raise ImageError("Unerwartete Browser-Schnittstelle.")
        self.sock = socket.create_connection(("127.0.0.1", parts.port), timeout=timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        self.sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: 127.0.0.1:{parts.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        answer = b""
        while b"\r\n\r\n" not in answer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ImageError("Browser-Schnittstelle hat die Verbindung abgelehnt.")
            answer += chunk
        head, self.buffer = answer.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ImageError("Browser-Schnittstelle hat die Verbindung abgelehnt.")

    def _read(self, n: int) -> bytes:
        while len(self.buffer) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buffer)))
            if not chunk:
                raise ImageError("Browser hat die Verbindung beendet.")
            self.buffer += chunk
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def send(self, text: str) -> None:
        payload = text.encode("utf-8")
        mask = secrets.token_bytes(4)
        n = len(payload)
        header = b"\x81" + (bytes([0x80 | n]) if n < 126 else
                            b"\xfe" + struct.pack(">H", n) if n < 65536 else b"\xff" + struct.pack(">Q", n))
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.settimeout(30)  # recv() may have left a very short timeout behind
        self.sock.sendall(header + mask + masked)

    def recv(self, wait: float) -> str | None:
        """Next text message, or None when nothing arrived within wait seconds.

        Once the first byte of a message is here, the rest is read with a longer timeout so a
        large message (the screenshot) is never cut in the middle.
        """
        if not self.buffer:
            self.sock.settimeout(max(0.05, wait))
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                return None
            if not chunk:
                raise ImageError("Browser hat die Verbindung beendet.")
            self.buffer += chunk
        self.sock.settimeout(30)
        message = b""
        while True:
            b1, b2 = self._read(2)
            opcode, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if n > 64 * 1024 * 1024:
                raise ImageError("Antwort des Browsers ist zu groß.")
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 8:
                raise ImageError("Browser hat die Verbindung beendet.")
            if opcode == 9:
                self.sock.sendall(b"\x8a\x80" + secrets.token_bytes(4))
                continue
            if opcode in (0, 1, 2):
                message += data
                if b1 & 0x80:
                    return message.decode("utf-8")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class _DevTools:
    def __init__(self, ws: _WebSocket, deadline: float, admitted: set[str] | None = None):
        self.ws, self.deadline, self.next_id, self.events = ws, deadline, 0, []
        self.admitted = admitted if admitted is not None else set()
        self.requests = 0

    def send(self, method: str, params: dict, session: str | None) -> None:
        """Command without waiting for its reply (the reply is ignored)."""
        self.next_id += 1
        message = {"id": self.next_id, "method": method, "params": params}
        if session:
            message["sessionId"] = session
        self.ws.send(json.dumps(message))

    def _paused(self, event: dict) -> None:
        params = event.get("params", {})
        parts = urlsplit(str(params.get("request", {}).get("url", "")))
        session = event.get("sessionId")
        if parts.scheme in ("http", "https") and parts.hostname:
            self.admitted.add(parts.hostname.lower())  # before the request continues, so the proxy knows it
            self.requests += 1
            self.send("Fetch.continueRequest", {"requestId": params.get("requestId")}, session)
        else:
            self.send("Fetch.failRequest", {"requestId": params.get("requestId"), "errorReason": "BlockedByClient"}, session)

    def _next(self, wait: float):
        if time.monotonic() >= self.deadline:
            raise ImageError("Zeitüberschreitung beim Laden der Seite.")
        text = self.ws.recv(min(wait, self.deadline - time.monotonic()))
        if text is None:
            return None
        message = json.loads(text)
        if message.get("method") == "Fetch.requestPaused":
            self._paused(message)
            return None
        if message.get("method") == "Page.javascriptDialogOpening":  # alert() would block the page
            self.send("Page.handleJavaScriptDialog", {"accept": False}, message.get("sessionId"))
            return None
        return message

    def call(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self.next_id += 1
        ident = self.next_id
        message = {"id": ident, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        self.ws.send(json.dumps(message))
        while True:
            reply = self._next(5.0)
            if reply is None:
                continue
            if reply.get("id") == ident:
                if "error" in reply:
                    raise ImageError("Browser meldet: " + str(reply["error"].get("message", ""))[:160])
                return reply.get("result", {})
            self._keep(reply)

    def wait_event(self, name: str, session: str, until: float) -> bool:
        while True:
            for event in self.events:
                if event.get("method") == name and event.get("sessionId") == session:
                    self.events.remove(event)
                    return True
            left = until - time.monotonic()
            if left <= 0:
                return False
            event = self._next(min(left, 1.0))
            if event is not None:
                self._keep(event)

    def _keep(self, message: dict) -> None:
        """Only the events we wait for are kept; everything else is dropped (bounded memory)."""
        if message.get("method") in WAITED_EVENTS and len(self.events) < 100:
            self.events.append(message)

    def pause(self, seconds: float) -> None:
        """Let the page settle while still answering dialogs."""
        self.wait_event("", "", time.monotonic() + seconds)


def _launch(browser: str, profile: Path, proxy_port: int) -> subprocess.Popen:
    args = [browser, "--headless=new", f"--user-data-dir={profile}", "--remote-debugging-port=0",
            f"--proxy-server=http://127.0.0.1:{proxy_port}", "--proxy-bypass-list=<-loopback>",
            "--disable-quic", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-sync",
            "--disable-background-networking", "--disable-component-update", "--disable-default-apps",
            # Local-network permission prompts would stall a page without a screen; the proxy above
            # is the guard and refuses every internal address anyway.
            "--disable-features=Translate,MediaRouter,OptimizationHints,AutofillServerCommunication,"
            "LocalNetworkAccessChecks,PrivateNetworkAccessPermissionPrompt",
            "--deny-permission-prompts",
            "--hide-scrollbars", "--mute-audio", f"--window-size={WIDTH},{VIEW_HEIGHT}", "about:blank"]
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0:
        args.insert(1, "--no-sandbox")  # Chromium refuses to start as root otherwise (containers)
    args[1:1] = EXTRA_ARGS
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)


def _devtools_url(profile: Path, process: subprocess.Popen, deadline: float) -> str:
    marker = profile / "DevToolsActivePort"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ImageError("Der Browser hat sich sofort beendet. Pfad und Version prüfen.")
        try:
            lines = marker.read_text(encoding="utf-8").split()
            if len(lines) >= 2 and lines[0].isdigit():
                return f"ws://127.0.0.1:{lines[0]}{lines[1]}"
        except OSError:
            pass
        time.sleep(0.1)
    raise ImageError("Der Browser hat nicht rechtzeitig geantwortet.")


def _stop(process: subprocess.Popen, profile: Path) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
    for _ in range(10):  # Windows keeps profile files locked for a moment after exit
        shutil.rmtree(profile, ignore_errors=True)
        if not profile.exists():
            return
        time.sleep(0.3)


def take(url: str, *, browser: str, check=None, ports=(80, 443), timeout: float = 45.0) -> dict:
    """Render url in the local browser and return the PNG plus what the browser contacted."""
    check = check or default_check
    if not browser or not os.path.isfile(browser):
        raise ImageError("Kein Edge oder Chrome gefunden. Pfad unter Einstellungen → Beweissicherung eintragen.")
    if urlsplit(url).scheme not in ("http", "https"):
        raise ImageError("Nur http- und https-Adressen.")
    if not _ONE_AT_A_TIME.acquire(timeout=timeout):
        raise ImageError("Es wird gerade ein anderes Seitenbild aufgenommen. Bitte gleich noch einmal versuchen.")
    profile = Path(tempfile.mkdtemp(prefix="eagleeye-seitenbild-"))
    deadline = time.monotonic() + timeout
    process = None
    ws = None
    admitted: set[str] = set()
    try:
        with FilterProxy(check=check, ports=ports, admit=admitted.__contains__) as proxy:
            try:
                process = _launch(browser, profile, proxy.port)
            except OSError as exc:
                raise ImageError(f"Browser konnte nicht gestartet werden ({type(exc).__name__}).") from None
            # A cold browser start on a busy machine can take longer than a few seconds to answer the
            # DevTools handshake; it may use the remaining time budget.
            ws = _WebSocket(_devtools_url(profile, process, deadline), timeout=max(5.0, deadline - time.monotonic()))
            tools = _DevTools(ws, deadline, admitted)
            version = tools.call("Browser.getVersion")
            tools.call("Browser.setDownloadBehavior", {"behavior": "deny"})
            target = tools.call("Target.createTarget", {"url": "about:blank"})["targetId"]
            session = tools.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
            tools.call("Page.enable", session=session)
            tools.call("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]}, session)
            agent = str(version.get("userAgent", "")).replace("HeadlessChrome", "Chrome")
            if agent:
                tools.call("Emulation.setUserAgentOverride", {"userAgent": agent}, session)
            tools.call("Emulation.setDeviceMetricsOverride",
                       {"width": WIDTH, "height": VIEW_HEIGHT, "deviceScaleFactor": 1, "mobile": False}, session)
            tools.events.clear()  # a late load event of about:blank must not count as the page's
            navigated = tools.call("Page.navigate", {"url": url}, session)
            if navigated.get("errorText"):
                raise ImageError("Die Seite ließ sich im Browser nicht laden (" + str(navigated["errorText"])[:80] + ").")
            complete = tools.wait_event("Page.loadEventFired", session, min(deadline - 8, time.monotonic() + LOAD_TIMEOUT))
            if not complete:
                # Busy CI runners occasionally lose the load-event notification even
                # after the final resource finishes. The browser DOM readiness state
                # is an independent completion signal; an image still loading (the
                # intentionally slow-page test) remains document.readyState=loading.
                try:
                    ready = tools.call("Runtime.evaluate",
                                       {"expression": "document.readyState === 'complete'",
                                        "returnByValue": True}, session)
                    complete = ready.get("result", {}).get("value") is True
                except (ImageError, OSError, KeyError, ValueError):
                    pass  # Conservative: leave incomplete when status is unknown.
            tools.pause(SETTLE)
            metrics = tools.call("Page.getLayoutMetrics", session=session)
            size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
            height = int(min(max(VIEW_HEIGHT, float(size.get("height", VIEW_HEIGHT))), MAX_HEIGHT))
            shot = tools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                                         "clip": {"x": 0, "y": 0, "width": WIDTH, "height": height, "scale": 1}},
                              session)
            png = base64.b64decode(shot.get("data", ""))
            if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ImageError("Der Browser hat kein Bild geliefert.")
            if len(png) > MAX_PNG:
                raise ImageError("Das Seitenbild ist zu groß.")
            try:
                tools.call("Browser.close")
            except (ImageError, OSError):
                pass
            return {"png": png, "width": WIDTH, "height": height, "complete": bool(complete),
                    "truncated": float(size.get("height", 0)) > MAX_HEIGHT,
                    "browser": str(version.get("product", "Browser"))[:120],
                    "hosts": sorted(proxy.hosts), "blocked": list(proxy.blocked), "requests": tools.requests,
                    "background_refused": len(proxy.background)}
    except TimeoutError:
        raise ImageError("Der Browser hat nicht rechtzeitig geantwortet. Bitte noch einmal versuchen.") from None
    except (OSError, ValueError, KeyError) as exc:
        raise ImageError(f"Seitenbild nicht möglich ({type(exc).__name__}).") from None
    finally:
        if ws is not None:
            ws.close()
        if process is not None:
            _stop(process, profile)
        else:
            shutil.rmtree(profile, ignore_errors=True)
        _ONE_AT_A_TIME.release()


def target_url(row: dict) -> str:
    """Address the browser opens for a stored capture. Archive captures use the replay without toolbar."""
    if row["kind"] == "archive" and row["archive_url"]:
        return row["archive_url"].replace("id_/", "if_/", 1)
    return row["url"]


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_global and not ip.is_multicast
