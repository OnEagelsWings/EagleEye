from __future__ import annotations
import hashlib, json, re, unicodedata
from collections import Counter
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()

def _clean(v: Any) -> Any:
    sensitive=('token','secret','password','authorization','cookie','session','api_key','private_key')
    if isinstance(v, Mapping):
        return {str(k):('[REDACTED]' if any(x in str(k).lower() for x in sensitive) else _clean(val)) for k,val in v.items()}
    if isinstance(v,list): return [_clean(x) for x in v]
    return v

def _norm(text: str) -> str:
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(text))).strip()

def _scripts(text: str) -> dict[str,int]:
    out=Counter()
    for ch in text:
        o=ord(ch)
        if 0x0590<=o<=0x05FF: out['Hebrew']+=1
        elif 0x0600<=o<=0x06FF: out['Arabic']+=1
        elif 0x0400<=o<=0x052F: out['Cyrillic']+=1
        elif ('LATIN' in unicodedata.name(ch,'')): out['Latin']+=1
    return dict(out)

LANG_MARKERS={
 'de':{'der','die','das','und','ist','nicht','eine','mit','für','von','auf','wird'},
 'en':{'the','and','is','not','with','for','from','this','will','was','are'},
 'fr':{'le','la','les','et','est','pas','avec','pour','des','une','dans'},
 'es':{'el','la','los','y','es','no','con','para','una','del','en'},
 'it':{'il','la','gli','e','è','non','con','per','una','del','in'},
 'nl':{'de','het','een','en','is','niet','met','voor','van','op'},
 'pl':{'i','jest','nie','z','dla','na','się','oraz','do','to'},
 'ru':{'и','в','не','на','с','что','это','для','как','по'},
 'he':{'של','את','לא','עם','על','הוא','היא','זה','כי','גם'},
 'ar':{'من','في','على','لا','مع','هذا','هذه','إلى','عن','هو'},
}

