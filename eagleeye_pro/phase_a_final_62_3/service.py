from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
PRIVATE_HOST_RE = re.compile(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.|169\.254\.)", re.I)
TRACKING_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}

SENSITIVE_FLAGS = {
    "minor_data": ["minderjähr", "kind", "schüler", "school", "klasse"],
    "private_address": ["wohnadresse", "privatadresse", "anschrift", "adresse", "street", "straße"],
    "private_phone": ["telefon", "handy", "mobil", "phone"],
    "email_review": ["e-mail", "email", "@"],
    "legal_proceeding": ["gericht", "urteil", "beschluss", "aktenzeichen", "anklage", "prozess"],
    "financial_review": ["insolvenz", "jahresabschluss", "bilanz", "bundesanzeiger", "finanz"],
    "victim_witness": ["opfer", "zeuge", "zeugin", "victim", "witness"],
}

SOURCE_RULES: List[Tuple[str, str, int, List[str]]] = [
    ("court_or_justice", "court", 88, ["gericht", "justiz", "urteil", "beschluss", "aktenzeichen", "landgericht", "amtsgericht", "oberlandesgericht"]),
    ("registry", "registry", 86, ["handelsregister", "unternehmensregister", "registerportal", "vereinsregister", "bundesanzeiger"]),
    ("official_public_record", "registry", 84, ["amtsblatt", "bekanntmachung", "bund.de", "stadt", "kreis", "land.de"]),
    ("financial_public_record", "financial", 78, ["insolvenz", "jahresabschluss", "bilanz", "zuwendung", "förderung", "vergabe"]),
    ("public_pdf", "pdf", 72, [".pdf", "filetype:pdf", "pdf"]),
    ("newspaper_press", "press", 64, ["zeitung", "presse", "news", "artikel", "lokal", "nachrichten"]),
    ("image_media", "image", 48, ["foto", "bild", "image", "portrait", "pressefoto"]),
    ("archival_source", "archive", 66, ["archiv", "archive", "kirchenbuch", "taufe", "trauung", "sterberegister", "geburtsregister"]),
    ("social_public_profile", "web", 52, ["linkedin", "xing", "facebook", "instagram", "twitter", "x.com", "github"]),
]


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _domain(url: str) -> str:
    try:
        return URLPolicy.normalize_public_url(url).get("host", "")
    except Exception:
        return ""


def _canonical(url: str) -> str:
    try:
        return URLPolicy.canonicalize_url(url) or url
    except Exception:
        return url


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _tokens(value: Any) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        text = " ".join(str(v or "") for v in value)
    else:
        text = str(value or "")
    return [t.lower() for t in re.findall(r"[\wÄÖÜäöüß.-]{3,}", text)]


