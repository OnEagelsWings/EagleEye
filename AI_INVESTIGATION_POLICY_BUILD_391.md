# AI Investigation Policy — Build 391.0

Build 391 introduces the Phase-17 AI Investigation Synthesis Layer.

The AI investigator may organize finalized Build-390 corroboration reviews into **candidate claims**, preserve supporting and contradicting observations, expose open questions, and create **hypothesis proposals** for human review. These objects are analytical work products, not verified facts.

The epistemic contract is explicit:

- Build-389 candidate = normalized observation requiring review.
- Build-390 corroboration = structure of independent source support/contradiction, not truth probability.
- Build-391 claim = reviewable proposition derived from a finalized corroboration review, not a verified fact.
- Build-391 hypothesis = explanatory/testable proposition, always `hypothesis_not_fact`.

Build 391 must not:

- infer truth from source-counts;
- calculate truth probability;
- call the legacy Investigation Kernel numeric `prior/confidence` hypothesis path;
- automatically promote evidence;
- automatically accept claims;
- automatically merge identities;
- create external research execution authority;
- perform network requests.

Reviewed claims and hypotheses may be mirrored into the Investigation Kernel **notebook/event stream only** after explicit admission. This creates a visible investigation work object without invoking the legacy probability model.
