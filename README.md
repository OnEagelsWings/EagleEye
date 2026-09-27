# EagleEye — Build 444

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 444 is the fourth build of **Phase 20 — Real-World Acquisition, Operationalization & Serious Beta**.

## Build 444 focus

Build 444 adds **Controlled Public-Social Acquisition** on top of the hardened Build-442 network path and the existing Build-432 social observation model.

Supported public adapters:

- Mastodon public JSON
- Bluesky public AppView JSON
- explicit `generic_public` schema `eagleeye_public_social_v1`

Every source must be registered as `source_type=social`, `access_mode=public` and must explicitly declare `coverage.social_adapter`.

## Acquisition chain

```
421 social source
  -> 425 single-endpoint task
  -> 442 hardened public retrieval
  -> 422/423 endpoint provenance
  -> normalized public social objects
  -> derived 422/423 observations
  -> 432 public-social observations
```

The endpoint JSON is parsed in memory and is not introduced as a second persistent raw-response store.

## Guardrails

Build 444 does not authenticate, use cookies, access private/direct content, send messages, execute JavaScript, enumerate follower/following graphs, auto-discover endpoints or paginate automatically.

Each run is limited to one reviewed endpoint and at most 50 returned objects.

Only `public` and `unlisted` objects are accepted. Posts and threads require a valid source timestamp. Profile/account collection-time fallback is explicitly labeled as observation time rather than publication time.

Canonical object URLs must remain on the source host or an explicitly reviewed `coverage.allowed_object_hosts` entry.

Responses containing credential/session-like fields are rejected.

## Live execution

Live execution requires exactly:

`SOCIAL444_LIVE`

All network access inherits Build 442 DNS rebinding protection, IP pinning, robots policy, TLS validation, retry/backoff, rate control and byte/time budgets.

## Phase 20 acquisition status

Implemented before the Build-445 gate:

- 441 controlled Surface-Web retrieval
- 442 Surface retrieval hardening
- 443 live public News feed acquisition
- 444 controlled Public-Social acquisition

Still not claimed:

- general production readiness
- broad platform coverage
- authenticated/private collection
- automated social-graph expansion
- process/container isolation
- broad external end-to-end validation

Therefore:

- `general_live_collection_complete: false`
- `real_world_general_research_ready: false`
- `production_release_ready: false`

The next build is **445 — Data Acquisition Hard Checkpoint**.

## Start

Python **3.12+** is required.

Windows:

```powershell
START_EAGLEEYE_PRO.bat
```

Manual start:

```powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_444_0.py
```

Linux/macOS:

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build444_integrated.py
```

See `README_BUILD_444_0.md`, `BUILD_444_CASE_TEST.md` and `RELEASE_MANIFEST_BUILD_444_0.json`.