def _unique(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = _clean(item)
        key = s.lower()
        if s and key not in seen:
            seen.add(key); out.append(s)
    return out


class PhaseAFinalCaptureService:
    """Build 62.1 Final: stronger browser/SERP capture layer.

    It remains user-initiated. It normalizes visible result blocks, canonicalizes
    URLs, rejects local/private URLs and attaches an import quality profile so
    downstream ranking is less dependent on manual cleanup.
    """

    def __init__(self, db: Database, audit: AuditService, *, capture_pro=None, browser_helper=None):
        self.db = db
        self.audit = audit
        self.capture_pro = capture_pro
        self.browser_helper = browser_helper
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS capture_final_imports_62_1 (
          final_import_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          import_mode TEXT NOT NULL,
          category_key TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          raw_hash TEXT NOT NULL,
          imported_count INTEGER DEFAULT 0,
          duplicate_count INTEGER DEFAULT 0,
          rejected_count INTEGER DEFAULT 0,
          quality_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS capture_final_results_62_1 (
          final_result_id TEXT PRIMARY KEY,
          final_import_id TEXT NOT NULL,
          capture_result_id TEXT DEFAULT '',
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          canonical_url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          position INTEGER DEFAULT 0,
          source_guess TEXT DEFAULT 'public_web',
          quality_score INTEGER DEFAULT 0,
          duplicate_key TEXT NOT NULL,
          import_warnings_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id, duplicate_key)
        );
        CREATE INDEX IF NOT EXISTS idx_capfinal621_entity ON capture_final_results_62_1(case_id, entity_id, quality_score DESC);
        ''')
        self.db.conn.commit()

    def import_clipboard(self, case_id: str, entity_id: str, raw_text: str, *, category_key: str = "", query: str = "", engine: str = "browser_clipboard") -> Dict[str, Any]:
        raw = str(raw_text or "").strip()
        if not raw:
            raise ValueError("Bitte einen sichtbaren SERP-Block, eine URL oder Capture-JSON einfügen.")
        # JSON payload first, then robust SERP block parser.
        payload = self._try_json(raw)
        items = [self._item_from_payload(payload)] if payload else self.parse_serp_block(raw)
        return self._import_items(case_id, entity_id, items, import_mode="clipboard", category_key=category_key, query=query, engine=engine, raw_hash=_sha(raw)[:32])

    def import_url(self, case_id: str, entity_id: str, url: str, *, title: str = "", snippet: str = "", category_key: str = "", query: str = "", engine: str = "manual_url") -> Dict[str, Any]:
        item = {"title": title or _domain(url) or url, "url": url, "snippet": snippet, "position": 1}
        return self._import_items(case_id, entity_id, [item], import_mode="single_url", category_key=category_key, query=query, engine=engine, raw_hash=_sha(url, title, snippet)[:32])

    def parse_serp_block(self, raw_text: str) -> List[Dict[str, Any]]:
        lines = [_clean(x) for x in str(raw_text or "").splitlines() if _clean(x)]
        results: List[Dict[str, Any]] = []
        seen = set()
        i = 0
        while i < len(lines):
            line = lines[i]
            urls = URL_RE.findall(line)
            if urls:
                for url in urls:
                    canonical = _canonical(url.rstrip(".,;"))
                    # Keep within-batch duplicates so the importer can report them.
                    if canonical in seen:
                        duplicate_hint = True
                    else:
                        duplicate_hint = False; seen.add(canonical)
                    title = self._nearest_title(lines, i)
                    snippet = self._nearby_snippet(lines, i)
                    results.append({"title": title or _domain(url) or url, "url": url.rstrip(".,;"), "snippet": snippet, "position": len(results) + 1, "duplicate_hint": duplicate_hint})
            elif i + 1 < len(lines) and URL_RE.search(lines[i + 1]):
                # Common SERP paste pattern: title line followed by URL line.
                pass
            i += 1
        if not results and URL_RE.search(raw_text or ""):
            for url in URL_RE.findall(raw_text):
                results.append({"title": _domain(url) or url, "url": url.rstrip(".,;"), "snippet": _clean(raw_text)[:900], "position": len(results) + 1})
        return results

    def list_final_results(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM capture_final_results_62_1 WHERE case_id=? AND entity_id=? ORDER BY quality_score DESC, created_at DESC LIMIT ?", [case_id, entity_id, int(limit)])
        for r in rows:
            r["import_warnings"] = loads(r.pop("import_warnings_json", "[]"), [])
        return rows

    def _import_items(self, case_id: str, entity_id: str, items: List[Dict[str, Any]], *, import_mode: str, category_key: str, query: str, engine: str, raw_hash: str) -> Dict[str, Any]:
        if not case_id or not entity_id:
            raise ValueError("case_id und entity_id sind erforderlich.")
        final_import_id = new_id("capfinal621")
        now = now_ts()
        imported: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        duplicate_count = 0
        seen_in_batch = set()
        for pos, item in enumerate(items, start=1):
            url = _clean(item.get("url", ""))
            canonical_for_batch = _canonical(url) if url else ""
            if canonical_for_batch and (canonical_for_batch in seen_in_batch or item.get("duplicate_hint")):
                duplicate_count += 1
                continue
            if canonical_for_batch:
                seen_in_batch.add(canonical_for_batch)
            warnings = self._url_warnings(url)
            if any(w.startswith("blocked_") for w in warnings):
                rejected.append({"url": url, "warnings": warnings}); continue
            canonical = _canonical(url)
            dup_key = _sha(canonical)[:32]
            existing = self.db.one("SELECT * FROM capture_final_results_62_1 WHERE case_id=? AND entity_id=? AND duplicate_key=?", [case_id, entity_id, dup_key])
            if existing:
                duplicate_count += 1; continue
            title = _clean(item.get("title") or _domain(url) or url)[:240]
            snippet = _clean(item.get("snippet") or "")[:1200]
            source_guess = self._source_guess(url, title, snippet, category_key)
            quality_score = self._quality_score(title, url, snippet, source_guess, pos, warnings)
            capture_id = ""
            if self.capture_pro:
                cap = self.capture_pro.import_url(case_id, entity_id, url, title=title, snippet=snippet, category_key=category_key, query=query, engine=engine).get("result", {})
                capture_id = cap.get("capture_result_id", "")
            final_result_id = new_id("capres621")
            self.db.execute('''INSERT INTO capture_final_results_62_1(final_result_id,final_import_id,capture_result_id,case_id,entity_id,title,url,canonical_url,domain,snippet,position,source_guess,quality_score,duplicate_key,import_warnings_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [final_result_id, final_import_id, capture_id, case_id, entity_id, title, url, canonical, _domain(url), snippet, int(item.get("position") or pos), source_guess, quality_score, dup_key, dumps(warnings), now])
            row = self.db.one("SELECT * FROM capture_final_results_62_1 WHERE final_result_id=?", [final_result_id]) or {}
            row["import_warnings"] = warnings
            imported.append(row)
        quality = {
            "raw_items": len(items), "imported": len(imported), "duplicates": duplicate_count, "rejected": len(rejected),
            "mean_quality": int(sum(int(x.get("quality_score", 0)) for x in imported) / max(1, len(imported))),
            "blocked_urls": rejected,
        }
        self.db.execute('''INSERT INTO capture_final_imports_62_1(final_import_id,case_id,entity_id,import_mode,category_key,query,engine,raw_hash,imported_count,duplicate_count,rejected_count,quality_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', [final_import_id, case_id, entity_id, import_mode, category_key, query, engine, raw_hash, len(imported), duplicate_count, len(rejected), dumps(quality), now])
        self.audit.log("import", "capture_final_62_1", final_import_id, case_id, {"entity_id": entity_id, "imported": len(imported), "duplicates": duplicate_count, "rejected": len(rejected)})
        return {"final_import_id": final_import_id, "count": len(imported), "duplicates": duplicate_count, "rejected": rejected, "quality": quality, "results": imported}

    def _nearest_title(self, lines: List[str], idx: int) -> str:
        for j in range(idx - 1, max(-1, idx - 5), -1):
            if j >= 0 and not URL_RE.search(lines[j]) and len(lines[j]) > 2 and not lines[j].lower().startswith(("http", "www.")):
                return lines[j]
        return ""

    def _nearby_snippet(self, lines: List[str], idx: int) -> str:
        parts: List[str] = []
        for j in range(idx + 1, min(len(lines), idx + 5)):
            if not URL_RE.search(lines[j]):
                parts.append(lines[j])
        return _clean(" ".join(parts))[:1200]

    def _try_json(self, raw: str) -> Dict[str, Any] | None:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _item_from_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"title": data.get("title") or data.get("name") or "Browser Capture", "url": data.get("url") or data.get("href") or "", "snippet": data.get("snippet") or data.get("selection") or data.get("text") or data.get("description") or "", "position": int(data.get("position") or 1)}

    def _url_warnings(self, url: str) -> List[str]:
        decision = URLPolicy.validate_capture_url(url)
        warnings: List[str] = list(decision.get("warnings") or [])
        if not decision.get("ok"):
            reason = decision.get("blocked_reason") or "blocked_url_policy"
            if reason.startswith("blocked_scheme"):
                warnings.append("blocked_non_http_url")
            elif reason == "blocked_missing_host":
                warnings.append("blocked_missing_host")
            else:
                warnings.append(reason)
        return warnings

    def _source_guess(self, url: str, title: str, snippet: str, category_key: str = "") -> str:
        hay = " ".join([url, title, snippet, category_key]).lower()
        for source_type, _finding_type, _base, terms in SOURCE_RULES:
            if any(t in hay for t in terms):
                return source_type
        return "public_web"

    def _quality_score(self, title: str, url: str, snippet: str, source_guess: str, position: int, warnings: List[str]) -> int:
        base_map = {s: base for s, _ft, base, _terms in SOURCE_RULES}
        score = base_map.get(source_guess, 50)
        if title and title != url:
            score += 5
        if snippet:
            score += 6
        if position <= 3:
            score += 6
        elif position <= 10:
            score += 2
        if warnings:
            score -= 8 * len(warnings)
        return max(0, min(100, score))


class FundIntelligenceFinalService:
    """Build 62.2 Final: converts capture-final results into full findings with
    source-type, sensitivity, claim proposal and export-readiness metadata.
    """

    def __init__(self, db: Database, audit: AuditService, *, capture_final=None, fund_intel=None, person_detail=None):
        self.db = db
        self.audit = audit
        self.capture_final = capture_final
        self.fund_intel = fund_intel
        self.person_detail = person_detail
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS fund_final_profiles_62_2 (
          fund_profile_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          final_result_id TEXT DEFAULT '',
          capture_result_id TEXT DEFAULT '',
          person_finding_id TEXT DEFAULT '',
          source_type TEXT NOT NULL,
          finding_type TEXT NOT NULL,
          source_quality INTEGER DEFAULT 0,
          sensitivity_level TEXT DEFAULT 'normal',
          sensitivity_flags_json TEXT NOT NULL,
          evidence_level TEXT DEFAULT 'candidate',
          suggested_status TEXT DEFAULT 'candidate',
          export_status TEXT DEFAULT 'review_required',
          claim_proposal_json TEXT NOT NULL,
          next_action TEXT DEFAULT 'review',
          explanation TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id, final_result_id)
        );
        CREATE INDEX IF NOT EXISTS idx_fundfinal622_entity ON fund_final_profiles_62_2(case_id, entity_id, source_quality DESC);
        ''')
        self.db.conn.commit()

    def import_final_result(self, final_result_id: str, *, analyst_note: str = "") -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM capture_final_results_62_1 WHERE final_result_id=?", [final_result_id])
        if not row:
            raise KeyError(final_result_id)
        analysis = self.analyze_result(row)
        person_finding_id = ""
        # Prefer existing 60.2 import if we have a capture_result_id; it creates a compatible person finding.
        if row.get("capture_result_id") and self.fund_intel:
            try:
                imported = self.fund_intel.import_capture_to_person_file(row["capture_result_id"], analyst_note=analyst_note)
                person_finding_id = imported.get("person_finding_id", "")
            except Exception:
                person_finding_id = ""
        if not person_finding_id and self.person_detail:
            finding = self.person_detail.add_finding_note(
                row["case_id"], row["entity_id"], title=row.get("title", "Fund"), summary=row.get("snippet") or row.get("url", ""),
                finding_type=analysis["finding_type"], source_url=row.get("url", ""), category=row.get("source_guess", "public_web"),
                status=analysis["suggested_status"], analyst_note=analyst_note or analysis["explanation"], evidence_level=analysis["evidence_level"],
                redaction_required=analysis["export_status"] != "export_ready", metadata={"build": "62.2-final", "final_result_id": final_result_id, "claim_proposal": analysis["claim_proposal"]},
            )
            person_finding_id = finding.get("finding_note_id", "")
        profile_id = self._upsert(row, analysis, person_finding_id)
        out = self.get_profile(profile_id)
        out["capture_final_result"] = row
        return out

    def import_all_for_entity(self, case_id: str, entity_id: str, limit: int = 200) -> Dict[str, Any]:
        rows = self.capture_final.list_final_results(case_id, entity_id, limit=limit) if self.capture_final else []
        profiles = [self.import_final_result(r["final_result_id"]) for r in rows]
        return {"case_id": case_id, "entity_id": entity_id, "count": len(profiles), "profiles": profiles}

    def analyze_result(self, row: Dict[str, Any]) -> Dict[str, Any]:
        hay = " ".join([row.get("title", ""), row.get("url", ""), row.get("snippet", ""), row.get("source_guess", "")]).lower()
        source_type = row.get("source_guess") or "public_web"
        finding_type = next((ft for st, ft, _base, _terms in SOURCE_RULES if st == source_type), "web")
        base = next((base for st, _ft, base, _terms in SOURCE_RULES if st == source_type), 50)
        quality = max(0, min(100, int(row.get("quality_score", 0) or base)))
        flags: List[str] = []
        for flag, terms in SENSITIVE_FLAGS.items():
            if any(t in hay for t in terms):
                flags.append(flag)
        flags = _unique(flags)
        sensitivity_level = "high" if any(f in flags for f in ["minor_data", "victim_witness", "private_address"]) else ("medium" if flags else "normal")
        evidence_level = "strong_indicator" if quality >= 82 and sensitivity_level == "normal" else ("review_indicator" if quality >= 62 else "candidate")
        suggested_status = "review_required" if sensitivity_level != "normal" or source_type in {"court_or_justice", "image_media"} else ("report_ready" if quality >= 85 else "included")
        export_status = "blocked_until_redacted" if sensitivity_level == "high" else ("redaction_required" if sensitivity_level == "medium" else "export_ready")
        claim_type = self._claim_type(source_type)
        claim_proposal = {
            "claim_type": claim_type,
            "draft": self._claim_sentence(row, claim_type),
            "needs_manual_review": True,
            "source_url": row.get("url", ""),
            "source_type": source_type,
            "evidence_level": evidence_level,
            "sensitivity_flags": flags,
        }
        next_action = "redact_and_review" if export_status != "export_ready" else ("verify_with_second_source" if evidence_level != "strong_indicator" else "consider_for_report")
        explanation = f"Quelle {source_type}, Qualität {quality}/100, Sensitivität {sensitivity_level}, Exportstatus {export_status}."
        return {"source_type": source_type, "finding_type": finding_type, "source_quality": quality, "sensitivity_level": sensitivity_level, "sensitivity_flags": flags, "evidence_level": evidence_level, "suggested_status": suggested_status, "export_status": export_status, "claim_proposal": claim_proposal, "next_action": next_action, "explanation": explanation}

    def list_profiles(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM fund_final_profiles_62_2 WHERE case_id=? AND entity_id=? ORDER BY source_quality DESC, created_at DESC LIMIT ?", [case_id, entity_id, int(limit)])
        return [self._decode(r) for r in rows]

    def get_profile(self, fund_profile_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM fund_final_profiles_62_2 WHERE fund_profile_id=?", [fund_profile_id])
        if not row:
            raise KeyError(fund_profile_id)
        return self._decode(row)

    def _decode(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["sensitivity_flags"] = loads(row.pop("sensitivity_flags_json", "[]"), [])
        row["claim_proposal"] = loads(row.pop("claim_proposal_json", "{}"), {})
        return row

    def _claim_type(self, source_type: str) -> str:
        return {
            "court_or_justice": "legal_or_court_indicator", "registry": "registry_indicator", "official_public_record": "official_record_indicator",
            "financial_public_record": "financial_public_indicator", "public_pdf": "public_document_indicator", "newspaper_press": "press_indicator",
            "image_media": "image_media_indicator", "archival_source": "archive_indicator", "social_public_profile": "public_profile_indicator",
        }.get(source_type, "public_web_indicator")

    def _claim_sentence(self, row: Dict[str, Any], claim_type: str) -> str:
        title = row.get("title") or row.get("domain") or "eine öffentliche Quelle"
        return f"Öffentliche Quelle '{title}' liefert einen {claim_type.replace('_', ' ')} zur Zielentität; manuelle Prüfung und Gegenprüfung erforderlich."

    def _upsert(self, row: Dict[str, Any], analysis: Dict[str, Any], person_finding_id: str) -> str:
        existing = self.db.one("SELECT fund_profile_id FROM fund_final_profiles_62_2 WHERE case_id=? AND entity_id=? AND final_result_id=?", [row["case_id"], row["entity_id"], row["final_result_id"]])
        now = now_ts()
        if existing:
            fid = existing["fund_profile_id"]
            self.db.execute('''UPDATE fund_final_profiles_62_2 SET capture_result_id=?,person_finding_id=?,source_type=?,finding_type=?,source_quality=?,sensitivity_level=?,sensitivity_flags_json=?,evidence_level=?,suggested_status=?,export_status=?,claim_proposal_json=?,next_action=?,explanation=?,updated_at=? WHERE fund_profile_id=?''', [row.get("capture_result_id", ""), person_finding_id, analysis["source_type"], analysis["finding_type"], analysis["source_quality"], analysis["sensitivity_level"], dumps(analysis["sensitivity_flags"]), analysis["evidence_level"], analysis["suggested_status"], analysis["export_status"], dumps(analysis["claim_proposal"]), analysis["next_action"], analysis["explanation"], now, fid])
        else:
            fid = new_id("fundfinal622")
            self.db.execute('''INSERT INTO fund_final_profiles_62_2(fund_profile_id,case_id,entity_id,final_result_id,capture_result_id,person_finding_id,source_type,finding_type,source_quality,sensitivity_level,sensitivity_flags_json,evidence_level,suggested_status,export_status,claim_proposal_json,next_action,explanation,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [fid, row["case_id"], row["entity_id"], row["final_result_id"], row.get("capture_result_id", ""), person_finding_id, analysis["source_type"], analysis["finding_type"], analysis["source_quality"], analysis["sensitivity_level"], dumps(analysis["sensitivity_flags"]), analysis["evidence_level"], analysis["suggested_status"], analysis["export_status"], dumps(analysis["claim_proposal"]), analysis["next_action"], analysis["explanation"], now, now])
        return fid


class EntityResolutionFinalService:
    """Build 62.3 Final: report-gate oriented identity-fit and doppler hardening."""

    def __init__(self, db: Database, audit: AuditService, *, hardening=None, fund_final=None, case_cockpit=None):
        self.db = db
        self.audit = audit
        self.hardening = hardening
        self.fund_final = fund_final
        self.case_cockpit = case_cockpit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS entity_resolution_final_62_3 (
          final_fit_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          identity_fit INTEGER DEFAULT 0,
          doppler_risk INTEGER DEFAULT 0,
          report_gate TEXT DEFAULT 'blocked',
          cluster_label TEXT DEFAULT 'unknown',
          required_actions_json TEXT NOT NULL,
          anchor_summary_json TEXT NOT NULL,
          explanation TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id, object_type, object_id)
        );
        CREATE INDEX IF NOT EXISTS idx_erfinal623_entity ON entity_resolution_final_62_3(case_id, entity_id, identity_fit DESC);
        ''')
        self.db.conn.commit()

    def assess_fund_profile(self, fund_profile_id: str) -> Dict[str, Any]:
        profile = self.fund_final.get_profile(fund_profile_id) if self.fund_final else None
        if not profile:
            raise KeyError(fund_profile_id)
        text_obj = self._source_text_for_profile(profile)
        base = self.hardening.assess_text(profile["case_id"], profile["entity_id"], "fund_final_profile", fund_profile_id, title=text_obj["title"], url=text_obj["url"], snippet=text_obj["snippet"], metadata=profile) if self.hardening else {"identity_fit": 0, "doppler_risk": 100, "anchors": [], "contradictions": []}
        return self._finalize(profile["case_id"], profile["entity_id"], "fund_final_profile", fund_profile_id, base, profile)

    def assess_all_for_entity(self, case_id: str, entity_id: str, limit: int = 200) -> Dict[str, Any]:
        profiles = self.fund_final.list_profiles(case_id, entity_id, limit=limit) if self.fund_final else []
        assessments = [self.assess_fund_profile(p["fund_profile_id"]) for p in profiles]
        return {"case_id": case_id, "entity_id": entity_id, "count": len(assessments), "assessments": assessments, "clusters": self.clusters(case_id, entity_id)}

    def clusters(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        rows = self.list_assessments(case_id, entity_id)
        clusters: Dict[str, List[Dict[str, Any]]] = {"reportable_high_fit": [], "review_needed": [], "likely_doppler_or_other": [], "blocked_sensitive": []}
        for r in rows:
            clusters.setdefault(r.get("cluster_label") or "review_needed", []).append(r)
        return {"case_id": case_id, "entity_id": entity_id, "counts": {k: len(v) for k, v in clusters.items()}, "clusters": clusters}

    def list_assessments(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM entity_resolution_final_62_3 WHERE case_id=? AND entity_id=? ORDER BY identity_fit DESC, doppler_risk ASC LIMIT ?", [case_id, entity_id, int(limit)])
        return [self._decode(r) for r in rows]

    def report_gate_for_object(self, case_id: str, entity_id: str, object_type: str, object_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM entity_resolution_final_62_3 WHERE case_id=? AND entity_id=? AND object_type=? AND object_id=?", [case_id, entity_id, object_type, object_id])
        if not row:
            return {"report_gate": "blocked", "required_actions": ["Identitätsfit vor Bericht prüfen."], "identity_fit": 0, "doppler_risk": 100}
        return self._decode(row)

    def _source_text_for_profile(self, profile: Dict[str, Any]) -> Dict[str, str]:
        cap = self.db.one("SELECT * FROM capture_final_results_62_1 WHERE final_result_id=?", [profile.get("final_result_id", "")]) or {}
        return {"title": cap.get("title") or profile.get("claim_proposal", {}).get("draft", ""), "url": cap.get("url", ""), "snippet": cap.get("snippet") or profile.get("explanation", "")}

    def _finalize(self, case_id: str, entity_id: str, object_type: str, object_id: str, base: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        identity_fit = int(base.get("identity_fit", 0))
        doppler_risk = int(base.get("doppler_risk", 100))
        flags = profile.get("sensitivity_flags", []) or []
        required: List[str] = []
        if identity_fit < 70:
            required.append("Identitätsfit durch zusätzliche Orts-/Organisations-/Zeitanker erhöhen.")
        if doppler_risk >= 45:
            required.append("Namensdoppler-Gegenprüfung durchführen.")
        if profile.get("export_status") != "export_ready":
            required.append("Redaktion/Datenschutzprüfung vor Export durchführen.")
        if profile.get("source_quality", 0) < 65:
            required.append("Quelle mit höherwertiger Zweitquelle bestätigen.")
        if flags:
            required.append("Sensible Daten nur mit Zweckbindung und Redaction verwenden.")
        if not required and identity_fit >= 75 and doppler_risk < 35:
            report_gate = "report_ready"
            cluster = "reportable_high_fit"
        elif identity_fit >= 55 and doppler_risk < 60:
            report_gate = "review_before_report"
            cluster = "review_needed"
        elif profile.get("export_status") == "blocked_until_redacted":
            report_gate = "blocked_until_redacted"
            cluster = "blocked_sensitive"
        else:
            report_gate = "blocked_doppler_or_low_fit"
            cluster = "likely_doppler_or_other"
        anchors = {"base_anchors": base.get("anchors", []), "contradictions": base.get("contradictions", []), "recommended_queries": base.get("recommended_queries", [])}
        explanation = f"Identitätsfit {identity_fit}/100, Doppler-Risiko {doppler_risk}/100, Gate {report_gate}."
        final_id = self._upsert(case_id, entity_id, object_type, object_id, identity_fit, doppler_risk, report_gate, cluster, required, anchors, explanation)
        return self.get_assessment(final_id)

    def get_assessment(self, final_fit_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM entity_resolution_final_62_3 WHERE final_fit_id=?", [final_fit_id])
        if not row:
            raise KeyError(final_fit_id)
        return self._decode(row)

    def _decode(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["required_actions"] = loads(row.pop("required_actions_json", "[]"), [])
        row["anchor_summary"] = loads(row.pop("anchor_summary_json", "{}"), {})
        return row

    def _upsert(self, case_id: str, entity_id: str, object_type: str, object_id: str, identity_fit: int, doppler_risk: int, report_gate: str, cluster: str, required: List[str], anchors: Dict[str, Any], explanation: str) -> str:
        now = now_ts()
        existing = self.db.one("SELECT final_fit_id FROM entity_resolution_final_62_3 WHERE case_id=? AND entity_id=? AND object_type=? AND object_id=?", [case_id, entity_id, object_type, object_id])
        if existing:
            fid = existing["final_fit_id"]
            self.db.execute('''UPDATE entity_resolution_final_62_3 SET identity_fit=?,doppler_risk=?,report_gate=?,cluster_label=?,required_actions_json=?,anchor_summary_json=?,explanation=?,updated_at=? WHERE final_fit_id=?''', [identity_fit, doppler_risk, report_gate, cluster, dumps(required), dumps(anchors), explanation, now, fid])
        else:
            fid = new_id("erfinal623")
            self.db.execute('''INSERT INTO entity_resolution_final_62_3(final_fit_id,case_id,entity_id,object_type,object_id,identity_fit,doppler_risk,report_gate,cluster_label,required_actions_json,anchor_summary_json,explanation,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [fid, case_id, entity_id, object_type, object_id, identity_fit, doppler_risk, report_gate, cluster, dumps(required), dumps(anchors), explanation, now, now])
        return fid


class PhaseAFinalOperations623Service:
    """Build 62.3: consolidated Phase A workflow."""

    def __init__(self, db: Database, audit: AuditService, *, capture_final=None, fund_final=None, entity_final=None, dashboard=None):
        self.db = db
        self.audit = audit
        self.capture_final = capture_final
        self.fund_final = fund_final
        self.entity_final = entity_final
        self.dashboard = dashboard
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS phase_a_cycles_62_3 (
          phase_a_cycle_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          imported_count INTEGER DEFAULT 0,
          fund_profile_count INTEGER DEFAULT 0,
          assessment_count INTEGER DEFAULT 0,
          readiness_score INTEGER DEFAULT 0,
          summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_phase_a_cycle(self, case_id: str, entity_id: str, *, clipboard_text: str = "", url: str = "", title: str = "", snippet: str = "", category_key: str = "person_core", query: str = "", engine: str = "manual_capture") -> Dict[str, Any]:
        imported = {"count": 0, "results": []}
        if clipboard_text:
            imported = self.capture_final.import_clipboard(case_id, entity_id, clipboard_text, category_key=category_key, query=query, engine=engine) if self.capture_final else imported
        elif url:
            imported = self.capture_final.import_url(case_id, entity_id, url, title=title, snippet=snippet, category_key=category_key, query=query, engine=engine) if self.capture_final else imported
        profiles: List[Dict[str, Any]] = []
        for r in imported.get("results", []):
            profiles.append(self.fund_final.import_final_result(r["final_result_id"]) if self.fund_final else {})
        assessment = self.entity_final.assess_all_for_entity(case_id, entity_id) if self.entity_final else {"count": 0, "clusters": {}}
        dash = self.dashboard.dashboard(case_id, entity_id) if self.dashboard else {}
        readiness = self._readiness(imported, profiles, assessment, dash)
        cycle_id = new_id("phasea623")
        summary = {"imported": imported.get("quality", {}), "fund_profiles": len(profiles), "entity_assessments": assessment.get("count", 0), "clusters": assessment.get("clusters", {}).get("counts", {}), "dashboard_metrics": dash.get("metrics", {}), "readiness_score": readiness}
        self.db.execute('''INSERT INTO phase_a_cycles_62_3(phase_a_cycle_id,case_id,entity_id,imported_count,fund_profile_count,assessment_count,readiness_score,summary_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', [cycle_id, case_id, entity_id, int(imported.get("count", 0)), len(profiles), int(assessment.get("count", 0)), readiness, dumps(summary), now_ts()])
        self.audit.log("run", "phase_a_final_cycle_62_3", cycle_id, case_id, {"entity_id": entity_id, "readiness": readiness})
        return {"phase_a_cycle_id": cycle_id, "imported": imported, "fund_profiles": profiles, "entity_assessment": assessment, "dashboard": dash, "readiness_score": readiness, "summary": summary}

    def _readiness(self, imported: Dict[str, Any], profiles: List[Dict[str, Any]], assessment: Dict[str, Any], dash: Dict[str, Any]) -> int:
        score = 40
        score += min(20, int(imported.get("count", 0)) * 4)
        score += min(15, len([p for p in profiles if p.get("export_status") == "export_ready"]) * 5)
        counts = (assessment.get("clusters", {}) or {}).get("counts", {})
        score += min(15, counts.get("reportable_high_fit", 0) * 5)
        score -= min(20, counts.get("likely_doppler_or_other", 0) * 5)
        metrics = dash.get("metrics", {}) if dash else {}
        score += min(10, int(metrics.get("finding_count", 0)))
        return max(0, min(100, score))
