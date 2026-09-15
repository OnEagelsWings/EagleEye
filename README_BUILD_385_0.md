# EagleEye Build 385.0 – Acquisition Orchestration

Build 385 ist der erste Phase-17-Build, der die Research-Planning-Schicht direkt mit den bestehenden governed Phase-16-Datenpfaden verbindet.

## Neu
- Source Capability Matrix für Phase-17-Registry-Sources.
- Abbildung auf vorhandene Corporate-, Public-Money- und Reference-Connectoren.
- Connector-native Identifier-Validierung bereits beim Packet-Compile.
- Persistente Acquisition Packets mit Identifier-Hashes im Packet-Fingerprint.
- Explizite, RBAC-geschützte `PREPARE ACQUISITION`-Stufe.
- Erstellung kanonischer Phase-15-Sources ausschließlich als `pending_review` oder plan-only.
- Execution-Readiness zeigt verbleibende Review-/Workflow-Blocker transparent an.

## Bewusste Grenze
Build 385 startet **keine** externe Recherche. Es entstehen keine Netzwerkrequests und keine Crawl-Jobs. Source Approval, Workflow-Budget, OPSEC und LIVE/CRAWL bleiben getrennte nachgelagerte Gates.

## Qualification
- Build-385 Tests: 14/14 PASS.
- Acceptance: 18/18 PASS.
- Benchmark: 1,200/1,200 Acquisition Packets, 0 violations.
- Phase-17 regression: 120/122; 2 expected Build-384 release-boundary assertions; 0 functional regressions.
- Historical Builds 360–380: 792/822; 30 known release-boundary assertions; 0 functional regressions.
- Production release ready: false.
