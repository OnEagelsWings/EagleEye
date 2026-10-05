# Build 447 case-specific qualification

Use a dedicated synthetic/demo case.

## Deterministic qualification

```
POST /api/build447/cases/{case_id}/selftest
```

The self-test:

1. runs the Build-446 deterministic live-loop qualification;
2. synchronizes resulting 422/423/429/432 observations into Build-447 Evidence;
3. explicitly reviews one supporting and one counterevidence item;
4. creates a Claim with both support and contradiction;
5. explicitly reviews the Claim;
6. creates a Living Dossier revision bound to the Build-439 loop;
7. verifies Build-418/419 analytical context is present;
8. explicitly approves the Dossier;
9. exports JSON, DOCX, PDF, manifest and ZIP Case Package;
10. verifies no raw source payload was copied into the package;
11. verifies integrity.

No external sockets are opened.

## Human-review confirmations

- Evidence: `REVIEW EVIDENCE 447`
- Claim: `REVIEW CLAIM 447`
- Dossier: `APPROVE DOSSIER 447`
- Export: `EXPORT DOSSIER 447`

These confirmations are separate and intentionally non-interchangeable.
