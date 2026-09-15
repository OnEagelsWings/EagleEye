# Release Notes – Build 385.0

## Acquisition Orchestration v2
Build 385 links Phase-17 Research Waves to the existing Phase-16 connector stack via a persistent Source Capability Matrix and Acquisition Packets.

## Important improvements
1. Exact connector mappings for GLEIF, SEC EDGAR, USAspending, TED Search, Federal Register and Internet Archive metadata.
2. Input validation uses the existing connector SDK before source preparation.
3. Acquisition Packets bind hashed identifiers into their immutable fingerprint; a benchmark-detected hash-collision/persistence bug was fixed before qualification.
4. `PREPARE ACQUISITION` can create canonical pending-review sources but cannot approve or execute them.
5. Execution Readiness surfaces Phase-15 review and workflow blockers without granting execution authority.

## Qualification
Build acceptance ready: **true**. General production release: **false**. No external connector validation status is promoted by this build.
