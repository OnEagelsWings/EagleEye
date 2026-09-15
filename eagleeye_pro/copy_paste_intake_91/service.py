from __future__ import annotations
import hashlib, re
from typing import Any, Dict
from urllib.parse import urlparse
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

class CopyPasteIntake91Service:
    """Build 91.0 / 100.1: robust copy-paste intake for public URLs and pasted web text.

    Design contract:
    - pasted URL/text is stored as candidate_not_claim
    - URL is normalized through URLPolicy
    - text/html is linked into Capture 74, Evidence Vault 75, Document Intel 85, Search Adapter 81, Graph 68
    - a missing case_id creates a local draft intake case so the UI can paste first and review later
    """
    def __init__(self, db: Database, audit: AuditService, *, real_capture: Any=None, evidence_vault: Any=None, search_adapter: Any=None, document_intel: Any=None, graph: Any=None):
        self.db = db
        self.audit = audit
        self.real_capture = real_capture
        self.evidence = evidence_vault
        self.search = search_adapter
        self.documents = document_intel
        self.graph = graph
        self.canonical_pipeline = None
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS pasted_findings_91(
          paste_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
          input_kind TEXT NOT NULL, url TEXT DEFAULT '', canonical_url TEXT DEFAULT '', host TEXT DEFAULT '',
          pasted_text_hash TEXT DEFAULT '', pasted_html_hash TEXT DEFAULT '',
          status TEXT DEFAULT 'candidate_not_claim', classification TEXT DEFAULT 'public_web_candidate',
          capture_id TEXT DEFAULT '', evidence_id TEXT DEFAULT '', search_result_id TEXT DEFAULT '', document_id TEXT DEFAULT '',
          warnings_json TEXT NOT NULL, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pasted91_case ON pasted_findings_91(case_id, created_at);
        """)
        self.db.conn.commit()
        self._add_column_if_missing('pasted_findings_91', 'content_excerpt', "TEXT DEFAULT ''")
        self._add_column_if_missing('pasted_findings_91', 'source_label', "TEXT DEFAULT ''")

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        cols = [r['name'] for r in self.db.all(f"PRAGMA table_info({table})")]
        if column not in cols:
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def ensure_default_case(self) -> str:
        row = self.db.one("SELECT case_id FROM cases WHERE title=? ORDER BY created_at DESC LIMIT 1", ["Copy-Paste Intake Case"])
        if row:
            return row['case_id']
        cid = new_id('case')
        ts = now_ts()
        self.db.execute("""INSERT INTO cases(case_id,title,client,purpose,legal_basis,jurisdiction,risk_level,status,retention_until,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [cid, 'Copy-Paste Intake Case', 'Local Analyst', 'Public-only copy-paste intake for manually reviewed OSINT findings', 'legitimate_interest / manual review required', 'DE/EU', 'medium', 'draft', '', ts, ts])
        self.audit.log('create', 'case', cid, cid, {'via': 'copy_paste_intake_91_default_case'})
        return cid

    def include_url(self, case_id: str, url: str, *, title: str='', note: str='', snippet: str='', html: str='', text: str='', target_ref: str='', metadata: Dict[str,Any]|None=None) -> Dict[str,Any]:
        if self.canonical_pipeline is not None:
            return self.canonical_pipeline.include_finding(case_id=case_id, url=url, title=title, text=text or snippet or note, html_snapshot=html, source_label='copy_paste_url', notes=note, input_kind='paste', metadata={'target_ref': target_ref, **(metadata or {})})
        case_id = case_id or self.ensure_default_case()
        dec = URLPolicy.normalize_public_url(url)
        if not dec.get('ok'):
            raise ValueError(dec.get('blocked_reason') or 'URL blocked by URLPolicy')
        canon = dec.get('canonical_url') or dec.get('normalized_url') or url
        host = urlparse(canon).netloc.lower()
        if not title:
            title = self._title(html) or canon
        body = text or self._html_to_text(html) or snippet or note
        warnings = []
        if not body and not html:
            warnings.append({'level':'medium','code':'url_only','message':'Only the URL was pasted; capture or manual review is still required.'})
        pid = new_id('paste91')
        capture_id = evidence_id = search_result_id = document_id = ''
        if self.search:
            try:
                search_result_id = self.search.import_result(case_id, title, canon, snippet=snippet or body[:280], plan_id='', metadata={'build':'100.1','intake':'copy_paste_url','target_ref':target_ref}).get('result_id','')
            except Exception as e:
                warnings.append({'level':'low','code':'search_import_failed','message':str(e)})
        if (html or body) and self.real_capture:
            try:
                capture_id = self.real_capture.capture_snapshot(case_id, canon, html=html, text=body, title=title, metadata={'build':'100.1','intake':'copy_paste_url','target_ref':target_ref}).get('capture_id','')
            except Exception as e:
                warnings.append({'level':'medium','code':'capture_failed','message':str(e)})
        if body and self.evidence:
            try:
                evidence_id = self.evidence.ingest_text(case_id, title, body, artifact_type='pasted_public_web_finding', source_ref=canon, linked_object_type='pasted_finding_91', linked_object_id=pid, metadata={'build':'100.1','url':canon,'target_ref':target_ref}).get('evidence_id','')
            except Exception as e:
                warnings.append({'level':'medium','code':'evidence_ingest_failed','message':str(e)})
        if body and self.documents:
            try:
                document_id = self.documents.analyze_text(case_id, title, body, source_url=canon, document_type='pasted_web_text', metadata={'build':'100.1','intake':'copy_paste'}).get('document_id','')
            except Exception as e:
                warnings.append({'level':'low','code':'document_analysis_failed','message':str(e)})
        html_hash = hashlib.sha256((html or '').encode()).hexdigest() if html else ''
        text_hash = hashlib.sha256((body or '').encode()).hexdigest() if body else ''
        excerpt = (body or snippet or note or html or '')[:2000]
        self.db.execute('''INSERT INTO pasted_findings_91(paste_id,case_id,title,input_kind,url,canonical_url,host,pasted_text_hash,pasted_html_hash,status,classification,capture_id,evidence_id,search_result_id,document_id,warnings_json,created_at,metadata_json,content_excerpt,source_label)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [pid,case_id,title,'url',url,canon,host,text_hash,html_hash,'candidate_not_claim','public_web_candidate',capture_id,evidence_id,search_result_id,document_id,dumps(warnings),now_ts(),dumps(metadata or {}),excerpt,host])
        self.audit.log('include','pasted_finding_91',pid,case_id,{'canonical_url':canon,'status':'candidate_not_claim','warnings':warnings})
        if self.graph:
            try:
                source_node = self.graph.add_node(case_id,'source',title,value=canon,confidence=40,sensitivity='normal',source_ref=canon,metadata={'build':'100.1','paste_id':pid})
                if evidence_id:
                    finding_node = self.graph.add_node(case_id,'finding','Pasted public finding',value=body[:500],confidence=40,sensitivity='normal',source_ref=evidence_id,metadata={'build':'100.1','paste_id':pid})
                    try:
                        self.graph.add_edge(case_id, source_node['node_id'], finding_node['node_id'], 'supports_candidate', confidence=35, review_status='candidate', evidence_ref=evidence_id, metadata={'paste_id':pid})
                    except Exception:
                        pass
            except Exception:
                pass
        return self.get(pid)

    def include_text(self, case_id: str, text: str, *, title: str='Pasted public finding', source_url: str='', metadata: Dict[str,Any]|None=None) -> Dict[str,Any]:
        if self.canonical_pipeline is not None:
            return self.canonical_pipeline.include_finding(case_id=case_id, url=source_url, title=title, text=text, source_label='copy_paste_text', input_kind='paste', metadata=metadata or {})
        case_id = case_id or self.ensure_default_case()
        urls = URL_RE.findall(text or '')
        if source_url or urls:
            return self.include_url(case_id, source_url or urls[0], title=title, text=text, metadata=metadata or {})
        pid = new_id('paste91')
        h = hashlib.sha256((text or '').encode()).hexdigest()
        evidence_id = document_id = ''
        warnings = [{'level':'medium','code':'missing_url','message':'No source URL was provided; export should require manual source review.'}]
        if self.evidence:
            evidence_id = self.evidence.ingest_text(case_id,title,text or '',artifact_type='pasted_public_text_no_url',source_ref='',linked_object_type='pasted_finding_91',linked_object_id=pid,metadata={'build':'100.1'}).get('evidence_id','')
        if self.documents:
            document_id = self.documents.analyze_text(case_id,title,text or '',source_url='',document_type='pasted_text',metadata={'build':'100.1'}).get('document_id','')
        self.db.execute('''INSERT INTO pasted_findings_91(paste_id,case_id,title,input_kind,url,canonical_url,host,pasted_text_hash,pasted_html_hash,status,classification,capture_id,evidence_id,search_result_id,document_id,warnings_json,created_at,metadata_json,content_excerpt,source_label)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [pid,case_id,title,'text','', '', '', h, '', 'candidate_not_claim','public_text_candidate','',evidence_id,'',document_id,dumps(warnings),now_ts(),dumps(metadata or {}),(text or '')[:2000],'manual_paste_no_url'])
        self.audit.log('include','pasted_finding_91',pid,case_id,{'status':'candidate_not_claim','warnings':warnings})
        return self.get(pid)

    def get(self, paste_id: str) -> Dict[str,Any]:
        r = self.db.one('SELECT * FROM pasted_findings_91 WHERE paste_id=?',[paste_id])
        if not r:
            raise KeyError(paste_id)
        r['warnings'] = loads(r.pop('warnings_json','[]'),[])
        r['metadata'] = loads(r.pop('metadata_json','{}'),{})
        return r

    def list(self, case_id: str='', limit: int=100):
        if case_id:
            rows = self.db.all('SELECT paste_id FROM pasted_findings_91 WHERE case_id=? ORDER BY created_at DESC LIMIT ?', [case_id, int(limit)])
        else:
            rows = self.db.all('SELECT paste_id FROM pasted_findings_91 ORDER BY created_at DESC LIMIT ?', [int(limit)])
        return [self.get(r['paste_id']) for r in rows]

    def _title(self, html: str) -> str:
        m = TITLE_RE.search(html or '')
        return re.sub(r'\s+',' ',m.group(1)).strip()[:180] if m else ''

    def _html_to_text(self, html: str) -> str:
        txt = re.sub(r'<(script|style).*?</\1>',' ',html or '',flags=re.I|re.S)
        txt = re.sub(r'<[^>]+>',' ',txt)
        return re.sub(r'\s+',' ',txt).strip()
