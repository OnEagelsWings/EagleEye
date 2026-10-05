# Build 451 — OPSEC / Retrieval Isolation

Status: implementation in progress, PR #39; released version remains Build 450.

## Changes in this iteration

- All Phase-20 public surface/news/social live entrypoints select the separated
  retrieval worker; Build-439/446 authorized dispatch keeps its existing GO.
- IPC accepts only the defined request fields and bounded public headers;
  unexpected case/session fields, credential headers and header injection fail
  before network contact. Worker response shape, HTTP status, timing, URL,
  headers, base64 and byte budgets are validated before intake.
- Executable/archive content is withheld. Its hash, length, MIME and reason
  enter the existing failed acquisition event. No rejected raw bytes enter
  content observations; failure and quarantine metadata survive restart.
- Worker startup uses an empty user environment, a temporary directory and
  isolated Python mode. Windows passes only SystemRoot for OS initialization.
- Linux/Windows CI now builds a wheel and probes the installed worker outside
  the checkout, in addition to the acquisition/UI/repository regressions.
- The Build-445 checkpoint and test distinguish implemented process separation
  from unqualified OS sandbox and malware scanning; those gaps remain visible.

## Current-head Codex findings and regression fixes

Review of `0a248865ea` found two valid issues after all three CI workflows passed:
P1 archive signatures were incomplete; P2 worker exceptions lost retry categories.
The fixes recognize gzip, tar (offset-based POSIX and checksummed legacy headers),
bzip2, xz, zstd and further common archive MIME/signature variants before intake.
Integration tests prove mislabeled gzip/tar payloads produce failed acquisition,
persist quarantine metadata after restart and create no content observations.

The worker now returns only bounded fixed error categories. Transient timeout,
connection and OS failures retain Build-442 bounded retries; TLS certificate,
request, protocol and unknown errors do not retry. No exception text, source
payload or credentials are emitted in the error protocol. Tests cover recovery,
budget exhaustion and permanent-failure refusal.

## Validation and remaining acceptance

Local worker tests and Linux wheel startup passed. The current iteration's
exact results are recorded in PR #39 after the regression completes; GitHub
checks on the new commit are required before any merge decision.

The tests use offline startup, deterministic replay and bounded mocked IPC;
they do not establish external source validation or real-world research quality.
Windows execution is only evidenced when its new CI job passes. OS filesystem/
network containment and malware scanner qualification are not implemented by
this process separation. No host firewall or OS configuration is changed.

Next: qualify the isolation operating profile and complete a real-source case
before finishing Build 451; then proceed with deployment/recovery/operations
through the complete research workflow gate at 455.
