# Release Notes — EagleEye Build 400.0

- Adds the Phase-17 Final End-to-End Acceptance ledger and human final review.
- Records all 19 predecessor stages plus Build 400 as a 20-build Phase-17 completion line.
- Exports a local final acceptance dossier while preserving evidence/provenance boundaries.
- Makes `phase18_entry_ready` independent of `production_release_ready`.
- Preserves `production_release_ready=false`, `broad_live_research_ready=false`, external Holdout=false, and external 72-hour Soak=false.
- Full current-tree regression rerun: 1,119/1,175 PASS, 56 historical version/health/server/launcher assertions, 0 functional regressions.
- Full static Python audit: 1,844 files, 210,555 lines, no AST errors, eval/exec, shell=True, runtime TLS bypass, or direct network imports in the new Build-400 layer.
