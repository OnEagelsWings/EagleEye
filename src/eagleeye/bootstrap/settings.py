from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings for the consolidated Build 120 bootstrap."""

    base_dir: Path
    db_path: Path
    install_dir: Path
    actor: str = "local-analyst"
