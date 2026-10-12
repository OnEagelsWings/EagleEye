# Build 456 — Multilingual Entity Resolution + Source Lineage

Build 456 begins the post-455 integration cycle. It does **not** add a new autonomous truth engine. It makes two existing research problems explicit in the current workflow: cross-script identity candidates and source-origin independence.

## Multilingual entity resolution

Build 456 reuses the existing multilingual identity engine and the canonical Entity Resolution store. It supports review candidates across:

- Hebrew ↔ Latin;
- Arabic ↔ Latin;
- Cyrillic ↔ Latin;
- Latin name-order variants.

The workflow is deliberately review-first:

1. scan the case's Person/Organisation resolution entities;
2. generate transliteration/name-order alias candidates;
3. generate explainable cross-script pair candidates;
4. an analyst reviews alias candidates;
5. an analyst may forward a pair into the existing Build-115/371 Entity Resolution comparison;
6. the existing human-governed resolution workflow remains responsible for any same-entity decision.

Similarity values are prioritization scores, not identity probabilities. Build 456 never performs an automatic merge.

## Canonical source lineage

Each Build-447 Evidence item can now be mapped to a conservative source lineage:

- source family;
- independence group;
- origin key;
- source role;
- countable/non-countable status.

The default inference uses an explicit publisher when available, otherwise the canonical host and finally the registered source ID. Archive/mirror evidence is non-countable by default. An analyst can override lineage only through an explicit reviewed record bound to the current Evidence hash.

Claim lineage reports distinguish:

- raw mentions;
- unique payloads;
- source families;
- independent origins;
- duplicates/non-countable observations.

Thus EagleEye can display results such as **"20 mentions / 3 independent origins"** instead of treating 20 republications as 20 corroborating sources. Exact duplicate payloads never add corroboration.

Source independence is not a truth probability and does not automatically accept a Claim.

## Test cadence

456 is a focused development build. It runs only Build-456 regressions, current import/compile/UI smoke, and isolated Linux/Windows installation. The next complete repository/real-case hard checkpoint remains Build 460.

## Next build

Build 457: Document Intelligence 2.0 with page/paragraph/table/footnote Evidence anchors and canonical document provenance.
