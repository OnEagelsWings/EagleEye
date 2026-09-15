# Release Notes – Build 364.0

## New
- Remote-team direct-TLS profile.
- Explicit network/Host/CIDR policy.
- Secure remote cookies and HSTS.
- Remote bootstrap disabled.
- Session fingerprint anomaly revocation.
- OPSEC denial-burst session protection.
- AI dossier remote-team validation context.
- Crawler remote-RBAC/session-awareness.

## Qualification
- 26/26 Build-364 tests PASS.
- 2200/2200 benchmark cases PASS; 0 boundary violations.
- Real loopback TLS: PASS, two authenticated clients, cross-case HTTP 403.
- Build-363 regression: 18/20; two expected version-only assertions.

## Not claimed
- No external remote-client/network validation.
- No production release.
