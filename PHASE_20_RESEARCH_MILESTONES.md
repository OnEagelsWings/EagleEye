# Research usability gates: 450, 455, 460, 465 and every fifth build

User requirement, 2026-10-05: every fifth build must be usable for a complete
research assignment. A version number or deterministic checkpoint PASS alone
does not satisfy this requirement.

## Required operational acceptance

Each milestone must provide a runnable version and repeat a real-source case:
case creation → explicit scope/GO → permitted acquisition → source provenance
and stored raw objects → Evidence/Claims → source-supported hypothesis and
counterevidence → independent review → dossier in the case → authorized DOCX
and case-package export. Reopen the case after restart and verify references.

Record exact commit, environment, source availability, model configuration,
timestamps, failures, remaining questions and exported file hashes. Validate
UI navigation and download, case separation, revocation, budgets and the
negative acquisition-chain regression. Any required step that is unavailable,
mocked, skipped or untested keeps research usability on HOLD. Preserve a known
usable milestone while intermediate builds are being developed.

Engineering tests, real-source research usability, independent external
validation and production readiness remain separate decisions. Build 450 has
engineering PASS; real-source operational acceptance must still be evidenced.
No existing production gate is silently waived.

## Current implementation sequence

The revised Phase-20 plan starts 451–455 with operations and isolation; 456–460
cover security qualification, investigation benchmark and serious beta.

- 451 begins with retrieval worker separation and pre-intake content quarantine.
- 452–454 complete deployment, recovery and operational integration according
  to the operations plan, retaining the working research chain.
- 455 qualifies the entire operational research workflow, not only new modules.
- 460 repeats the workflow alongside the serious-beta acceptance gates.
- 465 and later five-build milestones repeat the same operational acceptance.

## Build 451 foundation delivered in this branch

The hardened live/external/authorized-loop surface paths now use a disposable
Python process per GET. Only a bounded request crosses IPC; user environment,
session tokens, case IDs and DB paths are not passed. Existing parent-side GO,
robots, task scope, rate limit and pinned-DNS contracts are retained. The child
revalidates public IPs, GET, header restrictions and budgets. Executable/archive
signatures and corresponding MIME types are rejected before acquisition intake.
Quarantine metadata (hash, size, MIME, reason) is persisted on the existing
failed acquisition event and survives restart; rejected payload bytes are not
promoted to the content store.

This is process separation, not a container/OS filesystem or network sandbox.
It has no qualified malware scanner or raw-payload quarantine vault. Direct
Build-441, hardened Build-442, news Build-443 and social Build-444 live paths
now choose the process transport. Windows inherits only SystemRoot for native
runtime initialization; no proxy settings, user paths or secrets are inherited.
The built wheel's worker has an offline startup probe. Linux/Windows CI tests
the installed wheel outside the checkout and tests the process boundary.
The milestone remains on HOLD until the chosen operating profile and a real-
source research case are qualified. No model training was performed: the new
negative tests contribute security evaluation cases, not trained model weights.
