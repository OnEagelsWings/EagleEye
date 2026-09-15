# Code Audit – Build 366.0

- Release-candidate files inspected: **1667**
- Python files: **1550**
- Python lines: **175048**
- AST parse errors: **0**
- `eval`/`exec` calls: **0**
- `shell=True` calls: **0**
- explicit TLS verification-disable patterns: **0**
- Python files importing `subprocess` (legacy/launcher footprint): **13**
- New Build-366 phase/application/web modules importing direct requests/httpx/aiohttp/socket/subprocess clients: **0**

## Result
**PASS**. Build 366 adds governed corporate connector orchestration on top of the existing bounded crawler transport; it does not add a separate uncontrolled HTTP/socket/subprocess client in the new Build-366 control-plane modules.
