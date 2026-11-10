"""Current isolated package contract for Build 500 release candidate (not a Windows acceptance test)."""
from pathlib import Path
import ast
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_build490_package_and_installer_agree():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == "500.0.0"
    version = ast.parse((ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8"))
    build = next(node.value.value for node in version.body
                 if isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "BUILD" for target in node.targets))
    assert build == "500.0"
    installer = (ROOT / "INSTALL_EAGLEEYE_500.py").read_text(encoding="utf-8")
    assert 'PACKAGE_VERSION = "490.0.0"' in installer
    assert 'RUNTIME_DIR = ".eagleeye-runtime-490"' in installer
    assert 'RECEIPT = "install-receipt-490.json"' in installer
    assert "editable" in installer and "in_runtime" in installer


def test_normal_launchers_select_isolated_install():
    for suffix in ("bat", "sh"):
        launcher = (ROOT / f"START_EAGLEEYE_PRO.{suffix}").read_text(encoding="utf-8")
        assert "INSTALL_EAGLEEYE_500.py" in launcher
        assert ".eagleeye-runtime-500" in launcher
        # Historical launcher contract was unsafe: it placed cases below the install root.
        assert ".eagleeye-config-490" not in launcher
        assert ".eagleeye-data-490" not in launcher
        assert "EAGLEEYE_DATA_DIR=" not in launcher
        assert "INSTALL_EAGLEEYE_487.py" not in launcher
        assert "INSTALL_EAGLEEYE_398.py" not in launcher
