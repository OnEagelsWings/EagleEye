# EagleEye Phase 16 Progress – Build 366

**Phase:** 16 — Live Operations, Entity Intelligence & External Validation  
**Progress:** 6/20 builds

## Build 366 — Corporate Live Data

### Delivered
- Governed execution path for the existing official public no-auth **GLEIF LEI** and **SEC EDGAR submissions** connector definitions.
- Exact identifier-bound source records prevent same-provider/host collisions across multiple LEIs or CIKs.
- Human `approved_read_only` source review remains mandatory before execution.
- A second explicit operator confirmation, exactly `LIVE`, is required before a corporate crawl job is queued.
- Live-capable execution reuses the bounded Phase-15 crawler, canonical object store, parse ledger, source-health ledger, job ledger and case audit chain.
- Corporate receipts are derived from the canonical crawl/object/parse ledgers and include hashes, transport kind, review state, HTTP/parser result and validation truthfulness.
- Deterministic/static replay is supported for qualification but can never set `externally_validated=true`.
- SEC execution requires an operator-declared User-Agent containing contact information.
- Authenticated corporate connectors remain plan-only in Build 366; no credential store or autonomous credential handling was added.
- Routine AI corporate context excludes addresses, EINs and person-linked fields; organization facts and filing metadata remain review context.
- Corporate correlation candidates are leads only; identity auto-merge remains disabled.
- Defensive OPSEC can cancel tampered corporate jobs inside the affected case but cannot mutate firewall, OS, Tor, credentials or ACLs.
- Crawler improvement build: **366**.

## Qualification
- Build-366 tests: **26/26 PASS**.
- Build-365 regression: **21/22 PASS**; the only failure is the expected historical version assertion requiring 365.0 instead of 366.0.
- Corporate benchmark: **2,600/2,600 PASS**, 0 violations.
- Schema: **141 tables / 128 indexes / 8 triggers**.
- Build acceptance: **PASS**.

## Truthful external-validation state
- GLEIF app-runtime live validation: **not_run**.
- SEC EDGAR app-runtime live validation: **not_run**.
- Network used by Build-366 acceptance/benchmark: **No**.
- Production release ready: **false**.

The included `tools/live_corporate_validate_366.py` harness can perform an operator-triggered read-only validation only when `--confirm LIVE` is supplied. A successful external status must be backed by an actual canonical receipt from that runtime path.
