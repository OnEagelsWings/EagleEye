# Build 452 — Deterministic local deployment

Build 452 is the deployment step between the Build-451 retrieval-isolation work and the Build-455 operational research gate. It deliberately avoids adding a large new investigation feature. Its purpose is to make the existing research chain reproducible on a real workstation and to remove integration defects that would otherwise be carried into 453–455.

## Consolidated fixes

This branch contains the Build-451 retrieval isolation work and incorporates the still-open Build-450 hardening changes: schema-driven qualification-resource isolation, immutable dossier export directories and the one-task retrieval budget. It also restores the launcher health contract (`ok: true`) found after the last Build-451 acceptance comment.

The pinned HTTP transport now has an absolute monotonic deadline. A timer holds the connected socket reference before `http.client` may detach it and aborts that socket when the shared deadline expires. This bounds header parsing and body reads even when a peer drip-feeds bytes frequently enough to avoid an ordinary inactivity timeout. Regression tests cover both header parsing and a detached response socket.

## Deployment contract

Run either default launcher:

- Linux/macOS shell: `./START_EAGLEEYE_PRO.sh`
- Windows: `START_EAGLEEYE_PRO.bat`

or install without launching:

- `./INSTALL_EAGLEEYE_PRO.sh`
- `INSTALL_EAGLEEYE_PRO.bat`

The cross-platform `INSTALL_EAGLEEYE_452.py` creates `.eagleeye-runtime`, installs package version `452.0.0` non-editably and records an installation receipt. The receipt contains a SHA-256 fingerprint of the package source used for the install. A changed source fingerprint or package mismatch causes a reinstall.

The default launchers execute the installed runtime with Python isolated mode (`-I`). This is important: merely using a non-editable pip install is not enough when the current working directory is the repository, because normal Python path resolution could otherwise import the source tree instead of the installed package.

Use `python INSTALL_EAGLEEYE_452.py --check` to verify the runtime without changing it.

## Boundaries

Build 452 is not a signed MSI/EXE/macOS application bundle. The first local installation may require access to the configured Python package index to obtain runtime dependencies. An offline wheelhouse/bundle is not claimed in this build. Windows still has the Build-451 process-isolation profile rather than a qualified native kernel containment profile.

Engineering and deployment checks do not establish production readiness or source truth. Real-source operational qualification remains **HOLD**. Build 453 is reserved for recovery/rollback behavior, Build 454 for reliability and operational integration, and Build 455 must execute the complete real-source case → evidence → claims → independent review → dossier → approved export chain with restart/reference verification.
