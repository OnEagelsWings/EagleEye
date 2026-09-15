# AI Investigation Policy – Build 386

The AI investigator may request a capability-scoped GO grant only for an already confirmed Build-384 research wave and a Build-385 acquisition packet. A grant is bounded to a case, exact packet hash, reviewed canonical sources, workflow generation, request budgets, Operations readiness, OPSEC state, and a short expiry.

Build 386 does **not** execute external requests or enqueue crawler work. It cannot expand source scope, approve sources, bypass workflow budgets, bypass OPSEC/Operations holds, inject credentials, or mutate firewall/OS/Tor/ACL settings. Downstream provider execution still requires the existing explicit `LIVE` confirmation.
