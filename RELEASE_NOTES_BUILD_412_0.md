# EagleEye Build 412.0 — Release Notes

Build 412 introduces a provenance-first Relationship Intelligence Graph over Federated Search results. Relationships are accepted only from explicitly structured provenance; names appearing together in text do not create graph edges. Unresolved endpoints are retained as review problems rather than guessed.

The build also hardens Source Registry authorization and integrity by denying inactive canonical identities and detecting missing/deleted registry rows plus orphaned Source Health ledgers.

Build 412 is a development build, not a release candidate. `production_release_ready=false` remains mandatory.
