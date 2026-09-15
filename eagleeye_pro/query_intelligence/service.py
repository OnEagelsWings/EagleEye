from __future__ import annotations
from typing import Any, Dict, List, Optional
import re
from urllib.parse import quote_plus
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate, MAX_MULTI_SEARCH_URLS
from eagleeye_pro.providers.dork_engine import ENGINES

LANGUAGE_PROFILES = {
    "de_eu": {
        "label": "Deutsch / EU",
        "terms": ["Presse", "Interview", "Vortrag", "Impressum", "Register", "Bekanntmachung", "Profil", "Team"],
        "geo_terms": ["Standort", "Ort", "Veranstaltung", "Adresse öffentlich"],
        "counter_terms": ["Namensdoppler", "gleichnamig", "andere Firma", "anderer Ort"],
    },
    "en_global": {
        "label": "English / Global",
        "terms": ["profile", "interview", "speaker", "press", "company", "team", "publication"],
        "geo_terms": ["location", "event", "office", "public address"],
        "counter_terms": ["same name", "different company", "different city", "not the same person"],
    },
}

OPERATOR_STRATEGIES = [
    ("exact", "Exact Match", "\"{name}\""),
    ("name_company", "Name + Firma", "\"{name}\" \"{company}\""),
    ("name_location", "Name + Ort", "\"{name}\" \"{location}\""),
    ("site_linkedin", "LinkedIn via Suchmaschine", "\"{name}\" site:linkedin.com/in"),
    ("site_xing", "Xing via Suchmaschine", "\"{name}\" site:xing.com/profile"),
    ("site_github", "GitHub via Suchmaschine", "\"{name}\" site:github.com"),
    ("file_pdf", "PDF / Dokumente", "\"{name}\" filetype:pdf"),
    ("file_docx", "DOCX / Dokumente", "\"{name}\" filetype:docx"),
    ("intitle_profile", "Profil im Seitentitel", "intitle:Profil \"{name}\""),
    ("inurl_impressum", "Impressum / Firmenkontext", "\"{name}\" inurl:impressum"),
    ("counter_same_name", "Gegenbeleg Namensdoppler", "\"{name}\" Namensdoppler OR \"same name\""),
]

