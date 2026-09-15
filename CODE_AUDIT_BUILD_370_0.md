# Code Audit — Build 370.0

- **build**: 370.0
- **python_files**: 1586
- **python_lines**: 179342
- **ast_errors**: 0
- **eval_exec**: 0
- **shell_true**: 0
- **tls_disable_patterns**: 0
- **historical_subprocess_calls**: 20
- **new370_network_or_subprocess_imports**: {"tools/benchmark_build370.py": [], "tests/test_build370.py": ["socket"], "src/eagleeye/phase16/tor_gateway370.py": ["http", "socket", "ssl"], "src/eagleeye/interfaces/web/app370.py": [], "src/eagleeye/application/build370/__init__.py": [], "src/eagleeye/application/build370/service.py": []}
- **truthful_note**: The stdlib socket/ssl/http imports are confined to the explicit loopback SOCKS5 read-only transport in tor_gateway370.py; Build-370 AI/service/web modules introduce no direct external network client or subprocess authority.
