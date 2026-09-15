from __future__ import annotations

from typing import Any


def version_tuple(value: Any) -> tuple[int, ...]:
    """Return a comparable numeric tuple for EagleEye dotted build versions."""
    text = str(value or "").strip()
    if not text:
        return ()
    parts: list[int] = []
    for raw in text.split("."):
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return ()
        parts.append(int(digits))
    return tuple(parts)


def version_at_least(value: Any, minimum: Any) -> bool:
    observed = version_tuple(value)
    required = version_tuple(minimum)
    if not observed or not required:
        return False
    width = max(len(observed), len(required))
    return observed + (0,) * (width - len(observed)) >= required + (0,) * (width - len(required))
