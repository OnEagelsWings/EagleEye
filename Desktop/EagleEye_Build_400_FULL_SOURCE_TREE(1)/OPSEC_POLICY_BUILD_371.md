# Defensive OPSEC Policy – Build 371

- Entity-link jobs are validated against case scope and their bound crawl provenance hash.
- Tampered or cross-case entity-link jobs may be cancelled only in the affected case.
- Entity-link analysis has no external request budget and no direct HTTP/socket/subprocess client.
- OPSEC cannot approve identity links or perform merges.
- Existing Build-370 Tor boundaries remain unchanged: no ControlPort, NEWNYM, torrc/process mutation or access-control bypass.
- No autonomous firewall, OS, Tor, credential, account or ACL mutation.
