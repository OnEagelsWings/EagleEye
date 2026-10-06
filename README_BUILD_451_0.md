# Build 451 — Retrieval isolation and content-risk gates

Build 451 preserves the Build-450 governed investigation workflow and adds a
separate retrieval process, strict IPC, executable/archive withholding and a
local ClamAV scanner adapter. The conservative content-risk gate recognizes
PE/ELF/Mach-O (32/64-bit and universal, both byte orders) and the documented
common archive MIME/signature variants; it is not a universal executable or
malware detector. Rejected bytes never enter content observations;
hash, reason and scan metadata remain in the failed acquisition event.

## Operating profiles

The default `process` profile runs on Linux and Windows. It separates process
state and environment; it does **not** isolate the host filesystem or network
at OS level. Configure `EAGLEEYE_CLAMD_SOCKET` to add the scanner gate on Linux.

For the guarded kernel profile, configure the trusted launcher environment:

```sh
export EAGLEEYE_RETRIEVAL_PROFILE=contained
export EAGLEEYE_CLAMD_SOCKET=/path/to/local/clamd.sock
./START_EAGLEEYE_PRO.sh
```

`contained` requires Linux x86-64, Landlock ABI >=3 and seccomp support. Before
opening a source socket, an offline disposable child must prove file reads,
file writes, new sockets and new processes are refused. No fallback occurs.
The parent validates the public pinned IP and opens one TCP connection. The
child receives only that socket, loads TLS trust before confinement, then
applies a filesystem ruleset with no allow rules and a syscall filter rejecting
new network/process/control and io_uring operations. HTTP(S) runs on the existing
socket with hostname TLS validation; redirects remain governed by the parent.
One monotonic deadline covers the kernel probe, all public-IP connection
attempts and the worker; exhaustion stops further contact/startup and closes the
connection. CPU, address-space and core-dump limits apply to this child. The filter is
specific to x86-64; unsupported platforms are refused.

This is a bounded worker profile, not a general-purpose sandbox or independent
security certification. No firewall, service or host policy is installed by the
application. Native Windows kernel containment is not qualified in Build 451.

## Scanner gate

Use a trusted local ClamAV daemon with a private Unix socket, current official
signature databases, UTC daemon timezone, and INSTREAM support. The adapter
requires a parseable engine/database version and signatures no older than 48
hours. It sends at most 2 MB in bounded chunks without writing payload files.
One monotonic scanner deadline covers connection, VERSION, INSTREAM chunks and
verdict reads; partial replies cannot renew the timeout. Only the exact
`stream: OK` verdict permits intake. Detection, stale signatures,
unavailable scanner, malformed responses and limits all withhold the content.
The contained profile requires a configured scanner. A clean verdict cannot
establish that every threat is absent.

Authenticated status is available at `/api/build451/status`. An administrator
can POST `/api/build451/diagnose` from the same origin to run offline kernel and
benign/EICAR scanner fixtures; results enter the audit log. Diagnostics grant no
source GO, release approval or real-case qualification.

## Acceptance

CI covers the retained research workflow, Linux/Windows process boundary,
installed wheel, actual Linux kernel denials plus HTTP on an inherited socket,
and a real ClamAV clean/EICAR gate with current official signatures. Local
container restrictions may make kernel/real-scanner tests unavailable; those
are reported separately and are mandatory in their respective CI jobs.

Operational qualification remains HOLD until the intended host/profile passes
its diagnostics and an authorized real-source case completes the research
chain. Production readiness remains false. Every fifth build, next **455**, must
separately demonstrate the complete case-to-reviewed-export workflow, including
restart and reference checks; engineering checks cannot substitute for that gate.
