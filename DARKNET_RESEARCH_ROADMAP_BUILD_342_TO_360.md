# EagleEye Phase 15 – Darknet Research Hardening 342–360

Build 342 adds a binding secondary workstream for every remaining Phase-15 build. The objective is not unrestricted darknet access. The objective is a safer, evidence-first research path for public or otherwise authorized material, with provenance, isolation, review and explicit epistemic status.

## Binding safety boundary

The Phase-15 darknet path is read-only and public/authorized-source only. It must never implement access-control bypass, credential stuffing, credential reuse, account takeover, purchases, messaging/contact automation, uploads, malware execution, exploit delivery, acquisition of stolen/private datasets, or automated deanonymization. Every future external request must pass the Search Session Capsule and OPSEC gate and remain attributable to an approved case/search_run.

## Build-by-build progression

| Build | Darknet improvement |
|---:|---|
| 342 | Source registry, human review states, provenance contract, safe non-networked research planning |
| 343 | Versioned Agent Task/Result contract; AI investigator receives no direct Tor/browser/network handle |
| 344 | Consolidated source/search/evidence schema and Build-340/342 migration |
| 345 | Search Session Capsule with isolated approved Tor profile, workspace, cookies/cache/secrets and per-search key material |
| 346 | OPSEC v2 leakage tests: DNS/WebRTC/referrer/redirect/secret exposure, malicious content and tracking indicators |
| 347 | Durable evidence/object-store path for quarantined raw artifacts and hash-verified restore |
| 348 | Persistent queue, cancellation, retries/backoff, checkpoints, resource/rate budgets and dead-letter handling |
| 349 | Governed crawler SDK and read-only onion worker contract; source/license/allowed-use manifest |
| 350 | Cross-source corporate/entity correlation without automatic identity promotion |
| 351 | Conditional/deduplicated retrieval for approved onion sources; unchanged content does not create new evidence; source assertions remain review-required |
| 352 | Archive/history snapshots, source health and temporal provenance |
| 353 | Safe image/document extraction from quarantined artifacts; metadata and OCR remain separated |
| 354 | Image similarity/duplicate leads and approved reverse-image services; hits remain leads |
| 355 | Visual geolocation/landmark/manipulation signals; visual location remains hypothesis unless metadata/evidence supports it |
| 356 | Image/document/entity/graph/timeline fusion with human merge gates |
| 357 | Approved multi-wave AI investigation and controlled delegation across clearnet/darknet evidence |
| 358 | Voice-requested darknet research with visible transcript and confirmation before any external execution |
| 359 | Team RBAC, case isolation, export/release governance and operational hardening |
| 360 | Independent pentest/red-team, OPSEC, load and pilot qualification of the complete path |

## Evidence contract for every darknet finding

Every result entering Evidence/Graph/Dossier must preserve at minimum: case_id, search_run_id, source_id, origin class, onion/clearnet indicator, retrieval timestamp, content hash, redirect chain, transport policy, OPSEC decision reference, security/quarantine state, parser version, provenance references, epistemic class, and human review state.

A source statement is not automatically a fact. Onion source claims remain source assertions until independently corroborated and reviewed.


## Build 343 delivered

Darknet requests are now persisted as versioned `darknet_research` Agent Tasks. The new kernel itself has no Tor/browser/network imports. Pending tasks are blocked; human-approved tasks remain deferred until a dedicated Search Session Capsule and OPSEC runtime gateway exist. No credentials, form submission, uploads, contact, payment, binary execution, access-control bypass or stolen/private dataset acquisition is introduced.

## Build 344 delivered

- Darknet source governance moved into build-independent `phase15_sources` and `phase15_source_review_events`.
- Build-343 Agent Tasks migrate into `phase15_agent_tasks` / `phase15_agent_results`.
- Pre-344 records remain preserved in a verified rollback snapshot.
- Runtime Tor/browser/network execution remains disabled pending Builds 345–346.

## Build 345 delivered

