# EagleEye Build 381.0 — Phase 17 start

Build 381 starts Phase 17 with two coupled foundations:

1. **Investigation Control Plane v381** — a case-scoped, read-only readiness and planning layer over Evidence, Crawler, Operations, OPSEC, Graph, Search, Image Intelligence and AI status providers.
2. **Global Source Registry foundation** — governed metadata for public, licensed or explicitly authorized data sources, with source classes, jurisdictions, entity types, access methods, validation state, provenance requirements and review gates.

## Deliberate boundaries

Build 381 is network-silent. It does not create crawler requests, does not execute connectors, does not expand scope, does not merge identities, and cannot mutate firewall/OS/Tor/credential/ACL state. A research plan always requires a later explicit GO and retains existing source/provider gates.

## Packaging status

This artifact is a Build-381 overlay because the current conversation contains Build-380 verification/manifests and the Build-380 ZIP checksum, but not the actual Build-380 source ZIP. It is therefore **not** represented as a complete Build-381 release package. Integration/version bump/regression against the full Build-380 tree must occur only when that exact source package is available.
