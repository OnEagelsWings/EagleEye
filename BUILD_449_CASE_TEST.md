# Build 449 Case Test

## Objective

Qualify the formal team-review chain without changing the analytical meaning of Build-447 objects.

## Deterministic scenario

1. Create a case with one system administrator/investigator and one independent case reviewer.
2. Seed governed synthetic/public acquisition through the existing Build-446 selftest path.
3. Synchronize unreviewed Build-447 Evidence.
4. Request Evidence review and assign it to the independent reviewer.
5. Verify that the requester cannot claim the task.
6. Reviewer claims the task and accepts the Evidence with documented rationale.
7. Investigator creates a Claim from accepted Evidence.
8. Request Claim review; reviewer claims and accepts it for dossier use.
9. Investigator creates a Living Dossier revision.
10. Request Dossier review; reviewer approves it for export.
11. Investigator requests Dossier export approval.
12. Reviewer approves the export.
13. Authorized executor, different from the approving reviewer, executes the export.
14. Verify JSON, DOCX, PDF and ZIP package creation and package hash.
15. Verify Build-449 review-record integrity.

## Negative tests

- same requester attempts to claim own review → denied;
- object creator is assigned as Claim/Dossier reviewer → denied;
- object changes after review request → request becomes stale;
- unassigned/assigned reviewer restrictions remain case-scoped;
- direct Build-447 review/export mutation routes are absent from the current Build-449 app;
- review comments preserve challenge and counter-hypothesis as discussion, not facts.

## Expected result

PASS only when the review chain is case-scoped, independently reviewed, stale-safe, auditable, and does not create automatic truth determination.
