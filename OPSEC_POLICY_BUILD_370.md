# Defensive OPSEC Policy – Build 370

- Tor SOCKS endpoint must be a literal loopback address.
- Onion DNS resolution must remain inside the SOCKS/Tor path; no local onion DNS is permitted.
- Per-search SOCKS authentication tokens are used only for stream/capsule isolation.
- No Tor ControlPort, NEWNYM, torrc mutation or Tor process spawning is available to EagleEye.
- No destination credentials, cookies, forms, uploads, payments or access-control bypass are supported.
- Tor jobs are case-scoped, manually confirmed and isolated from the Clearnet worker queue.
- OPSEC may cancel invalid/tampered Tor jobs inside the affected case, but cannot mutate firewall, OS, Tor, credentials, accounts or ACLs.
