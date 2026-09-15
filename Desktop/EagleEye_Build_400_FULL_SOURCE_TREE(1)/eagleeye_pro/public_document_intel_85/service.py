from __future__ import annotations
import hashlib, re
from pathlib import Path
from typing import Any
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy
EMAIL=re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
URL=re.compile(r'https?://[^\s)>"\']+')
DATE=re.compile(r'\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b')
ORG=re.compile(r'\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß-]+\s){0,4}(?:GmbH|AG|e\.V\.|Ltd\.|Inc\.|LLC|University|Universität|Schule|Ministerium)\b')
class PublicDocumentIntel85Service:
    def __init__(self,db:Database,audit:AuditService,evidence_vault:Any=None,graph:Any=None): self.db=db; self.audit=audit; self.evidence=evidence_vault; self.graph=graph; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS public_documents_85 (document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT DEFAULT '', document_type TEXT DEFAULT 'text', content_hash TEXT NOT NULL, entity_counts_json TEXT NOT NULL, entities_json TEXT NOT NULL, evidence_id TEXT DEFAULT '', created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);"""); self.db.conn.commit()
    def _entities(self,text):
        emails=sorted(set(EMAIL.findall(text or '')))[:50]; urls=sorted(set(URL.findall(text or '')))[:50]; dates=sorted(set(DATE.findall(text or '')))[:50]; orgs=sorted(set(m.group(0).strip() for m in ORG.finditer(text or '')))[:50]
        return {'emails':emails,'urls':urls,'dates':dates,'organizations':orgs}
    def analyze_text(self,case_id,title,text,source_url='',document_type='text',metadata=None):
        if source_url:
            dec=URLPolicy.normalize_public_url(source_url)
            if not dec.get('ok'): raise ValueError(dec.get('blocked_reason'))
            source_url=dec['canonical_url']
        ents=self._entities(text or ''); counts={k:len(v) for k,v in ents.items()}; did=new_id('doc85'); h=hashlib.sha256((text or '').encode()).hexdigest(); evidence_id=''
        if self.evidence: evidence_id=self.evidence.ingest_text(case_id,title,text or '',artifact_type='public_document_text',source_ref=source_url,metadata={'build':'85','document_type':document_type}).get('evidence_id','')
        self.db.execute('INSERT INTO public_documents_85 VALUES(?,?,?,?,?,?,?,?,?,?,?)',[did,case_id,title,source_url,document_type,h,dumps(counts),dumps(ents),evidence_id,now_ts(),dumps(metadata or {})]); self.audit.log('analyze','public_document_85',did,case_id,{'counts':counts,'evidence_id':evidence_id}); return self.get(did)
    def analyze_file(self,case_id,path,title='',source_url='',metadata=None):
        p=Path(path); text=p.read_text(encoding='utf-8', errors='ignore'); return self.analyze_text(case_id,title or p.name,text,source_url,document_type=p.suffix.lstrip('.') or 'text',metadata=metadata)
    def get(self,did):
        r=self.db.one('SELECT * FROM public_documents_85 WHERE document_id=?',[did])
        if not r: raise KeyError(did)
        r['entity_counts']=loads(r.pop('entity_counts_json','{}'),{}); r['entities']=loads(r.pop('entities_json','{}'),{}); r['metadata']=loads(r.pop('metadata_json','{}'),{}); return r
    def list(self,case_id): return [self.get(r['document_id']) for r in self.db.all('SELECT document_id FROM public_documents_85 WHERE case_id=? ORDER BY created_at',[case_id])]
