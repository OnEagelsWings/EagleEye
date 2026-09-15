# EagleEye Phase 15 – verbindlicher Crawler-Workstream Builds 349–360

**Start:** Build 349.0  
**Leitprinzip:** Der Crawler wird in jedem verbleibenden Phase-15-Build messbar verbessert. Keine Verbesserung darf Search Capsule, OPSEC-v2, Source Governance, Human Review, Quarantäne oder Provenienz umgehen.

## Dauerhafte Sicherheitsgrenzen

- nur öffentliche oder ausdrücklich autorisierte Read-only-Quellen
- GET/HEAD-only; keine Formulare, Uploads, Zahlungen oder Kontoaktionen
- keine Zugangskontrollumgehung und kein Credential-Reuse
- exakte Host-/Source-Allowlist je Crawl
- Search Session Capsule + OPSEC-v2 vor jedem Fetch
- Robots-/Terms-/Lizenzstatus als Source-Governance-Daten
- persistente Job-Budgets, Leases, Retry/Backoff und Checkpoints
- vollständige Fetch-Provenienz, Content-Hash und Object-Store-Referenz
- Darknet-Artefakte grundsätzlich Quarantäne bis Human Review
- kein autonomes Ändern von Tor, Proxy, Firewall, Betriebssystem oder Zugangsdaten

## Buildfolge

| Build | Verbindliche Crawler-Verbesserung | Messbarer Gate |
|---:|---|---|
| **349** | Governed Crawler SDK, bounded crawl, Robots, Terms-Review, Queue/Capsule/OPSEC/Object-Store-Pipeline | 0 Allowlist-/Robots-/OPSEC-Bypasses im adversariellen Benchmark; keine Background-Autonomie |
| **350** | Connector-/Parser-SDK für HTML, XML, JSON und priorisierte Corporate-/Registerquellen; Source Health v2 | Parser-Contracttests, reproduzierbare Normalisierung, Source-Health-Metriken, keine stillen Parsefehler |
| **351** | inkrementelles Crawling mit ETag/Last-Modified, Conditional Requests, Content-Deltas und exakter Deduplikation | deutlich reduzierte unnötige Re-Fetches; Delta-/Dedup-Korrektheit gemessen |
| **352** | Archive-/Sitemap-Traversal, Canonical-URL-Normalisierung, Link-Priorisierung und robuste Resume-Checkpoints | Crash/Resume ohne verlorene oder doppelt terminale Seiten; Crawl-Frontier reproduzierbar |
| **353** | sicherer Media-/Image-Fetch-Pfad für Image Intelligence; MIME-/Magic-/Hash-Prüfung | keine ungeprüften aktiven Dateien in Bildpipeline; Medienprovenienz vollständig |
| **354** | Bild-/Asset-Deduplikation, perceptual hashes und lokale Embedding-Handoffs | Duplicate Precision/Recall separat gemessen; Varianten gruppiert statt mehrfach gecrawlt |
| **355** | geolokationsrelevante visuelle Kontextgewinnung und Source-neighborhood Crawls | visuelle Indizien strikt als Hypothesen; keine GPS-Fakten aus bloßer visueller Vermutung |
| **356** | Cross-modal Crawl Fusion: Dokumente, Medien, Entities, Graph und Timeline | Herkunft jedes Graph-/Timeline-Links auf konkrete Fetch-/Object-Evidenz rückführbar |
| **357** | AI Research Waves delegieren begrenzte Crawl-Subjobs über Task Contracts | Agent kann Budgets/Allowlist nicht erweitern; Delegations- und Stop-Gates gemessen |
| **358** | Voice-initiierte Crawl-Pläne mit sichtbarem Transkript und Bestätigung | kein Voice-Befehl startet Fetch ohne bestätigten strukturierten Auftrag |
| **359** | Team-RBAC, Crawl-Permissions, Audit-/Dossierexport und Betriebs-/Soak-Härtung | unberechtigte Crawl-/Exportaktionen 100 % blockiert; Recovery-/Soak-Metriken dokumentiert |
| **360** | unabhängige Crawler-Security-, OPSEC-, Last-, Failure- und Pilotprüfung | externer/independenter Nachweis; offene kritische Findings = 0 oder Release bleibt gesperrt |

