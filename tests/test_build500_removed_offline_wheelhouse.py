"""Build 500 must reject removal of a previously verified offline wheelhouse."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


def test_cached_offline_receipt_rejects_missing_wheelhouse(tmp_path: Path, capsys):
    installer = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = importlib.util.spec_from_file_location("eagleeye_500_offline_receipt", installer)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    receipt = {
        "build": module.BUILD,
        "package_version": module.PACKAGE_VERSION,
        "source_fingerprint_sha256": "fingerprint",
        "offline_wheelhouse": True,
    }
    with patch.object(module, "_root", return_value=tmp_path), patch.object(
        module, "_read_receipt", return_value=receipt
    ), patch.object(module, "_source_fingerprint", return_value="fingerprint"), patch.object(
        module, "_probe", return_value={"ready": True}
    ):
        assert module.main(["--check"]) == 2
        assert module.main(["--quiet"]) == 2
    assert "wheelhouse removed" in capsys.readouterr().err
