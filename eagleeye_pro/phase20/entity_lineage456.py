from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit
import hashlib
import json
import re
import secrets
import unicodedata

BUILD = "456.0"
POLICY_ID = "phase20.multilingual-entity-source-lineage.v456"

ALIAS_CONFIRM = "REVIEW ALIAS 456"
PAIR_CONFIRM = "REVIEW ENTITY PAIR 456"
LINEAGE_CONFIRM = "REVIEW SOURCE LINEAGE 456"

PAIR_DECISIONS = {"investigate_same", "likely_distinct", "dismiss"}
ALIAS_DECISIONS = {"approve", "reject"}
SOURCE_ROLES = {"publisher", "primary", "mirror", "archive", "aggregator", "unknown"}


HEBREW = {
    "א":"a","ב":"v","ג":"g","ד":"d","ה":"h","ו":"v","ז":"z","ח":"h","ט":"t","י":"y",
    "כ":"kh","ך":"kh","ל":"l","מ":"m","ם":"m","נ":"n","ן":"n","ס":"s","ע":"a","פ":"f",
    "ף":"f","צ":"ts","ץ":"ts","ק":"k","ר":"r","ש":"sh","ת":"t"
}
ARABIC = {
    "ا":"a","أ":"a","إ":"i","آ":"a","ب":"b","ت":"t","ث":"th","ج":"j","ح":"h","خ":"kh",
    "د":"d","ذ":"dh","ر":"r","ز":"z","س":"s","ش":"sh","ص":"s","ض":"d","ط":"t","ظ":"z",
    "ع":"a","غ":"gh","ف":"f","ق":"q","ك":"k","ل":"l","م":"m","ن":"n","ه":"h","و":"w",
    "ي":"y","ى":"a","ة":"a","ء":""
}
CYRILLIC = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i",
    "й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t",
    "у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y",
    "ь":"","э":"e","ю":"yu","я":"ya","і":"i","ї":"yi","є":"ye","ґ":"g"
}
PARTICLES = {"de","del","della","di","da","van","von","der","den","al","el","bin","ibn","bat","ben","bar"}


def _script(ch):
    name = unicodedata.name(ch, "")
    if "HEBREW" in name:
        return "Hebrew"
    if "ARABIC" in name:
        return "Arabic"
    if "CYRILLIC" in name:
        return "Cyrillic"
    if "LATIN" in name:
        return "Latin"
    return "Common" if not ch.isalpha() else "Other"


def _transliterate(value):
    out = []
    for ch in unicodedata.normalize("NFKD", str(value or "")):
        if unicodedata.combining(ch):
            continue
        low = ch.casefold()
        if ch in HEBREW:
            out.append(HEBREW[ch])
        elif ch in ARABIC:
            out.append(ARABIC[ch])
        elif low in CYRILLIC:
            out.append(CYRILLIC[low])
        else:
            out.append(low)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _normalize_name(value):
    original = _clean(value, 500)
    nfkc = unicodedata.normalize("NFKC", original)
    folded = nfkc.casefold()
    cleaned = re.sub(r"[^\w\s'\-]+", " ", folded, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    markless = "".join(
        ch for ch in unicodedata.normalize("NFKD", cleaned)
        if not unicodedata.combining(ch)
    )
    scripts = sorted({_script(ch) for ch in original if ch.isalpha()})
    latin = _transliterate(original)
    tokens = [x for x in markless.split() if x]
    core = [x for x in tokens if x not in PARTICLES] or tokens
    variants = sorted({
        markless,
        " ".join(tokens),
        " ".join(reversed(tokens)) if len(tokens) > 1 else markless,
        latin,
        " ".join(core),
        " ".join(reversed(core)) if len(core) > 1 else " ".join(core),
    })
    return {
        "original": original,
        "comparison_key": markless,
        "tokens": tokens,
        "scripts": scripts,
        "latin_transliteration": latin,
        "variants": variants,
    }


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value, limit=1000):
    return " ".join(str(value or "").split())[:limit]


