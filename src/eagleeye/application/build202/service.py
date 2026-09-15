from __future__ import annotations
import hashlib,json,re
from typing import Any,Mapping,Sequence
from urllib.parse import quote_plus
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(q:str)->str:
    q=re.sub(r'(?<!\d)\b(?:0[\.,]\d+|1[\.,]0+)\b',' ',q)
    return re.sub(r'\s+',' ',q.replace(';',' ')).strip()

class Build202GlobalCountryPacksService:
    BUILD='202.0'
    COUNTRY_PACKS={
      'DE':[
       ('de_bundestag_dip','Deutscher Bundestag DIP','structured_api','official','https://search.dip.bundestag.de/api/v1','parliament'),
       ('de_dnb_gnd','DNB/GND','structured_api','authority','https://services.dnb.de/sru/authorities','identity'),
       ('de_govdata','GovData','structured_api','official','https://ckan.govdata.de/api/3/action/package_search','open_data'),
       ('de_bundesanzeiger','Bundesanzeiger','guided_browser','official','https://www.bundesanzeiger.de/pub/de/suche','company'),
       ('de_handelsregister','Handelsregister','guided_browser','official','https://www.handelsregister.de/rp_web/mask.do','company'),
       ('de_archivportal','Archivportal-D','guided_browser','archive','https://www.archivportal-d.de/search','archive'),
       ('de_tagesschau','Tagesschau','rss_or_browser','news','https://www.tagesschau.de/suche2.html','news'),
       ('de_spiegel','Der Spiegel','guided_browser','news','https://www.spiegel.de/suche/','news')],
      'EU':[
       ('eu_parliament_open','European Parliament Open Data','structured_api','official','https://data.europarl.europa.eu/api/v2','parliament'),
       ('eu_data_portal','data.europa.eu','structured_api','official','https://data.europa.eu/api/hub/search','open_data'),
       ('eu_ted','TED Search API','structured_api','official','https://api.ted.europa.eu/v3/notices/search','procurement'),
       ('eu_cellar','EU Publications Cellar','structured_api','official','https://publications.europa.eu/webapi/rdf/sparql','documents'),
       ('eu_sanctions','EU Sanctions Map','guided_browser','official','https://www.sanctionsmap.eu/','sanctions'),
       ('eu_court','CURIA','guided_browser','official','https://curia.europa.eu/juris/recherche.jsf','court'),
       ('eu_eurlex','EUR-Lex','structured_api','official','https://eur-lex.europa.eu/search.html','law'),
       ('eu_politico','POLITICO Europe','guided_browser','news','https://www.politico.eu/search/','news')],
      'US':[
       ('us_congress','Congress.gov API','credentialed_api','official','https://api.congress.gov/v3','parliament'),
       ('us_govinfo','GovInfo API','credentialed_api','official','https://api.govinfo.gov','documents'),
       ('us_sec','SEC EDGAR','structured_api','official','https://data.sec.gov','company'),
       ('us_federal_register','Federal Register API','structured_api','official','https://www.federalregister.gov/api/v1','official_notices'),
       ('us_courtlistener','CourtListener','structured_api','court','https://www.courtlistener.com/api/rest/v3','court'),
       ('us_data_gov','Data.gov','structured_api','official','https://catalog.data.gov/api/3/action/package_search','open_data'),
       ('us_npr','NPR','rss_or_browser','news','https://www.npr.org/search','news'),
       ('us_ap','Associated Press','guided_browser','news','https://apnews.com/search','news')],
      'IL':[
       ('il_knesset','Knesset OData','structured_api','official','https://knesset.gov.il/OData/ParliamentInfo.svc','parliament'),
       ('il_data_gov','data.gov.il','structured_api','official','https://data.gov.il/api/3/action/package_search','open_data'),
       ('il_corporations','Israel Corporations Authority','guided_browser','official','https://ica.justice.gov.il/GenericCorporarionInfo/SearchCorporation?unit=8','company'),
       ('il_state_archives','Israel State Archives','guided_browser','archive','https://www.archives.gov.il/archives/','archive'),
       ('il_court','Nevo/Court decisions public routing','guided_browser','court','https://www.gov.il/he/departments/dynamiccollectors/verdicts','court'),
       ('il_kan','KAN News','rss_or_browser','news','https://www.kan.org.il/search/','news'),
       ('il_ynet','Ynet','guided_browser','news','https://www.ynet.co.il/home/0,7340,L-8,00.html','news'),
       ('il_timesofisrael','Times of Israel','guided_browser','news','https://www.timesofisrael.com/?s=','news')]
    }
    def __init__(self,db:Any,audit:Any,*,runtime:Any,source_ops:Any,source_ai:Any,workspace:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.runtime=runtime;self.source_ops=source_ops;self.source_ai=source_ai;self.workspace=workspace;self.actor=actor
    def seed(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='COUNTRY PACKS 202 ANLEGEN':raise PermissionError('explicit approval required')
        created=now_ts();n=0
        for country,items in self.COUNTRY_PACKS.items():
            for sid,name,access,klass,endpoint,domain in items:
                status='guided_ready' if access in ('guided_browser','rss_or_browser') else 'contract_validated'
                p={'source_id':sid,'country':country,'name':name,'access':access,'source_class':klass,'endpoint':endpoint,'domain':domain,'status':status}
                self.db.execute('INSERT OR REPLACE INTO country_source_profiles_202 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,country,name,access,klass,endpoint,domain,status,0,0,0,0,created,created,_hash(p)));n+=1
        return {'countries':4,'sources':n,'structured_sources':sum(1 for x in self.COUNTRY_PACKS.values() for i in x if i[2] in ('structured_api','credentialed_api')),'automatic_activation':False}
    def create_plan(self,*,case_id:str,question:str,countries:Sequence[str],person:Mapping[str,Any],mode:str='balanced',confirmation:str)->dict[str,Any]:
        if confirmation!=f'COUNTRY PLAN 202 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        clean=_clean(question);name=' '.join(str(person.get(k,'')).strip() for k in ('given_name','family_name') if person.get(k)).strip()
        query=_clean(f'{name} {clean}')
        selected=[]
        for c in countries:
            rows=self.db.all('SELECT * FROM country_source_profiles_202 WHERE country=? ORDER BY CASE source_class WHEN "official" THEN 0 WHEN "authority" THEN 1 WHEN "court" THEN 2 WHEN "news" THEN 4 ELSE 3 END,name',(c,))
            selected.extend(dict(r) for r in rows[:8])
        # rank by question domain and source authority
        ql=clean.lower()
        def score(r):
            s=0
            if r['source_class'] in ('official','authority','court'):s+=40
            if r['domain']=='news' and any(w in ql for w in ('bericht','zeitung','presse','medien','news')):s+=35
            if r['domain']=='company' and any(w in ql for w in ('firma','unternehmen','geschäft','organisation')):s+=35
            if r['domain']=='parliament' and any(w in ql for w in ('politik','parlament','abgeordnet')):s+=35
            if r['domain']=='archive' and any(w in ql for w in ('histor','famil','geburt','archiv')):s+=35
            return -s,r['country'],r['name']
        selected=sorted({r['source_id']:r for r in selected}.values(),key=score)
        tabs=[];jobs=[]
        for r in selected:
            if len(tabs)<5:
                if r['access'] in ('guided_browser','rss_or_browser'):
                    url=r['endpoint'] + (quote_plus(query) if r['endpoint'].endswith(('=','/')) and 'search' in r['endpoint'].lower() else '')
                else:
                    url='https://www.google.com/search?q='+quote_plus(f'site:{r["endpoint"].split("/")[2]} {query}')
                tabs.append({'source_id':r['source_id'],'title':r['name'],'url':url,'command':['firefox.exe','-new-tab',url],'existing_firefox_session':True})
            if r['access'] in ('structured_api','credentialed_api'):
                jobs.append({'source_id':r['source_id'],'query':query,'mode':mode,'candidate_only':True,'citation_required':True})
        pid=new_id('countryplan202');payload={'plan_id':pid,'case_id':case_id,'question':clean,'query':query,'countries':list(countries),'tabs':tabs,'jobs':jobs}
        self.db.execute('INSERT INTO country_search_plans_202 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,clean,dumps(list(countries)),dumps(dict(person)),mode,dumps(tabs),dumps(jobs),now_ts(),_hash(payload)))
        return {**payload,'parallel_tabs':len(tabs),'tab_limit':5,'sources_before_models':True,'automatic_identity_confirmation':False}
    def validate_source(self,*,source_id:str,fixture_ok:bool,parser_ok:bool,live_ok:bool,terms_reviewed:bool,confirmation:str)->dict[str,Any]:
        if confirmation!=f'COUNTRY SOURCE 202 {source_id} VALIDIEREN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM country_source_profiles_202 WHERE source_id=?',(source_id,))
        if not row:raise KeyError(source_id)
        if row['access'] in ('guided_browser','rss_or_browser'):
            status='guided_ready' if terms_reviewed else 'blocked_terms'
        elif fixture_ok and parser_ok and live_ok and terms_reviewed:status='production_ready'
        elif fixture_ok and parser_ok and live_ok:status='live_validated'
        elif fixture_ok and parser_ok:status='fixture_validated'
        else:status='contract_validated'
        self.db.execute('UPDATE country_source_profiles_202 SET status=?,fixture_ok=?,parser_ok=?,live_ok=?,terms_reviewed=?,updated_at=? WHERE source_id=?',(status,int(fixture_ok),int(parser_ok),int(live_ok),int(terms_reviewed),now_ts(),source_id))
        return {'source_id':source_id,'status':status,'automatic_activation':False,'next_action':'human activation' if status=='production_ready' else 'complete missing gates'}
    def activate_source(self,*,source_id:str,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'COUNTRY SOURCE 202 {source_id} AKTIVIEREN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM country_source_profiles_202 WHERE source_id=?',(source_id,))
        if not row:raise KeyError(source_id)
        if row['status']!='production_ready':raise ValueError('production_ready required')
        self.db.execute("UPDATE country_source_profiles_202 SET status='production_active',updated_at=? WHERE source_id=?",(now_ts(),source_id))
        return {'source_id':source_id,'status':'production_active','approved_by':approved_by,'human_approved':True}
    def coverage(self)->dict[str,Any]:
        rows=self.db.all('SELECT country,status,COUNT(*) n FROM country_source_profiles_202 GROUP BY country,status')
        out={}
        for r in rows:out.setdefault(r['country'],{})[r['status']]=r['n']
        return {'build':'202.0','country_packs':out,'countries':['DE','EU','US','IL'],'evidence_first':True}
