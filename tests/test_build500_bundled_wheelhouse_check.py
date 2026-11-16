"""Build 500: a bundled offline wheelhouse must be verified on every check."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


def test_cached_check_rejects_tampered_bundled_wheelhouse(tmp_path: Path, capsys):
    installer_path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = importlib.util.spec_from_file_location("eagleeye_500_installer_check", installer_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "eagleeye_personosint_pro-500.0.0-py3-none-any.whl"
    wheel.write_bytes(b"tampered")
    (wheelhouse / "MANIFEST-SHA256.json").write_text(
        json.dumps({wheel.name: "0" * 64}), encoding="utf-8"
    )

    # Even a matching cached runtime/receipt must not bypass verification.
    with patch.object(module, "_root", return_value=tmp_path), patch.object(
        module, "_source_fingerprint", return_value="fingerprint"
    ), patch.object(module, "_read_receipt", return_value={
        "build": module.BUILD,
        "package_version": module.PACKAGE_VERSION,
        "source_fingerprint_sha256": "fingerprint",
    }), patch.object(module, "_probe", return_value={"ready": True}):
        assert module.main(["--check"]) == 2
        assert module.main(["--quiet"]) == 2
    assert "SHA-256 mismatch" in capsys.readouterr().err
