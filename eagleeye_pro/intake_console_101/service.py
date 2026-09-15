from __future__ import annotations
import html, json
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class IntakeConsole101Service:
    """Build 101.0: robust user-facing Copy-Paste / URL intake console.

    This layer exists because a working backend command is not enough for analysts.
    It provides a stable form-oriented workflow:
    - create/reuse draft case when no case_id is supplied
    - include URL, pasted text, or both
    - immediately run security/Spearhead checks when available
    - keep all pasted material as candidate_not_claim
    - render a local HTML console that can be opened without a web framework
    """
    def __init__(self, db: Database, audit: AuditService, *, copy_paste: Any, security: Any=None, dashboard: Any=None, review_board: Any=None, local_ai: Any=None):
        self.db = db
        self.audit = audit
        self.copy_paste = copy_paste
        self.security = security
        self.dashboard = dashboard
        self.review_board = review_board
        self.local_ai = local_ai
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS intake_console_101_events(
          event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, paste_id TEXT DEFAULT '',
          action TEXT NOT NULL, status TEXT NOT NULL, url TEXT DEFAULT '', title TEXT DEFAULT '',
          security_status TEXT DEFAULT '', created_at TEXT NOT NULL, details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_intake101_case ON intake_console_101_events(case_id, created_at);
        ''')
        self.db.conn.commit()

    def include(self, *, case_id: str='', url: str='', text: str='', html_snapshot: str='', title: str='', note: str='', snippet: str='', source_label: str='', run_security: bool=True, run_ai_triage: bool=True) -> Dict[str, Any]:
        url = (url or '').strip()
        text = text or ''
        html_snapshot = html_snapshot or ''
        title = (title or '').strip() or 'Pasted public finding'
        if not url and not text.strip() and not html_snapshot.strip():
            raise ValueError('No URL, text, or HTML snapshot supplied.')
        if url:
            finding = self.copy_paste.include_url(case_id or '', url, title=title, note=note, snippet=snippet, html=html_snapshot, text=text, metadata={'build':'101.0','source_label':source_label,'intake_console':True})
        else:
            finding = self.copy_paste.include_text(case_id or '', text or html_snapshot, title=title, source_url='', metadata={'build':'101.0','source_label':source_label,'intake_console':True})
        cid = finding['case_id']
        security_result = None
        ai_result = None
        if run_security and self.security:
            try:
                security_result = self.security.assess_case_security(cid, scope='copy_paste_intake_101')
            except Exception as e:
                security_result = {'decision':'review_required','error':str(e)}
        if run_ai_triage and self.local_ai:
            try:
                ai_result = self.local_ai.triage_pasted_finding(cid, finding.get('paste_id',''))
            except Exception as e:
                ai_result = {'status':'error','error':str(e)}
        event_id = new_id('intake101')
        sec_status = (security_result or {}).get('decision') or (security_result or {}).get('status') or ''
        self.db.execute('''INSERT INTO intake_console_101_events(event_id,case_id,paste_id,action,status,url,title,security_status,created_at,details_json)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [event_id,cid,finding.get('paste_id',''),'include_public_paste','stored_candidate_not_claim',finding.get('canonical_url') or finding.get('url',''),title,sec_status,now_ts(),dumps({'finding':finding,'security':security_result,'local_ai':ai_result})])
        self.audit.log('include', 'intake_console_101', event_id, cid, {'paste_id':finding.get('paste_id'), 'security_status': sec_status})
        return {'event_id': event_id, 'case_id': cid, 'finding': finding, 'security': security_result, 'local_ai': ai_result, 'status': 'stored_candidate_not_claim'}

    def recent(self, case_id: str='', limit: int=25) -> Dict[str, Any]:
        if case_id:
            rows = self.db.all('SELECT * FROM intake_console_101_events WHERE case_id=? ORDER BY created_at DESC LIMIT ?', [case_id, int(limit)])
        else:
            rows = self.db.all('SELECT * FROM intake_console_101_events ORDER BY created_at DESC LIMIT ?', [int(limit)])
        for r in rows:
            r['details'] = loads(r.pop('details_json','{}'), {})
        return {'count': len(rows), 'events': rows}

    def render_html(self, *, case_id: str='', message: str='', result: Dict[str,Any]|None=None) -> str:
        recent = self.recent(case_id, 15)['events']
        rows = []
        for r in recent:
            url = html.escape(r.get('url',''))
            title = html.escape(r.get('title',''))
            status = html.escape(r.get('status',''))
            sec = html.escape(r.get('security_status','') or 'not_run')
            rows.append(f'<tr><td>{html.escape(r.get("created_at",""))}</td><td>{title}</td><td><code>{url}</code></td><td>{status}</td><td>{sec}</td></tr>')
        res = ''
        if result is not None:
            res = '<h2>Letztes Ergebnis</h2><pre>' + html.escape(json.dumps(result, ensure_ascii=False, indent=2, default=str)) + '</pre>'
        msg = f'<p class="msg">{html.escape(message)}</p>' if message else ''
        case_value = html.escape(case_id or '')
        return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>EagleEye Intake Console 101</title>
<style>body{{font-family:Arial, sans-serif;margin:32px;max-width:1200px}} textarea,input{{width:100%;box-sizing:border-box;margin:6px 0 14px;padding:10px}} button{{padding:10px 16px;font-weight:bold}} code,pre{{background:#f4f4f4;padding:4px}} pre{{white-space:pre-wrap;border:1px solid #ddd;padding:12px}} table{{border-collapse:collapse;width:100%;margin-top:16px}}td,th{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}} .msg{{padding:10px;background:#eef7ee;border:1px solid #9c9}} .warn{{background:#fff7dc;padding:12px;border:1px solid #e2c36a}}</style></head><body>
<h1>EagleEye Copy-Paste / URL Intake Console 101</h1>
<div class="warn"><b>Prinzip:</b> Eingefügte URLs und Texte werden als <code>candidate_not_claim</code> gespeichert. Kein Fund wird automatisch zur Personenbehauptung.</div>
{msg}
<form method="post" action="/include">
<label>Case ID optional; leer = Draft-Fall wird automatisch erstellt/wiederverwendet</label><input name="case_id" value="{case_value}">
<label>Titel</label><input name="title" value="Pasted public finding">
<label>Öffentliche URL optional</label><input name="url" placeholder="https://...">
<label>Snippet / sichtbarer Text / Copy-Paste Text</label><textarea name="text" rows="10" placeholder="Hier öffentlichen Text oder Suchtreffer-Snippet einfügen"></textarea>
<label>HTML Snapshot optional</label><textarea name="html_snapshot" rows="6" placeholder="Optional: kopierter HTML-Auszug"></textarea>
<label>Source Label optional</label><input name="source_label" placeholder="z.B. Website, Suchmaschine, öffentliches Register">
<p><label><input type="checkbox" name="run_security" checked style="width:auto"> Security Complex sofort prüfen</label><br>
<label><input type="checkbox" name="run_ai_triage" checked style="width:auto"> Lokalen KI-Agenten für Triage-Vorschläge nutzen</label></p>
<button type="submit">Als öffentlichen Recherchekandidaten aufnehmen</button>
</form>
{res}
<h2>Letzte Intake-Ereignisse</h2><table><tr><th>Zeit</th><th>Titel</th><th>URL</th><th>Status</th><th>Security</th></tr>{''.join(rows) or '<tr><td colspan="5">Noch keine Intake-Ereignisse.</td></tr>'}</table>
</body></html>'''
