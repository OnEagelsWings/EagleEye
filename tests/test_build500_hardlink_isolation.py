"""Regression: internal-release databases must not alias older installations via hard links."""
from pathlib import Path

import pytest

from eagleeye.bootstrap.paths import RuntimePaths


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm"])
def test_build500_rejects_hardlinked_database_file(tmp_path: Path, suffix: str, monkeypatch):
    import eagleeye.bootstrap.paths as paths

    monkeypatch.setattr(paths, "BUILD", "500.0")
    old = tmp_path / ("legacy" + suffix)
    old.write_bytes(b"original")
    workspace = tmp_path / "fresh"
    db = workspace / "data" / "eagleeye.db"
    db.parent.mkdir(parents=True)
    import os
    os.link(old, Path(str(db) + suffix))

    with pytest.raises(ValueError, match="hard linked"):
        RuntimePaths.resolve(install_dir=tmp_path / "installation", base_dir=workspace)

    assert old.read_bytes() == b"original"
    assert not (workspace / "reports").exists()
