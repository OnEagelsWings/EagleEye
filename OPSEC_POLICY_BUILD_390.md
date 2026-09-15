# OPSEC Policy — Build 390.0

The Build-390 review engine is local and network-silent. It consumes already-normalized Build-389 candidates and provenance metadata only. It cannot fetch remote resources, issue GO grants, enqueue jobs, mutate host security, credentials, firewall, Tor or ACL state, or bypass source review. Candidate integrity failure blocks trustworthy corroboration counting and finalization.
