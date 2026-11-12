"""Small in-process rate limit for user-triggered web captures.

Two windows protect third parties and the investigator: a cap per user and a cap per
target server (across users). A refused attempt is not counted.
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class Throttle:
    def __init__(self, *, per_user: int = 12, per_host: int = 6, window: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.per_user, self.per_host, self.window, self.clock = per_user, per_host, window, clock
        self._lock = threading.Lock()
        self._users: dict[str, list[float]] = {}
        self._hosts: dict[str, list[float]] = {}

    def _recent(self, table: dict[str, list[float]], key: str, now: float) -> list[float]:
        recent = [t for t in table.get(key, ()) if now - t < self.window]
        if recent:
            table[key] = recent
        else:
            table.pop(key, None)
        return recent

    def check(self, user_key: str, host: str) -> tuple[int, str]:
        """Return (0, "") and record the attempt, or (seconds to wait, "user"|"host")."""
        now = self.clock()
        host = host.casefold()
        with self._lock:
            users = self._recent(self._users, user_key, now)
            hosts = self._recent(self._hosts, host, now)
            if len(hosts) >= self.per_host:
                return max(1, int(self.window - (now - hosts[0])) + 1), "host"
            if len(users) >= self.per_user:
                return max(1, int(self.window - (now - users[0])) + 1), "user"
            self._users[user_key] = users + [now]
            self._hosts[host] = hosts + [now]
            if len(self._users) > 2000 or len(self._hosts) > 2000:  # bound memory
                for table in (self._users, self._hosts):
                    for key in [k for k, v in table.items() if not v or now - v[-1] >= self.window]:
                        table.pop(key, None)
            return 0, ""
