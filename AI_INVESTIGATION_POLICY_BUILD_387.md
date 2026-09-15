# AI Investigation Policy — Build 387

Build 387 adds a controlled execution boundary after the Build-386 capability-scoped GO grant. The AI investigator may prepare or request execution only inside an already approved case/source/workflow scope. An actual dispatch requires the one-time grant token plus exact human `LIVE` confirmation.

The executor may enqueue only existing reviewed read-only Phase-16 connector sources. It may not invent URLs, inject credentials, expand scope, merge identities, claim a worker lease, perform a network fetch, or mutate host/firewall/Tor/credential/ACL state. Every dispatch is case-scoped, budget-bound, provenance-anchored and replay-protected.
