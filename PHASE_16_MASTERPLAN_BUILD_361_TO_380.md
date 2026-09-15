# EagleEye Phase 16 – Live Operations, Entity Intelligence & External Validation

## Ziel
Builds 361–380 transformieren den kontrollierten lokalen Pilotkandidaten in ein real validiertes Nischenprodukt für kleine professionelle Investigation-Teams.

## Dauerziele jedes Builds
1. AI-Ermittlung: Nach explizitem GO selbstständig planen, recherchieren/delegieren, Crawler überwachen, Evidenz fusionieren, Hypothesen mit Plausibilität bilden und ein schriftliches Evidence-first-Dossier zur Prüfung vorlegen.
2. Datenlücke: reale, rechtmäßig zugängliche oder lizenzierte OSINT-Datenquellen live anbinden und nur nach realem Receipt als externally_validated markieren.
3. Defensive OPSEC-Autonomie: Research-Waves/Crawls/Requests fortlaufend prüfen, blockieren, pausieren, isolieren und quarantänisieren; keine autonome Firewall-/OS-/Tor-/Credential-Mutation.

## Builds
361 Baseline/Pilot & External Validation; 362 PostgreSQL Live; 363 Object/Search Live; 364 Remote Team; 365 Operations; 366 Corporate Live Data; 367 Procurement/Public Money; 368 Sanctions/Legal/Government/Archives; 369 Crawler Production; 370 Controlled Tor Gateway; 371 Entity Resolution v2; 372 Entity Resolution Eval; 373 Analyst Graph UX; 374 Case Workflow; 375 AI Investigation Eval; 376 Dossier vNext; 377 Image Live Validation; 378 Voice Live Validation; 379 External Qualification; 380 Professional Pilot/Production Decision.


## Build 362 actual status
- PostgreSQL migration/live harness implemented and internally qualified.
- Local backup/restore rollback drill PASS.
- External PostgreSQL live validation: **not_run** because no PostgreSQL server/psycopg is present in the build environment.
- Phase progress: **2/20**.

## Build 363 actual status
- Local CAS and SQLite FTS5 remain actively live-validated reference backends.
- S3/MinIO object-store live harness implemented with SHA-256 roundtrip, required SSE and cleanup probe.
- Team-search live harness implemented using explicit PostgreSQL FTS executor/DSN path with case-scoped contract.
- External S3/MinIO live validation: **not_run** because no external endpoint is available in the build environment.
- External Team Search live validation: **not_run** because no PostgreSQL/team-search endpoint is available in the build environment.
- AI investigator now records storage/search validation and degraded-mode context in the review dossier.
- Defensive OPSEC supervisor detects insecure storage endpoints/embedded backend credentials and can stop affected case jobs.
- Crawler improvement build: **363**.
- Phase progress: **3/20**.

## Build 364 actual status
- Remote-team mode implemented as explicit opt-in direct-TLS profile; local loopback remains default.
- Remote mode requires explicit interface IP, TLS certificate/key, allowed hosts and allowed client CIDRs; wildcard bind is blocked.
- Proxy forwarding headers are not trusted in Build 364; direct TLS is the only qualified remote transport profile.
- Real loopback TLS validation: **PASS** with 2 independently authenticated clients and a live cross-case HTTP 403 denial.
- External remote-network/client validation: **not_run**; loopback TLS is not claimed as external validation.
- Session fingerprint changes can revoke the affected session; denial bursts can be defensively revoked by the OPSEC supervisor.
- AI investigator records remote-team validation context in the review dossier.
- Crawler improvement build: **364** with remote RBAC/session context and audited recovery.
- Phase progress: **4/20**.

## Build 365 actual status
- Consolidated case-scoped Operations layer implemented without new per-build telemetry tables.
- Queue/job metrics, worker lease health, crawler metrics, case trace and Incident Console integrated.
- AI investigator performs an operational preflight and enters `operations_hold` before new research when the circuit breaker is open.
- Defensive OPSEC can cancel queued/running jobs only within the affected case; system/firewall/Tor/credential/ACL mutation remains prohibited.
- Crawler improvement build: **365** with queue/lease health, trace context, incident awareness and human-controlled recovery.
- Build-365 tests: **22/22 PASS**; benchmark **2400/2400 PASS**, 0 violations.
- Real local SQLite/job/audit operations validation: **PASS**.
- External multi-user operations/load validation: **not_run**.
- Production release: **false**.
- Phase progress: **5/20**.

