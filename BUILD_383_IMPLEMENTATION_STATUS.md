# Build 383.0 – Source Planner v1

Status: **qualified Phase-17 overlay**.

Implemented:
- transparent mission taxonomy with German/English planning cues;
- advisory inferred source classes with mandatory `CONFIRM SELECTORS` before case-scope mutation;
- explicit source selectors remain supported without weakening GO/execution boundaries;
- acquisition templates for corporate, procurement, public-money, regulatory, government, legal, archive, reference and sanctions source classes;
- deterministic source ranking by source class, jurisdiction, entity overlap, acquisition path and validation state;
- explicit `registry_gap`, `jurisdiction_gap`, `entity_type_gap`, `validation_gap`, `access_path_gap`, `selector_gap` and `selector_review_required` findings;
- persistent acquisition-plan, step and gap ledgers layered on Build 382;
- no automatic source approval, connector execution, identity merge or network/system mutation.

Qualification:
- complete overlay regression: **85/85 tests PASS**;
- Build-383 acceptance: **13/13 PASS**;
- deterministic planner benchmark: **4000/4000 PASS, 0 violations**;
- network used: **false**;
- system mutations: **0**;
- compileall/AST audit: **PASS**.

Truthful boundary: this remains an overlay because the complete Build-380 application source tree is not present in the working set. No external connector validation or production-release claim is made.
