# OPSEC Policy – Build 383

Source Planner v1 is network-silent. It imports no network client and cannot mutate firewall, OS, Tor, credentials, ACLs, proxy settings or external services. Operations/OPSEC holds block planning before a plan is persisted.

Source ranking is metadata-only. Endpoint metadata from the existing governed registry remains subject to Build-381/382 source validation and review. Human selector confirmation is not network authorization and does not bypass provider-specific LIVE gates, crawler budgets, RBAC, provenance or OPSEC controls.
