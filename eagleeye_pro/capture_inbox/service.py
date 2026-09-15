from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse, urlunparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.policy import PolicyGate

MAX_CAPTURE_INBOX_URLS = 50

CATEGORY_RULES: List[Tuple[str, List[str]]] = [
    ("professional_profile", ["linkedin.", "xing.", "kununu", "about.me"]),
    ("technical_profile", ["github.", "gitlab.", "stackoverflow.", "stackexchange."]),
    ("image_media", ["images", "img", "foto", "photo", "youtube.", "vimeo.", "instagram.", "flickr."]),
    ("geo_context", ["maps.google.", "openstreetmap.", "maps.", "map", "location"]),
    ("document_pdf", [".pdf", "filetype:pdf", "/pdf", "document"]),
    ("news_press", ["news", "presse", "press", "zeitung", "magazin"]),
    ("business_register", ["register", "opencorporates", "northdata", "bundesanzeiger", "company", "firma", "impressum"]),
    ("counter_evidence", ["namensdoppler", "widerspruch", "gegenbeleg", "same name"]),
]

SOURCE_LABELS = {
    "professional_profile": "Berufliches/öffentliches Profil",
    "technical_profile": "Technisches öffentliches Profil",
    "image_media": "Bild-/Medienfund",
    "geo_context": "Geo-/Karten-/Ortskontext",
    "document_pdf": "Dokument/PDF",
    "news_press": "Presse/News",
    "business_register": "Firma/Register/Impressum",
    "counter_evidence": "Gegenbeleg/Namensdoppler",
    "web_public": "Öffentlicher Webtreffer",
}