PHASE_META = {
    "02_identity_web": ("Identitätsanker", "standard", ["Google", "Bing", "DuckDuckGo", "Brave"]),
    "02b_alias_contacts": ("Alias / Usernames / E-Mail", "standard", ["Google", "Bing", "DuckDuckGo", "Brave"]),
    "03_profiles_context": ("Profile, Beruf & Kontext", "deep_public", ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage", "Ecosia", "Mojeek", "Yahoo"]),
    "04_image_media": ("Bild-, Medien- & Reverse-Spur", "image_reverse", ["Google Bilder", "Bing Bilder", "Yandex Bilder", "Google", "Bing"]),
    "05_geo_places": ("Geo-, Ort- & Kartenkontext", "geo_maps", ["Google Maps", "OpenStreetMap", "Google News", "Google", "Bing", "DuckDuckGo", "Brave"]),
    "06_docs_archives": ("Dokumente, PDFs, Presse & Archive", "document_media", ["Google", "Bing", "DuckDuckGo", "Brave", "Google News"]),
    "06b_business_registers": ("Firma, Register, Domain & Impressum", "document_media", ["Google", "Bing", "DuckDuckGo", "Brave"]),
    "07_counter_evidence": ("Gegenbelege & Namensdoppler", "standard", ["Google", "Bing", "DuckDuckGo", "Brave"]),
}
PHASE_ORDER = {k: i for i, k in enumerate(PHASE_META, start=1)}

class QueryIntelligenceService:
    """Build 44.0: richer, explainable query-generation layer.

    It never confirms identity. It produces candidate search strings and requires the
    existing Research Center -> Capture -> Review -> Evidence chain.
    """
    def __init__(self, db: Database, audit: AuditService, research_execution=None, query_factory=None):
        self.db = db
        self.audit = audit
        self.research_execution = research_execution
        self.query_factory = query_factory
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS query_intelligence_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          profile_key TEXT DEFAULT 'de_eu', status TEXT DEFAULT 'generated',
          query_count INTEGER DEFAULT 0, blocked_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS query_intelligence_items (
          item_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          phase_key TEXT NOT NULL, phase_title TEXT NOT NULL, strategy_key TEXT NOT NULL, strategy_title TEXT NOT NULL,
          query_text TEXT NOT NULL, query_family TEXT NOT NULL, priority INTEGER DEFAULT 50,
          preset_key TEXT NOT NULL, engines_json TEXT NOT NULL, rationale TEXT NOT NULL,
          expected_signal TEXT DEFAULT '', counter_check TEXT DEFAULT '', policy_status TEXT DEFAULT 'allowed', policy_reason TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES query_intelligence_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS query_intelligence_name_variants (
          variant_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          variant_type TEXT NOT NULL, variant_value TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES query_intelligence_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS query_intelligence_security_checks (
          check_id TEXT PRIMARY KEY, run_id TEXT DEFAULT '', case_id TEXT NOT NULL, target_id TEXT DEFAULT '',
          check_key TEXT NOT NULL, status TEXT NOT NULL, severity TEXT DEFAULT 'info', details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    @staticmethod
    def _loads(v: Any) -> List[str]:
        if isinstance(v, list): return [str(x).strip() for x in v if str(x).strip()]
        return [str(x).strip() for x in loads(v, []) if str(x).strip()]

    @staticmethod
    def _dedupe(seq: List[str]) -> List[str]:
        out=[]; seen=set()
        for s in seq:
            v=' '.join(str(s or '').split()).strip()
            if v and v.lower() not in seen:
                seen.add(v.lower()); out.append(v)
        return out

    @staticmethod
    def _quote(v: str) -> str:
        v=' '.join((v or '').split()).strip()
        if not v: return ''
        return v if (v.startswith('"') and v.endswith('"')) else f'"{v}"'

    def _target(self, case_id: str, target_id: str='') -> Dict[str, Any]:
        row = self.db.one('SELECT * FROM targets WHERE case_id=? AND target_id=?', [case_id, target_id]) if target_id else None
        if not row:
            row = self.db.one('SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1', [case_id])
        if not row:
            raise ValueError('Keine Zielperson vorhanden. Bitte zuerst Zielperson/Suchanker anlegen.')
        for key in ['aliases_json','emails_json','usernames_json','locations_json','companies_json','domains_json']:
            row[key] = self._loads(row.get(key))
        return row

    def name_variants(self, name: str) -> List[Dict[str,str]]:
        name = ' '.join((name or '').split()).strip()
        if not name: return []
        parts = name.split()
        variants = [("exact", name)]
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            variants.extend([
                ("initial_last", f"{first[0]}. {last}"),
                ("last_first", f"{last}, {first}"),
                ("first_last_unquoted", f"{first} {last}"),
            ])
            if len(parts) > 2:
                variants.append(("first_last_short", f"{first} {last}"))
        out=[]; seen=set()
        for variant_type, variant_value in variants:
            vv=' '.join((variant_value or '').split()).strip()
            key=(variant_type, vv.lower())
            if vv and key not in seen:
                seen.add(key); out.append({"variant_type": variant_type, "variant_value": vv})
        return out

    def _phase(self, key: str) -> Dict[str, Any]:
        title,preset,engines = PHASE_META.get(key, (key,'standard',["Google","Bing","DuckDuckGo","Brave"]))
        return {"phase_key":key,"phase_title":title,"preset_key":preset,"engines":[e for e in engines if e in ENGINES][:MAX_MULTI_SEARCH_URLS]}

    def _add(self, out: List[Dict[str,Any]], phase_key: str, strategy_key: str, strategy_title: str, query: str, family: str, priority: int, rationale: str, expected: str='', counter: str='') -> None:
        q=' '.join((query or '').split()).strip()
        if not q: return
        ph=self._phase(phase_key)
        policy=PolicyGate.evaluate_query(q)
        out.append({
            "phase_key": phase_key, "phase_title": ph["phase_title"], "strategy_key": strategy_key, "strategy_title": strategy_title,
            "query_text": q, "query_family": family, "priority": int(priority), "preset_key": ph["preset_key"], "engines": ph["engines"],
            "rationale": rationale, "expected_signal": expected, "counter_check": counter,
            "policy_status": "allowed" if policy.get("ok") else "blocked", "policy_reason": policy.get("reason", ""),
        })

    def build_candidates(self, target: Dict[str,Any], profile_key: str='de_eu') -> Dict[str, Any]:
        name = target.get('name','')
        variants = self.name_variants(name)
        names = [v['variant_value'] for v in variants] or [name]
        aliases = self._dedupe(target.get('aliases_json') or [])
        emails = self._dedupe(target.get('emails_json') or [])
        usernames = self._dedupe(target.get('usernames_json') or [])
        locations = self._dedupe(target.get('locations_json') or [])
        companies = self._dedupe(target.get('companies_json') or [])
        domains = self._dedupe([str(d).replace('https://','').replace('http://','').strip('/ ') for d in (target.get('domains_json') or [])])
        prof = LANGUAGE_PROFILES.get(profile_key, LANGUAGE_PROFILES['de_eu'])
        items=[]
        for nm in names[:6]:
            qn=self._quote(nm)
            self._add(items,'02_identity_web','name_variant','Namensvariante',qn,'name_variant',95,'Exakte/alternative Namensschreibung als Kernanker prüfen.','Treffer mit Zielanker','Namensdoppler prüfen')
            for loc in locations[:3]:
                self._add(items,'02_identity_web','name_location','Name + Ort',f'{qn} {self._quote(loc)}','geo_identity',92,'Name mit öffentlichem Ortskontext kombinieren.','Ort taucht öffentlich mit Name auf','Ortswiderspruch / anderer Ort')
            for company in companies[:3]:
                self._add(items,'02_identity_web','name_company','Name + Firma',f'{qn} {self._quote(company)}','business_identity',91,'Name mit Firmen-/Berufsanker kombinieren.','Firma taucht mit Name auf','Firma ohne Zielperson / andere Person')
        for alias in aliases[:6]:
            self._add(items,'02b_alias_contacts','alias_name','Alias + Name',f'{self._quote(alias)} {self._quote(name)}','alias',88,'Alias mit Realnamen verbinden, nur als Kandidat.','Alias/Name-Koexistenz','Alias gehört anderer Person')
            for c in companies[:2]: self._add(items,'02b_alias_contacts','alias_company','Alias + Firma',f'{self._quote(alias)} {self._quote(c)}','alias_business',82,'Alias gegen Firmenkontext testen.','Alias/Firma-Koexistenz','Firma ohne Alias')
            for l in locations[:2]: self._add(items,'02b_alias_contacts','alias_location','Alias + Ort',f'{self._quote(alias)} {self._quote(l)}','alias_geo',80,'Alias gegen Ortskontext testen.','Alias/Ort-Koexistenz','Ortsdoppler')
        for user in usernames[:8]:
            self._add(items,'02b_alias_contacts','username_name','Username + Name',f'{self._quote(user)} {self._quote(name)}','username',90,'Username mit Zielnamen korrelieren.','Username/Name-Koexistenz','Username ohne Zielperson')
            for site in ['github.com','reddit.com','youtube.com','stackoverflow.com']:
                self._add(items,'03_profiles_context','username_site',f'Username site:{site}',f'{self._quote(user)} site:{site}','username_site',78,'Öffentliche Accountspuren per Suchoperator finden.','öffentlicher Accountkontext','Namens-/Aliasdoppler')
        for email in emails[:6]:
            local = email.split('@')[0] if '@' in email else email
            domain = email.split('@',1)[1] if '@' in email else ''
            self._add(items,'02b_alias_contacts','email_exact','E-Mail exakt',self._quote(email),'email',90,'E-Mail nur als rechtmäßig vorhandener Suchanker; Ergebnis bleibt Review-Kandidat.','öffentliche E-Mail-Erwähnung','veralteter/anderer Account')
            if local: self._add(items,'02b_alias_contacts','email_localpart','E-Mail Local-Part',self._quote(local),'email_localpart',72,'Local-Part als Username-/Alias-Hypothese testen.','Local-Part taucht als öffentlicher Alias auf','zufälliger Local-Part')
            if domain: self._add(items,'06b_business_registers','email_domain','E-Mail-Domain + Name',f'{self._quote(name)} site:{domain}','domain_identity',76,'Domainkontext mit Zielnamen prüfen.','Name auf zugehöriger Domain','anderer Domainkontext')
        # site/file/operator intelligence
        for strat_key, title, template in OPERATOR_STRATEGIES:
            for nm in names[:2]:
                base = template.format(name=nm, company=(companies[0] if companies else ''), location=(locations[0] if locations else ''))
                phase = '03_profiles_context' if 'site_' in strat_key or 'intitle' in strat_key else '06_docs_archives' if 'file_' in strat_key else '06b_business_registers' if 'impressum' in strat_key else '07_counter_evidence' if 'counter' in strat_key else '02_identity_web'
                self._add(items,phase,strat_key,title,base,'operator',74 if 'counter' not in strat_key else 82,'Suchoperator gezielt einsetzen, um Trefferraum zu reduzieren.','präzisere Treffer','Operator kann relevante Treffer ausschließen')
        for term in prof['terms'][:8]:
            self._add(items,'03_profiles_context','language_context',f'{prof["label"]}: {term}',f'{self._quote(name)} {term}','language_profile',65,'Sprach-/Länderkontext erweitert Quellenabdeckung.','Kontexttreffer in passender Sprache','Begriff erzeugt irrelevante Treffer')
        for loc in locations[:4]:
            for geo_term in prof['geo_terms'][:3]:
                self._add(items,'05_geo_places','geo_language',f'Geo-Kontext: {geo_term}',f'{self._quote(name)} {self._quote(loc)} {geo_term}','geo_context',63,'Öffentliche Orts-/Eventkontexte prüfen, keine private Wohnortbehauptung.','Ort/Event als Kontext','Privatadresse nicht ableiten')
        for company in companies[:4]:
            self._add(items,'06b_business_registers','company_impressum','Firma + Impressum',f'{self._quote(company)} Impressum {self._quote(name)}','business_register',81,'Öffentliche Firmen-/Impressumsbezüge prüfen.','Name in Firmenkontext','Impressum zeigt andere Person')
            self._add(items,'06_docs_archives','company_archive','Firma + Archive/Presse',f'{self._quote(company)} Presse OR Bekanntmachung OR Register','business_archive',70,'Firmen-/Presse-/Registerkontext unabhängig vom Namen prüfen.','Firma existiert öffentlich','Firma ohne Personenbezug')
        for domain in domains[:5]:
            self._add(items,'06b_business_registers','domain_site_name','Domain site:Name',f'site:{domain} {self._quote(name)}','domain',83,'Name auf bekannter Domain suchen.','Name/Domain-Verbindung','Domain ohne Name')
            self._add(items,'06b_business_registers','domain_impressum','Domain Impressum',f'site:{domain} impressum OR kontakt','domain',78,'Impressum/Kontaktseiten der Domain prüfen.','öffentliche Kontaktdaten der Organisation','private Daten nicht ableiten')
        # Image/media
        for nm in names[:3]:
            self._add(items,'04_image_media','image_context','Bild-/Medienkontext',f'{self._quote(nm)} Foto OR Bild OR Pressefoto OR Team','image_media',69,'Bild-/Medienfundstellen als Kontext, keine Face-ID.','Bildquelle/Medienkontext','ähnliche Personen nicht identifizieren')
        # Counter evidence: force explicit contradictory queries
        for nm in names[:3]:
            for cterm in prof['counter_terms'][:4]:
                self._add(items,'07_counter_evidence','counter_language',f'Gegenbeleg: {cterm}',f'{self._quote(nm)} {cterm}','counter_evidence',85,'Gegenbelege und Namensdoppler vor Schlussfolgerungen prüfen.','Widerspruch / Doppelgänger','kein Gegenbeleg gefunden')
            for c in companies[:2]: self._add(items,'07_counter_evidence','minus_company','Name ohne Firma',f'{self._quote(nm)} -{self._quote(c)}','counter_evidence',76,'Prüfen, ob Treffer ohne Firmenanker zu anderen Personen führen.','Namensdoppler / anderer Kontext','Ausschlussoperator kann Treffer verzerren')
            for l in locations[:2]: self._add(items,'07_counter_evidence','minus_location','Name ohne Ort',f'{self._quote(nm)} -{self._quote(l)}','counter_evidence',74,'Prüfen, ob Treffer ohne Ortsanker andere Kandidaten zeigen.','Ortsdoppler / anderer Kontext','Ausschlussoperator kann Treffer verzerren')
        # Deduplicate
        seen=set(); dedup=[]
        for it in items:
            key=(it['phase_key'], it['query_text'].lower(), it['strategy_key'])
            if key not in seen:
                seen.add(key); dedup.append(it)
        dedup.sort(key=lambda x: (PHASE_ORDER.get(x['phase_key'], 99), -x['priority'], x['strategy_title'], x['query_text']))
        return {"variants": variants, "items": dedup}

    def generate_for_case(self, case_id: str, target_id: str='', profile_key: str='de_eu', created_by: str='local-analyst', notes: str='') -> Dict[str, Any]:
        target=self._target(case_id, target_id)
        built=self.build_candidates(target, profile_key=profile_key)
        run_id=new_id('qir'); ts=now_ts()
        items=built['items']; blocked=sum(1 for i in items if i['policy_status']!='allowed')
        self.db.execute('''INSERT INTO query_intelligence_runs(run_id,case_id,target_id,profile_key,status,query_count,blocked_count,created_at,created_by,notes) VALUES(?,?,?,?,?,?,?,?,?,?)''',[run_id,case_id,target['target_id'],profile_key,'generated',len(items),blocked,ts,created_by,notes or 'Build 44.0 Query Intelligence generation'])
        for v in built['variants']:
            self.db.execute('''INSERT INTO query_intelligence_name_variants(variant_id,run_id,case_id,target_id,variant_type,variant_value,created_at) VALUES(?,?,?,?,?,?,?)''',[new_id('qiv'),run_id,case_id,target['target_id'],v['variant_type'],v['variant_value'],ts])
        for it in items:
            self.db.execute('''INSERT INTO query_intelligence_items(item_id,run_id,case_id,target_id,phase_key,phase_title,strategy_key,strategy_title,query_text,query_family,priority,preset_key,engines_json,rationale,expected_signal,counter_check,policy_status,policy_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',[new_id('qii'),run_id,case_id,target['target_id'],it['phase_key'],it['phase_title'],it['strategy_key'],it['strategy_title'],it['query_text'],it['query_family'],it['priority'],it['preset_key'],dumps(it['engines']),it['rationale'],it.get('expected_signal',''),it.get('counter_check',''),it['policy_status'],it.get('policy_reason',''),ts])
        sec=self.security_check(case_id,target['target_id'],run_id)
        self.audit.log('generate','query_intelligence_run',run_id,case_id,{'queries':len(items),'blocked':blocked,'profile':profile_key,'security':sec.get('gate')})
        return self.dashboard(case_id, run_id=run_id)

    def latest_run(self, case_id: str, target_id: str='') -> Optional[Dict[str,Any]]:
        if target_id:
            return self.db.one('SELECT * FROM query_intelligence_runs WHERE case_id=? AND target_id=? ORDER BY created_at DESC LIMIT 1',[case_id,target_id])
        return self.db.one('SELECT * FROM query_intelligence_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id])

    def list_items(self, case_id: str, run_id: str='', phase_key: str='', allowed_only: bool=True) -> List[Dict[str,Any]]:
        clauses=['case_id=?']; params=[case_id]
        if run_id: clauses.append('run_id=?'); params.append(run_id)
        if phase_key: clauses.append('phase_key=?'); params.append(phase_key)
        if allowed_only: clauses.append("policy_status='allowed'")
        order=' CASE phase_key ' + ' '.join([f"WHEN '{k}' THEN {i}" for k,i in PHASE_ORDER.items()]) + ' ELSE 99 END, priority DESC, query_family, strategy_title, query_text'
        rows=self.db.all('SELECT * FROM query_intelligence_items WHERE '+' AND '.join(clauses)+' ORDER BY '+order,params)
        for r in rows: r['engines']=loads(r.get('engines_json'),[])
        return rows

    def list_variants(self, case_id: str, run_id: str='') -> List[Dict[str,Any]]:
        if not run_id:
            latest=self.latest_run(case_id); run_id=latest['run_id'] if latest else ''
        return self.db.all('SELECT * FROM query_intelligence_name_variants WHERE case_id=? AND run_id=? ORDER BY variant_type, variant_value',[case_id,run_id]) if run_id else []

    def security_check(self, case_id: str, target_id: str='', run_id: str='') -> Dict[str,Any]:
        if not run_id:
            latest=self.latest_run(case_id,target_id); run_id=latest['run_id'] if latest else ''
        rows=self.list_items(case_id,run_id=run_id,allowed_only=False) if run_id else []
        blocked=[r for r in rows if r.get('policy_status')!='allowed']
        over=[r for r in rows if len(r.get('engines') or loads(r.get('engines_json'),[])) > MAX_MULTI_SEARCH_URLS]
        forbidden_family=[r for r in rows if r.get('query_family') in {'private_address','credentials','bypass'}]
        gate='QUERY_INTELLIGENCE_SECURITY_PASS' if not blocked and not over and not forbidden_family else 'QUERY_INTELLIGENCE_SECURITY_REVIEW'
        details={
            'query_count':len(rows),'blocked_count':len(blocked),'over_url_limit':len(over),'forbidden_family':len(forbidden_family),
            'guardrails':['public_osint_only','candidate_queries_only','no_private_accounts','no_login_or_captcha_bypass','no_credentials','no_auto_face_id','no_private_address_assertion','review_first']
        }
        check_id=new_id('qis')
        self.db.execute('''INSERT INTO query_intelligence_security_checks(check_id,run_id,case_id,target_id,check_key,status,severity,details_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',[check_id,run_id or '',case_id,target_id or '','query_intelligence_guardrails',gate,'info' if gate.endswith('PASS') else 'warning',dumps(details),now_ts()])
        return {'gate':gate,'check_id':check_id,**details}

    def selected_query_to_research_center(self, case_id: str, item_id: str) -> Dict[str,Any]:
        row=self.db.one('SELECT * FROM query_intelligence_items WHERE case_id=? AND item_id=?',[case_id,item_id])
        if not row: raise KeyError('Query-Intelligence-Eintrag nicht gefunden.')
        if row.get('policy_status')!='allowed': raise ValueError('Diese Query ist durch die Policy-Gates blockiert und darf nicht gestartet werden.')
        engines=loads(row.get('engines_json'),[])
        out={'query':row['query_text'],'phase_key':row['phase_key'],'preset_key':row['preset_key'],'engines':engines,'rationale':row.get('rationale','')}
        if self.research_execution:
            out['research_center']=self.research_execution.set_active_phase(case_id,row['phase_key'],target_id=row.get('target_id',''),query=row['query_text'])
        self.audit.log('send_to_research_center','query_intelligence_item',item_id,case_id,out)
        return out

    def dashboard(self, case_id: str, target_id: str='', run_id: str='') -> Dict[str,Any]:
        run=self.db.one('SELECT * FROM query_intelligence_runs WHERE run_id=? AND case_id=?',[run_id,case_id]) if run_id else None
        if not run: run=self.latest_run(case_id,target_id)
        if not run: return {'status':'no_query_intelligence_run','next_action':'Zielperson wählen und Query Intelligence starten.','run':None,'items':[],'variants':[],'security_checks':[]}
        rows=self.list_items(case_id,run_id=run['run_id'],allowed_only=False)
        variants=self.list_variants(case_id,run_id=run['run_id'])
        checks=self.db.all('SELECT * FROM query_intelligence_security_checks WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 5',[case_id,run['run_id']])
        for c in checks: c['details']=loads(c.get('details_json'),{})
        allowed=[r for r in rows if r.get('policy_status')=='allowed']; blocked=[r for r in rows if r.get('policy_status')!='allowed']
        family_counts={}
        phase_counts={}
        for r in rows:
            family_counts[r.get('query_family','unknown')]=family_counts.get(r.get('query_family','unknown'),0)+1
            phase_counts[r.get('phase_title','unknown')]=phase_counts.get(r.get('phase_title','unknown'),0)+1
        return {
            'status':'query_intelligence_ready','next_action':'Top-Query oder offene Gegenbeleg-Query an das Research Center übergeben.',
            'run':run,'query_count':len(rows),'allowed_count':len(allowed),'blocked_count':len(blocked),'variants':variants,'items':rows,'top_items':allowed[:20],
            'family_counts':family_counts,'phase_counts':phase_counts,'security_checks':checks,
            'guardrails':['öffentliche Suchoberflächen','Suchhypothesen statt Identitätsbehauptungen','Gegenbeleg-Queries Pflichtlogik','keine privaten Accounts','Review-first']
        }
