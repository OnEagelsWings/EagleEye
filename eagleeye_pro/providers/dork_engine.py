from __future__ import annotations
from typing import Dict, List
from urllib.parse import quote_plus
from eagleeye_pro.core.database import Database, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate

ENGINES = {
    "Google": "https://www.google.com/search?q={q}",
    "Bing": "https://www.bing.com/search?q={q}",
    "DuckDuckGo": "https://duckduckgo.com/?q={q}",
    "Brave": "https://search.brave.com/search?q={q}",
    "Startpage": "https://www.startpage.com/sp/search?query={q}",
    "Ecosia": "https://www.ecosia.org/search?q={q}",
    "Mojeek": "https://www.mojeek.com/search?q={q}",
    "Yahoo": "https://search.yahoo.com/search?p={q}",
    # Build 37.0: Bild-/Geo-Pfade aus Build 15.0 wieder eingebunden.
    # Nur normale öffentliche Such-/Kartenoberflächen, kein Login-, Captcha- oder Account-Bypass.
    "Google Bilder": "https://www.google.com/search?tbm=isch&q={q}",
    "Bing Bilder": "https://www.bing.com/images/search?q={q}",
    "Yandex Bilder": "https://yandex.com/images/search?text={q}",
    "TinEye URL": "https://tineye.com/search?url={q}",
    "Google Maps": "https://www.google.com/maps/search/{q}",
    "OpenStreetMap": "https://www.openstreetmap.org/search?query={q}",
    "Google News": "https://news.google.com/search?q={q}",
}

class DorkEngine:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    @staticmethod
    def _quote(s: str) -> str:
        s = (s or "").strip()
        return f'"{s}"' if s and " " in s else s

    def generate_queries(self, target: Dict[str, object]) -> List[Dict[str, str]]:
        name = str(target.get("name", "")).strip()
        aliases = target.get("aliases_json") or []
        emails = target.get("emails_json") or []
        usernames = target.get("usernames_json") or []
        locations = target.get("locations_json") or []
        companies = target.get("companies_json") or []
        domains = target.get("domains_json") or []
        base = self._quote(name)
        queries: List[Dict[str, str]] = []
        def add(category: str, query: str):
            if query and PolicyGate.evaluate_query(query).get("ok"):
                queries.append({"category": category, "query": query})
        add("Identitätsanker", base)
        for loc in locations:
            add("Ortskontext", f"{base} {self._quote(loc)}")
        for company in companies:
            add("Beruf/Firma", f"{base} {self._quote(company)}")
            add("Register/Presse", f"{base} {self._quote(company)} Presse OR Register")
        for alias in aliases:
            add("Alias", f"{self._quote(alias)} {base}")
        for user in usernames:
            add("Username", f"{self._quote(user)}")
            add("Username + Name", f"{self._quote(user)} {base}")
        for email in emails:
            add("E-Mail", self._quote(email))
        for domain in domains:
            add("Domain", f"site:{domain} {base}")
            add("Impressum", f"site:{domain} impressum {base}")
        for site, cat in [
            ("linkedin.com/in", "Öffentliches Berufsprofil"),
            ("xing.com/profile", "Öffentliches Berufsprofil"),
            ("github.com", "Technisches Profil"),
            ("medium.com", "Publikationen"),
            ("researchgate.net", "Fachprofil"),
            ("orcid.org", "Fachprofil"),
        ]:
            add(cat, f"{base} site:{site}")
        add("Dokumente", f"{base} filetype:pdf")
        add("Presse", f"{base} Presse OR Interview OR Vortrag")
        add("Bild-/Medienpfad", f"{base} Foto OR Bild OR Pressefoto")
        if locations:
            for loc in locations:
                add("Geo-/Maps-Spur", f"{base} {self._quote(loc)}")
        else:
            add("Geo-/Maps-Spur", f"{base} Ort OR Adresse OR Standort")
        if companies:
            add("Gegenbelege/Namensdoppler", f"{base} -{self._quote(companies[0])}")
        else:
            add("Gegenbelege/Namensdoppler", f"{base} Namensdoppler")
        seen=set(); out=[]
        for q in queries:
            key=q["category"]+"|"+q["query"]
            if key not in seen:
                seen.add(key); out.append(q)
        return out

    def build_search_urls(self, queries: List[Dict[str, str]], engines: List[str] | None=None) -> List[Dict[str, str]]:
        selected = engines or list(ENGINES.keys())
        tasks=[]
        for q in queries:
            for engine in selected:
                template = ENGINES.get(engine)
                if template:
                    tasks.append({"category": q["category"], "query": q["query"], "engine": engine, "url": template.format(q=quote_plus(q["query"]))})
        return tasks

    def save_tasks(self, case_id: str, target_id: str, tasks: List[Dict[str, str]]) -> int:
        for t in tasks:
            self.db.execute("INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                [new_id("task"), case_id, target_id, t["category"], t["query"], t["engine"], t["url"], "planned", now_ts()])
        self.audit.log("generate", "search_tasks", target_id, case_id, {"count": len(tasks)})
        return len(tasks)

    def list_tasks(self, case_id: str) -> List[Dict[str, str]]:
        return self.db.all("SELECT * FROM search_tasks WHERE case_id=? ORDER BY created_at DESC", [case_id])
