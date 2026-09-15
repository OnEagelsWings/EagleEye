from __future__ import annotations

import hashlib
import io
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote_plus, urlsplit

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


WORKFLOW_OBJECTIVES = {
    "identity_confirmation": "Identität bestätigen",
    "employment_history": "Beruf und Arbeitgeber rekonstruieren",
    "location_verification": "Orts- und Aufenthaltsbezüge prüfen",
    "digital_profiles": "Digitale Profile zuordnen",
    "company_links": "Firmen- und Organbeziehungen untersuchen",
    "publication_history": "Publikationen und fachliche Laufbahn rekonstruieren",
    "custom": "Benutzerdefinierte Ermittlungsfrage",
}

WORKFLOW_STAGES = (
    ("basis_identity", "1. Basisidentität", "Namensvarianten, Lebensdaten und belastbare Identitätsanker prüfen."),
    ("professional", "2. Berufliche Informationen", "Beruf, Arbeitgeber, Ausbildung und zeitliche Einordnung prüfen."),
    ("registers_companies", "3. Register und Unternehmen", "Amtliche Register, Organfunktionen und Firmenbeziehungen prüfen."),
    ("publications", "4. Publikationen", "Publikationen, Autorenprofile und institutionelle Zugehörigkeiten prüfen."),
    ("digital_footprint", "5. Digitale Spuren", "Öffentliche Accounts, technische Profile und Domainbezüge prüfen."),
    ("archives_history", "6. Historische Quellen", "Frühere Webseitenstände, ältere Namens- und Organisationsbezüge prüfen."),
    ("contradictions", "7. Widerspruchsprüfung", "Gegenbelege, zeitliche Konflikte und mögliche Personenverwechslungen prüfen."),
)

WORKFLOW_STATUSES = {"active", "completed", "paused", "cancelled"}
TASK_STATUSES = {"planned", "opened", "completed", "skipped", "unresolved", "blocked"}

PHOTO_PROVIDERS: dict[str, dict[str, str]] = {
    "google_lens": {"label": "Google Lens", "url": "https://lens.google.com/"},
    "bing_visual": {"label": "Bing Visual Search", "url": "https://www.bing.com/visualsearch"},
    "tineye": {"label": "TinEye", "url": "https://tineye.com/"},
    "yandex_images": {"label": "Yandex Images", "url": "https://yandex.com/images/"},
}
PHOTO_JOB_STATUSES = {"prepared", "provider_opened", "uploaded_manually", "results_review", "completed", "cancelled"}
PHOTO_COPY_MAX_DIMENSION = 3000
PHOTO_COPY_MIN_DIMENSION = 256
PHOTO_COPY_MAX_BYTES = 8 * 1024 * 1024
IMAGE_HASH_VERSION = "ahash64+dhash64-v1"


def _safe_text(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slug(value: Any, limit: int = 80) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    return (text or "item")[:limit]


def _utc_after(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _search_url(engine: str, query: str) -> str:
    encoded = quote_plus(query)
    mapping = {
        "Google": f"https://www.google.com/search?q={encoded}",
        "Bing": f"https://www.bing.com/search?q={encoded}",
        "DuckDuckGo": f"https://duckduckgo.com/?q={encoded}",
        "Brave": f"https://search.brave.com/search?q={encoded}",
    }
    return mapping[engine]


def _hamming_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _bits_to_hex(bits: list[bool]) -> str:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    return f"{value:016x}"


def _average_hash(image: Image.Image) -> str:
    gray = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.get_flattened_data())
    average = sum(pixels) / len(pixels)
    return _bits_to_hex([value >= average for value in pixels])


def _difference_hash(image: Image.Image) -> str:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.get_flattened_data())
    bits: list[bool] = []
    for row in range(8):
        offset = row * 9
        for col in range(8):
            bits.append(pixels[offset + col] > pixels[offset + col + 1])
    return _bits_to_hex(bits)