- Every approved Darknet research run can now receive its own `search_run_id` and isolated Search Session Capsule.
- `tor_read_only_v1` is a policy/profile reference only; Build 345 never changes local Tor/proxy configuration and opens no connection itself.
- Exact v3 Onion egress allowlists are derived from human-reviewed `approved_read_only` sources.
- Each intended Onion request is checked independently for source match, allowlist, redirect scope, read-only method, secret/header leakage and resource budget.
- OPSEC decisions are persisted; security logs are redacted and encrypted with per-capsule AES-GCM key material.
- The adversarial Build-345 benchmark contains 250 cases and records zero boundary violations.
- Runtime execution remains deferred until the later governed worker/gateway builds; Build 346 now adds leakage intelligence and adversarial OPSEC evaluation.

## Build 346 implemented checkpoint

Build 346 adds OPSEC Intelligence v2 to every Darknet Search Session Capsule. Onion requests require the approved Tor policy path, no local Onion DNS resolution, verified WebRTC-off/DNS-path evidence, exact source binding and redirect containment. Imported/future response content can be quarantined for prompt-injection, secret-exposure and active-content signals. The module still opens no Tor/network connection and cannot mutate Tor, proxy, firewall, OS or credentials.

## Build 347 completion status

Build 347 implements the durable artifact side of the Darknet research path. Onion content is **not fetched by Build 347**; only controlled gateway/local handoffs can be ingested. Every Darknet artifact requires a case-linked search run and a human-reviewed `approved_read_only` onion source, is SHA-256 content-addressed, and is physically placed in quarantine. Review decisions are append-only and do not rewrite the original ingest state. PostgreSQL and S3/MinIO adapters are present as opt-in data-platform foundations, but external live validation remains explicitly `not_run`.

## Build 348 completion status

Build 348 moves Darknet research planning onto the same durable job infrastructure as local investigation work. A Darknet network handoff can only be enqueued after the source is human-reviewed, the case owns an active Darknet Search Session Capsule, and OPSEC Intelligence v2 has issued `allow_for_gateway` for the exact URL. The persisted payload records that `network_execution_by_build348=false` and requires a later governed worker gateway. Quarantined Onion artifacts remain excluded from FTS5 until an explicit human `approve_safe` object-review event exists. Jobs are idempotent, leased, checkpointable, cancellable/resumable and dead-lettered after bounded retries. Build 348 itself starts no background worker and opens no external connection.

## Build 349 update – crawler workstream now permanent through Build 360

From Build 349 onward, Darknet research shares the governed crawler architecture. Onion sources remain human-reviewed `public_or_authorized_read_only`; Crawl Jobs inherit Queue budgets, Search Session Capsules, OPSEC-v2 preflight, fetch provenance and mandatory Object-Store quarantine. Build 349 deliberately contains no built-in live Tor transport and refuses direct `.onion` use in its clearnet transport. The detailed crawler progression is defined in `CRAWLER_ROADMAP_BUILD_349_TO_360.md` and must be advanced in every remaining Phase-15 build.


## Build 350 completion status

Build 350 adds deterministic parser and corporate-source normalization while preserving the Darknet quarantine boundary. Onion artifacts are not auto-parsed. Cross-source entity correlation produces review-required leads with both source/object/parse references and `identity_confirmed=false`; it never promotes identity automatically. The crawler remains read-only and bounded.


## Build 351 completion status

Build 351 adds ETag/Last-Modified conditional fetch and exact SHA-256 deduplication to the governed crawler, including approved onion source jobs. A 304 response or unchanged body does not create a new raw artifact or parse run. Changed onion content still enters mandatory quarantine and is linked to the previous fetch/hash. The built-in clearnet transport continues to refuse `.onion`; live onion execution still requires an explicitly approved Tor gateway transport.

## Build 352 completion status

Build 352 adds bounded archive/history seeds, sitemap discovery, conservative canonical URLs and a durable prioritized frontier to approved darknet crawl jobs. Frontier state is stored in the existing persistent job checkpoint rather than a new per-build schema family. After worker interruption, an onion crawl can resume from the saved frontier while retaining the exact source allowlist, Search Session Capsule, OPSEC-v2 boundary and mandatory quarantine. HTTP replay is at-least-once; conditional validators and exact SHA-256 dedup prevent unchanged content from becoming duplicate Evidence. The built-in clearnet transport still refuses `.onion`, and no live Tor transport is bundled.

