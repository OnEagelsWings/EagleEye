# OPSEC Policy — Build 387

Build 387 preserves defensive OPSEC as an independent last-moment gate. Immediately after one-time grant reservation and before enqueue, the executor revalidates grant expiry, acquisition packet hash, workflow identity/generation, Operations readiness hash, OPSEC preflight hash, source review/enabled state, request budgets and active-crawl limits.

Any mismatch fails closed and rolls the transaction back. The executor itself performs no external request and claims no worker lease. No firewall, OS, Tor, credential, ACL or offensive countermeasure authority is added.
