# Defensive OPSEC Policy — Build 363

- OPSEC supervision is autonomous and defensive inside approved profiles.
- Insecure non-loopback HTTP S3/MinIO endpoints are blocked from live validation.
- Embedded endpoint/backend credentials are treated as security findings.
- Affected queued/retry/running case jobs may be cancelled defensively.
- S3 server-side encryption is mandatory for external object-store validation.
- No autonomous firewall, OS, Tor, account, credential or ACL mutation.
