# EagleEye Build 372.0 – Release Notes

## Entity Resolution Eval
- Added offline labeled-comparison evaluator with false-link, false-distinct, precision, recall, defer, cohort and Wilson interval metrics.
- Added a 20-scenario synthetic holdout corpus with no real-person training data.
- Strong identifier conflicts and common-name cases have dedicated safety metrics.
- Evaluation never changes production thresholds automatically.

## Crawler increment
- Added calibrated source-quality annotations for crawler→entity leads.
- Quality incorporates human source review, source class, hash evidence, fetch success, source health and terms-reference presence.
- Quality is not an identity probability and cannot confirm identity or bypass review.

## Safety
- No automatic entity merging.
- No new network authority.
- No Build-372-specific database tables.
- External real-world holdout validation remains not_run.