## Build 366 actual status
- Governed public no-auth corporate connector execution implemented for exact GLEIF LEI and SEC EDGAR CIK lookup.
- Human source review and exact `LIVE` confirmation are mandatory; startup remains network-silent.
- Authenticated corporate connectors remain plan-only; no credential storage/execution added.
- Corporate receipt derives from canonical crawl/object/parse/source-review ledgers; replay cannot qualify as external validation.
- AI corporate context is case-scoped and data-minimized; addresses/EINs/person-linked fields are excluded from routine context and identity auto-merge remains disabled.
- Defensive OPSEC cancels tampered corporate jobs case-locally without system-control mutation.
- Build-366 tests 26/26 PASS; benchmark 2,600/2,600 PASS, 0 violations.
- GLEIF and SEC external app-runtime validation: **not_run**.
- Crawler improvement build: **366**.
- Phase progress: **6/20**.


## Build 367 actual status
- USAspending exact award and TED exact published-notice XML public-money connectors implemented behind source review + explicit LIVE confirmation.
- TED Search remains plan-only because its official endpoint requires POST; qualified crawler remains GET/HEAD-only.
- Public-money receipts bind source review, crawl/fetch, object hash and parser provenance; replay cannot become external validation.
- AI public-money context is case-scoped and data-minimized; money-flow/corporate-link matches remain review-required leads.
- Defensive OPSEC can contain affected-case public-money jobs without system/network-policy mutation.
- External USAspending/TED validation: **not_run**.
- Phase progress: **7/20**.

## Build 368 actual status
- Federal Register exact-document and Internet Archive exact-item metadata connectors are live-eligible behind human source review + explicit `LIVE`; crawler remains GET/HEAD-only.
- Internet Archive handling is metadata-only; archive payload/content download is not enabled.
- NARA Catalog and GovInfo are plan-only: Build 368 introduces no API-key/credential execution, and current NARA API storage/caching terms conflict with normal Evidence-Vault persistence.
- OFAC SDN and UN consolidated sanctions sources are plan-only until the current expiring signed-redirect download path is explicitly qualified for durable provenance.
- Sanctions parsing is data-minimized and reference-only; fuzzy name screening, automatic match confirmation and adverse-decision support remain disabled.
- AI legal/government/archive context remains case-scoped and review-first; defensive OPSEC can contain only affected-case jobs without system/network-policy mutation.
- Build-368 tests: **35/35 PASS**; Build-367 functional regression: **29/30 PASS** with one expected version assertion.
- Federal Register / Internet Archive real external validation: **not_run**; NARA/GovInfo/OFAC/UN: **plan_only**.
- Crawler improvement build: **368**.
- Phase progress: **8/20**.

## Build 369 actual status
- Crawler Production layer implemented without new per-build database tables.
- Explicit recurring scheduler remains operator-orchestrated; no background worker or automatic external network activity occurs at boot.
- Queue backpressure, source-health circuits/backoff, lease heartbeat/recovery, conditional delta fetching, frontier checkpoint resume and case-scoped soak telemetry are integrated.
- Provider-specific connector `LIVE` gates and darknet/Tor pathways cannot be bypassed by the generic recurring scheduler.
- AI investigator performs crawler-production preflight and can hold new research waves; OPSEC can cancel invalid scheduled jobs only in the affected case.
- Local deterministic scheduler/worker/delta/resume/lease qualification is required for the Build-369 acceptance gate.
- External long-running soak/load qualification remains **not_run** and `production_release_ready=false`.
- Phase progress: **9/20**.

## Verbindliches Crawler-Dauerprogramm Build 370–380
Ab Build 370 wird der Crawler in **jedem** verbleibenden Build der Phase 16 messbar weiterentwickelt. Diese Dauerentwicklung erweitert nicht automatisch den Recherche-Scope: jede neue Quelle und jeder externe Ausführungspfad behält Source Review, RBAC, OPSEC, Provenienz und explizite menschliche Freigaben.

