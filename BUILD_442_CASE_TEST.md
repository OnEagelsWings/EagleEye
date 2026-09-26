# Build 442 case-specific qualification

Use a dedicated synthetic/demo case.

## Deterministic qualification

\`\`\`
POST /api/build442/cases/{case_id}/retrieval/selftest
\`\`\`

This opens no external sockets. It verifies:

1. a Build-425 public task enters the Build-442 hardening path;
2. robots.txt is checked through the Build-441 boundary;
3. an initial HTTP 503 is classified as transient;
4. bounded retry occurs;
5. exponential backoff is recorded;
6. the second target attempt succeeds;
7. DNS public-IP pinning is recorded;
8. result provenance still flows through Build 425 -> 422/423;
9. Build-442 telemetry and hardening records pass integrity verification.

Automated tests additionally verify DNS-rebind blocking, source rate limiting, non-retry of TLS certificate failures, authorization boundaries and current launcher/version contracts.

## Optional real external validation

This is deliberately separate from deterministic CI.

Create a reviewed public source/task, then call:

\`\`\`
POST /api/build442/cases/{case_id}/tasks/{task_id}/external-validation
\`\`\`

with:

\`\`\`json
{"confirmation":"VALIDATE442_EXTERNAL"}
\`\`\`

Do not use synthetic fixture sources, authenticated targets, private services, internal IPs or sensitive data. One successful validation is evidence for that exact task/path only; it is not a production certification.
