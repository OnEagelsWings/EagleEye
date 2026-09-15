# Defensive OPSEC Policy – Build 368

- Live Build-368 execution is allowlisted only to exact Federal Register document GET and exact Internet Archive metadata GET sources.
- Every live-eligible source requires human read-only source review and the exact `LIVE` confirmation before network execution.
- Generic/free URL execution, keyword search substitution and sanctions fuzzy-name screening are blocked.
- NARA and GovInfo execution remain blocked because Build 368 does not introduce API-key/credential execution and the current NARA API storage/caching constraint is incompatible with normal Evidence-Vault persistence.
- OFAC and UN consolidated sanctions export execution remain blocked until the signed-redirect provenance path is explicitly qualified; stable source plans may not be rewritten to transient signed cloud-object URLs.
- Internet Archive access is metadata-only; archive payload/content download is blocked by Build-368 policy.
- Replay/static fixtures may exercise the canonical crawler/parser/receipt chain but can never claim external validation.
- Invalid or tampered reference jobs may be cancelled only within the affected case.
- No autonomous firewall, OS, Tor, credential, account, ACL or system-policy mutation is permitted.