| Build | Verbindlicher Crawler-Increment |
|---:|---|
| 370 | Tor-spezifische Queue, SOCKS-Auth-Capsule-Isolation, Tor-Backpressure und Lease/Recovery; kein ControlPort/NEWNYM. |
| 371 | Entity-linked Crawl-Provenienz und Source-to-Entity-Lead-Queues ohne Auto-Merge. |
| 372 | Crawler/Entity-Resolution-Evaluationskorpus, False-Link- und Source-Quality-Kalibrierung. |
| 373 | Graph-aware, aber menschlich begrenzte Navigation mit Traversal-Budgets. |
| 374 | Case-Workflow-Orchestrierung, Source-Budgets, Pause/Resume und Analyst-Handoff. |
| 375 | AI-Crawl-Planning-Evaluation, Coverage-Metriken und Scope-Expansion-Denial-Tests. |
| 376 | Dossier-Metriken für Source Coverage, Negative Evidence und Staleness. |
| 377 | Image/Media-Crawl-Provenienz, Deduplizierung und Object-Store-Pressure-Control. |
| 378 | Voice-to-Crawl-Intent mit Bestätigung; keine direkte Voice-Netzwerkautorität. |
| 379 | Externe Soak/Load/Failure-Qualifikation und Recovery-SLO-Messung. |
| 380 | Pilot-Telemetrie, SLO-Gate und Produktionsentscheidung. |

**Dauergrenzen:** keine freie URL-/Credential-Ausführung, kein Umgehen von Zugriffskontrollen, kein automatischer Identity Merge, keine autonomen Firewall/OS/Tor/Credential/ACL-Mutationen. `production_release_ready` bleibt false, bis die externen Qualifikations- und Pilotgates tatsächlich erfüllt sind.


## Build 371 actual status
- Entity Resolution v2 is evidence-weighted and explicitly not a calibrated identity probability.
- Strong email/phone/external-ID conflicts veto same-entity inference; common-name collision penalty and source-independence weighting are active.
- Human review is mandatory and only non-destructive same-entity links can be approved; no automatic identity confirmation or merge.
- Crawler increment: entity-linked crawl provenance plus source-to-entity lead queue using the canonical job ledger, with zero network request budget.
- Each lead binds source/crawl/fetch/object provenance hashes and is case-scoped.
- Entity Resolution external/holdout calibration remains scheduled for Build 372.
- Phase progress: **11/20**.


## Build 372 actual status
- Entity Resolution v2 evaluation layer implemented with a deterministic 20-scenario synthetic holdout corpus.
- False-link, false-distinct, precision/recall, defer, common-name and strong-conflict-escape metrics implemented.
- Crawler increment: source-quality calibration and per-lead quality annotation without review bypass.
- Automatic threshold tuning: **false**; automatic merge: **false**.
- External real-world holdout validation: **not_run**.
- Phase progress: **12/20**.

## Build 373 actual status
- Analyst Graph UX implemented as a read-only case-scoped projection over canonical Entity Resolution, review, crawl, source-quality and provenance ledgers; no parallel graph truth store added.
- Graph edges distinguish review candidates, reviewed non-destructive links and crawler-originated source→entity leads; evidence/source-quality scores are explicitly not identity probabilities.
- Offline focus navigation is bounded to depth 2 and does not execute network requests.
- Crawler increment: analysts may explicitly select up to 2 already-evidenced, approved clearnet sources and confirm `NAVIGATE`; source health, backpressure, provider/Tor separation and a 30-request aggregate budget are enforced.
- Graph navigation cannot discover new sources autonomously, cannot use darknet or provider-gated connectors, and cannot bypass review or identity-merge controls.
- AI receives graph aggregates only and has no direct graph-navigation authority; OPSEC cancels tampered graph-originated crawler jobs case-locally.
- External professional graph-UX/navigation validation remains **not_run**; production release ready remains **false**.
- Phase progress: **13/20**.


## Build 374 actual status
- Case Workflow v374 implemented on canonical job/event/audit ledgers with **0 new Build-374 data tables**.
- Case-scoped source-request budgets, aggregate case request budget and active-crawl limits are enforced for workflow-aware crawler starts.
- Queue pause/resume is explicit (`PAUSE` / `RESUME`); running workers are marked to drain rather than force-killed.
- Analyst handoff is two-step (`HANDOFF` then target `ACCEPT`) and requires active case membership.
- Crawler increment: graph navigation and manual crawler enqueue are bound to workflow budgets and workflow IDs; untagged post-activation crawler jobs are OPSEC-detectable.
- AI investigation enters a workflow hold while a case is paused or handoff is pending; AI has no workflow mutation authority.
- External multi-analyst workflow/handoff validation remains **not_run**; production release ready remains **false**.
- Phase progress: **14/20**.


