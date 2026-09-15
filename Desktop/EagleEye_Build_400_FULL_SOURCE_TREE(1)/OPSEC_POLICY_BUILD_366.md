# Defensive OPSEC Policy – Build 366

- Corporate live jobs require an allowlisted no-auth connector, human-approved read-only source and explicit `LIVE` confirmation.
- GLEIF and SEC host/URL policies are exact and remain governed by the bounded crawler transport.
- SEC live execution requires a declared operator User-Agent with contact information.
- Authenticated corporate connectors are blocked from live execution in Build 366.
- Static replay or fixture transports can qualify parser/provenance behavior but can never claim external validation.
- The OPSEC supervisor may cancel a tampered/invalid corporate job only inside the affected case.
- No autonomous firewall, OS, Tor, credential, account or ACL mutation is introduced.
