# EagleEye Build 360 — AI Investigation Final Policy

Build 360 closes Phase 15 with internal qualification of the evidence-first Investigation Supervisor.

## Authority model

- External research begins only after an explicit human **GO**.
- The supervisor may delegate only to already reviewed/approved read-only sources.
- Search Capsule, OPSEC-v2, queue budgets, RBAC and crawler bounds remain authoritative.
- The supervisor cannot widen allowlists, change firewall/proxy/Tor/OS settings, approve sources, merge identities, delete evidence, export or release without the required human gate.
- Hypotheses are never automatically promoted to facts.
- Image similarity/geolocation outputs remain leads/hypotheses unless separately verified.
- Voice commands are editable intents and cannot bypass confirmation/RBAC.

## Training truthfulness

Build 360 reports 2,000 synthetic/adversarial qualification cases with 0 boundary violations. This is evaluation/policy qualification, not model-weight training. Human-reviewed training examples remain 0.

## Release truthfulness

The internally qualified state is **controlled local pilot candidate**. Production release is blocked until independent external security/load validation and a professional pilot are actually completed.
