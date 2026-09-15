# Code Audit – Build 364.0

Audit of the deterministic slim release ZIP:
- Release files: **1622**
- Python files: **1532**
- Python lines: **173825**
- AST errors: **0**
- `eval`/`exec` calls: **0**
- `shell=True`: **0**
- TLS-disable matches (`CERT_NONE`, `verify=False`, `check_hostname=False`): **0**
- Historical subprocess attribute calls: **20**
- Historical `ProxyHandler({})` text matches: **2**
- New Build-364 application/team/OPSEC modules direct requests/httpx/aiohttp/urllib/socket/subprocess imports: **0**

Build 364 configures TLS only in the server runtime. Remote mode is opt-in, direct-TLS, explicit-host/CIDR allowlisted and does not trust proxy forwarding headers.