## Kernmetriken ab 349

Jeder weitere Build führt mindestens diese Metriken fort: `crawl_requests_total`, `crawl_pages_stored`, `crawl_policy_blocks`, `robots_blocks`, `opsec_blocks`, `redirect_escape_blocks`, `bytes_fetched`, `duplicate_ratio`, `parse_failures`, `retry_count`, `dead_letter_count`, `crawl_resume_success`, `source_health`, `quarantine_ratio` und `provenance_complete_ratio`.


## Build 350 delivered

- Versioned Connector/Parser SDK for HTML, JSON, XML and text.
- DTD/entity declarations are rejected; parser input/output is bounded.
- Official source manifests for GLEIF, SEC EDGAR and Companies House.
- GLEIF and SEC remain human-review-first; SEC live transport requires a declared operator User-Agent.
- Companies House stays plan-only because API authentication is required.
- Crawler v2 post-processes safe clearnet artifacts into parse runs and source-health events.
- Quarantined and darknet artifacts are never auto-parsed.
- Cross-source corporate matches are correlation leads only; no automatic entity/identity promotion.
- Build 351 must add ETag/Last-Modified conditional fetch, exact-content dedup and delta-sync without new per-feature schema families.


## Build 351 delivered

- Conditional requests use persisted ETag and Last-Modified validators.
- HTTP 304 responses create no new Object Store object and no new parse run.
- Servers that ignore validators are protected by exact SHA-256 deduplication.
- Changed content creates an immutable new object with previous-fetch/hash provenance.
- Delta counters (`new`, `changed`, `not_modified`, `deduplicated`, estimated bytes saved) are persisted in crawl summaries/checkpoints.
- No new per-build schema family was created; the consolidated fetch ledger was extended in place.
- Onion sources use the same conditional/delta semantics but retain mandatory Tor-gateway, OPSEC and quarantine boundaries.

## Build 352 delivered

- Replaced volatile FIFO traversal with a bounded, priority-ordered frontier persisted in the durable job checkpoint.
- Added conservative canonical URL handling; query strings remain intact and cross-host canonical expansion is rejected.
- Added bounded explicit sitemap traversal plus same-host `Sitemap:` discovery from robots.txt.
- Added explicit same-host archive/history seeds without broadening source allowlists.
- Added crash-safe resume with persisted frontier, seen canonical URLs, counters and in-flight URL.
- Resume is at-least-once at HTTP-request level; Build-351 validators and exact SHA-256 dedup prevent duplicate Evidence promotion.
- No new frontier table was created; consolidated schema remains below the Phase-15 gate.
- Onion sources inherit the same frontier/resume logic but still require an approved Tor gateway and mandatory quarantine.

## Build 353 completed – Media/Image Crawler v1

- same-host image discovery from stored HTML (`img`, `source`, `srcset`, OG/Twitter image hints)
- explicit `media_image_fetch_v1` jobs; no autonomous background media crawl
- Search Capsule + OPSEC-v2 + request-budget gate before each media fetch
- magic-byte validation before image promotion
- redirects require a separate reviewed job
- darknet images force physical quarantine
- crawler workstream remains mandatory through Build 360

## Build 354 completed – Asset Similarity & Variant Intelligence

- Every ingested crawler image receives deterministic local SHA-256, aHash64, dHash64 and a handcrafted local visual descriptor.
- Exact duplicates and resize/re-encoding-like variants are linked as review-required media candidates in the existing `phase15_object_links` graph; no Build-354 table family was added.
- The same image arriving through different URLs keeps separate fetch/source/object provenance while gaining a candidate duplicate/variant relationship.
- Similarity never confirms identity, person, location or common source.
- External reverse-image services are represented only as human-reviewed, gateway-deferred providers; Build 354 sends no image bytes or network requests itself.
- Darknet images remain physically quarantined and cannot be handed to an external image-search provider until a separate human safe-review occurs.
- Build 355 must add visual-location/manipulation clues while retaining hypothesis-only semantics and the permanent crawler safety boundary.


## Build 355 completed – Visual Context & Source Neighborhood

