# Code Audit – Build 369.0

- **python_files**: 1577
- **python_lines**: 178394
- **ast_errors**: 0
- **eval_exec**: 0
- **shell_true**: 0
- **tls_disable_patterns**: 0
- **historical_subprocess_calls**: 20
- **new369_direct_http_socket_subprocess_imports**: []
- **result**: pass

Build 369 adds no direct HTTP/socket/subprocess client to the Crawler Production layer. Historical subprocess use remains in compatibility/runtime code and is reported rather than hidden. Static scanning is not an external penetration test.
