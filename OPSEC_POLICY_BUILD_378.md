# OPSEC Policy — Build 378

Build 378 binds voice-triggered crawler jobs to a canonical voice intent ID, preview hash and exact `VOICE CRAWL` confirmation marker. OPSEC detects missing/mismatched intent provenance, direct-network-authority claims, automatic scope-expansion claims and attempts to use the standard voice path for Tor jobs.

Queued affected-case jobs may be cancelled. Running system/network policy is not mutated. Firewall, OS, Tor configuration, credentials and ACLs remain outside Build-378 mutation authority.
