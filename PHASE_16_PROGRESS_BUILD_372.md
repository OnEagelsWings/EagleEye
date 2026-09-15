# EagleEye Phase 16 Progress – Build 372

**Phase:** 16 – Live Operations, Entity Intelligence & External Validation  
**Progress:** 12/20 builds

## Build 372 – Entity Resolution Evaluation

### Delivered
- Deterministic synthetic holdout corpus with difficult same-name, near-name, strong-identifier-conflict, ambiguous and multi-source scenarios; no real persons are used.
- False-link, false-distinct, review-positive precision, same-entity candidate recall, defer-rate, common-name and strong-conflict-escape metrics.
- Wilson 95% interval for the observed unsafe false-link rate.
- Evaluation gate does not mutate production thresholds automatically.
- Crawler source-quality calibration from source type, human review, content hashes, successful fetch state, source health and terms provenance.
- Source-quality values are evidence-quality heuristics, never identity probabilities.
- Per-lead crawler source-quality packets preserve the existing Source→Crawl→Fetch→Object provenance and remain review-only.
- AI dossier gains entity-evaluation and case-scoped source-quality context without new merge/network authority.
- OPSEC detects attempts to smuggle automatic-merge/identity-confirmation claims into entity-link jobs.
- No new Build-372 data tables; evaluation remains offline/non-persistent except for normal audit evidence.

### Crawler increment 372
- crawler/entity-resolution evaluation corpus;
- false-link calibration;
- source-quality calibration;
- source-quality annotation for crawler→entity leads;
- source quality cannot skip review or confirm identity.

### Validation boundary
- Deterministic synthetic holdout validation: performed internally.
- External real-world holdout / independently labeled operational dataset: **not_run**.
- Production release ready: **false**.
