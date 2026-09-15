from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row_hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _seed_boundaries(db: Any) -> None:
    rows = [
        {
            "component_key": "lead_investigator",
            "display_name": "Leitender Ermittler",
            "may": ["Auftrag und Zweck festlegen", "Rechts- und Quellenprofil bestimmen", "Freigaben, Review und Release entscheiden"],
            "may_not": ["Freigabepflichten durch Sprache oder UI umgehen"],
            "confirmation": ["externe Suche", "Export", "Merge", "Löschung", "Release"],
            "external_action_policy": "human_authority",
            "network_mutation_policy": "not_applicable",
        },
        {
            "component_key": "voice_gateway",
            "display_name": "Voice & Command Gateway",
            "may": ["lokal Push-to-talk transkribieren", "Intent vorschlagen", "Transkript sichtbar und editierbar machen"],
            "may_not": ["Always-on-Mikrofon betreiben", "Audio verdeckt in eine Cloud übertragen", "Sprachbiometrie als alleinige Authentisierung nutzen", "bestätigungspflichtige externe Aktionen selbst freigeben"],
            "confirmation": ["externe Suche", "Export", "Merge", "Löschung", "Release"],
            "external_action_policy": "confirm_before_external_action",
            "network_mutation_policy": "forbidden",
        },
        {
            "component_key": "ai_investigator",
            "display_name": "KI-Ermittlung",
            "may": ["Fälle strukturieren", "genehmigte Aufgaben delegieren", "Evidenz fusionieren", "Widersprüche und offene Fragen markieren", "Dossierentwürfe erstellen"],
            "may_not": ["Identität autonom bestätigen", "Anschuldigungen als Fakten setzen", "externe Kontakte autonom durchführen", "direkten Shell-, Browser- oder Datenbankzugriff erhalten"],
            "confirmation": ["Research-Wave mit externer Ausführung", "Release-relevante Aktion"],
            "external_action_policy": "delegate_through_controlled_gateways_only",
            "network_mutation_policy": "forbidden",
        },
        {
            "component_key": "image_intelligence",
            "display_name": "Image Intelligence Agent",
            "may": ["Metadaten extrahieren", "OCR durchführen", "Bildähnlichkeit berechnen", "visuelle Ortsindizien und Manipulationssignale als getrennte Evidenzklassen liefern"],
            "may_not": ["Gesichtserkennung autonom als Identitätsbestätigung verwenden", "visuelle Stadtvermutung als GPS-Fakt ausgeben", "aktive Bildinhalte außerhalb isolierter Verarbeitung ausführen"],
            "confirmation": ["externer Reverse-Image-Dienst", "Merge aufgrund eines Bildtreffers"],
            "external_action_policy": "subagent_no_direct_egress",
            "network_mutation_policy": "forbidden",
        },
        {
            "component_key": "crawler_data_worker",
            "display_name": "Crawler- und Daten-Worker",
            "may": ["genehmigte öffentliche oder lizenzierte Quellen abrufen", "Parser ausführen", "Daten normalisieren", "Provenienz zurückliefern"],
            "may_not": ["Zugriffskontrollen umgehen", "nicht genehmigte private Daten beschaffen", "direkt in den Kern-Datenbestand schreiben", "Quellen außerhalb der Allowlist aufrufen"],
            "confirmation": ["neue Quelle oder neue Nutzungsart"],
            "external_action_policy": "isolated_worker_allowlist_only",
            "network_mutation_policy": "forbidden",
        },
        {
            "component_key": "opsec_gate",
            "display_name": "OPSEC Intelligence Gate",
            "may": ["jede externe Aktion vorab prüfen", "Leakage-Risiken bewerten", "Anfragen erlauben, blockieren oder an menschliches Review eskalieren", "Security Evidence speichern"],
            "may_not": ["Firewall autonom verändern", "Proxy autonom verändern", "Tor autonom verändern", "Betriebssystem autonom verändern", "Zugangsdaten oder Accounts autonom verändern"],
            "confirmation": ["Policy-Änderung", "jede System- oder Netzwerkrekonfiguration"],
            "external_action_policy": "independent_preflight_required",
            "network_mutation_policy": "forbidden",
        },
    ]
    for row in rows:
        payload = {
            "component_key": row["component_key"],
            "display_name": row["display_name"],
            "may": row["may"],
            "may_not": row["may_not"],
            "confirmation": row["confirmation"],
            "external_action_policy": row["external_action_policy"],
            "network_mutation_policy": row["network_mutation_policy"],
            "contract_version": "15.0/341",
        }
        db.execute(
            """INSERT OR REPLACE INTO phase15_agent_boundaries_341
            (component_key,display_name,may_json,may_not_json,confirmation_required_json,
             external_action_policy,network_mutation_policy,contract_version,updated_at,record_hash)
             VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                row["component_key"], row["display_name"], _canon(row["may"]), _canon(row["may_not"]),
                _canon(row["confirmation"]), row["external_action_policy"], row["network_mutation_policy"],
                "15.0/341", _now(), _row_hash(payload),
            ),
        )


def _seed_threats(db: Any) -> None:
    rows = [
        ("T341-01", "release_integrity", "Interner Selftest wird als Produktionsfreigabe dargestellt", "Fünfdimensionale Capability-Nachweise; historische Selfclaims sind nicht autoritativ", "AST-Gate-Test + Evidence Registry", 341, "implemented"),
        ("T341-02", "agent_isolation", "Modell erhält direkten Shell-, Browser- oder DB-Zugriff", "versionierter Agent Task/Result Contract und Tool-Gateways", "Architektur-/Integrationstest", 343, "specified"),
        ("T341-03", "search_isolation", "Zustand, Cookies, Secrets oder Schlüssel leaken zwischen Suchen", "Search Session Capsule pro search_run_id", "1000 Session-Switch-Isolationstest", 345, "planned"),
        ("T341-04", "network_privacy", "DNS/WebRTC/Cookie/Cache/Referer-Leakage", "OPSEC Preflight und isolierter Netzwerk-/Browserzustand", "Leakage-Benchmark", 346, "planned"),
        ("T341-05", "network_attack", "Redirect-, SSRF- oder DNS-Rebinding-Angriff", "Egress-Allowlist, URL-/DNS-Revalidation, Redirect-Budget", "adversarieller Netzwerk-Test", 346, "planned"),
        ("T341-06", "secrets", "Secret, Token oder Fallidentifier verlässt den genehmigten Kontext", "fallbezogene Secrets, Redaction, Secret-Scanning", "Canary-Secret-Test", 346, "planned"),
        ("T341-07", "content_safety", "Prompt Injection oder aktiver Inhalt beeinflusst Kernagent/Host", "isolierte Worker, Content-Tainting und Daten-/Instruktions-Trennung", "adversarieller Dokument-/Web-Test", 349, "planned"),
        ("T341-08", "identity", "Namens-, Dokument- oder Bildtreffer wird automatisch zur Identität hochgestuft", "Human Merge Gate und epistemische Statusklassen", "False-Merge-Benchmark", 356, "planned"),
        ("T341-09", "image_epistemics", "visuelle Ortsvermutung wird als GPS-Fakt ausgegeben", "Metadaten/Fakten/Ableitungen/Indizien/Hypothesen strikt trennen", "Geolocation-Kalibrierungstest", 355, "planned"),
        ("T341-10", "voice", "Fehltranskription löst externe oder irreversible Aktion aus", "sichtbares editierbares Transkript und Bestätigungsgate", "Voice-Command-Adversarial-Test", 358, "planned"),
        ("T341-11", "authorization", "Route oder Job umgeht Team-RBAC/Case-ACL", "zentrale Autorisierung vor Use-Case-Ausführung", "Route-/Job-Autorisierungsmatrix", 359, "planned"),
        ("T341-12", "external_validation", "Interne Freigabe ersetzt unabhängigen Security-Nachweis", "Produktionsfreigabe erfordert unabhängige externe Validierung", "Pentest/Red-Team-Artefakt", 360, "specified"),
    ]
    for threat_id, domain, threat, control, verification, target_build, status in rows:
        payload = [threat_id, domain, threat, control, verification, target_build, status]
        db.execute(
            """INSERT OR REPLACE INTO phase15_threat_model_341
            (threat_id,domain,threat,required_control,verification_method,target_build,current_status,updated_at,record_hash)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (threat_id, domain, threat, control, verification, target_build, status, _now(), _row_hash(payload)),
        )


