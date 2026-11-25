"""Netzschalter des Vaults: Außenverbindungen gibt es nur, solange Sie das Netz ausdrücklich geöffnet haben.

Der Schalter sitzt an der tiefsten Stelle des Programms – beim Verbindungsaufbau (``socket.connect``) und bei der
Namensauflösung (``socket.getaddrinfo``). Damit gilt er für jede Bibliothek im Prozess (Quellenabfragen,
Webarchiv, Geokodierung, Updates einzelner Pakete …), auch für künftige, ohne dass diese davon wissen müssen.

* **Geschlossen** (Standard nach Start und nach jedem Sperren): Nur Verbindungen innerhalb dieses Rechners
  (127.0.0.1, ::1) sind möglich. Jede andere Verbindung und jede DNS-Anfrage scheitert sofort („fail closed“).
* **Offen**: für ein gewähltes Zeitfenster; danach schließt der Schalter von selbst. Jede Außenverbindung wird mit
  Zeit, Ziel und Ergebnis protokolliert.

Grenzen (ehrlich): Der Schalter wirkt nur in diesem Programm. Ihr Browser, andere Programme und das Betriebssystem
haben ihren eigenen Netzzugang. Bereits bestehende Verbindungen laufen beim Schließen zu Ende (keine neuen).
"""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from collections import deque
from typing import Any

DURATIONS = (5, 15, 30, 60, 120)   # Minuten, die beim Öffnen gewählt werden können
MAX_MINUTES = 240
_original: dict[str, Any] = {}


class NetClosed(OSError):
    """Verbindung verweigert: Das Netz des Vaults ist geschlossen."""

    def __init__(self, target: str):
        super().__init__(f"Netz geschlossen (Vault): Verbindung zu {target} verweigert. Netz in der Vault-Leiste öffnen.")


def _is_local(host: Any) -> bool:
    if host is None:
        return True
    text = str(host).strip("[]").split("%", 1)[0]
    if text.casefold() in {"localhost", "localhost.", ""}:
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


class NetGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open_until = 0.0
        self._opened_at = 0.0
        self._purpose = ""
        self.log: deque[dict[str, Any]] = deque(maxlen=500)
        self.blocked = 0
        self.allowed = 0
        self.sessions: deque[dict[str, Any]] = deque(maxlen=100)
        #: werden nach jedem Schließen aufgerufen (z. B. Legendenfenster beenden) – außerhalb der Sperre
        self.on_close: list[Any] = []

    # ------------------------------------------------------------------ Zustand
    def is_open(self) -> bool:
        expired = False
        with self._lock:
            if self._open_until and time.time() >= self._open_until:
                self._close_locked("Zeitfenster abgelaufen")
                expired = True
            state = bool(self._open_until)
        if expired:
            self._notify("Zeitfenster abgelaufen")
        return state

    def _notify(self, reason: str) -> None:
        for callback in list(self.on_close):
            try:
                callback(reason)
            except Exception:  # noqa: BLE001 - ein Beobachter darf das Schließen nie verhindern
                pass

    def open(self, minutes: int, purpose: str = "") -> dict[str, Any]:
        minutes = int(minutes)
        if not 1 <= minutes <= MAX_MINUTES:
            raise ValueError(f"Zeitfenster zwischen 1 und {MAX_MINUTES} Minuten wählen.")
        with self._lock:
            now = time.time()
            if not self._open_until:
                self._opened_at = now
                self.sessions.append({"opened": now, "closed": None, "purpose": purpose[:200], "reason": ""})
            self._open_until = now + minutes * 60
            self._purpose = purpose[:200]
        return self.status()

    def close(self, reason: str = "von Hand geschlossen") -> dict[str, Any]:
        with self._lock:
            was_open = bool(self._open_until)
            self._close_locked(reason)
        if was_open:
            self._notify(reason)
        return self.status()

    def _close_locked(self, reason: str) -> None:
        if self._open_until and self.sessions:
            self.sessions[-1]["closed"] = time.time()
            self.sessions[-1]["reason"] = reason
        self._open_until = 0.0
        self._purpose = ""

    def status(self) -> dict[str, Any]:
        is_open = self.is_open()
        with self._lock:
            return {"open": is_open, "seconds_left": max(0, int(self._open_until - time.time())) if is_open else 0,
                    "purpose": self._purpose if is_open else "", "allowed": self.allowed, "blocked": self.blocked,
                    "durations": list(DURATIONS)}

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.log)[-limit:][::-1]

    # ------------------------------------------------------------------ Prüfung je Verbindung
    def check(self, host: Any, port: Any, kind: str) -> None:
        if _is_local(host):
            return
        allowed = self.is_open()
        with self._lock:
            entry = {"time": time.time(), "kind": kind, "host": str(host)[:255], "port": port, "allowed": allowed}
            self.log.append(entry)
            if allowed:
                self.allowed += 1
            else:
                self.blocked += 1
        if not allowed:
            raise NetClosed(f"{host}:{port}" if port else str(host))


