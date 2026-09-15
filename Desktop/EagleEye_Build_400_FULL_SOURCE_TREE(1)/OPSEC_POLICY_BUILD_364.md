# Defensive OPSEC Policy – Build 364

- The OPSEC supervisor monitors remote-session integrity in addition to search/crawler/backend security.
- A session fingerprint mismatch may autonomously revoke only that session.
- Repeated denied cross-case access events can trigger defensive session revocation.
- Remote transport must be direct TLS with explicit bind IP, allowed Host values and allowed client CIDRs.
- Build 364 does not trust `Forwarded`, `X-Forwarded-*` or `X-Real-IP` headers.
- The supervisor may block, cancel, pause, isolate or quarantine within approved profiles.
- No autonomous firewall, OS, Tor, account, credential or ACL mutation.
