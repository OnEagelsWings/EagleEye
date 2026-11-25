# Claude Code – EagleEye/PersonOSINT integration handoff

Repository: `OnEagelsWings/EagleEye`
Integration branch: `integration/build493-unified-personosint`
Review PR: https://github.com/OnEagelsWings/EagleEye/pull/92
Claude original reference: `claude/osint-platform-person-search-r875rx`
Build 492 parent: `claude/spiderfoot-reverse-engineering-dn8lpd`

## Target architectural rule
ONE canonical EagleEye case, Evidence/Vault, team identity, OPSEC and audit.
No second live PersonOSINT auth server or database. No silent alias merges,
no unreviewed relationship confirmation.

## Already implemented; do not rewrite

1. Normal entry: `src/eagleeye/interfaces/web/server.py` selects
   `app496`, built on 495 and the original 492 chain. Installed identity remains
   490.0 until the installer and runtime are updated as a release unit.
2. `personosint493.py` (application+web): bounded JSON export import into
   existing `research_leads_483` with source URL canonicalization, CSRF,
   case grants, hash checking and provenance audit.
3. `personosint494.py` (application+web): review-only entity queue in the
   canonical case DB, with supported type translation, case scoping,
   persistent hashes and human decision notes.
4. `personosint495.py`: single case-scoped, no-automatic-fetch person and
   company source workbench with links to capture, graph and reports.
5. Existing `research483` links can pre-fill `intel492` WARC capture
   forms, after which explicit network consent is still required.
6. Startup fix for work directory and current Windows helper scripts.
7. Tests: `tests/test_build493_personosint.py`,
   `tests/test_build494_personosint.py`,
   `tests/test_build495_person_workbench.py`, current server/launcher tests.
8. Build 496: case-scoped investigation plan with strict step kinds, RBAC,
   tamper hashes, audit, human review and manual outcome notes. Plan approval
   does NOT authorize live source access. Endpoint:
   `/workbench/plan496`. Tests: `tests/test_build496_plan.py`.
9. GitHub Actions source bundle workflow:
   `.github/workflows/build495-claude-handoff.yml`.

## Next milestones after 496

- **497:** controlled provider execution using already-approved search intent
  and query IDs (existing ProviderCollection120), queue, retries, audit and
  replay tests. No live action merely because a plan was approved.
- **498:** AI proposals with strict schemas, read-only retrieval and
  human-approved tool dispatch. No unsupervised outbound requests.
- **499:** recoverable candidate/graph/evidence transfer, OPSEC, backup/restore,
  WARC provenance and sensible retention.
- **500:** installable Windows internal release after full real runtime checks.

## First jobs for Claude Code

1. Verify the active Windows/Ubuntu CI and amend only current issues.
2. Decide how to safely insert the best PersonOSINT source connectors into
   the existing approved live-acquisition framework; every outgoing request
   must obey case approval, URL/redirect restrictions, OPSEC and provenance.
3. Build a reviewed, idempotent transfer from accepted PersonOSINT entity
   candidates to the canonical `EntityRegistry461`; do not write to two
   SQLite databases without a recoverable transaction protocol.
4. Reuse PersonOSINT strengths in mandate risk assessment, lifecycle/retention,
   monitoring and professional dossier templates through EagleEye services.
5. Validate backup/restore for both canonical case DB and entity registry,
   original files and WARC snapshots. Test invalid/legacy workspace detection.
6. Prepare a **new** versioned Windows installer, release script and ZIP
   only when runtime/installer version is consistent and acceptance is green.

## Explicit non-goals
No unapproved tracking of private individuals, no automated claims of
identity, no illicit access, no silently importing protected PersonalOSINT
photos/telephone/email identifiers or carrying over someone else's permissions.

## Commands

```sh
git switch integration/build493-unified-personosint
python -m pip install -e '.[test]'
python -m pytest -q tests/test_build496_plan.py tests/test_build495_person_workbench.py tests/test_build490_server_selection.py
```

Keep historical accepted Builds 398 and 478 untouched.
