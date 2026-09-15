# AI Investigation Policy – Build 385

Build 385 erlaubt dem AI-Ermittler, bestätigte Build-384-Research-Waves in konkrete **Acquisition Packets** zu übersetzen. Die KI darf dabei vorhandene, bereits governte Phase-16-Connectorpfade auswählen und Identifier gegen deren bestehende Input-Contracts validieren.

Die KI besitzt weiterhin **keine externe Ausführungsautorität**. Ein Acquisition Packet erzeugt weder Netzwerkzugriffe noch Crawler-Jobs. Die Vorbereitung eines konkreten Sources benötigt explizit `PREPARE ACQUISITION`, Case-RBAC und einen zuvor bestätigten Phase-17-Source-Scope. Das Ergebnis bleibt `pending_review` bzw. `plan_only`.

Nach der Vorbereitung bleiben Human Source Review, Case-Workflow-Budgets, OPSEC-Preflight und die bereits etablierten expliziten LIVE/CRAWL-Bestätigungen verpflichtend. Freie URL-Ausführung, Credential-Injection, automatische Scope-Erweiterung und automatisches Source-Approval bleiben verboten.
