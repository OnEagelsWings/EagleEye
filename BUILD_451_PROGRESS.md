# Build 451 — OPSEC / Retrieval Isolation

Status: Build-451 implementation in PR #39; current runtime version 451.0.
Engineering acceptance requires current-head CI and review. Operating-host / real-source acceptance remains HOLD.

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
Windows execution is only evidenced when its new CI job passes. The earlier process-only iteration did not implement OS containment or a
scanner; the completion implementation below adds separate guarded profiles. No host firewall or OS configuration is changed.

## Completion implementation

The guarded Linux x86-64 profile now passes a single public-IP-pinned TCP socket
into the child. Landlock refuses all filesystem access; seccomp refuses new
connections, sockets, processes/control, io_uring and related bypass surfaces.
TLS trust is loaded before confinement. The profile probes real kernel denials
before source contact, applies CPU/memory/core limits, and never downgrades.

A bounded ClamAV INSTREAM adapter with engine/database freshness checks gates
intake. Detection and unavailable/stale/invalid scan results preserve failure
metadata without content observations. The contained profile requires a scanner.
Trusted successful scan hashes/profile metadata propagate into acquisition
provenance, including through news/social capture and retry wrappers.

Build service, authenticated status/admin diagnostics, app/server, both launchers,
package version and release manifest now identify 451. Diagnostics are offline,
audited, authenticated and origin guarded. CI requires actual Linux kernel
confinement and real ClamAV benign/EICAR fixtures separately from mock regressions.

The current workspace denies the Landlock syscall, so local kernel tests cannot
qualify the profile. Native Windows remains process-only. A target host and a
real-source authorized case remain necessary for operational acceptance; those
facts do not become PASS from deterministic engineering tests. Next planned
implementation: deployment/recovery/operations through research gate 455.

## Shared deadline review fix

The current-head Codex review identified a valid P2: multiple public-IP TCP
candidates each received the full timeout. The contained profile now establishes
one monotonic deadline before its kernel probe. Each connection receives only
the remaining time; the child also receives only the remaining wall-clock budget.
Exhaustion stops before another address/worker can start, and a connected socket
is closed even when the deadline expires before worker startup. Regressions cover
16 unreachable candidates, shrinking attempt budgets, successful connection with
only the worker's remaining budget, expired startup cleanup and probe exhaustion.
