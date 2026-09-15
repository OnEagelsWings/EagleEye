from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy


class BrowserCaptureBridge102Service:
    """Build 102.0: Real Browser Capture Bridge.

    This is the practical bridge between a human browser session and EagleEye:
    - The analyst pastes a public URL plus visible text/HTML or imports a saved HTML/TXT file.
    - EagleEye normalizes the URL, writes immutable local snapshots, computes hashes,
      creates a manifest, links Evidence Vault 75, Real Capture 74, Copy-Paste Intake 91,
      Source Reliability 98, Security Complex 100 and Local AI 101 when available.
    - It never bypasses login, CAPTCHA, paywall or private accounts. Live network fetching
      is intentionally not performed by this service.
    """

    def __init__(
        self,
        db: Database,
        audit: AuditService,
        bridge_dir: str | Path,
        *,
        real_capture: Any = None,
        evidence_vault: Any = None,
        copy_paste: Any = None,
        security: Any = None,
        local_ai: Any = None,
        reliability: Any = None,
        canonical_pipeline: Any = None,
    ):
        self.db = db
        self.audit = audit
        self.bridge_dir = Path(bridge_dir)
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.real_capture = real_capture
        self.evidence = evidence_vault
        self.copy_paste = copy_paste
        self.security = security
        self.local_ai = local_ai
        self.reliability = reliability
        self.canonical_pipeline = canonical_pipeline
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS browser_captures_102(
              bridge_capture_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              url TEXT NOT NULL,
              canonical_url TEXT NOT NULL,
              title TEXT NOT NULL,
              capture_mode TEXT NOT NULL,
              status TEXT NOT NULL,
              html_path TEXT DEFAULT '',
              text_path TEXT DEFAULT '',
              screenshot_path TEXT DEFAULT '',
              manifest_path TEXT NOT NULL,
              html_sha256 TEXT DEFAULT '',
              text_sha256 TEXT DEFAULT '',
              screenshot_sha256 TEXT DEFAULT '',
              manifest_sha256 TEXT NOT NULL,
              real_capture_id TEXT DEFAULT '',
              evidence_id TEXT DEFAULT '',
              paste_id TEXT DEFAULT '',
              source_rating_id TEXT DEFAULT '',
              security_decision TEXT DEFAULT '',
              ai_run_id TEXT DEFAULT '',
              warnings_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_browsercapture102_case ON browser_captures_102(case_id, created_at);
            """
        )
        self.db.conn.commit()

    def capture_from_browser(
        self,
        *,
        case_id: str = "",
        url: str,
        title: str = "",
        visible_text: str = "",
        html_snapshot: str = "",
        screenshot_path: str = "",
        source_label: str = "browser_manual_public_capture",
        notes: str = "",
        run_security: bool = True,
        run_ai_triage: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if self.canonical_pipeline is not None:
            return self.canonical_pipeline.include_finding(case_id=case_id, url=url, title=title, text=visible_text, html_snapshot=html_snapshot, screenshot_path=screenshot_path, source_label=source_label, notes=notes, input_kind='browser_capture', run_security=run_security, run_ai_triage=run_ai_triage, metadata=metadata or {})
        if not (url or "").strip():
            raise ValueError("A public URL is required for Browser Capture Bridge 102.")
        policy = URLPolicy.normalize_public_url(url)
        if not policy.get("ok"):
            raise ValueError(policy.get("blocked_reason") or "URL blocked by URLPolicy")
        canonical_url = policy.get("canonical_url") or policy.get("normalized_url") or url.strip()
        case_id = case_id or self._ensure_default_case()
        title = (title or self._extract_title(html_snapshot) or canonical_url).strip()[:240]
        html_snapshot = html_snapshot or ""
        visible_text = visible_text or self._html_to_text(html_snapshot)
        if not visible_text.strip() and not html_snapshot.strip():
            raise ValueError("Capture requires visible text or HTML snapshot. URL-only capture belongs in Intake 101, not Browser Capture 102.")

        bridge_id = new_id("bc102")
        cdir = self.bridge_dir / case_id / bridge_id
        cdir.mkdir(parents=True, exist_ok=True)
        html_path = text_path = copied_screenshot = ""
        html_hash = text_hash = screenshot_hash = ""
        warnings: List[Dict[str, str]] = []

        if html_snapshot:
            hp = cdir / "snapshot.html"
            hp.write_text(html_snapshot, encoding="utf-8")
            html_path = str(hp)
            html_hash = self._sha_file(hp)
        if visible_text:
            tp = cdir / "visible_text.txt"
            tp.write_text(visible_text, encoding="utf-8")
            text_path = str(tp)
            text_hash = self._sha_file(tp)
        if screenshot_path:
            sp = Path(screenshot_path)
            if sp.exists() and sp.is_file():
                dest = cdir / ("screenshot" + sp.suffix[:20])
                shutil.copy2(sp, dest)
                copied_screenshot = str(dest)
                screenshot_hash = self._sha_file(dest)
            else:
                warnings.append({"level": "medium", "code": "screenshot_missing", "message": f"Screenshot path not found: {screenshot_path}"})
        else:
            warnings.append({"level": "low", "code": "screenshot_not_supplied", "message": "No screenshot was supplied; capture is still useful but less complete."})

        real_capture_id = evidence_id = paste_id = source_rating_id = ai_run_id = ""
        security_decision = "not_run"

        if self.real_capture:
            try:
                real = self.real_capture.capture_snapshot(
                    case_id,
                    canonical_url,
                    html=html_snapshot,
                    text=visible_text,
                    title=title,
                    metadata={"build": "102.0", "bridge_capture_id": bridge_id, "source_label": source_label, **(metadata or {})},
                )
                real_capture_id = real.get("capture_id", "")
            except Exception as exc:
                warnings.append({"level": "medium", "code": "real_capture_failed", "message": str(exc)})

        if self.evidence:
            try:
                ev = self.evidence.ingest_text(
                    case_id,
                    title,
                    visible_text or self._html_to_text(html_snapshot),
                    artifact_type="browser_visible_text_snapshot_102",
                    source_ref=canonical_url,
                    linked_object_type="browser_capture_102",
                    linked_object_id=bridge_id,
                    metadata={"build": "102.0", "canonical_url": canonical_url, "source_label": source_label},
                )
                evidence_id = ev.get("evidence_id", "")
            except Exception as exc:
                warnings.append({"level": "medium", "code": "evidence_ingest_failed", "message": str(exc)})

        if self.copy_paste:
            try:
                paste = self.copy_paste.include_url(
                    case_id,
                    canonical_url,
                    title=title,
                    note=notes,
                    snippet=(visible_text or "")[:500],
                    html=html_snapshot,
                    text=visible_text,
                    metadata={"build": "102.0", "bridge_capture_id": bridge_id, "source_label": source_label},
                )
                paste_id = paste.get("paste_id", "")
            except Exception as exc:
                warnings.append({"level": "low", "code": "copy_paste_link_failed", "message": str(exc)})

        if self.reliability:
            try:
                rating = self.reliability.rate(
                    case_id,
                    source_ref=canonical_url,
                    source_type="public_web_capture",
                    factors={
                        "primary_source": False,
                        "archived": False,
                        "timestamped": True,
                        "hash_verified": bool(text_hash or html_hash),
                        "anonymous": False,
                        "user_generated": False,
                        "stale": False,
                        "contradicted": False,
                        "browser_capture_102": True,
                    },
                )
                source_rating_id = rating.get("rating_id", "") or rating.get("source_rating_id", "")
            except Exception as exc:
                warnings.append({"level": "low", "code": "source_reliability_failed", "message": str(exc)})

        if run_security and self.security:
            try:
                sec = self.security.assess_case_security(case_id, scope="browser_capture_bridge_102")
                security_decision = sec.get("decision") or sec.get("status") or "review_required"
            except Exception as exc:
                security_decision = "review_required"
                warnings.append({"level": "medium", "code": "security_check_failed", "message": str(exc)})

        if run_ai_triage and self.local_ai and paste_id:
            try:
                ai = self.local_ai.triage_pasted_finding(case_id, paste_id)
                ai_run_id = ai.get("run_id", "")
            except Exception as exc:
                warnings.append({"level": "low", "code": "local_ai_triage_failed", "message": str(exc)})

        manifest = {
            "schema": "browser_capture_bridge_manifest_v1",
            "build": "102.0",
            "bridge_capture_id": bridge_id,
            "case_id": case_id,
            "url": url,
            "canonical_url": canonical_url,
            "title": title,
            "capture_mode": "manual_browser_snapshot",
            "public_only": True,
            "no_login_bypass": True,
            "no_captcha_bypass": True,
            "no_paywall_bypass": True,
            "created_at": now_ts(),
            "files": {
                "html_path": html_path,
                "text_path": text_path,
                "screenshot_path": copied_screenshot,
                "html_sha256": html_hash,
                "text_sha256": text_hash,
                "screenshot_sha256": screenshot_hash,
            },
            "links": {
                "real_capture_id": real_capture_id,
                "evidence_id": evidence_id,
                "paste_id": paste_id,
                "source_rating_id": source_rating_id,
                "ai_run_id": ai_run_id,
            },
            "warnings": warnings,
            "metadata": metadata or {},
        }
        mp = cdir / "MANIFEST_BROWSER_CAPTURE_102.json"
        mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_hash = self._sha_file(mp)
        created = manifest["created_at"]

        self.db.execute(
            """INSERT INTO browser_captures_102(bridge_capture_id,case_id,url,canonical_url,title,capture_mode,status,html_path,text_path,screenshot_path,manifest_path,html_sha256,text_sha256,screenshot_sha256,manifest_sha256,real_capture_id,evidence_id,paste_id,source_rating_id,security_decision,ai_run_id,warnings_json,metadata_json,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                bridge_id,
                case_id,
                url,
                canonical_url,
                title,
                "manual_browser_snapshot",
                "stored_candidate_not_claim",
                html_path,
                text_path,
                copied_screenshot,
                str(mp),
                html_hash,
                text_hash,
                screenshot_hash,
                manifest_hash,
                real_capture_id,
                evidence_id,
                paste_id,
                source_rating_id,
                security_decision,
                ai_run_id,
                dumps(warnings),
                dumps(metadata or {}),
                created,
            ],
        )
        self.audit.log("capture", "browser_capture_102", bridge_id, case_id, {"canonical_url": canonical_url, "security_decision": security_decision, "evidence_id": evidence_id})
        return self.get(bridge_id)

    def capture_from_file(
        self,
        *,
        case_id: str = "",
        url: str,
        file_path: str | Path,
        title: str = "",
        source_label: str = "browser_saved_file",
        notes: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
        raw = path.read_text(encoding="utf-8", errors="ignore")
        suffix = path.suffix.lower()
        if suffix in {".html", ".htm"} or "<html" in raw[:500].lower():
            return self.capture_from_browser(case_id=case_id, url=url, title=title or self._extract_title(raw), html_snapshot=raw, visible_text=self._html_to_text(raw), source_label=source_label, notes=notes, metadata={"source_file": str(path), **(metadata or {})})
        return self.capture_from_browser(case_id=case_id, url=url, title=title or path.name, visible_text=raw, source_label=source_label, notes=notes, metadata={"source_file": str(path), **(metadata or {})})

    def get(self, bridge_capture_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM browser_captures_102 WHERE bridge_capture_id=?", [bridge_capture_id])
        if not row:
            raise KeyError(bridge_capture_id)
        row["warnings"] = loads(row.pop("warnings_json", "[]"), [])
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def list(self, case_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        if case_id:
            rows = self.db.all("SELECT bridge_capture_id FROM browser_captures_102 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])
        else:
            rows = self.db.all("SELECT bridge_capture_id FROM browser_captures_102 ORDER BY created_at DESC LIMIT ?", [int(limit)])
        return [self.get(r["bridge_capture_id"]) for r in rows]

    def verify(self, bridge_capture_id: str) -> Dict[str, Any]:
        cap = self.get(bridge_capture_id)
        problems: List[str] = []
        for field, hash_field in (("html_path", "html_sha256"), ("text_path", "text_sha256"), ("screenshot_path", "screenshot_sha256"), ("manifest_path", "manifest_sha256")):
            path = cap.get(field) or ""
            expected = cap.get(hash_field) or ""
            if not path:
                continue
            p = Path(path)
            if not p.exists():
                problems.append(f"{field}_missing")
            elif expected and self._sha_file(p) != expected:
                problems.append(f"{field}_hash_mismatch")
        return {"bridge_capture_id": bridge_capture_id, "valid": not problems, "problems": problems, "status": "verified" if not problems else "tamper_warning"}

    def render_html(self, case_id: str = "", message: str = "", result: Dict[str, Any] | None = None) -> str:
        rows = []
        for cap in self.list(case_id=case_id, limit=20):
            rows.append(
                "<tr>"
                f"<td>{html_lib.escape(cap.get('created_at',''))}</td>"
                f"<td>{html_lib.escape(cap.get('title',''))}</td>"
                f"<td><code>{html_lib.escape(cap.get('canonical_url',''))}</code></td>"
                f"<td>{html_lib.escape(cap.get('status',''))}</td>"
                f"<td>{html_lib.escape(cap.get('security_decision',''))}</td>"
                f"<td><code>{html_lib.escape(cap.get('bridge_capture_id',''))}</code></td>"
                "</tr>"
            )
        result_html = ""
        if result is not None:
            result_html = "<h2>Letztes Capture</h2><pre>" + html_lib.escape(json.dumps(result, ensure_ascii=False, indent=2, default=str)) + "</pre>"
        msg_html = f'<p class="msg">{html_lib.escape(message)}</p>' if message else ""
        return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>EagleEye Browser Capture Bridge 102</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;max-width:1200px}}textarea,input{{width:100%;box-sizing:border-box;margin:6px 0 14px;padding:10px}}button{{padding:10px 16px;font-weight:bold}}pre,code{{background:#f4f4f4}}pre{{white-space:pre-wrap;border:1px solid #ddd;padding:12px}}table{{border-collapse:collapse;width:100%;margin-top:16px}}td,th{{border:1px solid #ddd;padding:8px;vertical-align:top;text-align:left}}.warn{{background:#fff7dc;border:1px solid #e2c36a;padding:12px}}.msg{{background:#eef7ee;border:1px solid #9c9;padding:10px}}</style></head><body>
<h1>EagleEye Browser Capture Bridge 102</h1>
<div class="warn"><b>Public-only:</b> Nutze diese Bridge nur für öffentlich sichtbare Inhalte. Kein Login-, CAPTCHA-, Paywall- oder Private-Account-Bypass. Captures bleiben <code>candidate_not_claim</code>.</div>
{msg_html}
<form method="post" action="/capture">
<label>Case ID optional</label><input name="case_id" value="{html_lib.escape(case_id or '')}">
<label>Öffentliche URL *</label><input name="url" placeholder="https://..." required>
<label>Titel</label><input name="title" placeholder="Seitentitel oder Fundtitel">
<label>Sichtbarer Text / kopierter Seiteninhalt *</label><textarea name="visible_text" rows="10" placeholder="Hier sichtbaren öffentlichen Text aus dem Browser einfügen"></textarea>
<label>HTML Snapshot optional</label><textarea name="html_snapshot" rows="8" placeholder="Optional: gespeicherter/kopierter HTML-Auszug"></textarea>
<label>Screenshot-Pfad optional</label><input name="screenshot_path" placeholder="C:\\...\\screenshot.png oder /home/.../screenshot.png">
<label>Source Label</label><input name="source_label" value="browser_manual_public_capture">
<p><label><input type="checkbox" name="run_security" checked style="width:auto"> Security Complex prüfen</label><br>
<label><input type="checkbox" name="run_ai_triage" checked style="width:auto"> Lokalen KI-Agenten triagieren lassen</label></p>
<button type="submit">Browser-Capture speichern</button>
</form>
{result_html}
<h2>Letzte Browser-Captures</h2><table><tr><th>Zeit</th><th>Titel</th><th>URL</th><th>Status</th><th>Security</th><th>ID</th></tr>{''.join(rows) or '<tr><td colspan="6">Noch keine Captures.</td></tr>'}</table>
</body></html>'''

    def _ensure_default_case(self) -> str:
        if self.copy_paste and hasattr(self.copy_paste, "ensure_default_case"):
            return self.copy_paste.ensure_default_case()
        row = self.db.one("SELECT case_id FROM cases WHERE title=? ORDER BY created_at DESC LIMIT 1", ["Browser Capture Bridge Case"])
        if row:
            return row["case_id"]
        cid = new_id("case")
        ts = now_ts()
        self.db.execute("""INSERT INTO cases(case_id,title,client,purpose,legal_basis,jurisdiction,risk_level,status,retention_until,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [cid, "Browser Capture Bridge Case", "Local Analyst", "Public-only browser capture review", "legitimate_interest / manual review required", "DE/EU", "medium", "draft", "", ts, ts])
        self.audit.log("create", "case", cid, cid, {"via": "browser_capture_bridge_102"})
        return cid

    def _extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    def _html_to_text(self, html: str) -> str:
        no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", no_script)
        return re.sub(r"\s+", " ", text).strip()

    def _sha_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
