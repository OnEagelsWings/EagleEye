# EagleEye — Build 432

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 432 is published here for **public testing and evaluation**, not as a general production-ready release.

## External testers wanted

We are actively looking for independent testers on Windows, Linux and macOS. A useful test can be as simple as: clone the repository, start EagleEye, create a demo case, restart the application, and report what worked or failed.

**Repository:** https://github.com/OnEagelsWings/EagleEye  
**Testing guide:** [TESTING.md](TESTING.md)  
**Public beta feedback:** https://github.com/OnEagelsWings/EagleEye/issues/2

Please test only with synthetic, demo, or clearly public data. Do **not** use confidential investigations, credentials, secrets, or sensitive personal information.

## Fastest Windows test

Requirements: **Python 3.12 or newer**.

```powershell
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
START_EAGLEEYE_PRO.bat
```

Alternatively, download the repository as ZIP, extract it, and double-click `START_EAGLEEYE_PRO.bat`.

On first start EagleEye creates a local `.venv`, installs missing runtime dependencies from `pyproject.toml`, starts its loopback-only web server and opens the workspace in Firefox when available (otherwise the default browser).

Manual Windows start:

```powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_432_0.py
```

## Linux / macOS

Debian/Ubuntu users may need the OS venv package before first start. If `python3 -m ensurepip --version` reports that ensurepip is unavailable, install `python3-venv` or the matching versioned package (for example `python3.14-venv`). The launcher checks this before creating `.venv` and cleans up an incomplete environment if creation fails.

```bash
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

The default local address is `http://127.0.0.1:8765`. If that port is occupied, EagleEye selects another free loopback port automatically.

## Five-minute smoke test

1. Start EagleEye on a clean machine or Python environment.
2. Confirm that the browser workspace opens.
3. Open `/health` on the displayed local address and verify `ok: true` and build `432.0`.
4. Create a test/demo case and navigate through the case/evidence workspace.
5. Close EagleEye completely and start it again.
6. Report PASS/FAIL and any error message in [the public beta issue](https://github.com/OnEagelsWings/EagleEye/issues/2) or open a separate issue for a reproducible defect.

Especially useful are tests on fresh Windows 10/11 systems, Python 3.12/3.13, ordinary 8–16 GB RAM computers, systems without Firefox, and systems where port 8765 is already occupied.

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

The canonical Build-432 integration suite is:

```bash
pytest -q tests/test_build432_integrated.py
```

## What feedback helps most

Please include operating system, Python version, RAM, install method, whether first start succeeded, whether the browser opened, whether `/health` passed, whether case creation and restart worked, and exact reproduction steps for failures. Screenshots and logs are welcome after removing credentials, tokens, usernames, private paths and case data.

See [TESTING.md](TESTING.md) for the complete test procedure and report template.

## Security and release scope

- The default server binds only to loopback (`127.0.0.1`).
- No automatic external research/network execution is started on boot.
- Case evidence, runtime databases, credentials, `.env` files, keys, certificates and logs are excluded from version control.
- Build 432 is a Phase-19 engineering checkpoint; broad live-research/general production readiness is **not** claimed.

See `README_BUILD_432_0.md`, the Build-432 manifest and regression artifacts for the engineering qualification record.