def _seed_test_matrix(db: Any) -> None:
    rows = [
        ("M341-01", "capability_truth", "Jede Capability führt implemented/integrated/tested/benchmarked/externally_validated separat", "automated_behavioral", 341, "automated"),
        ("M341-02", "release_integrity", "Aktiver Phase-15-Releasegate enthält keine Literal-True-Selbstattestation", "ast_scan", 341, "automated"),
        ("M341-03", "release_integrity", "Interne Tests allein können production_release_ready nicht erreichen", "behavioral_negative", 341, "automated"),
        ("M341-04", "agent_contract", "Phase-15-Agentengrenzen sind maschinenlesbar und OPSEC darf keine Netzwerk-/OS-Konfiguration autonom ändern", "contract_test", 341, "automated"),
        ("M342-01", "packaging", "Version, Launcher, Wheel/ZIP und SBOM sind kanonisch und reproduzierbar", "ci_reproducibility", 342, "planned"),
        ("M343-01", "agent_isolation", "Modelle besitzen keinen direkten Shell-, Browser- oder DB-Zugriff", "architecture_test", 343, "planned"),
        ("M344-01", "schema", "Build-340-Migration und Rollback; frische DB <150 Tabellen, <300 Indizes, <5 MB", "migration_benchmark", 344, "planned"),
        ("M345-01", "search_isolation", "1000 Capsule-Wechsel ohne Cookie/Cache/Secret/Key-Leakage", "isolation_benchmark", 345, "planned"),
        ("M346-01", "opsec", "Jeder externe Request besitzt vor Ausführung eine persistierte OPSEC-Entscheidung", "integration_benchmark", 346, "planned"),
        ("M360-01", "external_security", "Unabhängiger Pentest/Red-Team ohne offene Critical/High Findings", "external_report", 360, "external_required"),
    ]
    for test_id, area, requirement, evidence_kind, target_build, status in rows:
        payload = [test_id, area, requirement, evidence_kind, target_build, status]
        db.execute(
            """INSERT OR REPLACE INTO phase15_test_matrix_341
            (test_id,area,requirement,evidence_kind,target_build,current_status,updated_at,record_hash)
            VALUES(?,?,?,?,?,?,?,?)""",
            (test_id, area, requirement, evidence_kind, target_build, status, _now(), _row_hash(payload)),
        )


