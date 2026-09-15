# Build 379 External Qualification Guide

The packaged build intentionally contains no passing external receipt. To qualify Build 379 externally, run the supplied qualification harness on an independent host/lab against the exact release fingerprint, retain metrics and evidence artifacts, and have an independent reviewer sign the canonical receipt with Ed25519. Configure only the reviewer's public-key PEM in `<runtime-base>/qualification_379/trusted_external_reviewer_ed25519.pem` and place the signed receipt at `<runtime-base>/qualification_379/external_receipt.json`.

Minimum receipt gates: at least 3600 seconds, 500 crawler jobs, 50 failure injections, 2 workers, >=99% recovery, p95 lease recovery <=10s, p95 queue dispatch <=30s, p95 failure containment <=10s, zero stale leases after recovery, zero cross-case leaks, zero evidence-loss/automatic-eviction events, zero unauthorized network escalations, consistent audit chain, and at least three SHA-256-bound evidence artifacts.

Receipt integrity does not grant network scope. All normal source review, RBAC, Search Capsule, OPSEC, provider-specific LIVE gates and Tor-specific gates remain active.


Release default: `external_qualification = not_run` and `externally_validated = false`. Local prequalification never changes this state.