class CaptureInboxService:
    """Fast return path from browser results to Review Inbox.

    Build 37.0 keeps the professional chain intact: URL intake creates preview
    items first; promotion creates Source Capture + Review Item through the
    existing SearchWorkbenchService. No capture is promoted directly to Evidence.
    """

    def __init__(self, db: Database, audit: AuditService, search_workbench):
        self.db = db
        self.audit = audit
        self.search_workbench = search_workbench
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS capture_inbox_batches (
          batch_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, phase_key TEXT DEFAULT '',
          target_id TEXT DEFAULT '', source_mode TEXT DEFAULT 'clipboard_or_manual',
          input_hash TEXT NOT NULL, raw_input_preview TEXT DEFAULT '', url_count INTEGER DEFAULT 0,
          valid_count INTEGER DEFAULT 0, invalid_count INTEGER DEFAULT 0,
          duplicate_count INTEGER DEFAULT 0, status TEXT DEFAULT 'parsed',
          created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS capture_inbox_items (
          inbox_item_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, case_id TEXT NOT NULL,
          phase_key TEXT DEFAULT '', source_url TEXT NOT NULL, normalized_url TEXT NOT NULL,
          host TEXT DEFAULT '', title_suggestion TEXT NOT NULL, snippet_suggestion TEXT DEFAULT '',
          source_category TEXT DEFAULT 'web_public', category_label TEXT DEFAULT '',
          duplicate_status TEXT DEFAULT 'new', duplicate_refs_json TEXT DEFAULT '[]',
          validation_status TEXT DEFAULT 'valid', validation_notes TEXT DEFAULT '',
          capture_id TEXT DEFAULT '', review_item_id TEXT DEFAULT '', status TEXT DEFAULT 'ready_for_capture',
          created_at TEXT NOT NULL, captured_at TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(batch_id) REFERENCES capture_inbox_batches(batch_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS capture_inbox_domain_profiles (
          profile_id TEXT PRIMARY KEY, host TEXT NOT NULL UNIQUE, source_category TEXT NOT NULL,
          category_label TEXT NOT NULL, trust_hint TEXT DEFAULT 'unknown', capture_hint TEXT DEFAULT '',
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_capture_inbox_batches_case ON capture_inbox_batches(case_id, created_at, status);
        CREATE INDEX IF NOT EXISTS idx_capture_inbox_items_case ON capture_inbox_items(case_id, status, duplicate_status, created_at);
        CREATE INDEX IF NOT EXISTS idx_capture_inbox_items_batch ON capture_inbox_items(batch_id, status);
        CREATE INDEX IF NOT EXISTS idx_capture_inbox_items_url ON capture_inbox_items(case_id, normalized_url);
        """)
        self.db.conn.commit()

    @staticmethod
    def _sha(text: str) -> str:
        return __import__("hashlib").sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _extract_urls(text: str) -> List[str]:
        urls: List[str] = []
        # Match full URLs and common www-prefixed URLs even when pasted from search results.
        pattern = re.compile(r"(?i)\b((?:https?://|www\.)[^\s<>'\"\]\)]+)")
        for m in pattern.finditer(text or ""):
            u = m.group(1).strip().rstrip(".,;:")
            if u.lower().startswith("www."):
                u = "https://" + u
            if u not in urls:
                urls.append(u)
            if len(urls) >= MAX_CAPTURE_INBOX_URLS:
                break
        return urls

    @staticmethod
    def _is_private_host(host: str) -> bool:
        h = (host or "").split(":", 1)[0].strip().lower()
        if h in {"localhost", "local", "0.0.0.0"}:
            return True
        try:
            ip = ipaddress.ip_address(h)
            return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        except ValueError:
            return h.endswith(".local") or h.endswith(".lan")

    @classmethod
    def normalize_public_url(cls, url: str) -> Tuple[str, str]:
        candidate = (url or "").strip()
        if candidate.lower().startswith("www."):
            candidate = "https://" + candidate
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Nur öffentliche http/https-URLs sind erlaubt.")
        host = (parsed.hostname or "").lower()
        if cls._is_private_host(host):
            raise ValueError("Lokale/private Netzwerkadressen werden blockiert.")
        # Normalize scheme/host, remove fragments, keep path/query for evidence traceability.
        netloc = parsed.netloc.lower()
        normalized = urlunparse((parsed.scheme.lower(), netloc, parsed.path or "/", "", parsed.query or "", ""))
        return normalized, host

    @staticmethod
    def suggest_category(url: str, host: str) -> str:
        hay = f"{host} {url}".lower()
        for category, needles in CATEGORY_RULES:
            if any(n in hay for n in needles):
                return category
        return "web_public"

    @staticmethod
    def suggest_title(url: str, host: str, title_prefix: str = "Öffentlicher Treffer") -> str:
        parsed = urlparse(url)
        path = (parsed.path or "/").strip("/")
        short_path = path.split("/")[-1] if path else ""
        if short_path:
            short_path = re.sub(r"[-_]+", " ", short_path)[:80]
            return f"{title_prefix}: {host} / {short_path}"
        return f"{title_prefix}: {host}"

    def duplicate_preview(self, case_id: str, normalized_url: str) -> Dict[str, Any]:
        refs: List[Dict[str, str]] = []
        for table, id_col, type_label in [
            ("source_captures", "capture_id", "source_capture"),
            ("review_items", "item_id", "review_item"),
            ("capture_inbox_items", "inbox_item_id", "capture_inbox_item"),
        ]:
            try:
                if table == "review_items":
                    rows = self.db.all("SELECT item_id AS id, title, normalized_url AS url, status FROM review_items WHERE case_id=? AND normalized_url=?", [case_id, normalized_url])
                elif table == "source_captures":
                    rows = self.db.all("SELECT capture_id AS id, title, url, chain_status AS status FROM source_captures WHERE case_id=? AND url=?", [case_id, normalized_url])
                else:
                    rows = self.db.all("SELECT inbox_item_id AS id, title_suggestion AS title, normalized_url AS url, status FROM capture_inbox_items WHERE case_id=? AND normalized_url=?", [case_id, normalized_url])
                for r in rows:
                    refs.append({"type": type_label, "id": r.get("id", ""), "title": r.get("title", ""), "status": r.get("status", "")})
            except Exception:
                continue
        return {"duplicate": bool(refs), "refs": refs, "count": len(refs)}

    def parse_candidates(self, case_id: str, urls_text: str, title_prefix: str = "Öffentlicher Treffer", snippet: str = "") -> Dict[str, Any]:
        extracted = self._extract_urls(urls_text)
        candidates: List[Dict[str, Any]] = []
        invalid: List[Dict[str, str]] = []
        for raw in extracted:
            try:
                normalized, host = self.normalize_public_url(raw)
                text_eval = PolicyGate.evaluate_query(" ".join([normalized, snippet or ""]))
                if not text_eval.get("ok"):
                    invalid.append({"url": raw, "reason": text_eval.get("reason", "policy_block")})
                    continue
                category = self.suggest_category(normalized, host)
                dup = self.duplicate_preview(case_id, normalized)
                candidates.append({
                    "raw_url": raw,
                    "normalized_url": normalized,
                    "host": host,
                    "title_suggestion": self.suggest_title(normalized, host, title_prefix),
                    "snippet_suggestion": snippet or "Manuell geprüfter öffentlicher Treffer; Kandidat für Review.",
                    "source_category": category,
                    "category_label": SOURCE_LABELS.get(category, SOURCE_LABELS["web_public"]),
                    "duplicate_status": "possible_duplicate" if dup["duplicate"] else "new",
                    "duplicate_refs": dup["refs"],
                    "validation_status": "valid",
                    "validation_notes": "http/https public URL; no login/captcha/private-network bypass",
                })
            except Exception as exc:
                invalid.append({"url": raw, "reason": str(exc)})
        return {"candidates": candidates, "invalid": invalid, "extracted": len(extracted)}

    def create_batch(self, case_id: str, urls_text: str, phase_key: str = "", target_id: str = "", title_prefix: str = "Öffentlicher Treffer", snippet: str = "", notes: str = "") -> Dict[str, Any]:
        if not case_id:
            raise ValueError("Fall-ID fehlt.")
        parsed = self.parse_candidates(case_id, urls_text, title_prefix=title_prefix, snippet=snippet)
        if not parsed["candidates"] and not parsed["invalid"]:
            raise ValueError("Keine URL im Eingabetext gefunden.")
        batch_id = new_id("capbatch")
        ts = now_ts()
        input_hash = self._sha(urls_text or "")
        duplicate_count = sum(1 for c in parsed["candidates"] if c["duplicate_status"] != "new")
        self.db.execute("""INSERT INTO capture_inbox_batches(batch_id,case_id,phase_key,target_id,source_mode,input_hash,raw_input_preview,url_count,valid_count,invalid_count,duplicate_count,status,created_at,created_by,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
            batch_id, case_id, phase_key, target_id, "clipboard_or_manual", input_hash, (urls_text or "")[:1200], parsed["extracted"],
            len(parsed["candidates"]), len(parsed["invalid"]), duplicate_count, "parsed", ts, "local-analyst", notes
        ])
        items = []
        for cand in parsed["candidates"]:
            item_id = new_id("capin")
            self.db.execute("""INSERT INTO capture_inbox_items(inbox_item_id,batch_id,case_id,phase_key,source_url,normalized_url,host,title_suggestion,snippet_suggestion,source_category,category_label,duplicate_status,duplicate_refs_json,validation_status,validation_notes,status,created_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
                item_id, batch_id, case_id, phase_key, cand["raw_url"], cand["normalized_url"], cand["host"], cand["title_suggestion"], cand["snippet_suggestion"],
                cand["source_category"], cand["category_label"], cand["duplicate_status"], dumps(cand["duplicate_refs"]), cand["validation_status"], cand["validation_notes"],
                "duplicate_review" if cand["duplicate_status"] != "new" else "ready_for_capture", ts, notes
            ])
            items.append(self.get_item(item_id))
            self._upsert_domain_profile(cand["host"], cand["source_category"], cand["category_label"])
        self.audit.log("parse", "capture_inbox_batch", batch_id, case_id, {"valid": len(items), "invalid": parsed["invalid"], "duplicates": duplicate_count, "phase_key": phase_key})
        return {"batch_id": batch_id, "created_items": len(items), "invalid_items": parsed["invalid"], "duplicate_count": duplicate_count, "items": items}

    def _upsert_domain_profile(self, host: str, category: str, label: str) -> None:
        if not host:
            return
        ts = now_ts()
        hint = "öffentliche Quelle manuell prüfen; kein Login-/Captcha-/Privatbereich-Abruf"
        existing = self.db.one("SELECT profile_id FROM capture_inbox_domain_profiles WHERE host=?", [host])
        if existing:
            self.db.execute("UPDATE capture_inbox_domain_profiles SET source_category=?, category_label=?, capture_hint=?, updated_at=? WHERE host=?", [category, label, hint, ts, host])
        else:
            self.db.execute("""INSERT INTO capture_inbox_domain_profiles(profile_id,host,source_category,category_label,trust_hint,capture_hint,updated_at)
            VALUES(?,?,?,?,?,?,?)""", [new_id("domprof"), host, category, label, "unknown", hint, ts])

    def get_item(self, inbox_item_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM capture_inbox_items WHERE inbox_item_id=?", [inbox_item_id])
        if not row:
            raise KeyError(f"Capture-Inbox-Item nicht gefunden: {inbox_item_id}")
        row["duplicate_refs_json"] = loads(row.get("duplicate_refs_json"), [])
        return row

    def list_items(self, case_id: str, status: str = "") -> List[Dict[str, Any]]:
        if status:
            rows = self.db.all("SELECT * FROM capture_inbox_items WHERE case_id=? AND status=? ORDER BY created_at DESC", [case_id, status])
        else:
            rows = self.db.all("SELECT * FROM capture_inbox_items WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["duplicate_refs_json"] = loads(r.get("duplicate_refs_json"), [])
        return rows

    def promote_item_to_review(self, inbox_item_id: str, force_duplicate: bool = False) -> Dict[str, Any]:
        item = self.get_item(inbox_item_id)
        if item.get("status") == "captured_to_review":
            return item
        if item.get("duplicate_status") != "new" and not force_duplicate:
            self.db.execute("UPDATE capture_inbox_items SET status=?, validation_notes=? WHERE inbox_item_id=?", ["duplicate_review", "Möglicher Duplicate; vor Capture prüfen oder force_duplicate=True setzen.", inbox_item_id])
            return self.get_item(inbox_item_id)
        cap = self.search_workbench.capture_public_hit(
            item["case_id"], "", item["title_suggestion"], item["normalized_url"], item.get("snippet_suggestion") or "Manuell geprüfter öffentlicher Treffer; Kandidat für Review.",
            notes=f"Build 37.0 Query Factory & Search Matrix Pro: phase={item.get('phase_key','')}; category={item.get('source_category','web_public')}; public_candidate_only",
            score=0.58,
        )
        cap_full = self.search_workbench.get_capture(cap["capture_id"])
        self.db.execute("""UPDATE capture_inbox_items SET capture_id=?, review_item_id=?, status=?, captured_at=?, validation_notes=? WHERE inbox_item_id=?""", [
            cap["capture_id"], cap_full.get("review_item_id", ""), "captured_to_review", now_ts(), "Captured through existing Source Capture → Review chain.", inbox_item_id
        ])
        self.audit.log("promote", "capture_inbox_item", inbox_item_id, item["case_id"], {"capture_id": cap["capture_id"], "review_item_id": cap_full.get("review_item_id"), "force_duplicate": force_duplicate})
        return self.get_item(inbox_item_id)

    def promote_batch_to_review(self, batch_id: str, force_duplicates: bool = False) -> Dict[str, Any]:
        batch = self.db.one("SELECT * FROM capture_inbox_batches WHERE batch_id=?", [batch_id])
        if not batch:
            raise KeyError("Capture-Inbox-Batch nicht gefunden.")
        items = self.db.all("SELECT inbox_item_id FROM capture_inbox_items WHERE batch_id=? ORDER BY created_at", [batch_id])
        promoted = 0; held = 0; errors: List[Dict[str, str]] = []
        for row in items:
            try:
                after = self.promote_item_to_review(row["inbox_item_id"], force_duplicate=force_duplicates)
                if after.get("status") == "captured_to_review":
                    promoted += 1
                else:
                    held += 1
            except Exception as exc:
                errors.append({"inbox_item_id": row["inbox_item_id"], "error": str(exc)})
        status = "captured_to_review" if promoted and not held and not errors else "review_required"
        self.db.execute("UPDATE capture_inbox_batches SET status=? WHERE batch_id=?", [status, batch_id])
        self.audit.log("promote", "capture_inbox_batch", batch_id, batch["case_id"], {"promoted": promoted, "held": held, "errors": errors})
        return {"batch_id": batch_id, "promoted": promoted, "held_for_duplicate_review": held, "errors": errors, "status": status}

    def dashboard(self, case_id: str) -> Dict[str, Any]:
        status_rows = self.db.all("SELECT status, COUNT(*) AS n FROM capture_inbox_items WHERE case_id=? GROUP BY status", [case_id])
        cat_rows = self.db.all("SELECT source_category, COUNT(*) AS n FROM capture_inbox_items WHERE case_id=? GROUP BY source_category", [case_id])
        dup = self.db.one("SELECT COUNT(*) AS n FROM capture_inbox_items WHERE case_id=? AND duplicate_status<>'new'", [case_id]) or {"n": 0}
        batches = self.db.all("SELECT * FROM capture_inbox_batches WHERE case_id=? ORDER BY created_at DESC LIMIT 10", [case_id])
        recent = self.list_items(case_id)[:20]
        ready = sum(int(r["n"]) for r in status_rows if r["status"] == "ready_for_capture")
        next_action = "URLs aus Browser/Clipboard einfügen" if not status_rows else ("Ready Items capturen → Review Inbox" if ready else "Duplicate-/Review-Hinweise prüfen")
        return {
            "case_id": case_id,
            "status_counts": {r["status"]: r["n"] for r in status_rows},
            "category_counts": {r["source_category"]: r["n"] for r in cat_rows},
            "duplicate_candidates": int(dup.get("n") or 0),
            "batches": batches,
            "recent_items": recent,
            "next_action": next_action,
            "guardrails": [
                "capture_to_review_before_evidence",
                "http_https_public_urls_only",
                "private_network_urls_blocked",
                "duplicate_preview_before_capture",
                "no_login_captcha_private_account_bypass",
            ],
        }