- Stored same-host HTML evidence is mined for image-adjacent context, page geo metadata and bounded source-neighborhood leads.
- `geo.placename`, `ICBM` and similar page metadata are classified as source context, never as image-scene fact.
- Visual geolocation remains an explicit human-approved analysis step; the crawler does not auto-promote context into location claims.
- Local reviewed landmark-reference images can create similarity-backed location candidates, but no general landmark-recognition claim is made.
- Technical manipulation signals remain non-conclusive and never establish forgery/authenticity.
- No new schema family was added; crawler context is stored in existing media metadata, job, object and link contracts.
- Build 356 must fuse media/document/entity/graph/timeline evidence while preserving fetch/object provenance for every relationship.


## Build 356 completed – Cross-Modal Crawl Fusion & AI Supervision

- The AI Investigation Supervisor reads governed crawl/job/search/parser/OPSEC state case-wide after an explicit human `GO`.
- Research-wave delegation can enqueue crawl jobs only for already human-reviewed, enabled read-only sources; the supervisor cannot widen allowlists or open network connections itself.
- Every dossier/hypothesis provenance chain can retain `crawl_run → fetch → object hash → parse/media/link → hypothesis/dossier`.
- Crawler outputs are fused with documents, media/image intelligence, entities, graph, timeline and prior agent results.
- Supervisor ticks evaluate crawler progress, failed/dead-letter jobs, OPSEC blocks, parser failures and evidence yield and rebuild the draft dossier; no hidden background autonomy is added.
- No new Build-356 crawler table family is introduced.
- Build 357 must extend this to bounded multi-wave delegation with explicit budgets, stop conditions and review gates.

## Build 357 implemented

- AI Investigation Supervisor delegates bounded crawler subjobs after explicit GO.
- Initial GO wave is unique; follow-up crawl waves wait for terminal evaluation.
- Source ranking uses approved source health and prior job outcomes.
- Hard caps: 4 research waves, 6 sources/wave, 24 case jobs.
- Autonomous continuation stops on OPSEC/content blocks, failed/dead-letter jobs, no material delta or exhausted case budget.
- Provenance chain now includes the research wave before crawl/fetch/object/analysis/dossier.


## Build 358 – Voice-directed bounded crawler control
- Push-to-talk commands can read crawler/job/OPSEC status.
- Commands that could create/continue research require visible transcript plus explicit confirmation.
- Voice delegates only through the existing Build 357 bounded wave orchestrator.
- Voice cannot approve sources, expand host allowlists, alter OPSEC/network configuration or directly fetch URLs.
- Export/Merge/Delete/Release remain manual UI only.
- Crawler provenance remains wave → crawl run → fetch → object hash → parse/media/link → hypothesis → dossier.

## Build 359 completed – Team-governed crawler operations

- Crawler execution is now protected by canonical Phase-15 case RBAC rather than UI-only controls.
- `case_lead`, `investigator` and `analyst` may run bounded crawls; source review remains a lead/reviewer permission and recovery is lead-only.
- Case visibility is membership-scoped before crawler data is exposed.
- Active crawl jobs are capped at 12 per case; manual team crawl authorizations are capped at 12 per user/case/hour, in addition to existing request/resource budgets.
- Expired running leases can be explicitly recovered by the case lead and emit immutable recovery events; dead-letter jobs remain human-attention states and are not auto-revived.
- Voice-initiated research remains subject to the same RBAC, GO, source, OPSEC and queue boundaries.
- Build 360 must independently load/failure/security-test the full governed crawler path before any production-release claim.


## Build 360 completed — Final governed crawler qualification

- Full governed crawler path was included in the internal final qualification: source review/RBAC, bounded jobs, Search Capsule/OPSEC-v2, quotas, lease recovery, provenance and failure-state handling.
- Build 360 adds no new crawler schema family; qualification remains on the consolidated Phase-15 structures.
- Final benchmark contains crawler boundedness, recovery and provenance categories and reports 0 boundary violations.
- Internal benchmark uses no external network and therefore does **not** count as external load validation.
- Built-in live Tor remains absent and is not claimed.
- Crawler workstream 349–360 is complete internally; future work should be driven by external pilot/load findings and real connector validation.
