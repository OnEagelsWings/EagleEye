from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, dumps, new_id
from eagleeye_pro.audit.service import AuditService

DEFAULT_PROVIDERS = [
    ("Search: Bing", "search_engine", "https://www.bing.com/search?q=", 1, 0, "manual/browser", 1, ["public-web", "no-bypass", "human-review"], "Manuelle Such-URL; keine Umgehung von Schutzmechanismen."),
    ("Search: DuckDuckGo", "search_engine", "https://duckduckgo.com/?q=", 1, 0, "manual/browser", 1, ["public-web", "no-bypass", "human-review"], "Manuelle Such-URL."),
    ("Search: Brave", "search_engine", "https://search.brave.com/search?q=", 1, 0, "manual/browser", 1, ["public-web", "no-bypass", "human-review"], "Manuelle Such-URL."),
    ("Wayback Machine", "archive", "https://web.archive.org/", 1, 0, "respect-service-limits", 1, ["archive", "public-web", "historical-context"], "Nur öffentlich archivierte Seiten."),
    ("RDAP/WHOIS", "domain_infrastructure", "", 1, 0, "respect-registry-limits", 1, ["domain", "public-registry"], "Domain-/Infrastrukturkontext, keine Deanonymisierung erzwingen."),
    ("OpenCorporates/Firmendaten", "company_registry", "", 0, 1, "licensed/api", 1, ["company", "licensed", "api-key"], "Optionaler lizenzierter Provider."),
    ("GitHub Public Profiles", "public_profile", "https://github.com/", 1, 0, "manual/browser", 1, ["public-profile", "technical-footprint"], "Nur öffentlich sichtbare Profil-/Repo-Informationen."),
]

SOURCE_CATALOG = [
    ("Öffentliche Suchmaschinen", "search", "public", "global", 0, "Recherche öffentlich indexierter Inhalte", "Captcha-Bypass, Login-Umgehung, Massenscraping", "low", "Prüfung und Speicherung nur fallbezogen."),
    ("Presse und Archive", "media", "public/licensed", "DE/EU/global", 0, "Reputations-, Ereignis- und Kontextprüfung", "Paywall-Umgehung, Volltextkopien ohne Recht", "low", "Quellenzitat und Abrufzeitpunkt sichern."),
    ("Register/Firmenquellen", "registry", "public/licensed", "DE/EU", 0, "Berufs-/Firmen- und Organbezüge", "Zweckfreie Massenerhebung", "medium", "Lizenzbedingungen beachten."),
    ("Öffentliche Berufsprofile", "profile", "public", "global", 0, "Berufliche Identitätsanker", "Scraping privater/geschützter Bereiche", "medium", "Kandidatenstatus beibehalten."),
    ("Domain/DNS/RDAP", "infrastructure", "public", "global", 0, "Domain- und Organisationsbezüge", "Umgehung von Privacy-Services oder Angriffe", "medium", "Technischer Kontext, keine intrusive Scans."),
    ("Bilder/Medien-Metadaten", "media_analysis", "case-provided/public", "DE/EU", 0, "Dokumentation sichtbarer und technischer Metadaten", "automatische biometrische Identifizierung", "high", "Nur nicht-invasive Analyse und manuelle Bewertung."),
]

class ProviderRegistry:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def seed_defaults(self) -> Dict[str, int]:
        providers_added = 0
        sources_added = 0
        for name, provider_type, base_url, enabled, requires_api_key, rate_limit_hint, public_only, tags, notes in DEFAULT_PROVIDERS:
            existing = self.db.one("SELECT provider_id FROM provider_registry WHERE name=?", [name])
            if not existing:
                self.db.execute("""INSERT INTO provider_registry(provider_id,name,provider_type,base_url,enabled,requires_api_key,rate_limit_hint,public_only,compliance_tags_json,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [new_id("prov"), name, provider_type, base_url, enabled, requires_api_key, rate_limit_hint, public_only, dumps(tags), notes])
                providers_added += 1
        for name, category, access_model, jurisdiction, requires_api_key, allowed, prohibited, default_risk, notes in SOURCE_CATALOG:
            existing = self.db.one("SELECT source_id FROM source_catalog WHERE name=?", [name])
            if not existing:
                self.db.execute("""INSERT INTO source_catalog(source_id,name,category,access_model,jurisdiction,requires_api_key,allowed_use,prohibited_use,default_risk,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [new_id("src"), name, category, access_model, jurisdiction, requires_api_key, allowed, prohibited, default_risk, notes])
                sources_added += 1
        self.audit.log("seed", "provider_registry", None, None, {"providers_added": providers_added, "sources_added": sources_added})
        return {"providers_added": providers_added, "sources_added": sources_added}

    def list_providers(self, enabled_only: bool=False) -> List[Dict[str, Any]]:
        if enabled_only:
            return self.db.all("SELECT * FROM provider_registry WHERE enabled=1 ORDER BY provider_type,name")
        return self.db.all("SELECT * FROM provider_registry ORDER BY provider_type,name")

    def list_sources(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM source_catalog ORDER BY default_risk, category, name")

    def provider_compliance_matrix(self) -> List[Dict[str, Any]]:
        out=[]
        for p in self.list_providers():
            out.append({
                "provider": p["name"],
                "type": p["provider_type"],
                "enabled": bool(p["enabled"]),
                "public_only": bool(p["public_only"]),
                "requires_api_key": bool(p["requires_api_key"]),
                "tags": p["compliance_tags_json"],
                "risk_note": p.get("notes", ""),
            })
        return out
