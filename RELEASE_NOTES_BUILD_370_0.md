# Release Notes – Build 370.0

## Controlled Tor Gateway
- Loopback-only SOCKS5 gateway profile.
- SOCKS5 domain forwarding prevents local onion DNS resolution.
- Per-search SOCKS-auth isolation tokens.
- Dedicated Tor job queue with case/global backpressure and lease recovery.
- Manual source review + `TOR_LIVE` gate.

## Crawler continuity
Crawler improvement is now a permanent Phase-16 requirement for Builds 370–380, with one measurable crawler increment in every build.

## Boundaries
No ControlPort/NEWNYM, no Tor/OS/firewall mutation, no credentials or authenticated browsing, no forms/uploads/payments, no access-control bypass, no automatic identity/fact promotion.
