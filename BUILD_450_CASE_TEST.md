# Build 450 Case Qualification

## Preconditions

Build 450 must create/use an **isolated synthetic qualification case**. A normal operational investigation case is not accepted.

Two independent active sessions are required:

1. system-administrator/executor session;
2. separate reviewer session.

The reviewer must have case-scoped `source.review`, `dossier.review`, and `dossier.export.approve` capabilities.

## End-to-end qualification

1. Create the isolated Build-450 qualification case and marker.
2. Assign the separately authenticated reviewer to that qualification case.
3. Verify all required component integrity before mutation.
4. Verify the authority contract.
5. Run deterministic Build-446 acquisition/dispatch selftest.
6. Synchronize Build-447 Evidence.
7. Request and complete independent Evidence review.
8. Create a bounded synthetic Claim.
9. Independently review the Claim.
10. Create a Living Dossier.
11. Independently approve the Dossier.
12. Request separate export approval.
13. Independently approve export.
14. Execute export with an authorized executor different from the approving reviewer.
15. Verify JSON, DOCX, PDF, manifest and ZIP package/hash bindings.
16. Re-run component integrity.
17. Store the Build-450 qualification record.

## Fail-closed conditions

The checkpoint must abort or HOLD when any of the following occurs:

- ordinary/unmarked investigation case;
- missing or revoked admin/reviewer session;
- same admin/reviewer identity;
- wrong reviewer for the qualification case;
- missing reviewer capabilities;
- invalid component integrity before mutation;
- forbidden automatic-authority flag;
- stale review object;
- exposed current-app review/export bypass;
- package/export hash mismatch;
- qualification-record or qualification-case-marker tamper.

## UI boundary

The operational Build-450 workspace shows read-only checkpoint status. It does not expose a browser action that can inject synthetic qualification data into the selected investigation case.

## Result semantics

`engineering_result=pass` means the isolated deterministic governed workflow qualified.

`external_validation_result=hold` means external non-fixture acquisition is not fully demonstrated.

`release_result=hold` means production/general release is not granted.