GATE = NetGate()


def require_open(target: str) -> None:
    """Zusätzliche Prüfung vor jeder Quellenabfrage: Auch ein lokaler Proxy (Tor u. Ä. auf 127.0.0.1) darf bei
    geschlossenem Netz nicht angesprochen werden – er würde sonst ins Internet weiterleiten."""
    if not _original:
        return
    allowed = GATE.is_open()
    with GATE._lock:  # noqa: SLF001
        # Protokoll auf Ebene der Quellenabfrage: zeigt das eigentliche Ziel auch dann, wenn ein Proxy dazwischen sitzt
        GATE.log.append({"time": time.time(), "kind": "Quellenabfrage", "host": str(target)[:255], "port": None, "allowed": allowed})
        if not allowed:
            GATE.blocked += 1
    if not allowed:
        raise NetClosed(target)


def install(gate: NetGate = GATE) -> NetGate:
    """Schaltet den Netzschalter für den ganzen Prozess scharf (einmalig; idempotent)."""
    if _original:
        return gate
    _original.update(connect=socket.socket.connect, connect_ex=socket.socket.connect_ex, getaddrinfo=socket.getaddrinfo,
                     gethostbyname=socket.gethostbyname, gethostbyname_ex=socket.gethostbyname_ex)

    def _target(address: Any) -> tuple[Any, Any]:
        if isinstance(address, tuple) and address:
            return address[0], address[1] if len(address) > 1 else None
        return None, None  # AF_UNIX u. Ä.: lokal

    def connect(self, address):  # noqa: ANN001
        if self.family in (socket.AF_INET, socket.AF_INET6):
            host, port = _target(address)
            gate.check(host, port, "Verbindung")
        return _original["connect"](self, address)

    def connect_ex(self, address):  # noqa: ANN001
        if self.family in (socket.AF_INET, socket.AF_INET6):
            host, port = _target(address)
            gate.check(host, port, "Verbindung")
        return _original["connect_ex"](self, address)

    def getaddrinfo(host, port, *args, **kwargs):  # noqa: ANN001
        gate.check(host, port, "Namensauflösung")
        return _original["getaddrinfo"](host, port, *args, **kwargs)

    def gethostbyname(host):  # noqa: ANN001
        gate.check(host, None, "Namensauflösung")
        return _original["gethostbyname"](host)

    def gethostbyname_ex(host):  # noqa: ANN001
        gate.check(host, None, "Namensauflösung")
        return _original["gethostbyname_ex"](host)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    socket.gethostbyname = gethostbyname
    socket.gethostbyname_ex = gethostbyname_ex
    return gate


def uninstall() -> None:
    """Nur für Tests: ursprüngliches Verhalten wiederherstellen."""
    if not _original:
        return
    socket.socket.connect = _original["connect"]
    socket.socket.connect_ex = _original["connect_ex"]
    socket.getaddrinfo = _original["getaddrinfo"]
    socket.gethostbyname = _original["gethostbyname"]
    socket.gethostbyname_ex = _original["gethostbyname_ex"]
    _original.clear()


__all__ = ["NetGate", "NetClosed", "GATE", "install", "uninstall", "require_open", "DURATIONS"]
