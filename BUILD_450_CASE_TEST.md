# Build 450 Case Qualification

## Preconditions

Use a dedicated qualification case, a system administrator as checkpoint executor, and a different active case reviewer with `source.review`, `dossier.review`, and `dossier.export.approve`.

## End-to-end qualification

Run the deterministic Build-446 surface/news/social dispatch selftest; synchronize Build-447 Evidence; request and complete independent Evidence review; create a bounded synthetic Claim; independently review the Claim; create and independently approve a Living Dossier; request and independently approve export; execute the export with a different authorized executor; verify JSON, DOCX, PDF, manifest and ZIP package/hash bindings; verify Build-447 and Build-449 integrity; then re-run component integrity.

## Fail-closed conditions

Same reviewer/executor identity where separation is required, missing reviewer capabilities, changed object after review request, invalid component integrity, forbidden automatic authority flags, exposed current-app review/export bypass, or package/export hash mismatch must hold the checkpoint.

## Result semantics

`engineering_result=pass` means the deterministic governed workflow qualified. `external_validation_result=hold` means external non-fixture acquisition is not fully demonstrated. `release_result=hold` means production/general release is not granted.