## Build 375 actual status
- AI Investigation Eval implemented as a structured, review-first crawl-planning guard.
- Deterministic 33-scenario synthetic holdout covers workflow state, source selection, case/source budgets, backpressure, Scope Expansion and special provider/Tor gates.
- Crawler increment 375: AI crawl-planning evaluation, coverage/source-selection metrics and Scope-Expansion-Denial testing.
- AI has no direct crawl execution authority; valid plans still require human workflow confirmation.
- External real-case/model evaluation: **not_run**; production release ready: **false**.
- Phase progress: **15/20**.


## Build 376 actual status
- Dossier vNext adds explicit source-coverage, bounded absence-observation, staleness and research-gap registers on canonical ledgers.
- Coverage metrics are explicitly not truth probabilities; absence observations never prove non-existence and are not counterevidence by default.
- Crawler increment 376: per-source coverage state, freshness thresholds, stale-source review gaps and no-auto-crawl gap handling.
- Bounded absence observations require a succeeded case/source crawl, at least one 2xx/3xx fetch and explicit analyst `RECORD`; tampered observations are excluded from the dossier.
- Dossier vNext can persist a review-only `phase16_ai_dossier_v376` report in the existing professional report ledger; Build 376 adds **0 new data tables**.
- AI receives coverage/gap context but cannot close gaps or execute crawler work; OPSEC cancels queued crawler jobs that claim automatic gap closure.
- External professional dossier/negative-evidence validation remains **not_run**; production release ready remains **false**.
- Phase progress: **16/20**.

## Build 377 actual status
Build 377 is implemented as Image Live Validation + Media Crawler Hardening. Phase 16 progress: **17/20**. The local image pipeline is qualified for provenance, exact deduplication, object-store pressure control and review-first local-agent handoff. External image-source, reverse-image-provider and professional image-analyst validation remain `not_run`. Continuous crawler expansion 370–380 remains mandatory.


## Build 378 actual status
- Voice Live Validation is implemented as a local push-to-talk/transcript-to-crawler intent layer over the existing Phase-15 voice gateway.
- Crawler increment 378: visible voice crawl preview, explicit source selection, workflow/source request-budget preview, preview-hash provenance and edit-triggered reconfirmation.
- Exact `VOICE CRAWL` confirmation is mandatory; confirmation always reruns a fresh workflow, source-health and backpressure preflight.
- Voice does not auto-select sources, auto-expand scope, execute provider/Tor special paths or perform network requests directly.
- Confirmed normal clearnet work delegates to the existing case-workflow crawler queue and is tagged with voice-intent provenance for OPSEC review.
- Local STT remains optional/offline and audio is not persisted; external STT accuracy, multi-analyst voice UX and external crawler-network validation remain **not_run**.
- Production release ready remains **false**.
- Phase progress: **18/20**.


## Build 379 actual status
- External Qualification framework implemented without new per-build database tables.
- Local soak/load/failure prequalification uses isolated temporary state and replay transports; it is explicitly not external validation.
- Crawler recovery qualification covers durable frontier checkpoints, expired-lease recovery, queue backpressure, case isolation and object-store hard-pressure behavior.
- Production runtime contains no fault-injection action. OPSEC rejects qualification-fault markers found in operational cases.
- External qualification receipt contract is fingerprint-bound and requires Ed25519 verification against a configured independent reviewer trust anchor.
- External receipt thresholds require >=3600 s duration, >=500 crawler jobs, >=50 injected failures, >=2 workers, >=99% recovery, bounded p95 recovery/dispatch/containment SLOs, and zero cross-case leaks, evidence loss, automatic eviction or unauthorized network escalation.
- No receipt is bundled into the release, so external qualification remains **not_run** in the packaged build.
- Production release remains **false**; Build 380 is the final professional-pilot/SLO production decision.
- Crawler improvement build: **379**.
- Phase progress: **19/20**.


## Build 380 actual status
- Phase 16 is complete: **20/20** builds.
- Final Professional Pilot / Production Decision layer is implemented without new per-build data tables.
- Pilot telemetry is read-only and starts no network work or background workers.
- Final crawler SLO gate separates local accelerated prequalification from independent production SLO evidence.
- Current independent Build-379 receipt state: **not_run**.
- Current decision: **professional_pilot_only**.
- `production_candidate=false` and `production_release_ready=false` in the packaged current state.
- Production candidacy requires independently signed Build-379 qualification; unvalidated specialty capabilities remain separately gated.
- Human release review remains mandatory; automatic production promotion is disabled.
