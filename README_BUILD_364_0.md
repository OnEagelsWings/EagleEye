# EagleEye PersonOSINT Pro – Build 364.0

Build 364 adds the Phase-16 Remote Multi-User Team profile while preserving local-first operation as the default.

Remote mode is explicit and fail-closed. It requires a concrete bind IP, TLS certificate/key, Host allowlist and client CIDR allowlist. Wildcard binds and untrusted forwarding headers are blocked. Bootstrap must be completed locally before remote mode is enabled.

A real loopback HTTPS validation was executed with two independent authenticated clients and a live cross-case access denial. This proves the direct-TLS multi-client transport on loopback, but is **not** external remote deployment validation.

Production release remains false pending real remote deployment validation, external load/failure testing and professional pilot evidence.
