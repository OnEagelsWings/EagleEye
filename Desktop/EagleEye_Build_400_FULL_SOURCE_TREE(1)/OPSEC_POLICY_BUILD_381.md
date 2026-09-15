# Defensive OPSEC Policy — Build 381

Build 381 preserves the Phase-16 defensive boundary. The Control Plane consumes OPSEC state read-only and must hold planning when the case OPSEC circuit is open. It cannot modify firewall, OS, Tor, credentials, ACLs or external systems. Source metadata cannot contain embedded credentials or secrets. No source registration action performs network I/O.
