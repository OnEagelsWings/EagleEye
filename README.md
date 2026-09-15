# EagleEye — Build 400

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 400 is published here for **testing and evaluation**, not as a general production-ready release.

## Quick start on Windows

1. Install **Python 3.11 or newer**.
2. Clone or download this repository.
3. Double-click **`START_EAGLEEYE_PRO.bat`**.

On the first start EagleEye creates a local `.venv`, installs missing runtime dependencies from `pyproject.toml`, starts its loopback-only web server and opens the workspace in Firefox when available (otherwise the default browser).

You can also start it manually:

```powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_400_0.py
```

## Linux / macOS

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

The default local address is `http://127.0.0.1:8765`. If that port is occupied, EagleEye selects another free loopback port automatically.

## Diagnostics and tests

After an editable install, diagnostics are available with:

```bash
eagleeye --diagnose
```

For development tests:

```bash
python -m pip install -e '.[test]'
pytest
```

The canonical Build-400 integration suite is:

```bash
pytest -q tests/test_build400_integrated.py
```

## Security and release scope

- The default server binds only to loopback (`127.0.0.1`).
- No automatic external research/network execution is started on boot.
- Case evidence, runtime databases, credentials, `.env` files, keys, certificates and logs are excluded from version control.
- Build 400 completed its internal Phase-17 engineering acceptance, but broad live-research/general production readiness is **not** claimed.

See `README_BUILD_400_0.md`, the Build-400 acceptance results and regression artifacts for the engineering qualification record.