def _fold(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("ß", "ss")
    text = re.sub(r"[^\w\s'-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _host(value):
    try:
        return (urlsplit(str(value or "")).hostname or "").casefold().strip(".")
    except ValueError:
        return ""


def _host_family(host):
    host = str(host or "").casefold().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _norm_label(value):
    return re.sub(r"[^a-z0-9]+", "-", _fold(value)).strip("-")[:180]


def _phonetic(value):
    text = _fold(value)
    replacements = (
        ("shch", "sh"),
        ("sch", "sh"),
        ("tsh", "ch"),
        ("zh", "j"),
        ("kh", "h"),
        ("ch", "h"),
        ("ph", "f"),
        ("th", "t"),
        ("tz", "ts"),
        ("q", "k"),
        ("w", "v"),
        ("j", "y"),
    )
    for left, right in replacements:
        text = text.replace(left, right)
    text = re.sub(r"[^a-z0-9\s]+", "", text)
    tokens = []
    for token in text.split():
        consonants = re.sub(r"[aeiouy]+", "", token)
        tokens.append(consonants or token)
    return " ".join(tokens)


class MultilingualEntitySourceLineage456:
    """Canonical Build-456 integration of multilingual entity review and source lineage.

    Similarity scores are investigative prioritization only. The service never merges
    identities, never promotes source independence to truth, and never converts an
    inferred publisher/family into a factual ownership relationship.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        resolution437,
        base115,
        closure447,
        registry421,
        events422,
        content423,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.resolution437 = resolution437
        self.base115 = base115
        self.closure447 = closure447
        self.registry421 = registry421
        self.events422 = events422
        self.content423 = content423
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase20_alias_candidate_456(
            candidate_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            resolution_entity_id TEXT NOT NULL,
            original_name TEXT NOT NULL,
            candidate_alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            method TEXT NOT NULL,
            scripts_json TEXT NOT NULL,
            state TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            review_reason TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            UNIQUE(case_id,resolution_entity_id,normalized_alias)
            );
            CREATE INDEX IF NOT EXISTS idx_alias456_case_state
            ON phase20_alias_candidate_456(case_id,state,resolution_entity_id);

            CREATE TABLE IF NOT EXISTS phase20_entity_pair_candidate_456(
            pair_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            left_entity_id TEXT NOT NULL,
            right_entity_id TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            confidence_band TEXT NOT NULL,
            signals_json TEXT NOT NULL,
            state TEXT NOT NULL,
            resolution_comparison_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            review_reason TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            UNIQUE(case_id,left_entity_id,right_entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_pair456_case_state
            ON phase20_entity_pair_candidate_456(case_id,state,similarity_score);

            CREATE TABLE IF NOT EXISTS phase20_source_lineage_review_456(
            review_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            evidence_hash TEXT NOT NULL,
            source_family TEXT NOT NULL,
            independence_group TEXT NOT NULL,
            origin_key TEXT NOT NULL,
            source_role TEXT NOT NULL,
            countable INTEGER NOT NULL,
            rationale TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lineage456_evidence
            ON phase20_source_lineage_review_456(case_id,evidence_id);

            CREATE TABLE IF NOT EXISTS phase20_entity_lineage_run_456(
            run_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            entities_considered INTEGER NOT NULL,
            alias_candidates INTEGER NOT NULL,
            pair_candidates INTEGER NOT NULL,
            result_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_run456_case
            ON phase20_entity_lineage_run_456(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required") from None
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "build456")}

    def _authorize(self, identity, case_id, capability, object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="multilingual_entity_source_lineage_456",
            object_id=str(object_id or case_id),
        )
        return ident

    def _entity(self, entity_id):
        row = self.db.one(
            "SELECT * FROM resolution_entities_115 WHERE resolution_entity_id=?",
            (str(entity_id),),
        )
        if not row:
            raise KeyError("resolution entity not found")
        return dict(row)

    def _aliases(self, entity_id):
        return [
            dict(row)
            for row in self.db.all(
                "SELECT * FROM resolution_aliases_115 WHERE resolution_entity_id=? ORDER BY created_at,alias_id",
                (str(entity_id),),
            )
        ]

    def preview_name(self, name):
        normalized = _normalize_name(str(name))
        latin = _fold(normalized.get("latin_transliteration") or "")
        return {
            **normalized,
            "latin_key_456": latin,
            "phonetic_key_456": _phonetic(latin),
            "similarity_is_probability": False,
        }

    def _candidate_alias_values(self, name):
        profile = self.preview_name(name)
        out = []
        latin = _clean(profile.get("latin_transliteration"), 500)
        original = _clean(profile.get("original"), 500)
        scripts = set(profile.get("scripts") or [])
        if latin and self.base115.normalize_text(latin) != self.base115.normalize_text(original):
            out.append((latin, "transliteration"))
            parts = latin.split()
            if len(parts) > 1:
                out.append((" ".join(reversed(parts)), "transliteration_name_order"))
        if scripts == {"Latin"}:
            parts = original.split()
            if 1 < len(parts) <= 5:
                out.append((" ".join(reversed(parts)), "name_order"))
        seen = set()
        result = []
        for value, method in out:
            norm = self.base115.normalize_text(value)
            if len(norm) < 2 or norm in seen:
                continue
            seen.add(norm)
            result.append((value, norm, method, sorted(scripts)))
        return result

    def _upsert_alias_candidate(self, ident, case_id, entity, original_name, value, norm, method, scripts):
        existing = self.db.one(
            "SELECT * FROM phase20_alias_candidate_456 WHERE case_id=? AND resolution_entity_id=? "
            "AND normalized_alias=?",
            (str(case_id), entity["resolution_entity_id"], norm),
        )
        if existing:
            return dict(existing), False
        row = {
            "candidate_id": "alias456_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "resolution_entity_id": entity["resolution_entity_id"],
            "original_name": _clean(original_name, 500),
            "candidate_alias": _clean(value, 500),
            "normalized_alias": norm,
            "method": method,
            "scripts_json": _canon(scripts),
            "state": "pending",
            "created_by": str(ident["username"]),
            "created_at": _now(),
            "reviewed_by": "",
            "reviewed_at": "",
            "review_reason": "",
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_alias_candidate_456 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        return row, True

    def _name_pair(self, left_name, right_name):
        left = self.preview_name(left_name)
        right = self.preview_name(right_name)
        lcmp = _fold(left.get("comparison_key") or "")
        rcmp = _fold(right.get("comparison_key") or "")
        llat = _fold(left.get("latin_transliteration") or left_name)
        rlat = _fold(right.get("latin_transliteration") or right_name)
        lphon = _phonetic(llat)
        rphon = _phonetic(rlat)
        exact = bool(lcmp and lcmp == rcmp)
        translit_exact = bool(llat and llat == rlat)
        phonetic_exact = bool(lphon and len(lphon.replace(" ", "")) >= 4 and lphon == rphon)
        seq = SequenceMatcher(None, llat, rlat).ratio() if llat and rlat else 0.0
        pseq = SequenceMatcher(None, lphon, rphon).ratio() if lphon and rphon else 0.0
        ltokens = set(llat.split())
        rtokens = set(rlat.split())
        token_jaccard = len(ltokens & rtokens) / len(ltokens | rtokens) if ltokens | rtokens else 0.0
        score = max(
            1.0 if exact else 0.0,
            0.96 if translit_exact else 0.0,
            0.92 if phonetic_exact else 0.0,
            0.60 * seq + 0.40 * pseq,
            0.55 * seq + 0.45 * token_jaccard,
        )
        scripts_left = sorted(left.get("scripts") or [])
        scripts_right = sorted(right.get("scripts") or [])
        return {
            "score": round(float(score), 6),
            "signals": {
                "exact_normalized": exact,
                "same_transliteration": translit_exact,
                "same_phonetic_key": phonetic_exact,
                "transliteration_similarity": round(seq, 6),
                "phonetic_similarity": round(pseq, 6),
                "token_jaccard": round(token_jaccard, 6),
                "left_scripts": scripts_left,
                "right_scripts": scripts_right,
                "cross_script": scripts_left != scripts_right,
                "left_latin": llat,
                "right_latin": rlat,
                "left_phonetic": lphon,
                "right_phonetic": rphon,
            },
        }

    def _best_entity_pair(self, left, right):
        left_names = [left["display_name"]] + [x["alias"] for x in self._aliases(left["resolution_entity_id"])]
        right_names = [right["display_name"]] + [x["alias"] for x in self._aliases(right["resolution_entity_id"])]
        best = {"score": 0.0, "signals": {}}
        for ln in left_names[:20]:
            for rn in right_names[:20]:
                candidate = self._name_pair(ln, rn)
                if candidate["score"] > best["score"]:
                    best = {**candidate, "left_name": ln, "right_name": rn}
        return best

    def _upsert_pair(self, ident, case_id, left, right, result):
        a, b = sorted([left["resolution_entity_id"], right["resolution_entity_id"]])
        existing = self.db.one(
            "SELECT * FROM phase20_entity_pair_candidate_456 WHERE case_id=? AND left_entity_id=? "
            "AND right_entity_id=?",
            (str(case_id), a, b),
        )
        band = "high" if result["score"] >= 0.88 else "medium" if result["score"] >= 0.72 else "low"
        if existing:
            row = dict(existing)
            row["similarity_score"] = result["score"]
            row["confidence_band"] = band
            row["signals_json"] = _canon(result)
            row["record_hash"] = self._rh(row)
            self.db.execute(
                "UPDATE phase20_entity_pair_candidate_456 SET similarity_score=?,confidence_band=?,"
                "signals_json=?,record_hash=? WHERE pair_id=?",
                (row["similarity_score"], row["confidence_band"], row["signals_json"], row["record_hash"], row["pair_id"]),
            )
            return row, False
        row = {
            "pair_id": "pair456_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "left_entity_id": a,
            "right_entity_id": b,
            "similarity_score": result["score"],
            "confidence_band": band,
            "signals_json": _canon(result),
            "state": "review_required",
            "resolution_comparison_id": "",
            "created_by": str(ident["username"]),
            "created_at": _now(),
            "reviewed_by": "",
            "reviewed_at": "",
            "review_reason": "",
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_entity_pair_candidate_456 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        return row, True

    def scan_case_entities(self, *, identity, case_id, min_pair_score=0.72, max_entities=250, max_pairs=5000):
        ident = self._authorize(identity, case_id, "research.run", case_id)
        case_id = str(case_id)
        threshold = float(min_pair_score)
        if not 0.55 <= threshold <= 0.98:
            raise ValueError("min_pair_score must be between 0.55 and 0.98")
        entities = [
            dict(row)
            for row in self.db.all(
                "SELECT * FROM resolution_entities_115 WHERE case_id=? "
                "AND entity_type IN ('person','organisation') ORDER BY resolution_entity_id",
                (case_id,),
            )
        ]
        if len(entities) > int(max_entities):
            raise ValueError("entity set exceeds max_entities; narrow the case scope")

        alias_added = 0
        for entity in entities:
            existing_norms = {
                x["normalized_alias"] for x in self._aliases(entity["resolution_entity_id"])
            }
            source_names = [entity["display_name"]] + [x["alias"] for x in self._aliases(entity["resolution_entity_id"])]
            for original in source_names[:20]:
                for value, norm, method, scripts in self._candidate_alias_values(original):
                    if norm in existing_norms:
                        continue
                    _row, created = self._upsert_alias_candidate(
                        ident, case_id, entity, original, value, norm, method, scripts
                    )
                    alias_added += int(created)

        pairs_added = 0
        pairs_considered = 0
        for idx, left in enumerate(entities):
            for right in entities[idx + 1:]:
                if left["entity_type"] != right["entity_type"]:
                    continue
                pairs_considered += 1
                if pairs_considered > int(max_pairs):
                    raise ValueError("candidate pair set exceeds max_pairs; narrow the case scope")
                result = self._best_entity_pair(left, right)
                if result["score"] < threshold:
                    continue
                _row, created = self._upsert_pair(ident, case_id, left, right, result)
                pairs_added += int(created)

        alias_total = int(
            self.db.one(
                "SELECT COUNT(*) AS n FROM phase20_alias_candidate_456 WHERE case_id=?",
                (case_id,),
            )["n"]
        )
        pair_total = int(
            self.db.one(
                "SELECT COUNT(*) AS n FROM phase20_entity_pair_candidate_456 WHERE case_id=?",
                (case_id,),
            )["n"]
        )
        result = {
            "build": BUILD,
            "case_id": case_id,
            "entities_considered": len(entities),
            "alias_candidates_total": alias_total,
            "alias_candidates_added": alias_added,
            "pair_candidates_total": pair_total,
            "pair_candidates_added": pairs_added,
            "min_pair_score": threshold,
            "similarity_score_is_probability": False,
            "automatic_identity_confirmation": False,
            "automatic_merge": False,
            "human_review_required": True,
        }
        row = {
            "run_id": "er456_" + secrets.token_hex(10),
            "case_id": case_id,
            "entities_considered": len(entities),
            "alias_candidates": alias_total,
            "pair_candidates": pair_total,
            "result_json": _canon(result),
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_entity_lineage_run_456 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "multilingual_entity_scan_456",
            "case",
            case_id,
            case_id,
            {
                "run_id": row["run_id"],
                "entities": len(entities),
                "alias_candidates": alias_total,
                "pair_candidates": pair_total,
                "automatic_merge": False,
            },
        )
        return result

    def alias_candidates(self, *, identity, case_id, state=""):
        self._authorize(identity, case_id, "case.read", case_id)
        sql = "SELECT * FROM phase20_alias_candidate_456 WHERE case_id=?"
        args = [str(case_id)]
        if state:
            sql += " AND state=?"
            args.append(str(state))
        sql += " ORDER BY CASE state WHEN 'pending' THEN 0 ELSE 1 END, created_at, candidate_id"
        out = []
        for row in self.db.all(sql, tuple(args)):
            item = dict(row)
            item["scripts"] = json.loads(item.pop("scripts_json"))
            out.append(item)
        return out

    def pair_candidates(self, *, identity, case_id, state=""):
        self._authorize(identity, case_id, "case.read", case_id)
        sql = "SELECT * FROM phase20_entity_pair_candidate_456 WHERE case_id=?"
        args = [str(case_id)]
        if state:
            sql += " AND state=?"
            args.append(str(state))
        sql += " ORDER BY similarity_score DESC,rowid"
        out = []
        for row in self.db.all(sql, tuple(args)):
            item = dict(row)
            item["signals"] = json.loads(item.pop("signals_json"))
            out.append(item)
        return out

    def review_alias_candidate(self, *, identity, candidate_id, decision, rationale, confirmation):
        raw = self.db.one(
            "SELECT * FROM phase20_alias_candidate_456 WHERE candidate_id=?",
            (str(candidate_id),),
        )
        if not raw:
            raise KeyError("Build-456 alias candidate not found")
        row = dict(raw)
        ident = self._authorize(identity, row["case_id"], "dossier.review", candidate_id)
        if str(confirmation or "").strip().upper() != ALIAS_CONFIRM:
            raise PermissionError(f"explicit {ALIAS_CONFIRM} confirmation required")
        decision = str(decision or "").strip().lower()
        if decision not in ALIAS_DECISIONS:
            raise ValueError("unsupported alias review decision")
        if row["state"] != "pending":
            raise ValueError("alias candidate already reviewed")
        why = _clean(rationale, 4000)
        if len(why) < 8:
            raise ValueError("alias review rationale must be documented")
        entity = self._entity(row["resolution_entity_id"])
        if entity["case_id"] != row["case_id"]:
            raise PermissionError("alias candidate entity changed case")
        if decision == "approve":
            self.base115.add_alias(
                row["resolution_entity_id"],
                row["candidate_alias"],
                "multilingual_456",
                str(ident["username"]),
                "build456:" + row["candidate_id"],
            )
            row["state"] = "approved"
        else:
            row["state"] = "rejected"
        row["reviewed_by"] = str(ident["username"])
        row["reviewed_at"] = _now()
        row["review_reason"] = why
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE phase20_alias_candidate_456 SET state=?,reviewed_by=?,reviewed_at=?,"
            "review_reason=?,record_hash=? WHERE candidate_id=?",
            (row["state"], row["reviewed_by"], row["reviewed_at"], row["review_reason"], row["record_hash"], row["candidate_id"]),
        )
        self.audit.log(
            "multilingual_alias_reviewed_456",
            "phase20_alias_candidate_456",
            row["candidate_id"],
            row["case_id"],
            {"decision": decision, "automatic_merge": False},
        )
        return row

    def review_pair_candidate(self, *, identity, pair_id, decision, rationale, confirmation):
        raw = self.db.one(
            "SELECT * FROM phase20_entity_pair_candidate_456 WHERE pair_id=?",
            (str(pair_id),),
        )
        if not raw:
            raise KeyError("Build-456 pair candidate not found")
        row = dict(raw)
        ident = self._authorize(identity, row["case_id"], "dossier.review", pair_id)
        if str(confirmation or "").strip().upper() != PAIR_CONFIRM:
            raise PermissionError(f"explicit {PAIR_CONFIRM} confirmation required")
        decision = str(decision or "").strip().lower()
        if decision not in PAIR_DECISIONS:
            raise ValueError("unsupported pair review decision")
        if row["state"] != "review_required":
            raise ValueError("pair candidate already reviewed")
        why = _clean(rationale, 4000)
        if len(why) < 8:
            raise ValueError("pair review rationale must be documented")
        comparison_id = ""
        if decision == "investigate_same":
            comparison = self.base115.compare(
                row["left_entity_id"], row["right_entity_id"], str(ident["username"])
            )
            comparison_id = str(comparison["comparison_id"])
            state = "forwarded_to_resolution_review"
        elif decision == "likely_distinct":
            state = "analyst_marked_distinct"
        else:
            state = "dismissed"
        row["state"] = state
        row["resolution_comparison_id"] = comparison_id
        row["reviewed_by"] = str(ident["username"])
        row["reviewed_at"] = _now()
        row["review_reason"] = why
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE phase20_entity_pair_candidate_456 SET state=?,resolution_comparison_id=?,"
            "reviewed_by=?,reviewed_at=?,review_reason=?,record_hash=? WHERE pair_id=?",
            (
                row["state"], row["resolution_comparison_id"], row["reviewed_by"],
                row["reviewed_at"], row["review_reason"], row["record_hash"], row["pair_id"],
            ),
        )
        self.audit.log(
            "multilingual_pair_reviewed_456",
            "phase20_entity_pair_candidate_456",
            row["pair_id"],
            row["case_id"],
            {
                "decision": decision,
                "resolution_comparison_id": comparison_id,
                "automatic_identity_confirmation": False,
                "automatic_merge": False,
            },
        )
        return row

    def _lineage_inference(self, evidence):
        descriptive = evidence.get("descriptive") or {}
        publisher = _clean(descriptive.get("publisher"), 300)
        host = _host_family(_host(evidence.get("canonical_url")))
        source_id = str(evidence.get("source_id") or "")
        publisher_key = _norm_label(publisher)
        if publisher_key:
            family = "publisher:" + publisher_key
            origin = family
            role = "publisher"
        elif host:
            family = "host:" + host
            origin = family
            role = "archive" if host == "archive.org" or host.endswith(".archive.org") else "primary"
        else:
            family = "source:" + source_id
            origin = family
            role = "unknown"
        duplicate_kind = str(evidence.get("duplicate_kind") or "").casefold()
        mirror = role == "archive" or "mirror" in duplicate_kind
        countable = not mirror
        group = "origin:" + origin
        return {
            "source_family": family,
            "independence_group": group,
            "origin_key": origin,
            "source_role": "mirror" if "mirror" in duplicate_kind else role,
            "countable": bool(countable),
            "inference_basis": {
                "publisher": publisher,
                "host": host,
                "source_id": source_id,
                "duplicate_kind": duplicate_kind,
            },
            "reviewed": False,
            "review_required_for_override": True,
        }

    def _latest_lineage_review(self, case_id, evidence_id):
        row = self.db.one(
            "SELECT * FROM phase20_source_lineage_review_456 WHERE case_id=? AND evidence_id=? "
            "ORDER BY rowid DESC LIMIT 1",
            (str(case_id), str(evidence_id)),
        )
        return dict(row) if row else None

    def evidence_lineage(self, *, identity, evidence_id):
        evidence = self.closure447.evidence(evidence_id)
        self._authorize(identity, evidence["case_id"], "case.read", evidence_id)
        inferred = self._lineage_inference(evidence)
        review = self._latest_lineage_review(evidence["case_id"], evidence_id)
        stale = False
        if review:
            valid = self._rh(review) == review.get("record_hash")
            stale = review.get("evidence_hash") != evidence.get("record_hash")
            if valid and not stale:
                return {
                    **inferred,
                    "source_family": review["source_family"],
                    "independence_group": review["independence_group"],
                    "origin_key": review["origin_key"],
                    "source_role": review["source_role"],
                    "countable": bool(review["countable"]),
                    "reviewed": True,
                    "review_id": review["review_id"],
                    "review_rationale": review["rationale"],
                    "reviewed_by": review["reviewed_by"],
                    "reviewed_at": review["reviewed_at"],
                    "evidence_id": evidence_id,
                    "evidence_hash": evidence["record_hash"],
                }
        return {
            **inferred,
            "evidence_id": evidence_id,
            "evidence_hash": evidence["record_hash"],
            "stale_review_ignored": stale,
        }

    def review_source_lineage(
        self,
        *,
        identity,
        evidence_id,
        source_family,
        independence_group,
        origin_key,
        source_role,
        countable,
        rationale,
        confirmation,
        expected_evidence_hash,
    ):
        evidence = self.closure447.evidence(evidence_id)
        ident = self._authorize(identity, evidence["case_id"], "source.review", evidence_id)
        if str(expected_evidence_hash or "") != str(evidence.get("record_hash") or ""):
            raise PermissionError("evidence changed after lineage review was opened")
        if type(countable) is not bool:
            raise ValueError("countable must be a JSON boolean")
        if str(confirmation or "").strip().upper() != LINEAGE_CONFIRM:
            raise PermissionError(f"explicit {LINEAGE_CONFIRM} confirmation required")
        family = _clean(source_family, 300)
        group = _clean(independence_group, 400)
        origin = _clean(origin_key, 1000)
        role = str(source_role or "").strip().lower()
        why = _clean(rationale, 4000)
        if not family or not group or not origin:
            raise ValueError("source_family, independence_group and origin_key are required")
        if role not in SOURCE_ROLES:
            raise ValueError("unsupported source role")
        if len(why) < 12:
            raise ValueError("source-lineage rationale must be documented")
        row = {
            "review_id": "lineage456_" + secrets.token_hex(10),
            "case_id": evidence["case_id"],
            "evidence_id": evidence_id,
            "evidence_hash": evidence["record_hash"],
            "source_family": family,
            "independence_group": group,
            "origin_key": origin,
            "source_role": role,
            "countable": int(bool(countable)),
            "rationale": why,
            "reviewed_by": str(ident["username"]),
            "reviewed_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_source_lineage_review_456 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "source_lineage_reviewed_456",
            "phase20_source_lineage_review_456",
            row["review_id"],
            evidence["case_id"],
            {
                "evidence_id": evidence_id,
                "source_family": family,
                "independence_group": group,
                "countable": bool(countable),
                "truth_determined": False,
            },
        )
        return {**row, "countable": bool(row["countable"])}

    def _publication_fingerprint(self, evidence):
        descriptive = evidence.get("descriptive") or {}
        metadata = descriptive.get("metadata") or {}
        published = str(metadata.get("publication_text_fingerprint_sha256") or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", published):
            return published, str(metadata.get("publication_text_fingerprint_basis") or "publication_text")
        # Build-443 news content_sha256 fingerprints a provenance envelope (URL,
        # publisher, timestamp, author), so it is not safe for cross-publisher
        # republication deduplication. Older news without the source-neutral
        # publication fingerprint remains uncountable until reviewed/reacquired.
        if evidence.get("evidence_kind") == "news":
            return "", "unavailable_for_legacy_news"
        raw = str(evidence.get("content_sha256") or "").strip().lower()
        return (raw, "content_payload") if re.fullmatch(r"[0-9a-f]{64}", raw) else ("", "unavailable")

    def claim_source_lineage(self, *, identity, claim_id):
        claim = self.closure447.claim(claim_id)
        self._authorize(identity, claim["case_id"], "case.read", claim_id)
        rows = []
        stale_overrides = 0
        for link in claim.get("links") or []:
            evidence = self.closure447.evidence(link["evidence_id"])
            lineage = self.evidence_lineage(identity=identity, evidence_id=evidence["evidence_id"])
            fingerprint, fingerprint_basis = self._publication_fingerprint(evidence)
            if lineage.get("stale_review_ignored"):
                stale_overrides += 1
            rows.append(
                {
                    "stance": link["stance"],
                    "evidence_id": evidence["evidence_id"],
                    "title": evidence["title"],
                    "canonical_url": evidence["canonical_url"],
                    "content_sha256": str(evidence.get("content_sha256") or ""),
                    "publication_fingerprint_sha256": fingerprint,
                    "publication_fingerprint_basis": fingerprint_basis,
                    "source_family": lineage["source_family"],
                    "independence_group": lineage["independence_group"],
                    "origin_key": lineage["origin_key"],
                    "source_role": lineage["source_role"],
                    "lineage_reviewed": bool(lineage.get("reviewed")),
                    "lineage_countable": bool(lineage.get("countable")),
                }
            )

        by_fingerprint = {}
        for item in rows:
            fp = item["publication_fingerprint_sha256"]
            if fp:
                by_fingerprint.setdefault(fp, []).append(item)

        cross_stance_fingerprints = {
            fp for fp, items in by_fingerprint.items()
            if len({x["stance"] for x in items}) > 1
        }
        conflicting_lineage_fingerprints = set()
        for fp, items in by_fingerprint.items():
            reviewed_groups = {
                x["independence_group"]
                for x in items
                if x["lineage_reviewed"] and x["lineage_countable"] and x["independence_group"]
            }
            if len(reviewed_groups) > 1:
                conflicting_lineage_fingerprints.add(fp)

        for item in rows:
            fp = item["publication_fingerprint_sha256"]
            group_items = by_fingerprint.get(fp, []) if fp else []
            item["publication_duplicate"] = bool(fp and len(group_items) > 1)
            item["cross_stance_duplicate"] = bool(fp and fp in cross_stance_fingerprints)
            item["lineage_conflict_same_payload"] = bool(
                fp and fp in conflicting_lineage_fingerprints
            )
            item["effective_countable"] = bool(
                item["lineage_reviewed"]
                and item["lineage_countable"]
                and fp
                and fp not in cross_stance_fingerprints
                and fp not in conflicting_lineage_fingerprints
            )

        summary = {}
        for stance in ("support", "contradict", "context"):
            subset = [x for x in rows if x["stance"] == stance]
            unique_fps = {
                x["publication_fingerprint_sha256"]
                for x in subset if x["publication_fingerprint_sha256"]
            }
            inferred_groups = {
                x["independence_group"]
                for x in subset
                if x["lineage_countable"] and x["independence_group"]
            }
            reviewed_units = {}
            for item in subset:
                if not item["effective_countable"]:
                    continue
                fp = item["publication_fingerprint_sha256"]
                reviewed_units.setdefault(fp, item["independence_group"])
            reviewed_origins = set(reviewed_units.values())
            summary[stance] = {
                "mentions": len(subset),
                "unique_publication_payloads": len(unique_fps),
                "source_families": len({x["source_family"] for x in subset if x["source_family"]}),
                "inferred_origin_candidates": len(inferred_groups),
                "reviewed_independent_origins": len(reviewed_origins),
                "unreviewed_or_non_countable": sum(
                    1 for x in subset if not x["effective_countable"]
                ),
            }

        warnings = []
        if any(x["publication_duplicate"] for x in rows):
            warnings.append("duplicate_publication_payloads_collapsed")
        if cross_stance_fingerprints:
            warnings.append("same_publication_payload_crosses_claim_stances")
        if conflicting_lineage_fingerprints:
            warnings.append("reviewed_lineage_conflict_for_same_publication_payload")
        if stale_overrides:
            warnings.append("stale_source_lineage_review_ignored")
        if any(not x["lineage_reviewed"] for x in rows):
            warnings.append("unreviewed_lineage_excluded_from_independent_origin_count")
        if any(not x["publication_fingerprint_sha256"] for x in rows):
            warnings.append("publication_fingerprint_unavailable_excluded_from_independent_count")

        return {
            "build": BUILD,
            "case_id": claim["case_id"],
            "claim_id": claim_id,
            "statement": claim["statement"],
            "claim_state": claim["state"],
            "summary": summary,
            "evidence": rows,
            "warnings": warnings,
            "display": {
                "support": f"{summary['support']['mentions']} mentions / "
                f"{summary['support']['reviewed_independent_origins']} reviewed independent origins",
                "contradict": f"{summary['contradict']['mentions']} mentions / "
                f"{summary['contradict']['reviewed_independent_origins']} reviewed independent origins",
            },
            "source_independence_is_truth_probability": False,
            "source_independence_determines_truth": False,
            "automatic_claim_acceptance": False,
        }

    def case_report(self, *, identity, case_id):
        self._authorize(identity, case_id, "case.read", case_id)
        claims = [
            self.claim_source_lineage(identity=identity, claim_id=claim["claim_id"])
            for claim in self.closure447.case_claims(case_id)
        ]
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "aliases": self.alias_candidates(identity=identity, case_id=case_id),
            "entity_pairs": self.pair_candidates(identity=identity, case_id=case_id),
            "claims": claims,
            "automatic_merge": False,
            "automatic_truth_determination": False,
        }

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("phase20_alias_candidate_456", "candidate_id"),
            ("phase20_entity_pair_candidate_456", "pair_id"),
            ("phase20_source_lineage_review_456", "review_id"),
            ("phase20_entity_lineage_run_456", "run_id"),
        ):
            for raw in self.db.all("SELECT * FROM " + table):
                row = dict(raw)
                if self._rh(row) != row.get("record_hash"):
                    bad.append({"table": table, key: row.get(key), "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        integrity = self.verify_integrity()
        aliases = int(self.db.one("SELECT COUNT(*) AS n FROM phase20_alias_candidate_456")["n"])
        pairs = int(self.db.one("SELECT COUNT(*) AS n FROM phase20_entity_pair_candidate_456")["n"])
        lineage = int(self.db.one("SELECT COUNT(*) AS n FROM phase20_source_lineage_review_456")["n"])
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "name": "Multilingual Entity Resolution + Source Lineage",
            "integrity_valid": bool(integrity["valid"]),
            "alias_candidates": aliases,
            "entity_pair_candidates": pairs,
            "source_lineage_reviews": lineage,
            "languages_scripts": ["Hebrew", "Arabic", "Cyrillic", "Latin"],
            "source_independence_metrics": True,
            "raw_mentions_vs_independent_origins": True,
            "automatic_identity_confirmation": False,
            "automatic_entity_merge": False,
            "automatic_truth_determination": False,
            "full_research_gate_this_build": False,
            "full_research_gate_cadence": "every_fifth_build",
            "next_checkpoint": "460.0",
            "production_release_ready": False,
        }
