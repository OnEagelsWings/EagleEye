from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib, json, re
from urllib.parse import urlparse, quote_plus
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.review.service import ReviewService
from eagleeye_pro.providers.dork_engine import DorkEngine, ENGINES
from eagleeye_pro.security.policy import PolicyGate, MAX_MULTI_SEARCH_URLS

PACKAGE_ORDER = [
    ("identity_anchor", "Identitätsanker", "Basisabgleich: Name, Aliasse, Usernames, E-Mail, Orts-/Firmenkontext"),
    ("professional_profile", "Beruf / Profile", "Öffentliche berufliche Profile, Firmen- und Publikationsspuren"),
    ("image_media_geo", "Bilder / Geo / Medien", "Bild-, Medien- und Geo-Spuren aus öffentlichen Such-/Kartenoberflächen; Uploads nur nach OPSEC-/Legal-Freigabe."),
    ("documents_media", "Dokumente / Medien", "PDFs, Presse, Vorträge, Interviews und archivierte öffentliche Inhalte"),
    ("registry_business", "Register / Firmen", "Öffentliche Register-, Impressums-, Domain- und Firmenbezüge"),
    ("counter_evidence", "Gegenbelege", "Namensdoppler, Ausschlussmarker und Widerspruchssuche"),
]


MULTI_SEARCH_PRESETS = [
    ("standard", "Standard: Google/Bing/DDG/Brave", ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage"], "Schneller Allround-Start über vier große Suchmaschinen."),
    ("deep_public", "Deep Public Web: 8 Engines", ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage", "Ecosia", "Mojeek", "Yahoo"], "Breite öffentliche Websuche ohne Login-/Bypass-Mechanismen."),
    ("privacy_alt", "Alternative/Privacy Engines", ["DuckDuckGo", "Startpage", "Brave", "Mojeek"], "Suchmaschinen mit alternativer Index-/Privacy-Perspektive."),
    ("classic_major", "Klassisch: Google/Bing/Yahoo", ["Google", "Bing", "Yahoo"], "Klassischer Vergleich großer Indizes."),
    ("minimal_safe", "Minimal: Google+Bing", ["Google", "Bing"], "Reduzierte Suche für kontrolliertes Öffnen weniger Tabs."),
    ("image_reverse", "Bild-/Reverse-Spur: Bilder + Web", ["Google Bilder", "Bing Bilder", "Yandex Bilder", "TinEye URL", "Google", "Bing"], "Bild-/Medienpfad aus Build 15.0: öffentliche Bildsuche und Gegencheck; TinEye ist für Bild-URLs gedacht."),
    ("geo_maps", "Geo-/Maps-Spur: Karten + Web + News", ["Google Maps", "OpenStreetMap", "Google", "Google News", "Bing", "DuckDuckGo", "Brave"], "Geo-/Ortspfad aus Build 15.0: Karten-, Web- und News-Kontext ohne private Adressbehauptung."),
    ("document_media", "Dokumente/Medien/Archive", ["Google", "Bing", "DuckDuckGo", "Brave", "Google News"], "Dokumente, Presse, Medien und öffentliche Archiv-/Kontextsuche."),
]

CATEGORY_TO_PACKAGE = {
    "Identitätsanker": "identity_anchor",
    "Alias": "identity_anchor",
    "Username": "identity_anchor",
    "Username + Name": "identity_anchor",
    "E-Mail": "identity_anchor",
    "Ortskontext": "identity_anchor",
    "Öffentliches Berufsprofil": "professional_profile",
    "Technisches Profil": "professional_profile",
    "Fachprofil": "professional_profile",
    "Publikationen": "professional_profile",
    "Dokumente": "documents_media",
    "Presse": "documents_media",
    "Bild-/Medienpfad": "image_media_geo",
    "Geo-/Maps-Spur": "image_media_geo",
    "Register/Presse": "registry_business",
    "Beruf/Firma": "registry_business",
    "Domain": "registry_business",
    "Impressum": "registry_business",
    "Gegenbelege/Namensdoppler": "counter_evidence",
}

class SearchWorkbenchService:
    """Build 20 Graph & Timeline Pro.

    This service deliberately keeps the first professional implementation conservative:
    it creates public-source search packages, opens normal browser search URLs,
    captures manually verified public hits into a tamper-evident local manifest,
    and forwards those hits to the Review Inbox. It does not bypass logins,
    CAPTCHAs, robots rules, private accounts, or paywalls.
    """

    def __init__(self, db: Database, audit: AuditService, dorks: DorkEngine, review: ReviewService, storage_dir: str | Path):
        self.db = db
        self.audit = audit
        self.dorks = dorks
        self.review = review
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _safe_name(text: str, max_len: int = 80) -> str:
        clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", text or "item").strip("_")
        return (clean or "item")[:max_len]

    @staticmethod
    def _host(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    @staticmethod
    def _validate_public_url(url: str) -> str:
        candidate = (url or "").strip()
        if candidate.startswith("www."):
            candidate = "https://" + candidate
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Nur öffentliche http/https-URLs dürfen als Capture übernommen werden.")
        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
        host = parsed.hostname or ""
        if host.lower() in blocked_hosts or host.startswith("10.") or host.startswith("192.168.") or host.startswith("172.16."):
            raise ValueError("Lokale/private Netzwerkadressen werden nicht als OSINT-Capture übernommen.")
        return candidate

    def _chain_event(self, case_id: str, object_type: str, object_id: str, event_type: str, details: Dict[str, Any], actor: str = "local-analyst") -> None:
        self.db.execute("""INSERT INTO chain_events(chain_event_id,case_id,object_type,object_id,event_type,timestamp,actor,details_json)
        VALUES(?,?,?,?,?,?,?,?)""", [new_id("chain"), case_id, object_type, object_id, event_type, now_ts(), actor, dumps(details)])

    def create_packages_from_target(self, case_id: str, target_id: str, engines: Optional[List[str]] = None) -> Dict[str, Any]:
        target = self.db.one("SELECT * FROM targets WHERE target_id=? AND case_id=?", [target_id, case_id])
        if not target:
            raise KeyError("Zielperson nicht gefunden.")
        # Target JSON fields are stored as JSON strings in DB. DorkEngine expects lists.
        for key in ["aliases_json", "emails_json", "usernames_json", "locations_json", "companies_json", "domains_json"]:
            target[key] = loads(target.get(key), [])
        queries = self.dorks.generate_queries(target)
        selected_engines = [e for e in (engines or list(ENGINES.keys())) if e in ENGINES]
        package_ids: Dict[str, str] = {}
        ts = now_ts()
        for package_key, name, objective in PACKAGE_ORDER:
            package_id = new_id("pkg")
            package_ids[package_key] = package_id
            self.db.execute("""INSERT INTO search_packages(package_id,case_id,target_id,package_key,name,objective,status,created_at,updated_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", [package_id, case_id, target_id, package_key, name, objective, "active", ts, ts, "Build 22.0 Provider Integration Pro Paket"])
            self._chain_event(case_id, "search_package", package_id, "created", {"name": name, "objective": objective})
        count = 0
        for q in queries:
            package_key = CATEGORY_TO_PACKAGE.get(q["category"], "identity_anchor")
            package_id = package_ids[package_key]
            for engine in selected_engines:
                template = ENGINES[engine]
                from urllib.parse import quote_plus
                task_id = new_id("task")
                url = template.format(q=quote_plus(q["query"]))
                self.db.execute("""INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", [task_id, case_id, target_id, q["category"], q["query"], engine, url, "planned", ts])
                self.db.execute("INSERT INTO search_package_tasks(package_id,task_id,created_at) VALUES(?,?,?)", [package_id, task_id, ts])
                count += 1
        self.audit.log("generate", "search_workbench_packages", target_id, case_id, {"packages": len(package_ids), "tasks": count, "engines": selected_engines})
        return {"packages": len(package_ids), "tasks": count, "engines": selected_engines}

    def list_packages(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("""SELECT sp.*, COUNT(spt.task_id) AS task_count
        FROM search_packages sp LEFT JOIN search_package_tasks spt ON sp.package_id=spt.package_id
        WHERE sp.case_id=? GROUP BY sp.package_id ORDER BY sp.created_at DESC, sp.name""", [case_id])

    def list_tasks(self, case_id: str, package_id: str = "") -> List[Dict[str, Any]]:
        if package_id:
            return self.db.all("""SELECT st.*, sp.name AS package_name, sp.package_key
            FROM search_tasks st JOIN search_package_tasks spt ON st.task_id=spt.task_id JOIN search_packages sp ON spt.package_id=sp.package_id
            WHERE st.case_id=? AND sp.package_id=? ORDER BY sp.name, st.category, st.engine, st.query""", [case_id, package_id])
        return self.db.all("""SELECT st.*, COALESCE(sp.name,'Legacy') AS package_name, COALESCE(sp.package_key,'legacy') AS package_key
        FROM search_tasks st LEFT JOIN search_package_tasks spt ON st.task_id=spt.task_id LEFT JOIN search_packages sp ON spt.package_id=sp.package_id
        WHERE st.case_id=? ORDER BY st.created_at DESC, package_name, st.category""", [case_id])

    def mark_task_opened(self, task_id: str) -> Dict[str, Any]:
        task = self.db.one("SELECT * FROM search_tasks WHERE task_id=?", [task_id])
        if not task:
            raise KeyError("Suchaufgabe nicht gefunden.")
        self.db.execute("UPDATE search_tasks SET status=? WHERE task_id=?", ["opened", task_id])
        self._chain_event(task["case_id"], "search_task", task_id, "opened_in_browser", {"engine": task.get("engine"), "query": task.get("query"), "url": task.get("url")})
        self.audit.log("open", "search_task", task_id, task["case_id"], {"engine": task.get("engine"), "query": task.get("query")})
        return task



    @staticmethod
    def _quote_if_needed(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if " " in value and not (value.startswith('"') and value.endswith('"')):
            return f'"{value}"'
        return value

    def suggest_multi_search_query_from_target(self, case_id: str, target_id: str = "") -> Dict[str, Any]:
        """Build 37.0 Hotfix: create a visible, usable search query from the selected case/target.

        This prevents the GUI from failing with an empty/hidden query. It deliberately uses
        only the target anchors already entered by the analyst and returns a candidate query
        that can be edited before opening multiple search engines.
        """
        target = None
        if target_id:
            target = self.db.one("SELECT * FROM targets WHERE target_id=? AND case_id=?", [target_id, case_id])
        if not target:
            target = self.db.one("SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not target:
            raise ValueError("Keine Suchanfrage vorhanden und keine Zielperson gefunden. Bitte im sichtbaren Feld 'Suchanfrage / freie Mehrfachsuche' einen Suchbegriff eingeben oder zuerst eine Zielperson anlegen.")
        aliases = loads(target.get("aliases_json"), [])
        usernames = loads(target.get("usernames_json"), [])
        emails = loads(target.get("emails_json"), [])
        locations = loads(target.get("locations_json"), [])
        companies = loads(target.get("companies_json"), [])
        domains = loads(target.get("domains_json"), [])
        parts = []
        name = self._quote_if_needed(target.get("name", ""))
        if name:
            parts.append(name)
        for bucket in (companies, locations, aliases, usernames, emails, domains):
            for value in bucket:
                v = self._quote_if_needed(str(value))
                if v and v not in parts:
                    parts.append(v)
                if len(parts) >= 4:
                    break
            if len(parts) >= 4:
                break
        query = " ".join(parts).strip()
        if not query:
            raise ValueError("Zielperson ist vorhanden, enthält aber keine nutzbaren Suchanker. Bitte Name, Alias, Ort, Firma, Username, E-Mail oder Domain ergänzen.")
        return {"query": query, "target_id": target.get("target_id", ""), "source": "target_fallback", "target_name": target.get("name", "")}

    def resolve_multi_search_query(self, case_id: str, explicit_query: str = "", target_id: str = "", task_id: str = "") -> Dict[str, Any]:
        """Resolve a multi-search query in a predictable GUI-friendly order.

        Order: visible free-search field -> selected search task -> selected/first target.
        """
        q = (explicit_query or "").strip()
        if q:
            return {"query": q, "target_id": target_id or "", "source": "free_field"}
        if task_id:
            task = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", [task_id, case_id])
            if task and (task.get("query") or "").strip():
                return {"query": task["query"].strip(), "target_id": task.get("target_id") or target_id or "", "source": "selected_task", "task_id": task_id}
        return self.suggest_multi_search_query_from_target(case_id, target_id=target_id)

    def seed_multi_search_presets(self) -> Dict[str, Any]:
        ts = now_ts()
        created = 0
        for idx, (key, title, engines, description) in enumerate(MULTI_SEARCH_PRESETS, start=1):
            exists = self.db.one("SELECT preset_id FROM multi_search_presets WHERE preset_key=?", [key])
            if not exists:
                self.db.execute("""INSERT INTO multi_search_presets(preset_id,preset_key,title,engines_json,description,display_order,created_at,active)
                VALUES(?,?,?,?,?,?,?,1)""", [new_id("msp"), key, title, dumps(engines), description, idx, ts])
                created += 1
        return {"created": created, "total": len(self.list_multi_search_presets())}

    def list_multi_search_presets(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM multi_search_presets WHERE active=1 ORDER BY display_order,title")
        for r in rows:
            r["engines"] = loads(r.get("engines_json"), [])
        return rows

    def multi_search_preset_options(self) -> List[str]:
        return [f"{p['preset_key']} | {p['title']}" for p in self.list_multi_search_presets()]

    def _preset_engines(self, preset_key: str = "standard", engines: Optional[List[str]] = None) -> List[str]:
        if engines:
            selected = engines
        else:
            preset = self.db.one("SELECT engines_json FROM multi_search_presets WHERE preset_key=? AND active=1", [preset_key or "standard"])
            selected = loads(preset.get("engines_json"), []) if preset else ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage"]
        clean = []
        for e in selected:
            if e in ENGINES and e not in clean:
                clean.append(e)
        return clean or ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage"]

    def build_multi_engine_urls(self, query: str, preset_key: str = "standard", engines: Optional[List[str]] = None) -> List[Dict[str, str]]:
        query = (query or "").strip()
        if not query:
            raise ValueError("Mehrfachsuche braucht eine Query.")
        policy = PolicyGate.evaluate_query(query)
        if not policy.get("ok"):
            raise ValueError("Mehrfachsuche blockiert: Query verletzt die eingebauten OSINT-Guardrails.")
        out = []
        q = quote_plus(query)
        for engine in self._preset_engines(preset_key, engines):
            # TinEye benötigt sinnvollerweise eine Bild-URL. Bei normalen Namens-/Textqueries
            # bleibt die Bildsuche auf Google/Bing/Yandex/Web-Gegencheck begrenzt.
            if engine == "TinEye URL" and not (query.startswith("http://") or query.startswith("https://")):
                continue
            url = ENGINES[engine].format(q=q)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(f"Unsicheres URL-Schema blockiert: {engine}")
            out.append({"engine": engine, "query": query, "url": url})
            if len(out) >= MAX_MULTI_SEARCH_URLS:
                break
        if not out:
            raise ValueError("Keine zulässigen Such-URLs erzeugt. Prüfe Preset/Query/Guardrails.")
        return out

    def create_multi_search_launch(self, case_id: str, query: str, preset_key: str = "standard", target_id: str = "", source_task_id: str = "", bundle_key: str = "", notes: str = "") -> Dict[str, Any]:
        urls = self.build_multi_engine_urls(query, preset_key=preset_key)
        launch_id = new_id("msl")
        ts = now_ts()
        engines = [u["engine"] for u in urls]
        self.db.execute("""INSERT INTO multi_search_launches(launch_id,case_id,target_id,source_task_id,bundle_key,preset_key,query,engines_json,url_count,status,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [launch_id, case_id, target_id or "", source_task_id or "", bundle_key or "", preset_key or "standard", query.strip(), dumps(engines), len(urls), "planned", ts, notes])
        for u in urls:
            self.db.execute("""INSERT INTO multi_search_launch_urls(launch_url_id,launch_id,engine,url,status,created_at)
            VALUES(?,?,?,?,?,?)""", [new_id("msu"), launch_id, u["engine"], u["url"], "planned", ts])
        self._chain_event(case_id, "multi_search_launch", launch_id, "created", {"query": query, "preset": preset_key, "engines": engines, "source_task_id": source_task_id})
        self.audit.log("create", "multi_search_launch", launch_id, case_id, {"query": query, "preset": preset_key, "engines": engines, "url_count": len(urls)})
        return {"launch_id": launch_id, "query": query.strip(), "preset_key": preset_key, "engines": engines, "urls": urls, "url_count": len(urls)}

    def create_multi_search_from_task(self, case_id: str, task_id: str, preset_key: str = "standard", bundle_key: str = "") -> Dict[str, Any]:
        task = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", [task_id, case_id])
        if not task:
            raise KeyError("Suchaufgabe nicht gefunden.")
        return self.create_multi_search_launch(case_id, task["query"], preset_key=preset_key, target_id=task.get("target_id") or "", source_task_id=task_id, bundle_key=bundle_key or "", notes=f"Aus markierter Suchaufgabe erzeugt: {task.get('category','')} / {task.get('engine','')}")

    def mark_multi_search_opened(self, launch_id: str) -> Dict[str, Any]:
        launch = self.db.one("SELECT * FROM multi_search_launches WHERE launch_id=?", [launch_id])
        if not launch:
            raise KeyError("Mehrfachsuche nicht gefunden.")
        ts = now_ts()
        self.db.execute("UPDATE multi_search_launches SET status='opened', opened_at=? WHERE launch_id=?", [ts, launch_id])
        self.db.execute("UPDATE multi_search_launch_urls SET status='opened', opened_at=? WHERE launch_id=?", [ts, launch_id])
        if launch.get("source_task_id"):
            self.db.execute("UPDATE search_tasks SET status='opened' WHERE case_id=? AND query=?", [launch["case_id"], launch["query"]])
        self._chain_event(launch["case_id"], "multi_search_launch", launch_id, "opened_in_browser", {"query": launch.get("query"), "preset": launch.get("preset_key"), "url_count": launch.get("url_count")})
        self.audit.log("open", "multi_search_launch", launch_id, launch["case_id"], {"query": launch.get("query"), "url_count": launch.get("url_count")})
        return launch

    def list_multi_search_launches(self, case_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM multi_search_launches WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, limit])
        for r in rows:
            r["engines"] = loads(r.get("engines_json"), [])
        return rows

    def get_multi_search_urls(self, launch_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM multi_search_launch_urls WHERE launch_id=? ORDER BY engine", [launch_id])

    def capture_public_hit(self, case_id: str, task_id: str, title: str, url: str, snippet: str, raw_text: str = "", notes: str = "", score: float = 0.55) -> Dict[str, Any]:
        url = self._validate_public_url(url)
        task = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", [task_id, case_id]) if task_id else None
        query = task.get("query", "") if task else ""
        text = "\n".join([title or "", url or "", snippet or "", raw_text or "", notes or "", query or ""])
        policy = PolicyGate.evaluate_query(text)
        if not policy.get("ok"):
            raise ValueError("Capture blockiert: Inhalt/Query verletzt die eingebauten OSINT-Guardrails.")
        sens = PolicyGate.classify_sensitivity(text)
        capture_id = new_id("cap")
        ts = now_ts()
        content_payload = {
            "capture_id": capture_id,
            "case_id": case_id,
            "task_id": task_id,
            "title": title,
            "url": url,
            "host": self._host(url),
            "query": query,
            "snippet": snippet,
            "raw_text": raw_text,
            "notes": notes,
            "captured_at": ts,
            "capture_mode": "manual_public_snapshot",
            "guardrail": "public_sources_only_no_login_no_bypass",
            "sensitivity": sens,
        }
        content_json = json.dumps(content_payload, ensure_ascii=False, indent=2, sort_keys=True)
        content_hash = self.sha256_text(content_json)
        metadata = {"case_id": case_id, "task_id": task_id, "url": url, "captured_at": ts, "content_hash": content_hash, "mode": "manual_public_snapshot"}
        metadata_hash = self.sha256_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        case_dir = self.storage_dir / self._safe_name(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / f"{ts.replace(':','').replace('-','')}_{self._safe_name(title)}_{capture_id}.json"
        path.write_text(content_json, encoding="utf-8")
        review_item = self.review.add_manual_hit(case_id, title, url, snippet, source_type="web", provider="search_workbench_capture", query=query, score=score, notes=notes)
        self.db.execute("""INSERT INTO source_captures(capture_id,case_id,task_id,review_item_id,title,url,host,snippet,query,storage_path,content_hash,metadata_hash,captured_at,captured_by,capture_mode,chain_status,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [capture_id, case_id, task_id or None, review_item["item_id"], title, url, self._host(url), snippet, query, str(path), content_hash, metadata_hash, ts, "local-analyst", "manual_public_snapshot", "captured_to_review", notes])
        if task_id:
            self.db.execute("UPDATE search_tasks SET status=? WHERE task_id=?", ["captured", task_id])
        self._chain_event(case_id, "source_capture", capture_id, "captured", {"url": url, "path": str(path), "content_hash": content_hash, "review_item_id": review_item["item_id"], "sensitivity": sens})
        self.audit.log("capture", "source_capture", capture_id, case_id, {"url": url, "review_item_id": review_item["item_id"], "content_hash": content_hash})
        return self.get_capture(capture_id)

    def get_capture(self, capture_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM source_captures WHERE capture_id=?", [capture_id])
        if not row:
            raise KeyError("Capture nicht gefunden.")
        return row

    def list_captures(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM source_captures WHERE case_id=? ORDER BY captured_at DESC", [case_id])

    def list_chain_events(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM chain_events WHERE case_id=? ORDER BY timestamp DESC", [case_id])

    def capture_manifest(self, case_id: str) -> Dict[str, Any]:
        captures = self.list_captures(case_id)
        issues = []
        for cap in captures:
            path = Path(cap.get("storage_path") or "")
            if not path.exists():
                issues.append({"capture_id": cap.get("capture_id"), "issue": "snapshot_file_missing"})
                continue
            current_hash = self.sha256_text(path.read_text(encoding="utf-8"))
            if current_hash != cap.get("content_hash"):
                issues.append({"capture_id": cap.get("capture_id"), "issue": "content_hash_mismatch"})
        return {"ok": not issues, "gate": "CAPTURE_CHAIN_PASS" if not issues else "CAPTURE_CHAIN_REVIEW", "captures": len(captures), "issues": issues}
