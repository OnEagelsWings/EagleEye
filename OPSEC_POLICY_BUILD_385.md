# OPSEC Policy – Build 385

Build 385 erweitert keine Host-, Firewall-, Tor-, Credential- oder ACL-Mutationsrechte. Der neue Acquisition-Orchestrator ist network-silent und nutzt ausschließlich vorhandene, allowlist-basierte Phase-16-Connectorpfade.

Sicherheitsgrenzen:
- keine freie URL-Ausführung;
- keine Credential-Injection;
- keine automatische Source-Freigabe;
- keine automatische Crawl-/Connector-Ausführung;
- keine automatische Scope-Erweiterung;
- Identifier werden vor der Vorbereitung gegen vorhandene Connector-Contracts geprüft;
- Klartext-Identifier werden nicht in den neuen Phase-17-Audit-Events protokolliert;
- externe Ausführung bleibt hinter bestehenden Source-Review-, Workflow-, OPSEC- und expliziten Confirmation-Gates.
