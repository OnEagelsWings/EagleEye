# OPSEC Policy – Build 379

Build 379 keeps qualification defensive and case-scoped. The production runtime has no fault-injection API. Jobs explicitly marked as Build-379 qualification fault injections are invalid in operational cases and may be cancelled by OPSEC before inherited controls run.

Unsigned or untrusted external receipts cannot satisfy the external-validation gate. No automatic evidence deletion/eviction, firewall/OS/Tor/credential/ACL mutation or uncontrolled network expansion is permitted.