def ensure_build341_schema(db: Any) -> None:
    # Phase 15 is deliberately independent here: Build 340 remains a frozen historical layer.
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_capability_registry_341(
      capability_key TEXT PRIMARY KEY,
      display_name TEXT NOT NULL,
      category TEXT NOT NULL,
      implemented INTEGER NOT NULL CHECK(implemented IN (0,1)),
      integrated INTEGER NOT NULL CHECK(integrated IN (0,1)),
      tested INTEGER NOT NULL CHECK(tested IN (0,1)),
      benchmarked INTEGER NOT NULL CHECK(benchmarked IN (0,1)),
      externally_validated INTEGER NOT NULL CHECK(externally_validated IN (0,1)),
      maturity TEXT NOT NULL,
      evidence_json TEXT NOT NULL,
      limitations_json TEXT NOT NULL,
      required_for_baseline INTEGER NOT NULL CHECK(required_for_baseline IN (0,1)),
      required_for_production INTEGER NOT NULL CHECK(required_for_production IN (0,1)),
      assessed_at TEXT NOT NULL,
      code_fingerprint TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_capability_assessments_341(
      assessment_id TEXT PRIMARY KEY,
      code_fingerprint TEXT NOT NULL,
      registry_json TEXT NOT NULL,
      baseline_status TEXT NOT NULL,
      production_status TEXT NOT NULL,
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_agent_boundaries_341(
      component_key TEXT PRIMARY KEY,
      display_name TEXT NOT NULL,
      may_json TEXT NOT NULL,
      may_not_json TEXT NOT NULL,
      confirmation_required_json TEXT NOT NULL,
      external_action_policy TEXT NOT NULL,
      network_mutation_policy TEXT NOT NULL,
      contract_version TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_threat_model_341(
      threat_id TEXT PRIMARY KEY,
      domain TEXT NOT NULL,
      threat TEXT NOT NULL,
      required_control TEXT NOT NULL,
      verification_method TEXT NOT NULL,
      target_build INTEGER NOT NULL,
      current_status TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_test_matrix_341(
      test_id TEXT PRIMARY KEY,
      area TEXT NOT NULL,
      requirement TEXT NOT NULL,
      evidence_kind TEXT NOT NULL,
      target_build INTEGER NOT NULL,
      current_status TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("CREATE TRIGGER IF NOT EXISTS trg_phase15_assessment341_no_update BEFORE UPDATE ON phase15_capability_assessments_341 BEGIN SELECT RAISE(ABORT,'phase15_capability_assessments_341 immutable'); END")
    db.execute("CREATE TRIGGER IF NOT EXISTS trg_phase15_assessment341_no_delete BEFORE DELETE ON phase15_capability_assessments_341 BEGIN SELECT RAISE(ABORT,'phase15_capability_assessments_341 immutable'); END")
    _seed_boundaries(db)
    _seed_threats(db)
    _seed_test_matrix(db)