## Build 353 update – Darknet Image Intake

Darknet image artifacts now pass the same reviewed Onion source, Search Capsule and OPSEC-v2 chain as textual research. All Onion images remain physically quarantined. Build 353 does not perform face identification, visual geolocation, reverse-image search or live Tor transport validation.

## Build 354 completion status – Darknet Image Similarity Leads

Build 354 adds local exact/perceptual image comparison to quarantined and reviewed image assets without performing any external request. SHA-256, aHash/dHash and a local handcrafted visual descriptor may create review-required duplicate/variant leads, but never identity or location claims. External reverse-image providers must be registered and human-reviewed; a quarantined Onion image cannot be handed off until a separate human safe-review. Provider execution remains gateway-deferred, external hits remain leads, and no live Tor transport is bundled.


## Build 355 completion status – Darknet Visual Geolocation Boundaries

Build 355 permits only local, explicit-human-approved visual geolocation analysis of quarantined Onion images. Embedded GPS remains metadata-derived evidence and is not treated as proof of the depicted scene location. Visual/landmark outputs are calibrated hypotheses, technical manipulation indicators are non-conclusive, and no face identity or authenticity claim is produced. Stored Onion page context may generate same-host source-context leads but never expands the allowlist or triggers an automatic fetch. No live Tor transport is bundled.


## Build 356 completion status – Darknet Cross-Modal Fusion

Build 356 allows the AI Investigation Supervisor to fuse already collected/reviewed darknet evidence with clearnet documents, media, entities, graph and timeline into candidate hypotheses and a provenance-bound draft dossier. External darknet delegation still requires explicit human `GO` and only already human-reviewed `approved_read_only` sources can be enqueued. The supervisor has no direct Tor/network handle and cannot auto-approve a source, broaden an allowlist, confirm identity/location, merge, export, delete or release. Darknet artifacts remain quarantined under the existing review policy, and no built-in live Tor transport is bundled.

## Build 357 implemented

- Approved read-only Onion sources may participate in bounded post-GO research waves.
- Follow-up Onion jobs remain subject to Search Capsule, OPSEC-v2, job/request budgets and quarantine.
- The supervisor does not gain a direct Tor/network client.
- Built-in live Tor transport remains unavailable; no direct Onion DNS resolution is introduced.
- OPSEC/content blocks stop automatic follow-up waves and require human attention.


### Build 358 voice boundary
Voice input does not create a new Darknet execution path. Spoken Darknet/search commands are first converted to a visible editable intent and require explicit confirmation; all existing reviewed-source, capsule, OPSEC-v2, Tor-profile-reference, quarantine and no-direct-onion-DNS controls remain authoritative. The built-in live Tor transport remains absent.

## Build 359 completion status – Team RBAC for Darknet research

Build 359 adds case-scoped team authorization around the existing darknet research workflow. A user must both belong to the case and hold a role permitting the requested research/crawler action; voice commands cannot bypass this boundary. Source review is restricted to authorized reviewer/lead roles, and crawler lease recovery is lead-only. All previous Onion controls remain authoritative: reviewed read-only sources, Search Capsule, OPSEC-v2, approved Tor-profile reference, mandatory quarantine and no direct Onion DNS. Build 359 still bundles no live Tor transport. External security/load/pilot validation remains Build 360.


## Build 360 completion status — Darknet boundary final internal qualification

Build 360 re-qualifies the existing darknet safety boundary as part of the final internal release matrix: reviewed read-only source governance, Search Capsule, OPSEC-v2, job/request budgets, RBAC and quarantine remain mandatory. No direct Onion DNS path or autonomous Tor/network mutation is introduced. The final benchmark uses no live Tor connection; **live Tor gateway validation remains `not_run`** and production readiness is not claimed.
