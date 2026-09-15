from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List
from urllib.parse import quote_plus

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.search_planning.name_variants import generate_name_variants
from eagleeye_pro.search_planning.query_templates import PERSON_TEMPLATES, ORG_TEMPLATES, INCIDENT_TEMPLATES, QueryTemplate
from eagleeye_pro.sources.registry import SourceIntelligenceRegistry


@dataclass(frozen=True)
class SearchParameter:
    query: str
    source_category: str
    source_key_hint: str
    expected_evidence: str
    priority: int
    purpose: str
    review_required: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class SearchParameterExpander:
    """Build 50.0 precision search planner.

    It generates source-class-aware search parameters. It does not execute searches.
    All generated parameters include purpose, expected evidence and source policy metadata.
    """

    def __init__(self, db: Database, audit: AuditService, sources: SourceIntelligenceRegistry):
        self.db = db
        self.audit = audit
        self.sources = sources
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS search_plans_46 (
          plan_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT DEFAULT '',
          mode TEXT NOT NULL,
          input_json TEXT NOT NULL,
          generated_at TEXT NOT NULL,
          generated_by TEXT DEFAULT 'local-analyst',
          source_count INTEGER DEFAULT 0,
          parameter_count INTEGER DEFAULT 0,
          status TEXT DEFAULT 'planned',
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS search_parameters_46 (
          parameter_id TEXT PRIMARY KEY,
          plan_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT DEFAULT '',
          mode TEXT NOT NULL,
          query TEXT NOT NULL,
          source_category TEXT NOT NULL,
          source_key_hint TEXT NOT NULL,
          expected_evidence TEXT NOT NULL,
          priority INTEGER DEFAULT 50,
          purpose TEXT NOT NULL,
          review_required INTEGER DEFAULT 1,
          status TEXT DEFAULT 'planned',
          search_url TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(plan_id) REFERENCES search_plans_46(plan_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_search_params_46_case ON search_parameters_46(case_id, priority DESC, source_category);
        CREATE INDEX IF NOT EXISTS idx_search_params_46_plan ON search_parameters_46(plan_id, priority DESC);
        ''')
        self.db.conn.commit()

    def create_plan(self, case_id: str, mode: str, seed: Dict[str, Any], target_id: str = "", notes: str = "") -> Dict[str, Any]:
        mode = (mode or "person").strip().lower()
        if mode == "person":
            params = self.expand_person(seed)
        elif mode in {"organization", "organisation", "org"}:
            mode = "organization"
            params = self.expand_organization(seed)
        elif mode in {"incident", "event", "ereignis"}:
            mode = "incident"
            params = self.expand_incident(seed)
        else:
            raise ValueError(f"Unsupported search plan mode: {mode}")

        plan_id = new_id("plan46")
        source_keys = sorted({p.source_key_hint for p in params})
        self.db.execute('''INSERT INTO search_plans_46(plan_id,case_id,target_id,mode,input_json,generated_at,source_count,parameter_count,notes)
        VALUES(?,?,?,?,?,?,?,?,?)''', [plan_id, case_id, target_id, mode, dumps(seed), now_ts(), len(source_keys), len(params), notes])
        for p in params:
            self._insert_param(plan_id, case_id, target_id, mode, p)
        result = self.get_plan(plan_id)
        self.audit.log("create", "search_plan_46", plan_id, case_id, {"mode": mode, "parameter_count": len(params), "source_count": len(source_keys)})
        return result

    def _insert_param(self, plan_id: str, case_id: str, target_id: str, mode: str, p: SearchParameter) -> None:
        pid = new_id("param46")
        search_url = "https://www.google.com/search?q=" + quote_plus(p.query)
        self.db.execute('''INSERT INTO search_parameters_46(parameter_id,plan_id,case_id,target_id,mode,query,source_category,source_key_hint,expected_evidence,priority,purpose,review_required,status,search_url,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [pid, plan_id, case_id, target_id, mode, p.query, p.source_category, p.source_key_hint, p.expected_evidence, int(p.priority), p.purpose, int(p.review_required), "planned", search_url, now_ts()])

    def _policy_enrich(self, template: QueryTemplate, query: str) -> SearchParameter:
        policy = self.sources.source_policy_summary(template.source_key_hint)
        if not policy.get("allowed"):
            review_required = True
            expected = template.expected_evidence + " (source not registered; review blocked)"
        else:
            review_required = bool(policy.get("requires_manual_review", True))
            expected = policy.get("expected_evidence") or template.expected_evidence
        return SearchParameter(query=query, source_category=template.source_category, source_key_hint=template.source_key_hint, expected_evidence=expected, priority=template.priority, purpose=template.purpose, review_required=review_required)

    def expand_person(self, seed: Dict[str, Any]) -> List[SearchParameter]:
        name = str(seed.get("name") or seed.get("person_name") or "").strip()
        if not name:
            raise ValueError("Person search requires name")
        aliases = seed.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [a.strip() for a in aliases.split(",") if a.strip()]
        names = generate_name_variants(name, aliases, max_variants=42)
        places = _as_list(seed.get("places") or seed.get("locations") or seed.get("place"))[:8]
        years = _date_hints(seed)[:6]
        orgs = _as_list(seed.get("organizations") or seed.get("companies") or seed.get("org"))[:6]
        params: List[SearchParameter] = []
        for variant in names:
            for t in PERSON_TEMPLATES:
                params.append(self._policy_enrich(t, t.template.format(name=variant)))
                if len(params) >= 76:
                    break
            if len(params) >= 76:
                break
        for place in places:
            for variant in names[:8]:
                params.append(self._policy_enrich(PERSON_TEMPLATES[0], f'"{variant}" "{place}"'))
                params.append(self._policy_enrich(PERSON_TEMPLATES[12], f'"{variant}" "{place}" filetype:pdf'))
        for year in years:
            for variant in names[:8]:
                params.append(self._policy_enrich(PERSON_TEMPLATES[4], f'"{variant}" "{year}" Zeitung OR Archiv OR Nachruf'))
                params.append(self._policy_enrich(PERSON_TEMPLATES[2], f'"{variant}" "{year}" Gericht OR Urteil OR Prozess'))
        for org in orgs:
            for variant in names[:8]:
                params.append(self._policy_enrich(PERSON_TEMPLATES[12], f'"{variant}" "{org}" Team OR Vorstand OR Mitarbeiter OR filetype:pdf'))
        return _dedupe(params, limit=140)

    def expand_organization(self, seed: Dict[str, Any]) -> List[SearchParameter]:
        name = str(seed.get("name") or seed.get("organization_name") or seed.get("org_name") or "").strip()
        if not name:
            raise ValueError("Organization search requires name")
        aliases = _as_list(seed.get("aliases") or seed.get("old_names"))
        names = _dedupe_strings([name, *aliases, name.replace("e.V.", "").strip(), name.replace("GmbH", "").strip(), name.replace("gGmbH", "").strip()], limit=24)
        places = _as_list(seed.get("places") or seed.get("seat") or seed.get("location"))[:8]
        params: List[SearchParameter] = []
        for n in names:
            for t in ORG_TEMPLATES:
                params.append(self._policy_enrich(t, t.template.format(name=n)))
        for place in places:
            for n in names[:10]:
                params.append(self._policy_enrich(ORG_TEMPLATES[0], f'"{n}" "{place}" Handelsregister OR Vereinsregister'))
                params.append(self._policy_enrich(ORG_TEMPLATES[5], f'"{n}" "{place}" Satzung OR Vorstand filetype:pdf'))
                params.append(self._policy_enrich(ORG_TEMPLATES[8], f'"{n}" "{place}" Presse OR Amtsblatt'))
        return _dedupe(params, limit=120)

    def expand_incident(self, seed: Dict[str, Any]) -> List[SearchParameter]:
        place = str(seed.get("place") or seed.get("location") or seed.get("ort") or "").strip()
        if not place:
            place = ""
        date_hint = str(seed.get("date") or seed.get("date_hint") or seed.get("zeitraum") or "").strip()
        keywords = _as_list(seed.get("keywords") or seed.get("incident_terms") or seed.get("terms"))[:10]
        orgs = _as_list(seed.get("organizations") or seed.get("orgs"))[:8]
        persons = _as_list(seed.get("persons") or seed.get("names"))[:8]
        params: List[SearchParameter] = []
        for t in INCIDENT_TEMPLATES:
            params.append(self._policy_enrich(t, t.template.format(place=place, date_hint=date_hint)))
        for kw in keywords:
            for t in INCIDENT_TEMPLATES:
                params.append(self._policy_enrich(t, t.template.format(place=place or kw, date_hint=date_hint or kw) + f' "{kw}"'))
        for org in orgs:
            params.append(self._policy_enrich(INCIDENT_TEMPLATES[3], f'"{org}" "{place}" "{date_hint}" antisemitisch OR Bedrohung OR Vorfall'))
            params.append(self._policy_enrich(INCIDENT_TEMPLATES[2], f'"{org}" "{place}" Presse OR Bericht OR Sicherheit'))
        for person in persons:
            variants = generate_name_variants(person, [], max_variants=8)
            for v in variants:
                params.append(self._policy_enrich(INCIDENT_TEMPLATES[2], f'"{v}" "{place}" "{date_hint}" Vorfall OR Polizei OR Bericht'))
                params.append(self._policy_enrich(INCIDENT_TEMPLATES[4], f'"{v}" "{place}" Gericht OR Staatsanwaltschaft OR Anklage'))
        if not params:
            params.append(self._policy_enrich(INCIDENT_TEMPLATES[2], f'"{date_hint}" "{place}" Vorfall'))
        return _dedupe(params, limit=90)

    def get_plan(self, plan_id: str) -> Dict[str, Any]:
        plan = self.db.one("SELECT * FROM search_plans_46 WHERE plan_id=?", [plan_id])
        if not plan:
            raise KeyError(plan_id)
        plan["input"] = loads(plan.pop("input_json", "{}"), {})
        plan["parameters"] = self.db.all("SELECT * FROM search_parameters_46 WHERE plan_id=? ORDER BY priority DESC, created_at ASC", [plan_id])
        return plan

    def list_plans(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM search_plans_46 WHERE case_id=? ORDER BY generated_at DESC", [case_id])
        for r in rows:
            r["input"] = loads(r.pop("input_json", "{}"), {})
        return rows


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value.strip()] if value.strip() else []
    return [str(v).strip() for v in value if str(v).strip()]


def _date_hints(seed: Dict[str, Any]) -> List[str]:
    values = []
    for key in ["birth_year", "death_year", "marriage_year", "year", "date", "date_hint"]:
        if seed.get(key):
            values.append(str(seed[key]))
    return _dedupe_strings(values, limit=12)


def _dedupe(params: Iterable[SearchParameter], limit: int) -> List[SearchParameter]:
    out: List[SearchParameter] = []
    seen: set[tuple[str, str]] = set()
    for p in params:
        key = (p.query.lower(), p.source_key_hint)
        if key in seen:
            continue
        seen.add(key); out.append(p)
        if len(out) >= limit:
            break
    return out


def _dedupe_strings(values: Iterable[str], limit: int) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for v in values:
        v = (v or "").strip()
        if not v:
            continue
        key = v.lower()
        if key not in seen:
            seen.add(key); out.append(v)
        if len(out) >= limit:
            break
    return out