class Build176MultilingualContentIntelligenceService:
    BUILD='176.0'
    SOURCE_PROFILES=[
      {'source_id':'eu_cellar_multilingual','title':'EU Publications Office Cellar','jurisdiction':'EU','category':'multilingual_publications','access_mode':'official_api_sparql_feeds','base_url':'https://publications.europa.eu','docs_url':'https://op.europa.eu/en/web/cellar/documentation','terms_url':'https://op.europa.eu/en/web/about-us/legal-notices/accessibility-statement','languages':['EU-24'],'capabilities':['multilingual_metadata','document_versions','sparql','rss_atom','content_download'],'constraints':['terms_review','format_negotiation','provenance_required']},
      {'source_id':'eu_parliament_open_data','title':'European Parliament Open Data API','jurisdiction':'EU','category':'parliamentary_open_data','access_mode':'official_rest_openapi','base_url':'https://data.europarl.europa.eu','docs_url':'https://data.europarl.europa.eu/en/developer-corner/opendata-api','terms_url':'https://data.europarl.europa.eu/en/discover/rules-on-the-european-parliaments-open-data','languages':['EU-24'],'capabilities':['members','proceedings','reports','amendments','multilingual_documents'],'constraints':['versioned_api','dataset_metadata_required']},
      {'source_id':'eu_etranslation','title':'European Commission eTranslation','jurisdiction':'EU','category':'machine_translation','access_mode':'credentialed_async_api','base_url':'https://language-tools.ec.europa.eu','docs_url':'https://language-tools.ec.europa.eu/assets/pages/05_example_python.html','terms_url':'https://commission.europa.eu/resources-partners/etranslation_en','languages':['EU-24','ar','zh','is','ja','no','ru','tr','uk'],'capabilities':['machine_translation','document_translation','callback_workflow'],'constraints':['eligible_users_only','credentials_required','human_revision_required','no_secret_storage']},
      {'source_id':'eu_dgt_tm','title':'DGT Translation Memory','jurisdiction':'EU','category':'parallel_corpus','access_mode':'official_download','base_url':'https://commission.europa.eu','docs_url':'https://commission.europa.eu/resources-partners/etranslation_en','terms_url':'https://commission.europa.eu/legal-notice_en','languages':['EU-24'],'capabilities':['parallel_text','terminology_support','translation_memory'],'constraints':['download_review','corpus_versioning','not_authoritative_translation']},
      {'source_id':'eu_commission_presscorner','title':'European Commission Press Corner','jurisdiction':'EU','category':'official_news','access_mode':'official_web_document_api','base_url':'https://ec.europa.eu','docs_url':'https://ec.europa.eu/commission/presscorner/home/en','terms_url':'https://commission.europa.eu/legal-notice_en','languages':['EU-24'],'capabilities':['press_releases','statements','speeches','multilingual_versions'],'constraints':['document_level_provenance','language_availability_varies']},
      {'source_id':'de_bundesregierung_news','title':'Bundesregierung Presse und Aktuelles','jurisdiction':'DE','category':'official_news','access_mode':'official_web_rss','base_url':'https://www.bundesregierung.de','docs_url':'https://www.bundesregierung.de/breg-de/aktuelles','terms_url':'https://www.bundesregierung.de/breg-de/service/impressum','languages':['de','en'],'capabilities':['press_releases','speeches','official_statements','rss'],'constraints':['web_structure_monitoring','citation_required']},
    ]
    AI_POLICY={'local_only':True,'external_model_called':False,'source_citations_required':True,'untrusted_content_is_data':True,'automatic_identity_confirmation':False,'automatic_accusation':False,'human_review_required':True}

    def __init__(self, db: Any, audit: Any, *, european_sources: Any, geospatial: Any, actor: str='system'):
        self.db,self.audit,self.european_sources,self.geospatial,self.actor=db,audit,european_sources,geospatial,actor

    def seed_sources(self, *, confirmation: str) -> dict[str,Any]:
        if confirmation!='MULTILINGUAL SOURCES 176 ERWEITERN': raise PermissionError('explicit multilingual source approval required')
        for p in self.SOURCE_PROFILES:
            payload={**p,'status':'DOCUMENTED'}
            self.db.execute('INSERT OR REPLACE INTO multilingual_source_profiles_176 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                p['source_id'],p['title'],p['jurisdiction'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],p['terms_url'],dumps(p['languages']),dumps(p['capabilities']),dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(payload)))
        return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}

    def detect_language(self,text: str) -> dict[str,Any]:
        normalized=_norm(text)
        scripts=_scripts(normalized)
        tokens=re.findall(r"[^\W\d_]+",normalized.casefold(),flags=re.UNICODE)
        scores={lang:sum(1 for t in tokens if t in markers) for lang,markers in LANG_MARKERS.items()}
        if scripts.get('Hebrew',0): scores['he']=scores.get('he',0)+max(2,scripts['Hebrew']//10)
        if scripts.get('Arabic',0): scores['ar']=scores.get('ar',0)+max(2,scripts['Arabic']//10)
        if scripts.get('Cyrillic',0): scores['ru']=scores.get('ru',0)+max(2,scripts['Cyrillic']//10)
        detected=max(scores,key=scores.get) if scores and max(scores.values())>0 else 'und'
        total=max(1,sum(scores.values()))
        return {'language':detected,'scores':{k:round(v/total,4) for k,v in scores.items() if v},'scripts':scripts,'confidence':round(max(scores.values())/total,4) if scores and max(scores.values()) else 0.0}

    def ingest_document(self,case_id: str,text: str,*,source_id: str|None=None,source_ref: str|None=None,provenance: Mapping[str,Any]|None=None,confirmation: str) -> dict[str,Any]:
        if confirmation!=f'CONTENT 176 {case_id} IMPORTIEREN': raise PermissionError('explicit content import approval required')
        if not str(text).strip(): raise ValueError('text required')
        if len(text)>2_000_000: raise ValueError('document too large')
        safe=_clean(dict(provenance or {})); normalized=_norm(text); language=self.detect_language(normalized); document_id=new_id('doc176')
        payload={'document_id':document_id,'case_id':case_id,'source_id':source_id,'source_ref':source_ref,'language':language,'provenance':safe,'content_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'review_status':'needs_review'}
        self.db.execute('INSERT INTO multilingual_documents_176 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
            document_id,case_id,source_id,source_ref,text,normalized,language['language'],dumps(language['scores']),dumps(language['scripts']),payload['content_sha256'],dumps(safe),'needs_review',now_ts(),_hash(payload)))
        self._event(case_id,'document_ingested',document_id,{'language':language['language'],'source_id':source_id})
        return {**payload,'review_required':True,'automatic_fact_confirmation':False}

    def extract_entities(self,document_id: str,*,confirmation: str) -> dict[str,Any]:
        if confirmation!=f'CONTENT 176 {document_id} ENTITAETEN EXTRAHIEREN': raise PermissionError('explicit extraction approval required')
        row=self.db.one('SELECT * FROM multilingual_documents_176 WHERE document_id=?',(document_id,))
        if not row: raise KeyError('document not found')
        text=row['original_text']; found=[]
        patterns=[('email',r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',.99),('url',r'https?://[^\s<>"\']+',.98),('date',r'\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})\b',.9),('handle',r'(?<!\w)@[A-Za-z0-9_.-]{2,64}',.85)]
        for typ,pat,conf in patterns:
            for m in re.finditer(pat,text): found.append(self._store_entity(row,typ,m.group(0),m.start(),m.end(),conf,{'method':'deterministic_regex'}))
        # Conservative capitalized-name/org candidates in Latin text.
        for m in re.finditer(r'\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß-]+(?:\s+|$)){2,4}',text):
            val=m.group(0).strip()
            if len(val)>5: found.append(self._store_entity(row,'named_entity_candidate',val,m.start(),m.end(),.55,{'method':'capitalized_sequence','requires_classification':True}))
        return {'created':len(found),'entities':found,'review_required':True,'automatic_identity_confirmation':False}

    def _store_entity(self,row: Mapping[str,Any],typ: str,value: str,start: int,end: int,confidence: float,evidence: Mapping[str,Any]) -> dict[str,Any]:
        eid=new_id('ent176'); payload={'entity_id':eid,'document_id':row['document_id'],'case_id':row['case_id'],'entity_type':typ,'value':value,'normalized_value':_norm(value).casefold(),'start_offset':start,'end_offset':end,'confidence':confidence,'evidence':dict(evidence),'review_status':'needs_review'}
        self.db.execute('INSERT INTO multilingual_entities_176 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,row['document_id'],row['case_id'],typ,value,payload['normalized_value'],start,end,confidence,dumps(evidence),'needs_review',now_ts(),_hash(payload)))
        return payload

    def translate_with_glossary(self,document_id: str,target_language: str,*,provider_id: str='local_glossary',glossary: Mapping[str,str]|None=None,confirmation: str) -> dict[str,Any]:
        if confirmation!=f'TRANSLATION 176 {document_id} ERSTELLEN': raise PermissionError('explicit translation approval required')
        row=self.db.one('SELECT * FROM multilingual_documents_176 WHERE document_id=?',(document_id,))
        if not row: raise KeyError('document not found')
        text=row['original_text']; hits=[]; translated=text
        for src,dst in (glossary or {}).items():
            n=len(re.findall(re.escape(str(src)),translated,flags=re.I))
            if n: translated=re.sub(re.escape(str(src)),str(dst),translated,flags=re.I); hits.append({'source':src,'target':dst,'count':n})
        tid=new_id('tr176'); machine=provider_id!='human'; payload={'translation_id':tid,'document_id':document_id,'source_language':row['detected_language'],'target_language':target_language,'provider_id':provider_id,'translated_text':translated,'glossary_hits':hits,'machine_translation':machine,'human_review_required':True}
        self.db.execute('INSERT INTO multilingual_translations_176 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,document_id,row['detected_language'],target_language,provider_id,translated,dumps(hits),int(machine),1,now_ts(),_hash(payload)))
        return payload

    def analyze(self,document_id: str,*,confirmation: str) -> dict[str,Any]:
        if confirmation!=f'CONTENT 176 {document_id} ANALYSIEREN': raise PermissionError('explicit content analysis approval required')
        row=self.db.one('SELECT * FROM multilingual_documents_176 WHERE document_id=?',(document_id,))
        if not row: raise KeyError('document not found')
        entities=self.db.all('SELECT entity_type,value,confidence FROM multilingual_entities_176 WHERE document_id=?',(document_id,))
        by_type={}
        for e in entities: by_type.setdefault(e['entity_type'],[]).append({'value':e['value'],'confidence':e['confidence']})
        words=[w.casefold() for w in re.findall(r"[^\W\d_]{4,}",row['normalized_text'],flags=re.UNICODE)]
        stop=set().union(*LANG_MARKERS.values()); topics=[w for w,n in Counter(w for w in words if w not in stop).most_common(12)]
        summary={'language':row['detected_language'],'character_count':len(row['original_text']),'entity_count':len(entities),'topic_count':len(topics),'limitations':['deterministic extraction','named entities require analyst classification','translation requires human review']}
        aid=new_id('ana176'); citations=[x for x in [row['source_ref'],row['source_id']] if x]
        payload={'analysis_id':aid,'document_id':document_id,'case_id':row['case_id'],'summary':summary,'topics':topics,'temporal_refs':by_type.get('date',[]),'location_refs':[],'person_refs':by_type.get('named_entity_candidate',[]),'organization_refs':[],'source_citations':citations,'ai_policy':self.AI_POLICY}
        self.db.execute('INSERT INTO multilingual_analysis_176 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,document_id,row['case_id'],dumps(summary),dumps(topics),dumps(payload['temporal_refs']),dumps([]),dumps(payload['person_refs']),dumps([]),dumps(citations),dumps(self.AI_POLICY),now_ts(),_hash(payload)))
        return {**payload,'review_required':True}

    def source_coverage(self) -> dict[str,Any]:
        counts=[]
        for table in ('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176'):
            try: counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {table}')['n']))
            except Exception: counts.append(0)
        payload={'total_documented_sources':sum(counts),'multilingual_sources':counts[-1],'production_active_new':0,'counts_by_layer':counts,'review_required':True}
        return {**payload,'payload_sha256':_hash(payload)}

    def _event(self,case_id: str|None,event_type: str,entity_ref: str|None,details: Mapping[str,Any]) -> None:
        payload={'case_id':case_id,'event_type':event_type,'entity_ref':entity_ref,'details':_clean(dict(details)),'created_at':now_ts()}
        self.db.execute('INSERT INTO multilingual_events_176 VALUES(?,?,?,?,?,?,?)',(new_id('ev176'),case_id,event_type,entity_ref,dumps(payload['details']),payload['created_at'],_hash(payload)))
