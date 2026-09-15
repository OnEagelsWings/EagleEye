
from __future__ import annotations
from typing import Any, Dict, List, Optional
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.providers.dork_engine import ENGINES
from eagleeye_pro.security.policy import PolicyGate, MAX_MULTI_SEARCH_URLS

QUERY_PHASES = [
    ("02_identity_web", "Identitätsanker", "standard", ["Google", "Bing", "DuckDuckGo", "Brave"], "Name, Ort, Firma und Kernanker prüfen."),
    ("02b_alias_contacts", "Alias / Usernames / E-Mail", "standard", ["Google", "Bing", "DuckDuckGo", "Brave"], "Alias-, Username- und E-Mail-Spuren als Kandidaten suchen."),
    ("03_profiles_context", "Profile, Beruf & Kontext", "deep_public", ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage", "Ecosia", "Mojeek", "Yahoo"], "Öffentliche Profil-, Berufs-, Projekt- und Kontextspuren suchen."),
    ("04_image_media", "Bild-, Medien- & Reverse-Spur", "image_reverse", ["Google Bilder", "Bing Bilder", "Yandex Bilder", "Google", "Bing"], "Öffentliche Bild-/Medienfundstellen suchen; keine automatische biometrische Identifikation."),
    ("05_geo_places", "Geo-, Ort- & Kartenkontext", "geo_maps", ["Google Maps", "OpenStreetMap", "Google", "Google News", "Bing", "DuckDuckGo", "Brave"], "Orts-/Event-/Firmenstandort-Kontext suchen; keine private Wohnortgewissheit."),
    ("06_docs_archives", "Dokumente, PDFs, Presse & Archive", "document_media", ["Google", "Bing", "DuckDuckGo", "Brave", "Google News"], "PDFs, Presse, Vorträge, Archive und öffentlich auffindbare Dokumente suchen."),
    ("06b_business_registers", "Firma, Register, Domain & Impressum", "document_media", ["Google", "Bing", "DuckDuckGo", "Brave"], "Firmen-/Register-/Domain-/Impressumsbezüge prüfen."),
    ("07_counter_evidence", "Gegenbelege & Namensdoppler", "standard", ["Google", "Bing", "DuckDuckGo", "Brave"], "Widersprüche, Namensdoppler und Ausschlussmarker suchen."),
]
PHASE_INDEX = {key: idx for idx, (key, *_rest) in enumerate(QUERY_PHASES, start=1)}

class QueryFactoryService:
    def __init__(self, db: Database, audit: AuditService, search_workbench=None, research_execution=None):
        self.db = db
        self.audit = audit
        self.search_workbench = search_workbench
        self.research_execution = research_execution
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS query_factory_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          status TEXT DEFAULT 'generated', query_count INTEGER DEFAULT 0, blocked_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS query_factory_items (
          query_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          phase_key TEXT NOT NULL, phase_title TEXT NOT NULL, category TEXT NOT NULL,
          query_text TEXT NOT NULL, priority INTEGER DEFAULT 50, preset_key TEXT NOT NULL,
          engines_json TEXT NOT NULL, purpose TEXT NOT NULL, policy_status TEXT DEFAULT 'allowed',
          policy_reason TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES query_factory_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS query_factory_matrix_rows (
          matrix_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          phase_key TEXT NOT NULL, phase_title TEXT NOT NULL, preset_key TEXT NOT NULL,
          query_count INTEGER DEFAULT 0, allowed_count INTEGER DEFAULT 0, blocked_count INTEGER DEFAULT 0,
          engine_count INTEGER DEFAULT 0, engines_json TEXT NOT NULL, next_action TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES query_factory_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS query_factory_security_checks (
          check_id TEXT PRIMARY KEY, run_id TEXT DEFAULT '', case_id TEXT NOT NULL, target_id TEXT DEFAULT '',
          check_key TEXT NOT NULL, status TEXT NOT NULL, severity TEXT DEFAULT 'info',
          details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    @staticmethod
    def _quote(value: str) -> str:
        v = (value or '').strip()
        if not v: return ''
        return f'"{v}"' if ' ' in v and not (v.startswith('"') and v.endswith('"')) else v

    @staticmethod
    def _unique(seq: List[str]) -> List[str]:
        out=[]; seen=set()
        for s in seq:
            x=(s or '').strip()
            if x and x not in seen:
                seen.add(x); out.append(x)
        return out

    def _get_target(self, case_id: str, target_id: str = '') -> Dict[str, Any]:
        row = self.db.one('SELECT * FROM targets WHERE target_id=? AND case_id=?', [target_id, case_id]) if target_id else None
        if not row:
            row = self.db.one('SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1', [case_id])
        if not row:
            raise ValueError('Keine Zielperson vorhanden. Bitte zuerst Zielperson/Suchanker anlegen.')
        for k in ['aliases_json','emails_json','usernames_json','locations_json','companies_json','domains_json']:
            row[k] = loads(row.get(k), [])
        return row

    def _phase_meta(self, phase_key: str) -> Dict[str, Any]:
        for idx, (key,title,preset,engines,purpose) in enumerate(QUERY_PHASES, start=1):
            if key == phase_key:
                return {'phase_key': key, 'phase_title': title, 'preset_key': preset, 'engines': engines[:MAX_MULTI_SEARCH_URLS], 'purpose': purpose, 'phase_order': idx}
        return {'phase_key': phase_key, 'phase_title': phase_key, 'preset_key':'standard', 'engines':['Google','Bing','DuckDuckGo','Brave'], 'purpose':'öffentliche OSINT-Kandidaten prüfen', 'phase_order': 99}

    def _add_candidate(self, candidates: List[Dict[str, Any]], phase_key: str, category: str, query: str, priority: int) -> None:
        query = ' '.join((query or '').split()).strip()
        if not query: return
        meta = self._phase_meta(phase_key)
        policy = PolicyGate.evaluate_query(query)
        candidates.append({'phase_key': phase_key,'phase_title': meta['phase_title'],'category': category,'query_text': query,'priority': int(priority),'preset_key': meta['preset_key'],'engines': [e for e in meta['engines'] if e in ENGINES][:MAX_MULTI_SEARCH_URLS],'purpose': meta['purpose'],'policy_status': 'allowed' if policy.get('ok') else 'blocked','policy_reason': policy.get('reason','')})

    def build_query_candidates(self, target: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = self._quote(target.get('name',''))
        aliases = self._unique([str(x) for x in target.get('aliases_json') or []])
        emails = self._unique([str(x) for x in target.get('emails_json') or []])
        usernames = self._unique([str(x) for x in target.get('usernames_json') or []])
        locations = self._unique([str(x) for x in target.get('locations_json') or []])
        companies = self._unique([str(x) for x in target.get('companies_json') or []])
        domains = self._unique([str(x).replace('https://','').replace('http://','').strip('/') for x in target.get('domains_json') or []])
        c=[]
        self._add_candidate(c, '02_identity_web', 'Exact name', name, 95)
        for loc in locations: self._add_candidate(c, '02_identity_web', 'Name + Ort', f'{name} {self._quote(loc)}', 92)
        for company in companies: self._add_candidate(c, '02_identity_web', 'Name + Firma', f'{name} {self._quote(company)}', 91)
        for alias in aliases:
            self._add_candidate(c, '02b_alias_contacts', 'Alias + Name', f'{self._quote(alias)} {name}', 86)
            self._add_candidate(c, '02b_alias_contacts', 'Alias solo', self._quote(alias), 70)
        for user in usernames:
            self._add_candidate(c, '02b_alias_contacts', 'Username solo', self._quote(user), 84)
            self._add_candidate(c, '02b_alias_contacts', 'Username + Name', f'{self._quote(user)} {name}', 88)
        for email in emails: self._add_candidate(c, '02b_alias_contacts', 'E-Mail', self._quote(email), 90)
        for site in ['linkedin.com/in','xing.com/profile','github.com','medium.com','researchgate.net','orcid.org','youtube.com','reddit.com']:
            self._add_candidate(c, '03_profiles_context', f'Profil site:{site}', f'{name} site:{site}', 72)
        for company in companies: self._add_candidate(c, '03_profiles_context', 'Beruf/Firma Kontext', f'{name} {self._quote(company)} LinkedIn OR Xing OR Profil', 76)
        self._add_candidate(c, '04_image_media', 'Bildsuche Name', f'{name} Foto OR Bild OR Pressefoto', 68)
        for company in companies: self._add_candidate(c, '04_image_media', 'Bildsuche Firma', f'{name} {self._quote(company)} Foto OR Team OR Presse', 67)
        for loc in locations:
            self._add_candidate(c, '05_geo_places', 'Geo Name + Ort', f'{name} {self._quote(loc)}', 66)
            for company in companies: self._add_candidate(c, '05_geo_places', 'Geo Firma + Ort', f'{self._quote(company)} {self._quote(loc)}', 64)
        for ft in ['pdf','doc','docx','ppt','pptx']: self._add_candidate(c, '06_docs_archives', f'Dokument filetype:{ft}', f'{name} filetype:{ft}', 62)
        self._add_candidate(c, '06_docs_archives', 'Presse/Interview/Vortrag', f'{name} Presse OR Interview OR Vortrag OR Podcast', 64)
        for company in companies: self._add_candidate(c, '06_docs_archives', 'Firma + Presse', f'{name} {self._quote(company)} Presse OR Register OR Bekanntmachung', 63)
        for domain in domains:
            self._add_candidate(c, '06b_business_registers', 'Domain site search', f'site:{domain} {name}', 78)
            self._add_candidate(c, '06b_business_registers', 'Impressum', f'site:{domain} impressum {name}', 80)
            self._add_candidate(c, '06b_business_registers', 'Domain Kontakt öffentlich', f'site:{domain} Kontakt {name}', 60)
        for company in companies: self._add_candidate(c, '06b_business_registers', 'Firma Register', f'{self._quote(company)} Register OR Handelsregister OR Impressum', 75)
        if companies:
            for company in companies[:2]: self._add_candidate(c, '07_counter_evidence', 'Name ohne Firma', f'{name} -{self._quote(company)}', 58)
        if locations:
            for loc in locations[:2]: self._add_candidate(c, '07_counter_evidence', 'Name ohne Ort', f'{name} -{self._quote(loc)}', 56)
        self._add_candidate(c, '07_counter_evidence', 'Namensdoppler', f'{name} Namensdoppler OR "same name"', 59)
        seen=set(); out=[]
        for item in c:
            key=(item['phase_key'], item['category'], item['query_text'])
            if key not in seen:
                seen.add(key); out.append(item)
        return sorted(out, key=lambda x: (PHASE_INDEX.get(x['phase_key'],99), -x['priority'], x['category'], x['query_text']))

    def generate_for_case(self, case_id: str, target_id: str = '', created_by: str = 'local-analyst', notes: str = '') -> Dict[str, Any]:
        target = self._get_target(case_id, target_id)
        candidates = self.build_query_candidates(target)
        run_id = new_id('qfr'); ts = now_ts()
        allowed_count = sum(1 for c in candidates if c['policy_status'] == 'allowed'); blocked_count = len(candidates)-allowed_count
        self.db.execute('''INSERT INTO query_factory_runs(run_id,case_id,target_id,status,query_count,blocked_count,created_at,created_by,notes) VALUES(?,?,?,?,?,?,?,?,?)''', [run_id, case_id, target['target_id'], 'generated', len(candidates), blocked_count, ts, created_by, notes or 'Build 37.0 Query Factory generation'])
        for item in candidates:
            self.db.execute('''INSERT INTO query_factory_items(query_id,run_id,case_id,target_id,phase_key,phase_title,category,query_text,priority,preset_key,engines_json,purpose,policy_status,policy_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [new_id('qfi'), run_id, case_id, target['target_id'], item['phase_key'], item['phase_title'], item['category'], item['query_text'], item['priority'], item['preset_key'], dumps(item['engines']), item['purpose'], item['policy_status'], item['policy_reason'], ts])
        for phase_key, phase_title, preset_key, engines, purpose in QUERY_PHASES:
            rows=[i for i in candidates if i['phase_key']==phase_key]; allowed=[i for i in rows if i['policy_status']=='allowed']; blocked=[i for i in rows if i['policy_status']!='allowed']
            next_action='Query auswählen und im Research Center öffnen' if allowed else 'Suchanker ergänzen oder Policy-Blocker prüfen'
            self.db.execute('''INSERT INTO query_factory_matrix_rows(matrix_id,run_id,case_id,target_id,phase_key,phase_title,preset_key,query_count,allowed_count,blocked_count,engine_count,engines_json,next_action,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [new_id('qfm'), run_id, case_id, target['target_id'], phase_key, phase_title, preset_key, len(rows), len(allowed), len(blocked), len([e for e in engines if e in ENGINES]), dumps([e for e in engines if e in ENGINES]), next_action, ts])
        sec=self.run_security_checks(case_id,target['target_id'],run_id)
        self.audit.log('generate','query_factory_run',run_id,case_id,{'target_id':target['target_id'],'queries':len(candidates),'blocked':blocked_count,'security':sec.get('gate')})
        return self.dashboard(case_id,run_id=run_id)

    def latest_run(self, case_id: str, target_id: str = '') -> Optional[Dict[str, Any]]:
        if target_id: return self.db.one('SELECT * FROM query_factory_runs WHERE case_id=? AND target_id=? ORDER BY created_at DESC LIMIT 1',[case_id,target_id])
        return self.db.one('SELECT * FROM query_factory_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id])

    def list_queries(self, case_id: str, run_id: str = '', phase_key: str = '', allowed_only: bool = True) -> List[Dict[str, Any]]:
        clauses=['case_id=?']; params=[case_id]
        if run_id: clauses.append('run_id=?'); params.append(run_id)
        if phase_key: clauses.append('phase_key=?'); params.append(phase_key)
        if allowed_only: clauses.append("policy_status='allowed'")
        order=' CASE phase_key ' + ' '.join([f"WHEN '{k}' THEN {i}" for i,(k,*_) in enumerate(QUERY_PHASES,start=1)]) + ' ELSE 99 END, priority DESC, category, query_text'
        rows=self.db.all('SELECT * FROM query_factory_items WHERE '+' AND '.join(clauses)+' ORDER BY '+order,params)
        for r in rows: r['engines']=loads(r.get('engines_json'),[])
        return rows

    def matrix(self, case_id: str, run_id: str = '') -> List[Dict[str, Any]]:
        if not run_id:
            latest=self.latest_run(case_id); run_id=latest['run_id'] if latest else ''
        rows=self.db.all('SELECT * FROM query_factory_matrix_rows WHERE case_id=? AND run_id=? ORDER BY rowid',[case_id,run_id]) if run_id else []
        for r in rows: r['engines']=loads(r.get('engines_json'),[])
        return rows

    def run_security_checks(self, case_id: str, target_id: str = '', run_id: str = '') -> Dict[str, Any]:
        if not run_id:
            latest=self.latest_run(case_id,target_id); run_id=latest['run_id'] if latest else ''
        rows=self.list_queries(case_id,run_id=run_id,allowed_only=False) if run_id else []
        blocked=[r for r in rows if r.get('policy_status')!='allowed']; over=[]
        for r in rows:
            engines=loads(r.get('engines_json'),[]) if isinstance(r.get('engines_json'),str) else r.get('engines',[])
            if len(engines)>MAX_MULTI_SEARCH_URLS: over.append(r.get('query_id'))
        gate='QUERY_FACTORY_SECURITY_PASS' if not blocked and not over else 'QUERY_FACTORY_SECURITY_REVIEW'
        details={'query_count':len(rows),'blocked_count':len(blocked),'over_url_limit':len(over),'guardrails':['public_search_only','no_login_bypass','no_captcha_bypass','no_doxxing','no_auto_face_id','no_private_address_assertion']}
        check_id=new_id('qfc')
        self.db.execute('''INSERT INTO query_factory_security_checks(check_id,run_id,case_id,target_id,check_key,status,severity,details_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',[check_id,run_id or '',case_id,target_id or '','query_factory_guardrails',gate,'info' if gate.endswith('PASS') else 'warning',dumps(details),now_ts()])
        return {'gate':gate,'check_id':check_id,**details}

    def selected_query_to_research_center(self, case_id: str, query_id: str) -> Dict[str, Any]:
        row=self.db.one('SELECT * FROM query_factory_items WHERE case_id=? AND query_id=?',[case_id,query_id])
        if not row: raise KeyError('Query Factory Eintrag nicht gefunden.')
        if row.get('policy_status')!='allowed': raise ValueError('Diese Query ist durch die Policy-Gates blockiert und darf nicht gestartet werden.')
        if not self.research_execution: return {'query':row['query_text'],'phase_key':row['phase_key'],'preset_key':row['preset_key'],'engines':loads(row.get('engines_json'),[])}
        dash=self.research_execution.set_active_phase(case_id,row['phase_key'],target_id=row.get('target_id',''),query=row['query_text'])
        return {'query':row['query_text'],'phase_key':row['phase_key'],'preset_key':row['preset_key'],'engines':loads(row.get('engines_json'),[]),'research_center':dash}

    def dashboard(self, case_id: str, target_id: str = '', run_id: str = '') -> Dict[str, Any]:
        run=self.db.one('SELECT * FROM query_factory_runs WHERE run_id=? AND case_id=?',[run_id,case_id]) if run_id else None
        if not run: run=self.latest_run(case_id,target_id)
        if not run: return {'status':'no_query_factory_run','next_action':'Zielperson auswählen und Query Factory starten.','run':None,'matrix':[],'queries':[],'security':None}
        rows=self.list_queries(case_id,run_id=run['run_id'],allowed_only=False); matrix=self.matrix(case_id,run_id=run['run_id'])
        checks=self.db.all('SELECT * FROM query_factory_security_checks WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 5',[case_id,run['run_id']])
        for c in checks: c['details']=loads(c.get('details_json'),{})
        allowed=[r for r in rows if r.get('policy_status')=='allowed']; blocked=[r for r in rows if r.get('policy_status')!='allowed']
        return {'status':'query_matrix_ready','next_action':'Top-Query auswählen, an Research Center übergeben und Phase öffnen.','run':run,'query_count':len(rows),'allowed_count':len(allowed),'blocked_count':len(blocked),'matrix':matrix,'queries':rows,'top_queries':allowed[:12],'security_checks':checks,'guardrails':['öffentliche Suchoberflächen','keine privaten Accounts','keine Login-/Captcha-Umgehung','keine automatische Identitäts-/Wohnortbehauptung']}
