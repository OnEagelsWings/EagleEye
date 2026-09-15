# Code Audit — Build 363.0

- **build**: 363.0
- **release_files**: 1710
- **python_files**: 1521
- **python_lines**: 170709
- **ast_errors**: 0
- **eval_exec**: 0
- **shell_true**: 0
- **tls_disable_patterns**: 0
- **historical_subprocess_calls**: 20
- **new363_direct_http_socket_subprocess_imports**: []
- **explicit_live_client_imports_in_new363**: ['boto3', 'psycopg']
- **truthful_note**: Exact slim-release scan. boto3/psycopg imports occur only inside explicit operator-triggered live validation paths; normal startup opens no external connection.
