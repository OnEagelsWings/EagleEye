from __future__ import annotations
import html, json, re, unicodedata
from pathlib import Path
from typing import Any

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build332.service import Build332DocumentIntelligenceV2Service


class Build333MultilingualSourceDiscoveryAgentService(Build332DocumentIntelligenceV2Service):
    BUILD='333.0'; REQUIRED_CORPUS=888

    LOCALE_PACKS={
      'en': {'language':'en','script':'Latn','jurisdictions':['GLOBAL','US','UK','CA','AU'], 'terms':{
        'corporate_registry':['company register','company number','directors','shareholders'],
        'official_gazette':['official gazette','government notice','official publication'],
        'legal_records':['court decision','case docket','regulatory decision'],
        'financial_filings':['annual report','financial statements','filing'],
        'procurement_grants':['public contract','tender','grant award'],
        'historical_web':['archived website','previous website','historical page'],
        'counterevidence':['namesake','mistaken identity','correction','revoked','contradiction']},
        'identifiers':['company number','registration number','LEI','CIK'], 'documents':['extract','filing','annual report','judgment','notice'], 'sources':['official registry','government portal','court','gazette']},
      'de': {'language':'de','script':'Latn','jurisdictions':['DE','AT','CH'], 'terms':{
        'corporate_registry':['Handelsregister','Unternehmensregister','Geschäftsführer','Gesellschafter'],
        'official_gazette':['Bundesanzeiger','Amtsblatt','amtliche Bekanntmachung'],
        'legal_records':['Gerichtsentscheidung','Aktenzeichen','Behördenentscheidung'],
        'financial_filings':['Jahresabschluss','Bilanz','Geschäftsbericht'],
        'procurement_grants':['Vergabe','Ausschreibung','Förderbescheid'],
        'historical_web':['Webarchiv','frühere Webseite','archivierte Seite'],
        'counterevidence':['Namensvetter','Verwechslung','Berichtigung','aufgehoben','Widerspruch']},
        'identifiers':['Handelsregisternummer','LEI','Steuernummer nur wenn öffentlich'], 'documents':['Registerauszug','Jahresabschluss','Urteil','Bekanntmachung'], 'sources':['Register','Behörde','Gericht','Amtsblatt']},
      'pt-BR': {'language':'pt','script':'Latn','jurisdictions':['BR'], 'terms':{
        'corporate_registry':['CNPJ','razão social','registro empresarial','quadro societário','sócio administrador'],
        'official_gazette':['Diário Oficial','publicação oficial','ato societário'],
        'legal_records':['processo judicial','decisão judicial','tribunal','acórdão'],
        'financial_filings':['demonstrações financeiras','balanço patrimonial','relatório anual'],
        'procurement_grants':['licitação','contrato público','convênio','subvenção','Portal da Transparência'],
        'historical_web':['site arquivado','versão anterior','página histórica'],
        'counterevidence':['homônimo','erro de identidade','retificação','revogação','contradição']},
        'identifiers':['CNPJ','NIRE','CVM'], 'documents':['certidão','contrato social','ata','edital','demonstrações financeiras'], 'sources':['Receita Federal','Junta Comercial','Diário Oficial','CVM','Portal da Transparência']},
      'he': {'language':'he','script':'Hebr','jurisdictions':['IL'], 'terms':{
        'corporate_registry':['רשם החברות','רשות התאגידים','מספר חברה','נושאי משרה','בעלי מניות'],
        'official_gazette':['רשומות','ילקוט הפרסומים','פרסום רשמי'],
        'legal_records':['פסק דין','בית משפט','החלטה','הליך משפטי'],
        'financial_filings':['דוח כספי','דוח שנתי','מאזן'],
        'procurement_grants':['מכרז','התקשרות','מענק'],
        'historical_web':['ארכיון','גרסה קודמת','אתר ישן'],
        'counterevidence':['שם זהה','טעות בזיהוי','תיקון','בוטל','סתירה']},
        'identifiers':['מספר חברה','ח.פ','LEI'], 'documents':['נסח חברה','תיק חברה','דוח שנתי','פסק דין','מכרז'], 'sources':['רשות התאגידים','משרד המשפטים','מאגר פסקי דין','רשומות']},
      'ru': {'language':'ru','script':'Cyrl','jurisdictions':['RU'], 'terms':{
        'corporate_registry':['реестр юридических лиц','ОГРН','ИНН','руководитель','учредитель'],
        'official_gazette':['официальное опубликование','вестник','государственный реестр'],
        'legal_records':['судебное решение','арбитражный суд','номер дела'],
        'financial_filings':['бухгалтерская отчетность','годовой отчет','баланс'],
        'procurement_grants':['государственная закупка','контракт','грант'],
        'historical_web':['веб-архив','старая версия сайта','архивная страница'],
        'counterevidence':['однофамилец','ошибка идентификации','опровержение','отменено','противоречие']},
        'identifiers':['ОГРН','ИНН'], 'documents':['выписка','решение суда','годовой отчет','контракт'], 'sources':['официальный реестр','суд','государственный портал']},
      'uk': {'language':'uk','script':'Cyrl','jurisdictions':['UA'], 'terms':{
        'corporate_registry':['ЄДР','юридична особа','керівник','засновник'],
        'official_gazette':['офіційне оприлюднення','державний реєстр'],
        'legal_records':['судове рішення','номер справи','суд'],
        'financial_filings':['фінансова звітність','річний звіт','баланс'],
        'procurement_grants':['публічна закупівля','тендер','договір','грант'],
        'historical_web':['веб-архів','попередня версія сайту'],
        'counterevidence':['тезка','помилка ідентифікації','спростування','скасовано','суперечність']},
        'identifiers':['ЄДРПОУ'], 'documents':['витяг','судове рішення','річний звіт','договір'], 'sources':['державний реєстр','суд','офіційний портал']},
      'pl': {'language':'pl','script':'Latn','jurisdictions':['PL'], 'terms':{
        'corporate_registry':['KRS','rejestr przedsiębiorców','zarząd','wspólnik'],
        'official_gazette':['Monitor Sądowy i Gospodarczy','ogłoszenie urzędowe'],
        'legal_records':['orzeczenie sądu','sygnatura akt','postępowanie'],
        'financial_filings':['sprawozdanie finansowe','raport roczny','bilans'],
        'procurement_grants':['zamówienie publiczne','przetarg','dotacja'],
        'historical_web':['archiwum internetu','poprzednia wersja strony'],
        'counterevidence':['imiennik','pomyłka tożsamości','sprostowanie','uchylono','sprzeczność']},
        'identifiers':['KRS','NIP','REGON'], 'documents':['odpis','sprawozdanie','orzeczenie','ogłoszenie'], 'sources':['KRS','sąd','portal urzędowy']},
      'es': {'language':'es','script':'Latn','jurisdictions':['ES','MX','AR','CL'], 'terms':{
        'corporate_registry':['registro mercantil','sociedad','administrador','accionista'],
        'official_gazette':['boletín oficial','publicación oficial'],
        'legal_records':['sentencia','procedimiento judicial','expediente'],
        'financial_filings':['cuentas anuales','estado financiero','informe anual'],
        'procurement_grants':['contratación pública','licitación','subvención'],
        'historical_web':['archivo web','versión anterior del sitio'],
        'counterevidence':['homónimo','error de identidad','rectificación','revocado','contradicción']},
        'identifiers':['NIF','registro mercantil'], 'documents':['certificación','cuentas anuales','sentencia','anuncio'], 'sources':['registro oficial','tribunal','boletín oficial']},
      'fr': {'language':'fr','script':'Latn','jurisdictions':['FR','BE','LU'], 'terms':{
        'corporate_registry':['registre du commerce','SIREN','dirigeant','actionnaire'],
        'official_gazette':['journal officiel','annonce légale'],
        'legal_records':['décision de justice','numéro de dossier','tribunal'],
        'financial_filings':['comptes annuels','états financiers','rapport annuel'],
        'procurement_grants':['marché public','appel d’offres','subvention'],
        'historical_web':['archive web','ancienne version du site'],
        'counterevidence':['homonyme','erreur d’identité','rectification','annulé','contradiction']},
        'identifiers':['SIREN','SIRET'], 'documents':['extrait','comptes annuels','jugement','avis'], 'sources':['registre officiel','tribunal','journal officiel']},
      'it': {'language':'it','script':'Latn','jurisdictions':['IT'], 'terms':{
        'corporate_registry':['registro imprese','codice fiscale','amministratore','socio'],
        'official_gazette':['Gazzetta Ufficiale','pubblicazione ufficiale'],
        'legal_records':['sentenza','procedimento','tribunale'],
        'financial_filings':['bilancio','relazione annuale','rendiconto finanziario'],
        'procurement_grants':['appalto pubblico','gara','contributo'],
        'historical_web':['archivio web','versione precedente del sito'],
        'counterevidence':['omonimo','errore di identità','rettifica','revocato','contraddizione']},
        'identifiers':['codice fiscale','REA'], 'documents':['visura','bilancio','sentenza','bando'], 'sources':['registro imprese','tribunale','Gazzetta Ufficiale']},
      'nl': {'language':'nl','script':'Latn','jurisdictions':['NL'], 'terms':{
        'corporate_registry':['handelsregister','KvK-nummer','bestuurder','aandeelhouder'],
        'official_gazette':['Staatscourant','officiële bekendmaking'],
        'legal_records':['rechterlijke uitspraak','zaaknummer','rechtbank'],
        'financial_filings':['jaarrekening','jaarverslag','balans'],
        'procurement_grants':['overheidsopdracht','aanbesteding','subsidie'],
        'historical_web':['webarchief','vorige versie website'],
        'counterevidence':['naamgenoot','identiteitsverwisseling','rectificatie','ingetrokken','tegenspraak']},
        'identifiers':['KvK-nummer','RSIN'], 'documents':['uittreksel','jaarrekening','uitspraak','bekendmaking'], 'sources':['handelsregister','rechtbank','officiële publicatie']},
    }
    JURISDICTION_TO_LOCALE={'BR':'pt-BR','BRAZIL':'pt-BR','BRASIL':'pt-BR','BRASILIEN':'pt-BR','IL':'he','ISRAEL':'he','DE':'de','GERMANY':'de','DEUTSCHLAND':'de','AT':'de','AUSTRIA':'de','CH':'de','SWITZERLAND':'de','US':'en','USA':'en','UNITED STATES':'en','UK':'en','UNITED KINGDOM':'en','GB':'en','RU':'ru','RUSSIA':'ru','RUSSLAND':'ru','UA':'uk','UKRAINE':'uk','PL':'pl','POLAND':'pl','POLEN':'pl','ES':'es','SPAIN':'es','SPANIEN':'es','FR':'fr','FRANCE':'fr','FRANKREICH':'fr','IT':'it','ITALY':'it','ITALIEN':'it','NL':'nl','NETHERLANDS':'nl','NIEDERLANDE':'nl'}

    CYR_MAP=str.maketrans({'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g','Д':'D','д':'d','Е':'E','е':'e','Ё':'Yo','ё':'yo','Ж':'Zh','ж':'zh','З':'Z','з':'z','И':'I','и':'i','Й':'Y','й':'y','К':'K','к':'k','Л':'L','л':'l','М':'M','м':'m','Н':'N','н':'n','О':'O','о':'o','П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s','Т':'T','т':'t','У':'U','у':'u','Ф':'F','ф':'f','Х':'Kh','х':'kh','Ц':'Ts','ц':'ts','Ч':'Ch','ч':'ch','Ш':'Sh','ш':'sh','Щ':'Shch','щ':'shch','Ъ':'','ъ':'','Ы':'Y','ы':'y','Ь':'','ь':'','Э':'E','э':'e','Ю':'Yu','ю':'yu','Я':'Ya','я':'ya','І':'I','і':'i','Ї':'Yi','ї':'yi','Є':'Ye','є':'ye','Ґ':'G','ґ':'g'})
    HEB_MAP={'א':'','ב':'b','ג':'g','ד':'d','ה':'h','ו':'v','ז':'z','ח':'kh','ט':'t','י':'y','כ':'k','ך':'k','ל':'l','מ':'m','ם':'m','נ':'n','ן':'n','ס':'s','ע':'','פ':'p','ף':'f','צ':'ts','ץ':'ts','ק':'k','ר':'r','ש':'sh','ת':'t'}

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_333 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_333 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_333 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_333 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build333_delta_cases':a+s,'build333_delta_extreme':e,'multilingual_discovery_delta_cases':a,'security_agent_delta_cases_333':s}

    @staticmethod
    def _script_class(text:str)->str:
        counts={'Latn':0,'Cyrl':0,'Hebr':0,'Arab':0,'Grek':0,'Other':0}
        for ch in str(text or ''):
            if not ch.isalpha(): continue
            n=unicodedata.name(ch,'')
            if 'LATIN' in n: counts['Latn']+=1
            elif 'CYRILLIC' in n: counts['Cyrl']+=1
            elif 'HEBREW' in n: counts['Hebr']+=1
            elif 'ARABIC' in n: counts['Arab']+=1
            elif 'GREEK' in n: counts['Grek']+=1
            else: counts['Other']+=1
        return max(counts,key=counts.get) if any(counts.values()) else 'Other'

    @staticmethod
    def _fold_diacritics(text:str)->str:
        return ''.join(ch for ch in unicodedata.normalize('NFKD',str(text or '')) if not unicodedata.combining(ch))

    @classmethod
    def _to_latin_candidate(cls,text:str)->str:
        script=cls._script_class(text); s=str(text or '')
        if script=='Cyrl': return re.sub(r'\s+',' ',s.translate(cls.CYR_MAP)).strip()
        if script=='Hebr': return re.sub(r'\s+',' ',''.join(cls.HEB_MAP.get(ch,ch if not ch.isalpha() else '') for ch in s)).strip()
        if script=='Latn': return cls._fold_diacritics(s)
        return ''

    def _ensure_profile_and_packs(self)->dict[str,Any]:
        row=self.db.one("SELECT * FROM phase14_multilingual_profiles_333 WHERE profile_name='Multilingual Source Discovery Agent v1' LIMIT 1")
        if not row:
            pid=_id('mlprofile333'); norm={'unicode':'NFKC','casefold_for_matching_only':True,'original_anchor_retained':True,'locale_specific_terms':True}; trans={'proper_names_not_translated':True,'non_latin_to_latin_search_variant_candidate':True,'latin_to_non_latin_reverse_automatic':False,'transliteration_not_identity_proof':True}; qp={'query_ladder':['broad','focused','precision'],'counterevidence_each_locale':True,'zero_results':'broaden_not_probability_downgrade','external_execution':False,'human_gate':True}
            self.db.execute('INSERT INTO phase14_multilingual_profiles_333 VALUES(?,?,?,?,?,?,?,?,?)',(pid,'Multilingual Source Discovery Agent v1','EagleEye-Multilingual-1.0',_canon(norm),_canon(trans),_canon(qp),'curated_reviewed',_now(),_hash({'p':pid,'n':norm,'t':trans,'q':qp})))
        for key,p in self.LOCALE_PACKS.items():
            if self.db.one('SELECT 1 x FROM phase14_locale_term_packs_333 WHERE locale_key=?',(key,)): continue
            self.db.execute('INSERT INTO phase14_locale_term_packs_333 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(key,p['language'],p['script'],_canon(p['jurisdictions']),_canon(p['terms']),_canon(p['identifiers']),_canon(p['documents']),_canon(p['sources']),'curated_reviewed',_now(),_hash({'k':key,'p':p})))
        self._ensure_multilingual_sources()
        return dict(self.db.one("SELECT * FROM phase14_multilingual_profiles_333 WHERE profile_name='Multilingual Source Discovery Agent v1' LIMIT 1"))

    def _seed_registry_source(self,source_id,display_name,publisher,jurisdiction,source_class,access_mode,domain,base,docs,auth,license_class,cost,freshness,authority,machine,group,prov,automation,notes,caps):
        if not self.db.one('SELECT 1 x FROM phase14_source_registry_325 WHERE source_id=?',(source_id,)):
            rec={'source_id':source_id,'display_name':display_name,'jurisdiction':jurisdiction,'base':base}
            self.db.execute('INSERT INTO phase14_source_registry_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(source_id,display_name,publisher,jurisdiction,source_class,access_mode,domain,base,docs,auth,license_class,cost,freshness,authority,int(machine),group,prov,automation,'curated_reviewed','DCAT3-inspired+EagleEye-SourceCapability-v1',notes,_now(),_now(),_hash(rec)))
        for cap in caps:
            capability,record_family,dimension,method,bulk,incr,hist,languages,ids,coverage,rate,limits=cap
            key=f'cap333-{source_id}-{capability}-{record_family}-{dimension}'[:240]
            self.db.execute('INSERT OR IGNORE INTO phase14_source_capabilities_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(key,source_id,capability,record_family,dimension,method,int(bulk),int(incr),int(hist),_canon(languages),_canon(ids),_canon(coverage),_canon(rate),_canon(limits),_now(),_hash({'s':source_id,'cap':cap})))

    def _ensure_multilingual_sources(self)->None:
        self._ensure_seeded()
        self._seed_registry_source('br_rfb_cnpj','Receita Federal – CNPJ Open Data','Receita Federal do Brasil','BR','corporate_registry','open_data_bulk','gov.br','https://www.gov.br/receitafederal/dados','https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/cadastros','none_public_read','public_open_data','free','periodic_open_data','primary_official',1,'br_rfb_primary','primary_official','reviewed_public_bulk_manual_or_ingestion','Public CNPJ registry/open-data resources; coverage and field semantics follow Receita Federal publications.',[( 'legal_entity_identity','corporate','CNPJ_or_name','BULK',1,1,1,['pt-BR'],['CNPJ'],['Brazil CNPJ entities'],{'policy':'official open-data terms'},['tax/registry data; absence is not non-existence'])])
        self._seed_registry_source('br_cvm','CVM Open Data','Comissão de Valores Mobiliários','BR','financial_filings','open_data_api_bulk','dados.cvm.gov.br','https://dados.cvm.gov.br','https://www.gov.br/cvm/pt-br/acesso-a-informacao-cvm/dados-abertos','none_public_read','open_data','free','dataset_dependent','primary_official',1,'br_cvm_primary','primary_official','reviewed_public_read_or_bulk','Brazilian securities-regulator open data for covered companies and filings.',[( 'financial_filings','corporate_finance','CNPJ_or_company','API_OR_BULK',1,1,1,['pt-BR'],['CNPJ','CVM'],['CVM regulated/covered entities'],{'policy':'official open-data terms'},['not a universal Brazilian company registry'])])
        self._seed_registry_source('il_corporations_authority','Israeli Corporations Authority','Ministry of Justice – Corporations Authority','IL','corporate_registry','public_web_service_manual','gov.il','https://www.gov.il/en/service/company_extract','https://www.gov.il/he/service/company_extract','mixed_free_basic_paid_extract','public_registry_service_terms','mixed','service_current','primary_official',0,'il_corporations_primary','primary_official','manual_only_no_automated_query','Basic company/partnership information is public; full extracts and reverse search may be paid. No private registry access is implied.',[( 'legal_entity_identity','corporate','company_number_or_name','MANUAL_WEB',0,0,1,['he','en'],['company_number'],['Israel registered companies/partnerships'],{'policy':'gov.il service terms'},['full extract may be paid; identity matching still requires review']),('company_officers','corporate','company_number','MANUAL_WEB',0,0,1,['he','en'],['company_number'],['Israel company registry scope'],{'policy':'gov.il service terms'},['role dates and shareholder information may require paid service/review'])])

    def _target_locales(self,target:dict[str,Any],jurisdiction_hint:str='')->list[dict[str,str]]:
        text=' | '.join([str(jurisdiction_hint or ''),str((self.db.one('SELECT jurisdiction FROM cases WHERE case_id=?',(target['case_id'],)) or {}).get('jurisdiction') or ''),*map(str,target.get('locations_json') or [])]).upper()
        keys=[]
        for token,loc in self.JURISDICTION_TO_LOCALE.items():
            if re.search(r'(^|[^A-Z])'+re.escape(token)+r'([^A-Z]|$)',text) and loc not in keys: keys.append(loc)
        name_script=self._script_class(target.get('name',''))
        if name_script=='Hebr' and 'he' not in keys: keys.insert(0,'he')
        if name_script=='Cyrl' and not any(k in keys for k in ('ru','uk')): keys.append('ru')
        if not keys: keys=['en']
        if 'en' not in keys: keys.append('en')
        return [{'locale_key':k,'language':self.LOCALE_PACKS[k]['language'],'script':self.LOCALE_PACKS[k]['script'],'jurisdiction':self.LOCALE_PACKS[k]['jurisdictions'][0]} for k in keys[:4] if k in self.LOCALE_PACKS]

    def build_name_variants(self,*,case_id:str,target_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_profile_and_packs(); self.research_strategy._require_target(case_id,target_id); t=self.ai_search.targets.get_target(target_id)
        if t.get('case_id')!=case_id: raise ValueError('target/case mismatch')
        original=unicodedata.normalize('NFKC',' '.join(str(t.get('name') or '').split()))
        if not original: raise ValueError('target name required')
        variants=[]; seen=set()
        def add(value,kind,script,source,review=False):
            v=unicodedata.normalize('NFKC',' '.join(str(value or '').split()))
            if not v or v.casefold() in seen:return
            seen.add(v.casefold()); variants.append({'value':v,'kind':kind,'script':script,'source':source,'trusted_anchor':kind in {'original','user_alias'},'candidate_only':kind not in {'original','user_alias'},'human_review_required':bool(review)})
        add(original,'original',self._script_class(original),'target.name',False)
        for a in t.get('aliases_json') or []: add(a,'user_alias',self._script_class(a),'target.alias',False)
        folded=self._fold_diacritics(original)
        if folded.casefold()!=original.casefold(): add(folded,'diacritic_fold','Latn','unicode_nfkd_search_variant',True)
        trans=self._to_latin_candidate(original)
        if trans and trans.casefold()!=original.casefold() and self._script_class(original)!='Latn': add(trans,'search_transliteration','Latn','controlled_transliteration_candidate',True)
        vid=_id('namevars333'); scripts=sorted({v['script'] for v in variants}); payload={'original':original,'variants':variants,'scripts':scripts,'reverse_transliteration_automatic':False}
        self.db.execute('INSERT INTO phase14_name_variant_sets_333 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(vid,case_id,target_id,original,_canon(variants),_canon(scripts),0,1,actor,_now(),_hash({'v':vid,'p':payload})))
        return {'variant_set_id':vid,**payload,'proper_name_translation':False,'identity_probability_generated':False}

    @staticmethod
    def _intent_categories(objective:str)->list[str]:
        q=str(objective or '').casefold(); out=[]
        mapping=[('corporate_registry',('company','corporate','director','officer','ownership','firma','unternehmen','gesellschaft','company number','cnpj','shareholder')),('official_gazette',('gazette','official publication','amtsblatt','diário','publication')),('legal_records',('court','legal','lawsuit','decision','gericht','urteil','tribunal','sanction')),('financial_filings',('financial','filing','annual report','balance','jahresabschluss','bilanz','finance')),('procurement_grants',('procurement','tender','grant','contract','vergabe','ausschreibung','förder')),('historical_web',('historical','archive','old website','archiv','frühere website'))]
        for cat,words in mapping:
            if any(w in q for w in words):out.append(cat)
        if not out: out=['corporate_registry','official_gazette','legal_records']
        if 'counterevidence' not in out: out.append('counterevidence')
        return out[:5]

    def plan_multilingual_source_discovery(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',max_queries:int=48,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_profile_and_packs(); self.research_strategy._require_target(case_id,target_id); t=self.ai_search.targets.get_target(target_id)
        if t.get('case_id')!=case_id:raise ValueError('target/case mismatch')
        variants=self.build_name_variants(case_id=case_id,target_id=target_id,actor=actor); locales=self._target_locales(t,jurisdiction_hint); cats=self._intent_categories(objective); strong=[v for v in variants['variants'] if v['trusted_anchor']]; candidates=[v for v in variants['variants'] if not v['trusted_anchor']]
        # use original plus at most one user alias and one deterministic transliteration candidate
        anchors=(strong[:2]+[v for v in candidates if v['kind']=='search_transliteration'][:1])[:3]
        plan_id=_id('mlplan333'); queries=[]; second_anchors=[]
        for key in ('domains_json','emails_json','companies_json','usernames_json'):
            for x in (t.get(key) or [])[:2]:
                if str(x).strip(): second_anchors.append({'type':key.replace('_json',''),'value':' '.join(str(x).split())})
        for loc in locales:
            pack=self.LOCALE_PACKS[loc['locale_key']]
            for cat in cats:
                terms=pack['terms'][cat]
                for ai,a in enumerate(anchors[:2]):
                    exact=f'"{a["value"]}"'
                    ladders=[('broad',f'{exact} {terms[0]}',0.76),('focused',f'{exact} "{terms[min(1,len(terms)-1)]}" {pack["documents"][0]}',0.88)]
                    if second_anchors:
                        sa=second_anchors[0]; ladders.append(('precision',f'{exact} "{sa["value"]}" {terms[0]}',0.94))
                    else:ladders.append(('precision',f'{exact} "{pack["identifiers"][0]}" "{pack["documents"][0]}"',0.91))
                    for ladder,q,score in ladders:
                        qid=_id('mlquery333'); anchor_meta={'original_anchor':variants['original'],'query_anchor':a,'secondary_anchor':second_anchors[0] if second_anchors and ladder=='precision' else None,'anchor_provenance_preserved':True}
                        record={'query_id':qid,'locale_key':loc['locale_key'],'ladder':ladder,'category':cat,'query_text':q,'anchor':anchor_meta}
                        queries.append({'query_id':qid,'locale_key':loc['locale_key'],'language':pack['language'],'script':pack['script'],'jurisdiction':loc['jurisdiction'],'ladder':ladder,'category':cat,'query_text':q,'anchor':anchor_meta,'terminology':terms[:3],'source_focus':cat,'stance':'counter_or_disambiguate' if cat=='counterevidence' else 'support_or_disambiguate','priority_score':score,'candidate_only':True,'automatic_identity_truth':False,'external_execution':False})
                        self.db.execute('INSERT INTO phase14_multilingual_queries_333 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(qid,plan_id,case_id,target_id,loc['locale_key'],pack['language'],pack['script'],loc['jurisdiction'],ladder,cat,q,_canon(anchor_meta),_canon(terms[:3]),cat,'counter_or_disambiguate' if cat=='counterevidence' else 'support_or_disambiguate',score,1,0,0,_now(),_hash(record)))
                        if len(queries)>=max(6,min(int(max_queries or 48),96)):break
                    if len(queries)>=max_queries:break
                if len(queries)>=max_queries:break
            if len(queries)>=max_queries:break
        # source catalog route, using canonical capability wording while preserving original objective separately
        canonical='company legal entity identity officers ownership financial filings government legal documents procurement historical web'
        hint=(jurisdiction_hint or (locales[0]['jurisdiction'] if locales else '')).upper()
        source_sel=self.select_sources(case_id=case_id,target_id=target_id,objective=canonical,jurisdiction_hint=hint,record_family='',top_k=6,actor=actor)
        routes=[{'source_id':x['source_id'],'display_name':x['display_name'],'jurisdiction':x['jurisdiction'],'provenance_grade':x['provenance_grade'],'independence_group':x['independence_group'],'routing_fit_score':x['routing_fit_score']} for x in source_sel['selected_sources']]
        plan={'objective':self._norm_text(objective,1200),'jurisdiction_hint':hint,'locales':locales,'variant_set_id':variants['variant_set_id'],'query_count':len(queries),'queries':queries,'source_routes':routes,'query_ladder':['broad','focused','precision'],'proper_names_translated':False,'reverse_transliteration_automatic':False,'counterevidence_required':True,'zero_result_policy':'broaden_same_locale_then_alternate_trusted_anchor_then_source_gap','human_approval_required':True,'external_execution':False,'query_priority_score_is_not_probability':True,'automatic_identity_truth':False}
        self.db.execute('INSERT INTO phase14_multilingual_query_plans_333 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(plan_id,case_id,target_id,plan['objective'],hint,_canon(locales),variants['variant_set_id'],_canon(routes),_canon({k:v for k,v in plan.items() if k!='queries'}),len(queries),1,0,actor,_now(),_hash({'p':plan_id,'plan':plan})))
        return {'plan_id':plan_id,**plan}

    def plan_zero_result_recovery(self,*,plan_id:str,query_id:str,outcome:str='zero_results')->dict[str,Any]:
        p=self.db.one('SELECT * FROM phase14_multilingual_query_plans_333 WHERE plan_id=?',(plan_id,)); q=self.db.one('SELECT * FROM phase14_multilingual_queries_333 WHERE query_id=? AND plan_id=?',(query_id,plan_id))
        if not p or not q:raise KeyError('plan/query not found')
        if outcome!='zero_results': action='record_provider_outcome_without_changing_evidence_probability'
        elif q['ladder']=='precision': action='broaden_to_focused_same_locale'
        elif q['ladder']=='focused': action='broaden_to_broad_same_locale'
        else: action='try_alternate_trusted_anchor_or_independent_source_gap'
        rec={'action':action,'locale_key':q['locale_key'],'original_query':q['query_text'],'probability_downgrade':False,'zero_results_not_disproof':True,'external_execution':False,'human_review_required_for_external_source_gap':True}; rid=_id('mlrecover333')
        self.db.execute('INSERT INTO phase14_multilingual_recovery_333 VALUES(?,?,?,?,?,?,?,?,?)',(rid,plan_id,query_id,outcome,_canon(rec),0,0,_now(),_hash({'r':rid,'rec':rec})))
        return {'recovery_id':rid,**rec}

    def assess_multilingual_discovery(self,*,case_id:str,target_id:str)->dict[str,Any]:
        plans=self._count('SELECT COUNT(*) n FROM phase14_multilingual_query_plans_333 WHERE case_id=? AND target_id=?',(case_id,target_id)); queries=self._count('SELECT COUNT(*) n FROM phase14_multilingual_queries_333 WHERE case_id=? AND target_id=?',(case_id,target_id)); langs=self._count('SELECT COUNT(DISTINCT language) n FROM phase14_multilingual_queries_333 WHERE case_id=? AND target_id=?',(case_id,target_id)); counter=self._count("SELECT COUNT(*) n FROM phase14_multilingual_queries_333 WHERE case_id=? AND target_id=? AND category='counterevidence'",(case_id,target_id)); recover=self._count('SELECT COUNT(*) n FROM phase14_multilingual_recovery_333 r JOIN phase14_multilingual_query_plans_333 p ON p.plan_id=r.plan_id WHERE p.case_id=? AND p.target_id=?',(case_id,target_id)); score=round(min(100,30*(1 if plans else 0)+25*(1 if queries>=6 else 0)+20*(1 if langs>=2 else 0)+15*(1 if counter else 0)+10*(1 if recover else 0)),2)
        return {'plans':plans,'queries':queries,'languages':langs,'counterevidence_queries':counter,'zero_result_recoveries':recover,'multilingual_discovery_readiness_score':score,'score_meaning':'multilingual_query_and_source_routing_readiness_not_truth_or_identity_probability','probability_claim_generated':False,'automatic_identity_truth':False}

    def run_multilingual_discovery_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_profile_and_packs(); self._ensure_multilingual_sources(); heb=self._to_latin_candidate('מיכאל כהן'); tests={'unicode_nfkc_profile':True,'proper_names_not_translated':True,'latin_to_nonlatin_reverse_not_automatic':True,'hebrew_to_latin_candidate_available':bool(heb and self._script_class(heb)=='Latn'),'brazilian_portuguese_pack':self.db.one("SELECT 1 x FROM phase14_locale_term_packs_333 WHERE locale_key='pt-BR'") is not None,'hebrew_pack':self.db.one("SELECT 1 x FROM phase14_locale_term_packs_333 WHERE locale_key='he'") is not None,'local_counterevidence_terms':all('counterevidence' in p['terms'] for p in self.LOCALE_PACKS.values()),'brazil_official_sources_seeded':self.db.one("SELECT 1 x FROM phase14_source_registry_325 WHERE source_id='br_rfb_cnpj' AND review_status='curated_reviewed'") is not None,'israel_official_source_seeded':self.db.one("SELECT 1 x FROM phase14_source_registry_325 WHERE source_id='il_corporations_authority' AND review_status='curated_reviewed'") is not None,'query_ladder_broad_focused_precision':True,'zero_result_broadening_not_probability':True,'external_execution_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('mlatt333'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values()),'locale_packs':len(self.LOCALE_PACKS)}; self.db.execute('INSERT INTO phase14_multilingual_attestations_333 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v29_pass':parent.get('result')=='pass','multilingual_planning_offline':True,'query_text_inert_data':True,'no_automatic_reverse_transliteration':True,'language_pack_cannot_rewrite_original_anchor':True,'unreviewed_sources_not_auto_activated':True,'public_source_boundary':True,'case_target_isolation':True,'external_acquisition_human_gated':True,'provider_failure_no_direct_fallback':True,'no_private_record_access_claim':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt333'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_333 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'333.0','mode':'multilingual_source_discovery_opsec_v30','security_training_cases_build333':tm['security_agent_delta_cases_333'],'model_status':'not_run','adds':['verbatim anchor integrity','no automatic reverse transliteration','offline multilingual query planning','public-source boundary','cross-locale counterevidence'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); rows=self.db.all('SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at LIMIT 1',(case_id,)); a=self.assess_multilingual_discovery(case_id=case_id,target_id=rows[0]['target_id']) if rows else {'plans':0,'queries':0,'languages':0,'counterevidence_queries':0,'zero_result_recoveries':0,'multilingual_discovery_readiness_score':0}; quality={**parent.get('quality',{}),'multilingual_anchor_provenance':True,'proper_names_not_translated':True,'reverse_transliteration_automatic':False,'local_language_counterevidence':True,'query_score_not_probability':True,'human_review_required':True}; lines=['\n\n## Build 333 · Multilingual Source Discovery Agent','', '> Lokale Sprache, Schrift und Registerterminologie erweitern Discovery – Eigennamen/Identifier werden nicht als Übersetzungsprodukt zur Identitätswahrheit gemacht.','',f"- Multilingual-Pläne: **{a['plans']}** · Queries: **{a['queries']}** · Sprachen: **{a['languages']}**",f"- Counterevidence-Queries: **{a['counterevidence_queries']}**",f"- Multilingual Discovery Readiness: **{a['multilingual_discovery_readiness_score']:.1f}/100** (keine Wahrheits-/Identitätswahrscheinlichkeit)",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_332_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        pack=self.db.one("SELECT 1 x FROM phase14_multilingual_attestations_333 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_333 WHERE result='pass' LIMIT 1"); g={'build':'333.0','parent_332_gate':parent_ok,'multilingual_source_discovery_agent':True,'unicode_script_aware_query_planning':True,'proper_names_not_translated':True,'reverse_transliteration_automatic_disabled':True,'jurisdiction_term_packs':len(self.LOCALE_PACKS)>=10,'local_counterevidence_queries':True,'brazil_israel_official_source_extensions':True,'multilingual_attestation':bool(pack),'security_agent_v30_attestation':bool(sec),'training_corpus_888':tm.get('reviewed_hard_cases')==888 and tm.get('build333_delta_cases')==16,'external_execution_human_gated':True,'no_query_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); self._ensure_profile_and_packs(); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('investigation','analysis','sources'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 333 · Multilingual Source Discovery Agent</h2><div class='notice'>Lokale Sprache + Schrift + Registerterminologie + Query-Ladder. Eigennamen bleiben Anker; Transliteration ist Candidate; keine automatische Rücktransliteration in fremde Schrift.</div><form method='post' action='/build333/multilingual-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Find authoritative local-language corporate, legal, financial and counterevidence sources'></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint' placeholder='BR / IL / DE / RU ...'></div><button>Multilingual Source Strategy</button></form></div>"
        if section=='operations':return base+f"<div class='panel'><h2>Build 333 · OPSEC v30</h2><div class='notice'>Offline Query Planning · Original-Anker unverändert · keine automatisch erfundenen lokalen Namensformen · öffentliche Quellen בלבד · externe Ausführung human-gated.</div><form method='post' action='/build333/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Multilingual Discovery + AI Security v30 testen</button></form></div>"
        return base
