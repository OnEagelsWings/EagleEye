# Defensive OPSEC Policy – Build 367

- Public-money live execution is allowlisted to exact-record USAspending Award GET and TED published-notice XML GET.
- Every source requires human read-only review and every execution requires the exact `LIVE` confirmation.
- Generic free-URL execution and recipient-name live search are blocked.
- TED Search API POST execution is not enabled in Build 367.
- Replay/static fixtures can exercise the real crawler/parser/receipt chain but can never claim external validation.
- Invalid or tampered public-money jobs may be cancelled within the affected case.
- No autonomous firewall, OS, Tor, credential, account or ACL mutation is permitted.
