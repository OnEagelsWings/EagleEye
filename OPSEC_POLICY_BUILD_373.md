# Defensive OPSEC Policy – Build 373

- Graph navigation is permitted only for analyst-selected sources already present in the case's crawler→entity provenance.
- Sources must remain human-approved, unauthenticated, clearnet, healthy and within the Build-373 page/request budget.
- Darknet/Tor sources and provider-gated connector sources cannot use the generic graph-navigation path.
- OPSEC revalidates tagged graph-originated crawler jobs and cancels invalid/tampered jobs only in the affected case.
- No automatic source discovery or scope expansion is permitted.
- No autonomous firewall, OS, Tor, credential, account or ACL mutation is permitted.
