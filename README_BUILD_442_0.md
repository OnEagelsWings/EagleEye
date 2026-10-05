# EagleEye Build 442.0 — Surface Retrieval Hardening & External Validation

Build 442 hardens the controlled ordinary Surface-Web executor introduced in Build 441. It does not broaden the source scope and does not add authenticated browsing.

## Hardening added

- task-scoped DNS pinning;
- repeated DNS observation with fail-closed rejection of any later private/non-public answer;
- original public IP pin retained if a public CDN answer set changes during the task;
- bounded retry for transport errors and transient HTTP statuses;
- exponential retry backoff;
- per-source task-rate window;
- minimum interval between tasks against the same source;
- source-scoped execution lock;
- one concurrent live Build-442 worker;
- fresh stateless transport object for every live execution;
- persisted per-attempt telemetry;
- explicit record of HTTP status, transport error class, transient classification, retry delay and elapsed time.

Build 441's boundaries remain authoritative: GET only, robots.txt fail-closed, exact registered host, same-host redirects, response/time budgets, TLS certificate validation, no credentials/cookies/forms/writes/JavaScript, no onion execution and no autonomous scope expansion.

## DNS rebinding

Build 442 resolves the public host at task start and pins that validated public set. Before later fetches in the same task, DNS is observed again. If a later answer contains a private, loopback, link-local or otherwise non-global address, execution fails closed before the next fetch. A changed but still-public answer is recorded while the original validated set remains pinned.

## Retry / backoff

At most three attempts are allowed for transient transport failures and HTTP:

408, 425, 429, 500, 502, 503, 504.

TLS certificate verification errors are not treated as retryable.

## Rate control

Build 442 currently limits each registered source to:

- maximum 6 task starts per rolling minute;
- minimum 1 second between task starts.

This is an EagleEye safety ceiling. Source-specific terms or server guidance can require stricter limits.

## External validation

External validation is never automatic and never runs on startup or in CI.

A reviewed non-fixture Build-425 task can be used for one real public validation run only after the exact confirmation:

\`VALIDATE442_EXTERNAL\`

The validation still uses the complete Build-441/442 safety path and does not imply production readiness.

## Worker isolation

Build 442 adds logical isolation: source-scoped locks, a single live worker and a fresh stateless transport for each live run. It does **not** claim OS-process/container isolation. Stronger process/network isolation remains scheduled for the Phase-20 OPSEC block.

## Readiness

After Build 442:

- controlled ordinary Surface-Web executor: implemented;
- retrieval hardening: implemented for the current one-page public scope;
- external-validation mechanism: implemented but opt-in;
- automatic external validation: false;
- News retrieval adapter: incomplete;
- Public-Social retrieval adapter: incomplete;
- general live collection: incomplete;
- production readiness: false.

Build 443 should implement the dedicated live News acquisition layer.
