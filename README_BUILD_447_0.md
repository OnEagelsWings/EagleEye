# EagleEye Build 447.0 — Evidence → Claims → Dossier Closure

Build 447 closes the investigative data path from acquired observations to a human-reviewable Living Dossier.

## Canonical chain

`Acquisition → Evidence → Claims → Hypotheses / Counterevidence → Matrix → Synthesis → Living Dossier`

Build 447 does not turn acquired content into facts automatically.

## Evidence layer

Build 447 synchronizes case-scoped Build-423 observations and binds them to:

- Build-421 source identity;
- Build-422 acquisition event and immutable source snapshot;
- Build-423 content hash and deduplication record;
- Build-429 News metadata where present;
- Build-432 Public-Social metadata where present.

It stores references, metadata snapshots and hashes. It does **not** duplicate raw source payloads.

Every evidence item starts `unreviewed`. Human review can mark it:

- `accepted`
- `context_only`
- `rejected`

Evidence review requires the exact confirmation:

`REVIEW EVIDENCE 447`

## Claim layer

Claims are explicit propositions created against reviewed evidence.

A claim requires at least one accepted supporting evidence reference.

Each evidence link has one explicit stance:

- `support`
- `contradict`
- `context`

Counterevidence is never discarded. Claims with counterevidence require an uncertainty note.

Claims begin as:

`candidate_review_required`

Human review requires:

`REVIEW CLAIM 447`

Only `accepted_for_dossier` claims can enter a dossier revision.

No probability or automatic truth score is generated.

## Living Dossier

Each dossier build creates a new immutable-numbered revision. The snapshot includes:

- case context;
- human-reviewed claims;
- full Claim↔Evidence mapping;
- counterevidence;
- explicit uncertainty register;
- Build-418 hypothesis/counterevidence matrix when bound to a Build-439 loop;
- latest Build-419 synthesis;
- Build-446 acquisition execution references;
- source snapshots and content hashes.

Every new revision begins:

`draft_for_review`

Approval requires:

`APPROVE DOSSIER 447`

## Export

Only an approved revision can be exported.

Export requires:

`EXPORT DOSSIER 447`

Build 447 creates:

- JSON dossier snapshot;
- DOCX Living Dossier;
- PDF Living Dossier;
- manifest with hashes;
- ZIP Case Package.

The Case Package contains references, provenance and hashes, not automatic copies of raw source payloads.

Formal four-eyes export workflow remains a Build-449 responsibility.

## Integrity

Build 447 detects:

- tampering with its own Evidence, Claim, link, Dossier and Export rows;
- missing or changed Build-421/422/423 provenance records after Evidence sync;
- Evidence changed after being linked to a Claim.

A failed integrity check blocks Dossier approval/export.

## Limits retained

Build 447 does not:

- determine truth automatically;
- accept claims automatically;
- remove counterevidence;
- suppress uncertainty;
- expand collection scope;
- perform network retrieval;
- publish dossiers automatically.

Production readiness remains false.

Next: Build 448 — Investigator Workspace.
