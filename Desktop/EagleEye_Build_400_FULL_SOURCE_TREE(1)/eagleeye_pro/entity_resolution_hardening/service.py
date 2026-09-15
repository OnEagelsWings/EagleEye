from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


def _tokens(values: Any) -> List[str]:
    if isinstance(values, (list, tuple, set)):
        text = " ".join(str(v or "") for v in values)
    else:
        text = str(values or "")
    return [t.lower() for t in re.findall(r"[\wÄÖÜäöüß.-]{3,}", text)]


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


class EntityResolutionDopplerHardeningService:
    """Build 60.3: Entity resolution and namesake/doppler hardening.

    The service computes a visible fit matrix for each fund. It never confirms
    identity; it assigns fit and risk labels that force review before reporting.
    """

    def __init__(self, db: Database, audit: AuditService, *, case_cockpit=None, fund_intelligence=None, person_detail=None):
        self.db = db
        self.audit = audit
        self.case_cockpit = case_cockpit
        self.fund_intelligence = fund_intelligence
        self.person_detail = person_detail
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS entity_fingerprints_60_3 (
          fingerprint_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          fingerprint_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id)
        );
        CREATE TABLE IF NOT EXISTS entity_fit_assessments_60_3 (
          fit_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          name_match INTEGER DEFAULT 0,
          place_match INTEGER DEFAULT 0,
          organization_match INTEGER DEFAULT 0,
          role_match INTEGER DEFAULT 0,
          time_match INTEGER DEFAULT 0,
          domain_match INTEGER DEFAULT 0,
          contradiction_score INTEGER DEFAULT 0,
          identity_fit INTEGER DEFAULT 0,
          doppler_risk INTEGER DEFAULT 0,
          fit_label TEXT DEFAULT 'unknown',
          doppler_label TEXT DEFAULT 'unknown',
          anchors_json TEXT NOT NULL,
          contradictions_json TEXT NOT NULL,
          recommended_queries_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id, object_type, object_id)
        );
        CREATE INDEX IF NOT EXISTS idx_fit603_entity ON entity_fit_assessments_60_3(case_id, entity_id, identity_fit DESC);
        ''')
        self.db.conn.commit()

    def fingerprint(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        if not self.case_cockpit:
            raise RuntimeError("case_cockpit service not attached")
        ent = self.case_cockpit.get_entity(entity_id)
        fp = {
            "entity_id": entity_id,
            "display_name": ent.get("display_name", ""),
            "names": [ent.get("display_name", "")] + (ent.get("known_names") or []) + (ent.get("aliases") or []),
            "places": ent.get("places") or [],
            "organizations": ent.get("organizations") or [],
            "roles": ent.get("roles") or [],
            "dates": ent.get("dates") or [],
            "identifiers": ent.get("identifiers") or [],
            "public_links": ent.get("public_links") or [],
            "exclude_terms": [],
        }
        fp["name_tokens"] = sorted(set(_tokens(fp["names"])))
        fp["place_tokens"] = sorted(set(_tokens(fp["places"])))
        fp["organization_tokens"] = sorted(set(_tokens(fp["organizations"])))
        fp["role_tokens"] = sorted(set(_tokens(fp["roles"])))
        fp["date_tokens"] = sorted(set(_tokens(fp["dates"])))
        fp["domain_tokens"] = sorted(set([_domain(x) for x in (fp["public_links"] + fp["identifiers"]) if _domain(x)]))
        now = now_ts()
        existing = self.db.one("SELECT fingerprint_id FROM entity_fingerprints_60_3 WHERE case_id=? AND entity_id=?", [case_id, entity_id])
        if existing:
            fid = existing["fingerprint_id"]
            self.db.execute("UPDATE entity_fingerprints_60_3 SET fingerprint_json=?, updated_at=? WHERE fingerprint_id=?", [dumps(fp), now, fid])
        else:
            fid = new_id("fp603")
            self.db.execute("INSERT INTO entity_fingerprints_60_3(fingerprint_id,case_id,entity_id,fingerprint_json,created_at,updated_at) VALUES(?,?,?,?,?,?)", [fid, case_id, entity_id, dumps(fp), now, now])
        return {"fingerprint_id": fid, "case_id": case_id, "entity_id": entity_id, "fingerprint": fp}

    def assess_text(self, case_id: str, entity_id: str, object_type: str, object_id: str, *, title: str = "", url: str = "", snippet: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        fp = self.fingerprint(case_id, entity_id)["fingerprint"]
        hay = " ".join([title, url, snippet, dumps(metadata or {})]).lower()
        anchors: List[str] = []
        contradictions: List[str] = []
        name_match = self._score_tokens(fp["name_tokens"], hay, 40, anchors, "name")
        place_match = self._score_tokens(fp["place_tokens"], hay, 15, anchors, "place")
        org_match = self._score_tokens(fp["organization_tokens"], hay, 22, anchors, "organization")
        role_match = self._score_tokens(fp["role_tokens"], hay, 12, anchors, "role")
        time_match = self._score_tokens(fp["date_tokens"], hay, 8, anchors, "date")
        domain = _domain(url)
        domain_match = 10 if domain and any(d in domain or domain in d for d in fp["domain_tokens"]) else 0
        if domain_match:
            anchors.append("domain")
        contradiction_score = 0
        if name_match > 0 and place_match == 0 and fp["place_tokens"]:
            contradiction_score += 10; contradictions.append("kein bekannter Ortsanker")
        if name_match > 0 and org_match == 0 and fp["organization_tokens"]:
            contradiction_score += 10; contradictions.append("kein bekannter Organisationsanker")
        if name_match == 0:
            contradiction_score += 25; contradictions.append("Name/Variante nicht sichtbar")
        identity_fit = max(0, min(100, name_match + place_match + org_match + role_match + time_match + domain_match - contradiction_score))
        doppler_risk = max(0, min(100, (45 if name_match and identity_fit < 55 else 15) + contradiction_score - min(20, org_match + place_match)))
        fit_label = "hoch" if identity_fit >= 75 else ("mittel" if identity_fit >= 50 else ("niedrig" if identity_fit >= 25 else "widersprüchlich"))
        doppler_label = "hoch" if doppler_risk >= 55 else ("mittel" if doppler_risk >= 30 else "niedrig")
        recommended = self._recommended_queries(fp, fit_label, doppler_label)
        fit_id = self._upsert(case_id, entity_id, object_type, object_id, name_match, place_match, org_match, role_match, time_match, domain_match, contradiction_score, identity_fit, doppler_risk, fit_label, doppler_label, anchors, contradictions, recommended)
        return self.get_assessment(fit_id)

    def assess_capture_result(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        return self.assess_text(capture["case_id"], capture["entity_id"], "capture_result", capture["capture_result_id"], title=capture.get("title", ""), url=capture.get("url", ""), snippet=capture.get("snippet", ""), metadata=capture)

    def assess_person_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        return self.assess_text(finding["case_id"], finding["entity_id"], "person_finding", finding["finding_note_id"], title=finding.get("title", ""), url=finding.get("source_url", ""), snippet=finding.get("summary", ""), metadata=finding.get("metadata", {}))

    def doppler_clusters(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        rows = self.db.all("SELECT * FROM entity_fit_assessments_60_3 WHERE case_id=? AND entity_id=? ORDER BY identity_fit DESC", [case_id, entity_id])
        clusters: Dict[str, List[Dict[str, Any]]] = {"high_fit": [], "review_doppler": [], "likely_other": []}
        for r in rows:
            r["anchors"] = loads(r.pop("anchors_json", "[]"), [])
            r["contradictions"] = loads(r.pop("contradictions_json", "[]"), [])
            r["recommended_queries"] = loads(r.pop("recommended_queries_json", "[]"), [])
            if r["identity_fit"] >= 70 and r["doppler_risk"] < 40:
                clusters["high_fit"].append(r)
            elif r["doppler_risk"] >= 50 or r["identity_fit"] < 35:
                clusters["likely_other"].append(r)
            else:
                clusters["review_doppler"].append(r)
        return {"case_id": case_id, "entity_id": entity_id, "clusters": clusters, "counts": {k: len(v) for k, v in clusters.items()}}

    def list_assessments(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM entity_fit_assessments_60_3 WHERE case_id=? AND entity_id=? ORDER BY identity_fit DESC, updated_at DESC LIMIT ?", [case_id, entity_id, int(limit)])
        for r in rows:
            r["anchors"] = loads(r.pop("anchors_json", "[]"), [])
            r["contradictions"] = loads(r.pop("contradictions_json", "[]"), [])
            r["recommended_queries"] = loads(r.pop("recommended_queries_json", "[]"), [])
        return rows

    def get_assessment(self, fit_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM entity_fit_assessments_60_3 WHERE fit_id=?", [fit_id])
        if not row:
            raise KeyError(fit_id)
        row["anchors"] = loads(row.pop("anchors_json", "[]"), [])
        row["contradictions"] = loads(row.pop("contradictions_json", "[]"), [])
        row["recommended_queries"] = loads(row.pop("recommended_queries_json", "[]"), [])
        return row

    def _score_tokens(self, tokens: List[str], hay: str, max_score: int, anchors: List[str], label: str) -> int:
        if not tokens:
            return 0
        hits = [t for t in tokens if t and t.lower() in hay]
        if hits:
            anchors.append(f"{label}:{','.join(hits[:3])}")
        return int(max_score * min(1.0, len(set(hits)) / max(1, min(3, len(set(tokens))))))

    def _recommended_queries(self, fp: Dict[str, Any], fit_label: str, doppler_label: str) -> List[str]:
        name = fp.get("display_name", "")
        queries: List[str] = []
        if name:
            for place in (fp.get("places") or [])[:2]:
                queries.append(f'"{name}" "{place}"')
            for org in (fp.get("organizations") or [])[:2]:
                queries.append(f'"{name}" "{org}"')
            if doppler_label in {"mittel", "hoch"}:
                queries.append(f'"{name}" "nicht dieselbe Person"')
                queries.append(f'"{name}" -"{(fp.get("places") or [""])[0]}"' if fp.get("places") else f'"{name}" "anderer Ort"')
        return [q for q in queries if q.strip()]

    def _upsert(self, case_id: str, entity_id: str, object_type: str, object_id: str, name_match: int, place_match: int, org_match: int, role_match: int, time_match: int, domain_match: int, contradiction_score: int, identity_fit: int, doppler_risk: int, fit_label: str, doppler_label: str, anchors: List[str], contradictions: List[str], recommended: List[str]) -> str:
        existing = self.db.one("SELECT fit_id FROM entity_fit_assessments_60_3 WHERE case_id=? AND entity_id=? AND object_type=? AND object_id=?", [case_id, entity_id, object_type, object_id])
        now = now_ts()
        if existing:
            fid = existing["fit_id"]
            self.db.execute('''UPDATE entity_fit_assessments_60_3 SET name_match=?,place_match=?,organization_match=?,role_match=?,time_match=?,domain_match=?,contradiction_score=?,identity_fit=?,doppler_risk=?,fit_label=?,doppler_label=?,anchors_json=?,contradictions_json=?,recommended_queries_json=?,updated_at=? WHERE fit_id=?''', [name_match, place_match, org_match, role_match, time_match, domain_match, contradiction_score, identity_fit, doppler_risk, fit_label, doppler_label, dumps(anchors), dumps(contradictions), dumps(recommended), now, fid])
        else:
            fid = new_id("fit603")
            self.db.execute('''INSERT INTO entity_fit_assessments_60_3(fit_id,case_id,entity_id,object_type,object_id,name_match,place_match,organization_match,role_match,time_match,domain_match,contradiction_score,identity_fit,doppler_risk,fit_label,doppler_label,anchors_json,contradictions_json,recommended_queries_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [fid, case_id, entity_id, object_type, object_id, name_match, place_match, org_match, role_match, time_match, domain_match, contradiction_score, identity_fit, doppler_risk, fit_label, doppler_label, dumps(anchors), dumps(contradictions), dumps(recommended), now, now])
        return fid