class Build137Service:
    """Guided investigation workflows and privacy-preserving photo research.

    Build 137 never uploads an image, never claims that visually similar images
    depict the same person and never merges identities automatically. All
    externally visible actions remain explicit, case-bound and investigator-led.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        build136: Any,
        build135: Any,
        protection: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.build136 = build136
        self.build135 = build135
        self.protection = protection
        self.photo_root = self.build136.photo_root.resolve()
        Image.MAX_IMAGE_PIXELS = 100_000_000
        self.cleanup_expired_research_copies(actor="startup-cleanup-137")

    # ---------- validation and events ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM targets WHERE target_id=? AND case_id=?", (target_id, case_id))
        if not row:
            raise KeyError("Zielperson nicht gefunden oder falscher Fall")
        return row

    def _event(self, *, case_id: str, object_type: str, object_id: str, event_type: str, actor: str, details: Mapping[str, Any] | None = None) -> None:
        payload = dict(details or {})
        self.db.execute(
            "INSERT INTO build137_events(event_id,case_id,object_type,object_id,event_type,details_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (new_id("evt137"), case_id, object_type, object_id, event_type, dumps(payload), _safe_text(actor, 120), now_ts()),
        )
        self.audit.log(event_type, object_type, object_id, case_id, payload)

    def cleanup_expired_research_copies(self, *, actor: str = "local-analyst") -> dict[str, Any]:
        """Remove only expired derivative bytes when no live research job needs them.

        Database provenance rows remain in place with status ``expired_removed``.
        Originals are never touched by this routine.
        """
        now = datetime.now(timezone.utc)
        removed: list[str] = []
        failed: list[dict[str, str]] = []
        rows = self.db.all("SELECT * FROM photo_research_copies_137 WHERE status='ready' AND expires_at!=''")
        for row in rows:
            try:
                expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if expires > now:
                continue
            active = int((self.db.one(
                "SELECT COUNT(*) AS n FROM photo_research_jobs_137 WHERE copy_id=? AND status NOT IN ('completed','cancelled')",
                (row["copy_id"],),
            ) or {}).get("n") or 0)
            if active:
                continue
            try:
                candidate = (self.base_dir / str(row["storage_relpath"])).resolve()
                case_root = (self.photo_root / str(row["case_id"])).resolve()
                if case_root.parent != self.photo_root or case_root not in candidate.parents:
                    raise PermissionError("Ungültiger Recherchekopiepfad")
                if candidate.exists():
                    if candidate.is_symlink() or not candidate.is_file():
                        raise PermissionError("Recherchekopie ist keine reguläre Datei")
                    candidate.unlink()
                self.db.execute("UPDATE photo_research_copies_137 SET status='expired_removed' WHERE copy_id=?", (row["copy_id"],))
                removed.append(str(row["copy_id"]))
            except Exception as exc:
                failed.append({"copy_id": str(row["copy_id"]), "error": _safe_text(exc, 500)})
        if removed or failed:
            self.audit.log("cleanup", "photo_research_copy_137", "expired", None, {"removed": removed, "failed": failed, "actor": actor})
        return {"removed": removed, "failed": failed}

    # ---------- guided investigation workflow ----------
    def _anchors(self, case_id: str, target_id: str) -> dict[str, Any]:
        target = self._target(case_id, target_id)
        anchors: dict[str, Any] = {"name": target["name"]}
        for key, column in (
            ("aliases", "aliases_json"), ("emails", "emails_json"), ("usernames", "usernames_json"),
            ("locations", "locations_json"), ("organisations", "companies_json"), ("domains", "domains_json"),
        ):
            values = [str(v).strip() for v in loads(target.get(column), []) if str(v).strip()]
            if values:
                anchors[key] = values[:8]
        try:
            profile = self.build135.profile(case_id, target_id)
        except Exception:
            profile = {"attributes": {}}
        attrs = profile.get("attributes") or {}
        birth = (attrs.get("birth_date") or {}).get("value")
        if birth:
            anchors["birth_year"] = str(birth)[:4]
        occupation = (attrs.get("occupation") or {}).get("value") or {}
        if occupation.get("organisation"):
            anchors.setdefault("organisations", []).append(str(occupation["organisation"]))
        if occupation.get("title"):
            anchors["occupation"] = str(occupation["title"])
        return anchors

    @staticmethod
    def _name_variants(name: str, aliases: list[str]) -> list[str]:
        candidates = [name, *aliases]
        result: list[str] = []
        for candidate in candidates:
            clean = _safe_text(candidate, 200)
            if not clean:
                continue
            variants = [clean]
            ascii_name = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode("ascii")
            if ascii_name and ascii_name.casefold() != clean.casefold():
                variants.append(ascii_name)
            parts = clean.split()
            if len(parts) >= 2:
                variants.append(f"{parts[0][0]}. {' '.join(parts[1:])}")
                variants.append(f"{' '.join(parts[1:])}, {parts[0]}")
            for item in variants:
                if item and item.casefold() not in {existing.casefold() for existing in result}:
                    result.append(item)
                if len(result) >= 12:
                    return result
        return result

    def _objective_queries(self, objective_key: str, objective_text: str, variants: list[str], anchors: Mapping[str, Any]) -> list[tuple[str, str, str, int]]:
        primary = variants[0]
        org = (anchors.get("organisations") or [""])[0]
        location = (anchors.get("locations") or [""])[0]
        username = (anchors.get("usernames") or [""])[0]
        domain = (anchors.get("domains") or [""])[0]
        year = str(anchors.get("birth_year") or "")
        quoted = f'"{primary}"'
        queries: list[tuple[str, str, str, int]] = [
            ("basis_identity", f"{quoted} {year}".strip(), "Exakte Namenssuche mit bekanntem Lebensdatenanker", 95),
            ("basis_identity", f"{quoted} {location}".strip(), "Namens- und Ortsbezug vergleichen", 90),
            ("professional", f"{quoted} {org}".strip(), "Berufliche oder institutionelle Zuordnung prüfen", 88),
            ("registers_companies", f"{quoted} Geschäftsführer OR Vorstand OR officer OR director", "Öffentliche Organ- und Firmenfunktionen prüfen", 82),
            ("publications", f"{quoted} publication OR author OR DOI OR ISBN", "Publikations- und Autorenbezüge prüfen", 70),
            ("digital_footprint", f"{quoted} {username}".strip(), "Öffentliche digitale Profile mit Ankern vergleichen", 75),
            ("digital_footprint", f"{quoted} {domain}".strip(), "Namens- und Domainbezüge prüfen", 65),
            ("archives_history", f"{quoted} archive OR archived OR früher OR ehemalig", "Historische Spuren und frühere Angaben finden", 60),
            ("contradictions", f"{quoted} -{org}" if org else f"{quoted} andere Person", "Gegenhypothese und mögliche Namensverwechslung prüfen", 92),
        ]
        objective_additions = {
            "identity_confirmation": [("contradictions", f"{quoted} age OR born OR Geburtstag", "Lebensdaten gegenprüfen", 94)],
            "employment_history": [("professional", f"{quoted} CV OR Lebenslauf OR Karriere OR Arbeitgeber", "Berufliche Chronologie rekonstruieren", 96)],
            "location_verification": [("basis_identity", f"{quoted} {location} address OR wohnort OR location", "Öffentliche Ortsbezüge prüfen", 96)],
            "digital_profiles": [("digital_footprint", f"{quoted} site:github.com OR site:linkedin.com OR site:gitlab.com", "Öffentliche Profilkandidaten finden", 96)],
            "company_links": [("registers_companies", f"{quoted} company OR GmbH OR AG OR Ltd OR LEI", "Firmen- und Registerbezüge priorisieren", 96)],
            "publication_history": [("publications", f"{quoted} ORCID OR Crossref OR OpenAlex OR DataCite", "Fachliche Publikationen priorisieren", 96)],
            "custom": [("basis_identity", f"{quoted} {_safe_text(objective_text, 300)}", "Benutzerdefinierte Ermittlungsfrage", 90)],
        }
        queries.extend(objective_additions.get(objective_key, []))
        # Include one alternate name query without multiplying the entire plan.
        if len(variants) > 1:
            queries.append(("basis_identity", f'"{variants[1]}" {org or location}'.strip(), "Alternative Namensschreibweise prüfen", 85))
        dedup: list[tuple[str, str, str, int]] = []
        seen: set[str] = set()
        for item in queries:
            normalized = item[1].casefold().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                dedup.append(item)
        return dedup[:14]

    def create_workflow(self, *, case_id: str, target_id: str, objective_key: str, objective_text: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        target = self._target(case_id, target_id)
        if objective_key not in WORKFLOW_OBJECTIVES:
            raise ValueError("Ungültiges Ermittlungsziel")
        objective_text = _safe_text(objective_text or WORKFLOW_OBJECTIVES[objective_key], 2000)
        if objective_key == "custom" and len(objective_text) < 8:
            raise ValueError("Benutzerdefiniertes Ermittlungsziel ist zu kurz")
        anchors = self._anchors(case_id, target_id)
        variants = self._name_variants(str(target["name"]), list(anchors.get("aliases") or []))
        if not variants:
            raise ValueError("Keine belastbare Namensvariante verfügbar")
        workflow_id = new_id("flow137")
        now = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO investigation_workflows_137(workflow_id,case_id,target_id,objective_key,objective_text,status,candidate_only,identity_claims_allowed,name_variants_json,anchors_json,created_by,created_at,updated_at) VALUES(?,?,?,?,?,'active',1,0,?,?,?,?,?)",
                (workflow_id, case_id, target_id, objective_key, objective_text, dumps(variants), dumps(anchors), _safe_text(actor, 120), now, now),
            )
            stage_ids: dict[str, str] = {}
            for order, (stage_key, title, purpose) in enumerate(WORKFLOW_STAGES, start=1):
                stage_id = new_id("stage137")
                stage_ids[stage_key] = stage_id
                self.db.execute(
                    "INSERT INTO investigation_workflow_stages_137(stage_id,workflow_id,case_id,stage_key,stage_order,title,purpose,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'planned',?,?)",
                    (stage_id, workflow_id, case_id, stage_key, order, title, purpose, now, now),
                )
            for stage_key, query, rationale, priority in self._objective_queries(objective_key, objective_text, variants, anchors):
                # Two general engines provide cross-checking without exploding the task count.
                for engine in ("Google", "Bing"):
                    task_id = new_id("task")
                    self.db.execute(
                        "INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)",
                        (task_id, case_id, target_id, f"workflow137:{stage_key}", query, engine, _search_url(engine, query), now),
                    )
                    self.db.execute(
                        "INSERT INTO investigation_workflow_tasks_137(workflow_task_id,workflow_id,stage_id,case_id,target_id,source_key,task_type,title,query_text,rationale,expected_output,search_task_id,priority,status,outcome_note,manual_review_required,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,? ,?,?,?,?,?,?,'planned','',1,1,?,?,?)",
                        (new_id("wft137"), workflow_id, stage_ids[stage_key], case_id, target_id, engine.casefold(), "web_search", f"{engine}: {query}", query, rationale, "Kandidaten, Gegenbelege oder Quellenhinweise; keine automatische Identitätszuordnung", task_id, priority, _safe_text(actor, 120), now, now),
                    )
            # Add a compact official-source route. No API call or external action occurs here.
            route = self.build135.route_sources(case_id=case_id, target_id=target_id, objective=objective_text, actor=actor)
            source_rows = {row["source_key"]: row for row in self.build135.list_sources()}
            for recommendation in route.get("recommendations", [])[:8]:
                source_key = str(recommendation["source_key"])
                source = source_rows.get(source_key) or {}
                data_classes = set(source.get("data_classes") or [])
                if data_classes & {"company", "legal_entity", "officer", "filing", "trademark", "patent"}:
                    stage_key = "registers_companies"
                elif data_classes & {"works", "publication", "doi", "book", "author", "isbn", "researcher_id"}:
                    stage_key = "publications"
                elif data_classes & {"snapshot", "archive_item"}:
                    stage_key = "archives_history"
                elif data_classes & {"profile", "repositories", "registration"}:
                    stage_key = "digital_footprint"
                else:
                    stage_key = "professional"
                official_url = str(recommendation.get("official_url") or source.get("official_url") or "")
                if urlsplit(official_url).scheme != "https":
                    continue
                task_id = new_id("task")
                label = str(recommendation.get("label") or source_key)
                self.db.execute(
                    "INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)",
                    (task_id, case_id, target_id, f"workflow137:{stage_key}", variants[0], label, official_url, now),
                )
                self.db.execute(
                    "INSERT INTO investigation_workflow_tasks_137(workflow_task_id,workflow_id,stage_id,case_id,target_id,source_key,task_type,title,query_text,rationale,expected_output,search_task_id,priority,status,outcome_note,manual_review_required,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'planned','',1,1,?,?,?)",
                    (new_id("wft137"), workflow_id, stage_ids[stage_key], case_id, target_id, source_key, "official_source", f"Offizielle Quelle: {label}", variants[0], "Vom Build-135-Source-Router empfohlen; minimale Offenlegung und manuelle Prüfung erforderlich", "Primär- oder institutionelle Quellenkandidaten", task_id, int(recommendation.get("score") or 50), _safe_text(actor, 120), now, now),
                )
        self._event(case_id=case_id, object_type="investigation_workflow_137", object_id=workflow_id, event_type="workflow_created", actor=actor, details={"objective_key": objective_key, "candidate_only": True, "identity_claims_allowed": False})
        return self.workflow(workflow_id=workflow_id, case_id=case_id)

    def workflow(self, *, workflow_id: str, case_id: str) -> dict[str, Any]:
        workflow = self.db.one("SELECT * FROM investigation_workflows_137 WHERE workflow_id=? AND case_id=?", (workflow_id, case_id))
        if not workflow:
            raise KeyError("Ermittlungsworkflow nicht gefunden")
        workflow["name_variants"] = loads(workflow.pop("name_variants_json", "[]"), [])
        workflow["anchors"] = loads(workflow.pop("anchors_json", "{}"), {})
        stages = self.db.all("SELECT * FROM investigation_workflow_stages_137 WHERE workflow_id=? ORDER BY stage_order", (workflow_id,))
        tasks = self.db.all("SELECT * FROM investigation_workflow_tasks_137 WHERE workflow_id=? ORDER BY priority DESC,created_at", (workflow_id,))
        by_stage: dict[str, list[dict[str, Any]]] = {}
        for task in tasks:
            by_stage.setdefault(str(task["stage_id"]), []).append(task)
        for stage in stages:
            stage_tasks = by_stage.get(str(stage["stage_id"]), [])
            stage["tasks"] = stage_tasks
            stage["task_count"] = len(stage_tasks)
            stage["completed_count"] = sum(1 for t in stage_tasks if t["status"] in {"completed", "skipped"})
            stage["open_count"] = sum(1 for t in stage_tasks if t["status"] in {"planned", "opened", "unresolved", "blocked"})
        workflow["stages"] = stages
        workflow["task_count"] = len(tasks)
        workflow["completed_count"] = sum(1 for t in tasks if t["status"] == "completed")
        workflow["unresolved_count"] = sum(1 for t in tasks if t["status"] in {"unresolved", "blocked"})
        return workflow

    def list_workflows(self, *, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        self._case(case_id)
        rows = self.db.all(
            "SELECT w.*,t.name AS target_name,(SELECT COUNT(*) FROM investigation_workflow_tasks_137 x WHERE x.workflow_id=w.workflow_id) AS task_count,(SELECT COUNT(*) FROM investigation_workflow_tasks_137 x WHERE x.workflow_id=w.workflow_id AND x.status='completed') AS completed_count FROM investigation_workflows_137 w JOIN targets t ON t.target_id=w.target_id WHERE w.case_id=? ORDER BY w.created_at DESC LIMIT ?",
            (case_id, max(1, min(int(limit), 200))),
        )
        return rows

    def update_workflow_task(self, *, case_id: str, workflow_task_id: str, status: str, outcome_note: str, actor: str) -> dict[str, Any]:
        if status not in TASK_STATUSES:
            raise ValueError("Ungültiger Aufgabenstatus")
        row = self.db.one("SELECT * FROM investigation_workflow_tasks_137 WHERE workflow_task_id=? AND case_id=?", (workflow_task_id, case_id))
        if not row:
            raise KeyError("Workflow-Aufgabe nicht gefunden")
        now = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE investigation_workflow_tasks_137 SET status=?,outcome_note=?,updated_at=? WHERE workflow_task_id=?", (status, _safe_text(outcome_note, 4000), now, workflow_task_id))
            if row.get("search_task_id"):
                mapped = "opened" if status == "opened" else ("done" if status in {"completed", "skipped"} else status)
                self.db.execute("UPDATE search_tasks SET status=? WHERE task_id=? AND case_id=?", (mapped, row["search_task_id"], case_id))
            stage_id = row["stage_id"]
            remaining = int((self.db.one("SELECT COUNT(*) AS n FROM investigation_workflow_tasks_137 WHERE stage_id=? AND status NOT IN ('completed','skipped')", (stage_id,)) or {}).get("n") or 0)
            stage_status = "completed" if remaining == 0 else ("active" if status in {"opened", "completed", "unresolved", "blocked"} else "planned")
            self.db.execute("UPDATE investigation_workflow_stages_137 SET status=?,updated_at=? WHERE stage_id=?", (stage_status, now, stage_id))
            workflow_id = row["workflow_id"]
            open_count = int((self.db.one("SELECT COUNT(*) AS n FROM investigation_workflow_tasks_137 WHERE workflow_id=? AND status NOT IN ('completed','skipped')", (workflow_id,)) or {}).get("n") or 0)
            self.db.execute("UPDATE investigation_workflows_137 SET status=?,updated_at=? WHERE workflow_id=?", ("completed" if open_count == 0 else "active", now, workflow_id))
        self._event(case_id=case_id, object_type="workflow_task_137", object_id=workflow_task_id, event_type="workflow_task_updated", actor=actor, details={"status": status})
        return self.db.one("SELECT * FROM investigation_workflow_tasks_137 WHERE workflow_task_id=?", (workflow_task_id,)) or {}

    def launch_workflow_task(self, *, case_id: str, workflow_task_id: str, actor: str, local_redirect_origin: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_workflow_tasks_137 WHERE workflow_task_id=? AND case_id=?", (workflow_task_id, case_id))
        if not row or not row.get("search_task_id"):
            raise KeyError("Workflow-Aufgabe besitzt keine startbare Recherche")
        result = self.build136.launch_research_task(case_id=case_id, task_id=row["search_task_id"], actor=actor, local_redirect_origin=local_redirect_origin)
        self.update_workflow_task(case_id=case_id, workflow_task_id=workflow_task_id, status="opened", outcome_note=str(row.get("outcome_note") or ""), actor=actor)
        result["workflow_task_id"] = workflow_task_id
        return result

    # ---------- local photo analysis ----------
    def _open_asset_image(self, *, case_id: str, asset_id: str) -> tuple[dict[str, Any], Path, Image.Image]:
        row, path = self.build136.photo_path(case_id=case_id, asset_id=asset_id)
        try:
            image = Image.open(path)
            image.verify()
            image = Image.open(path)
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"Bild konnte nicht sicher analysiert werden: {exc}") from exc
        return row, path, image

    def analyze_photo(self, *, case_id: str, asset_id: str, actor: str) -> dict[str, Any]:
        row, _path, image = self._open_asset_image(case_id=case_id, asset_id=asset_id)
        try:
            exif = image.getexif()
            exif_names = sorted({str(ExifTags.TAGS.get(int(tag), tag)) for tag in exif.keys()}) if exif else []
            gps_present = any(name == "GPSInfo" for name in exif_names)
            sensitive_names = [name for name in exif_names if name in {"GPSInfo", "DateTimeOriginal", "DateTimeDigitized", "BodySerialNumber", "CameraSerialNumber", "LensSerialNumber", "OwnerName"}]
            safe_summary: dict[str, Any] = {}
            for tag, value in exif.items() if exif else []:
                name = str(ExifTags.TAGS.get(int(tag), tag))
                if name in {"Make", "Model", "Software", "Orientation", "ColorSpace"}:
                    safe_summary[name] = _safe_text(value, 200)
            info_keys = sorted(str(key) for key in image.info.keys())
            ahash = _average_hash(image)
            dhash = _difference_hash(image)
            metadata_id = new_id("pmeta137")
            fingerprint_id = new_id("pfp137")
            now = now_ts()
            with self.db.transaction(immediate=True):
                self.db.execute(
                    "INSERT INTO photo_metadata_137(metadata_id,asset_id,case_id,target_id,image_format,color_mode,frame_count,animated,exif_present,gps_present,icc_present,metadata_keys_json,exif_tag_names_json,safe_summary_json,sensitive_fields_json,analyzed_by,analyzed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET image_format=excluded.image_format,color_mode=excluded.color_mode,frame_count=excluded.frame_count,animated=excluded.animated,exif_present=excluded.exif_present,gps_present=excluded.gps_present,icc_present=excluded.icc_present,metadata_keys_json=excluded.metadata_keys_json,exif_tag_names_json=excluded.exif_tag_names_json,safe_summary_json=excluded.safe_summary_json,sensitive_fields_json=excluded.sensitive_fields_json,analyzed_by=excluded.analyzed_by,analyzed_at=excluded.analyzed_at",
                    (metadata_id, asset_id, case_id, row.get("target_id"), str(image.format or row.get("mime_type") or ""), str(image.mode), int(getattr(image, "n_frames", 1) or 1), int(bool(getattr(image, "is_animated", False))), int(bool(exif_names)), int(gps_present), int("icc_profile" in image.info), dumps(info_keys), dumps(exif_names), dumps(safe_summary), dumps(sensitive_names), _safe_text(actor, 120), now),
                )
                self.db.execute(
                    "INSERT INTO photo_fingerprints_137(fingerprint_id,asset_id,case_id,ahash64,dhash64,algorithm_version,analyzed_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(asset_id,algorithm_version) DO UPDATE SET ahash64=excluded.ahash64,dhash64=excluded.dhash64,analyzed_at=excluded.analyzed_at",
                    (fingerprint_id, asset_id, case_id, ahash, dhash, IMAGE_HASH_VERSION, now),
                )
                self.db.execute("DELETE FROM photo_similarity_links_137 WHERE case_id=? AND (left_asset_id=? OR right_asset_id=?)", (case_id, asset_id, asset_id))
                peers = self.db.all("SELECT * FROM photo_fingerprints_137 WHERE case_id=? AND asset_id<>? AND algorithm_version=?", (case_id, asset_id, IMAGE_HASH_VERSION))
                for peer in peers:
                    ad = _hamming_hex(ahash, peer["ahash64"])
                    dd = _hamming_hex(dhash, peer["dhash64"])
                    if ad <= 6 and dd <= 8:
                        band = "very_similar"
                    elif ad <= 12 and dd <= 14:
                        band = "similar_candidate"
                    else:
                        continue
                    left, right = sorted((asset_id, str(peer["asset_id"])))
                    self.db.execute(
                        "INSERT OR REPLACE INTO photo_similarity_links_137(link_id,case_id,left_asset_id,right_asset_id,ahash_distance,dhash_distance,similarity_band,candidate_only,created_at) VALUES(?,?,?,?,?,?,?,1,?)",
                        (new_id("plink137"), case_id, left, right, ad, dd, band, now),
                    )
            self._event(case_id=case_id, object_type="photo_asset_136", object_id=asset_id, event_type="photo_analyzed_137", actor=actor, details={"ahash64": ahash, "dhash64": dhash, "gps_present": gps_present, "identity_claim": False})
            return self.photo_analysis(case_id=case_id, asset_id=asset_id)
        finally:
            image.close()

    def photo_analysis(self, *, case_id: str, asset_id: str) -> dict[str, Any]:
        metadata = self.db.one("SELECT * FROM photo_metadata_137 WHERE case_id=? AND asset_id=?", (case_id, asset_id)) or {}
        fingerprint = self.db.one("SELECT * FROM photo_fingerprints_137 WHERE case_id=? AND asset_id=? AND algorithm_version=?", (case_id, asset_id, IMAGE_HASH_VERSION)) or {}
        links = self.db.all("SELECT * FROM photo_similarity_links_137 WHERE case_id=? AND (left_asset_id=? OR right_asset_id=?) ORDER BY ahash_distance+dhash_distance", (case_id, asset_id, asset_id))
        for key in ("metadata_keys_json", "exif_tag_names_json", "safe_summary_json", "sensitive_fields_json"):
            if key in metadata:
                metadata[key.removesuffix("_json")] = loads(metadata.pop(key), [] if key != "safe_summary_json" else {})
        return {"metadata": metadata, "fingerprint": fingerprint, "similarity_links": links, "identity_claim": False}

    # ---------- privacy-preserving research copies ----------
    def create_research_copy(
        self,
        *,
        case_id: str,
        asset_id: str,
        max_dimension: int,
        quality: int,
        crop: Mapping[str, Any] | None,
        actor: str,
    ) -> dict[str, Any]:
        row, _path, image = self._open_asset_image(case_id=case_id, asset_id=asset_id)
        max_dimension = max(PHOTO_COPY_MIN_DIMENSION, min(int(max_dimension or 1600), PHOTO_COPY_MAX_DIMENSION))
        quality = max(60, min(int(quality or 88), 95))
        crop = dict(crop or {})
        derivation: dict[str, Any] = {"metadata_removed": True, "exif_transpose": True, "max_dimension": max_dimension, "quality": quality, "output": "JPEG", "crop": None}
        try:
            working = ImageOps.exif_transpose(image)
            if working is image:
                working = image.copy()
            width, height = working.size
            crop_values = [int(crop.get(key) or 0) for key in ("left", "top", "right", "bottom")]
            if any(crop_values):
                left, top, right, bottom = crop_values
                if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                    raise ValueError("Ungültiger Bildausschnitt")
                working = working.crop((left, top, right, bottom))
                derivation["crop"] = {"left": left, "top": top, "right": right, "bottom": bottom}
            working.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            if working.mode in {"RGBA", "LA"} or (working.mode == "P" and "transparency" in working.info):
                rgba = working.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                working = background
            elif working.mode != "RGB":
                working = working.convert("RGB")
            buffer = io.BytesIO()
            working.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            data = buffer.getvalue()
            if len(data) > PHOTO_COPY_MAX_BYTES:
                raise ValueError("Bereinigte Recherchekopie überschreitet 8 MB; kleinere Maximalabmessung wählen")
            digest = hashlib.sha256(data).hexdigest()
            existing = self.db.one("SELECT * FROM photo_research_copies_137 WHERE case_id=? AND parent_asset_id=? AND sha256=?", (case_id, asset_id, digest))
            if existing:
                return {**existing, "duplicate": True, "download_url": f"/api/photo137/copy/{existing['copy_id']}?case_id={case_id}"}
            copy_id = new_id("pcopy137")
            case_dir = (self.photo_root / case_id).resolve()
            if case_dir.parent != self.photo_root:
                raise PermissionError("Ungültiger fallgebundener Fototresorpfad")
            research_dir = (case_dir / "research_137").resolve()
            if case_dir not in research_dir.parents:
                raise PermissionError("Ungültiger Recherchekopiepfad")
            research_dir.mkdir(parents=True, exist_ok=True)
            try:
                research_dir.chmod(0o700)
            except OSError:
                pass
            filename = f"{_slug(row.get('title') or row.get('original_filename') or 'photo')}_{copy_id}.jpg"
            final_path = research_dir / filename
            temp_path = research_dir / f".{copy_id}.tmp"
            temp_path.write_bytes(data)
            try:
                temp_path.chmod(0o600)
            except OSError:
                pass
            os.replace(temp_path, final_path)
            try:
                final_path.chmod(0o600)
            except OSError:
                pass
            relpath = final_path.relative_to(self.base_dir).as_posix()
            now = now_ts()
            self.db.execute(
                "INSERT INTO photo_research_copies_137(copy_id,case_id,target_id,parent_asset_id,storage_relpath,filename,mime_type,byte_size,width_px,height_px,sha256,metadata_removed,derivation_json,status,expires_at,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,'ready',?,?,?)",
                (copy_id, case_id, row.get("target_id"), asset_id, relpath, filename, "image/jpeg", len(data), working.width, working.height, digest, dumps(derivation), _utc_after(24), _safe_text(actor, 120), now),
            )
            self._event(case_id=case_id, object_type="photo_research_copy_137", object_id=copy_id, event_type="research_copy_created", actor=actor, details={"parent_asset_id": asset_id, "sha256": digest, "metadata_removed": True})
            return {**(self.db.one("SELECT * FROM photo_research_copies_137 WHERE copy_id=?", (copy_id,)) or {}), "duplicate": False, "download_url": f"/api/photo137/copy/{copy_id}?case_id={case_id}"}
        finally:
            try:
                working.close()  # type: ignore[name-defined]
            except Exception:
                pass
            image.close()

    def copy_path(self, *, case_id: str, copy_id: str) -> tuple[dict[str, Any], Path]:
        row = self.db.one("SELECT * FROM photo_research_copies_137 WHERE copy_id=? AND case_id=?", (copy_id, case_id))
        if not row:
            raise KeyError("Recherchekopie nicht gefunden")
        if row.get("status") != "ready":
            raise FileNotFoundError("Recherchekopie ist abgelaufen oder nicht mehr verfügbar")
        candidate = (self.base_dir / str(row["storage_relpath"])).resolve()
        case_root = (self.photo_root / case_id).resolve()
        if case_root.parent != self.photo_root or case_root not in candidate.parents:
            raise PermissionError("Ungültiger Recherchekopiepfad")
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            raise FileNotFoundError("Recherchekopie fehlt")
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != row["sha256"]:
            raise PermissionError("Integritätsprüfung der Recherchekopie fehlgeschlagen")
        return row, candidate

    def create_photo_research_job(self, *, case_id: str, copy_id: str, provider_key: str, purpose: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        if provider_key not in PHOTO_PROVIDERS:
            raise ValueError("Unbekannter Reverse-Image-Search-Anbieter")
        if confirmation.strip() != "FOTORECHERCHE FREIGEBEN":
            raise PermissionError("Freigabephrase FOTORECHERCHE FREIGEBEN erforderlich")
        purpose = _safe_text(purpose, 1500)
        if len(purpose) < 8:
            raise ValueError("Recherche-Zweck ist zu kurz")
        copy_row, _path = self.copy_path(case_id=case_id, copy_id=copy_id)
        provider = PHOTO_PROVIDERS[provider_key]
        task_id = new_id("task")
        job_id = new_id("pjob137")
        now = now_ts()
        disclosure = {
            "file": copy_row["filename"],
            "mime_type": copy_row["mime_type"],
            "byte_size": copy_row["byte_size"],
            "width_px": copy_row["width_px"],
            "height_px": copy_row["height_px"],
            "sha256": copy_row["sha256"],
            "metadata_removed": True,
            "original_not_disclosed": True,
            "automatic_upload": False,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)",
                (task_id, case_id, copy_row.get("target_id"), "photo_reverse_search_137", f"Reverse image research: {copy_row['filename']}", provider["label"], provider["url"], now),
            )
            self.db.execute(
                "INSERT INTO photo_research_jobs_137(job_id,case_id,target_id,parent_asset_id,copy_id,provider_key,provider_label,provider_url,purpose,disclosure_json,status,search_task_id,manual_upload_required,external_upload_performed,result_note,approved_by,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'prepared',?,1,0,'',?,?,?)",
                (job_id, case_id, copy_row.get("target_id"), copy_row["parent_asset_id"], copy_id, provider_key, provider["label"], provider["url"], purpose, dumps(disclosure), task_id, _safe_text(actor, 120), now, now),
            )
        self._event(case_id=case_id, object_type="photo_research_job_137", object_id=job_id, event_type="photo_research_prepared", actor=actor, details={"provider": provider_key, "automatic_upload": False, "identity_claim": False})
        return self.photo_job(case_id=case_id, job_id=job_id)

    def photo_job(self, *, case_id: str, job_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM photo_research_jobs_137 WHERE case_id=? AND job_id=?", (case_id, job_id))
        if not row:
            raise KeyError("Fotorecherche-Job nicht gefunden")
        row["disclosure"] = loads(row.pop("disclosure_json", "{}"), {})
        row["copy_download_url"] = f"/api/photo137/copy/{row['copy_id']}?case_id={case_id}"
        return row

    def launch_photo_research_job(self, *, case_id: str, job_id: str, actor: str, local_redirect_origin: str) -> dict[str, Any]:
        row = self.photo_job(case_id=case_id, job_id=job_id)
        result = self.build136.launch_research_task(case_id=case_id, task_id=row["search_task_id"], actor=actor, local_redirect_origin=local_redirect_origin)
        self.db.execute("UPDATE photo_research_jobs_137 SET status='provider_opened',updated_at=? WHERE job_id=? AND case_id=?", (now_ts(), job_id, case_id))
        self._event(case_id=case_id, object_type="photo_research_job_137", object_id=job_id, event_type="photo_provider_opened", actor=actor, details={"provider": row["provider_key"], "manual_upload_required": True})
        result.update({"job_id": job_id, "copy_download_url": row["copy_download_url"], "manual_upload_required": True, "automatic_upload": False})
        return result

    def update_photo_job(self, *, case_id: str, job_id: str, status: str, result_note: str, actor: str) -> dict[str, Any]:
        if status not in PHOTO_JOB_STATUSES:
            raise ValueError("Ungültiger Fotorecherche-Status")
        row = self.photo_job(case_id=case_id, job_id=job_id)
        # Only the investigator may attest that a manual upload occurred.
        external_upload = 1 if status in {"uploaded_manually", "results_review", "completed"} else int(row.get("external_upload_performed") or 0)
        self.db.execute("UPDATE photo_research_jobs_137 SET status=?,external_upload_performed=?,result_note=?,updated_at=? WHERE job_id=? AND case_id=?", (status, external_upload, _safe_text(result_note, 4000), now_ts(), job_id, case_id))
        self._event(case_id=case_id, object_type="photo_research_job_137", object_id=job_id, event_type="photo_research_status_updated", actor=actor, details={"status": status, "external_upload_performed": bool(external_upload)})
        return self.photo_job(case_id=case_id, job_id=job_id)

    def photo_dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        copies = self.db.all("SELECT * FROM photo_research_copies_137 WHERE case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
        for row in copies:
            row["derivation"] = loads(row.pop("derivation_json", "{}"), {})
            row["download_url"] = f"/api/photo137/copy/{row['copy_id']}?case_id={case_id}"
        jobs = self.db.all("SELECT * FROM photo_research_jobs_137 WHERE case_id=? ORDER BY updated_at DESC LIMIT 200", (case_id,))
        for row in jobs:
            row["disclosure"] = loads(row.pop("disclosure_json", "{}"), {})
            row["copy_download_url"] = f"/api/photo137/copy/{row['copy_id']}?case_id={case_id}"
        links = self.db.all("SELECT * FROM photo_similarity_links_137 WHERE case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
        return {
            "copies": copies,
            "jobs": jobs,
            "similarity_links": links,
            "analyzed_count": int((self.db.one("SELECT COUNT(*) AS n FROM photo_metadata_137 WHERE case_id=?", (case_id,)) or {}).get("n") or 0),
            "copy_count": len(copies),
            "job_count": len(jobs),
            "open_job_count": sum(1 for row in jobs if row["status"] not in {"completed", "cancelled"}),
            "identity_claims": 0,
            "automatic_uploads": 0,
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {
            "build": "137.0",
            "workflow_objectives": WORKFLOW_OBJECTIVES,
            "workflow_count": int((self.db.one("SELECT COUNT(*) AS n FROM investigation_workflows_137 WHERE case_id=?", (case_id,)) or {}).get("n") or 0) if case_id else int((self.db.one("SELECT COUNT(*) AS n FROM investigation_workflows_137") or {}).get("n") or 0),
            "workflows": self.list_workflows(case_id=case_id) if case_id else [],
            "photos": self.photo_dashboard(case_id) if case_id else {},
            "safety": {"automatic_identity_claims": 0, "automatic_image_uploads": 0, "manual_review_required": True},
        }
