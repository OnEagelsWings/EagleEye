from __future__ import annotations
import hashlib, json, re, unicodedata
from difflib import SequenceMatcher
from typing import Any, Mapping
from eagleeye_pro.core.database import dumps, new_id, now_ts

SPACE_RE=re.compile(r"\s+")
PARTICLES={'de','del','della','di','da','van','von','der','den','al','el','bin','ibn','bat','ben','bar'}
ARABIC_PREFIXES=('al','el')
PUNCT_RE=re.compile(r"[^\w\s'\-]", re.UNICODE)
HEBREW={
'א':'a','ב':'v','ג':'g','ד':'d','ה':'h','ו':'v','ז':'z','ח':'h','ט':'t','י':'y','כ':'kh','ך':'kh','ל':'l','מ':'m','ם':'m','נ':'n','ן':'n','ס':'s','ע':'a','פ':'f','ף':'f','צ':'ts','ץ':'ts','ק':'k','ר':'r','ש':'sh','ת':'t'
}
ARABIC={'ا':'a','أ':'a','إ':'i','آ':'a','ب':'b','ت':'t','ث':'th','ج':'j','ح':'h','خ':'kh','د':'d','ذ':'dh','ر':'r','ز':'z','س':'s','ش':'sh','ص':'s','ض':'d','ط':'t','ظ':'z','ع':'a','غ':'gh','ف':'f','ق':'q','ك':'k','ل':'l','م':'m','ن':'n','ه':'h','و':'w','ي':'y','ى':'a','ة':'a','ء':''}
CYRILLIC={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya','і':'i','ї':'yi','є':'ye','ґ':'g'}
CONFUSABLES={'а':'a','е':'e','о':'o','р':'p','с':'c','х':'x','у':'y','і':'i','ј':'j','Α':'A','Β':'B','Ε':'E','Ζ':'Z','Η':'H','Ι':'I','Κ':'K','Μ':'M','Ν':'N','Ο':'O','Ρ':'P','Τ':'T','Υ':'Y','Χ':'X'}


def _canonical(v:Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _digest(v:Any)->str: return hashlib.sha256(_canonical(v).encode()).hexdigest()

def _script(ch:str)->str:
    n=unicodedata.name(ch,'')
    if 'HEBREW' in n:return 'Hebrew'
    if 'ARABIC' in n:return 'Arabic'
    if 'CYRILLIC' in n:return 'Cyrillic'
    if 'LATIN' in n:return 'Latin'
    return 'Common' if not ch.isalpha() else 'Other'

class Build158MultilingualIdentityService:
    BUILD='158.0'; MISSION='Multilingual Identity Engine'
    def __init__(self,db:Any,audit:Any,*,benchmark:Any|None=None,actor:str='system'):
        self.db=db; self.audit=audit; self.benchmark=benchmark; self.actor=actor
        self._seed_profiles()

    def _seed_profiles(self)->None:
        for name,src,locale,rules in [('hebrew_latin','Hebrew','he',HEBREW),('arabic_latin','Arabic','ar',ARABIC),('cyrillic_latin','Cyrillic','und-Cyrl',CYRILLIC)]:
            self.db.execute('INSERT OR IGNORE INTO transliteration_profiles_158 VALUES(?,?,?,?,?,?,?,?,?)',(new_id('tr158'),name,src,'Latin',locale,'158.0',_digest(rules),'active',now_ts()))

    def normalize_name(self,name:str,*,locale:str|None=None,strip_marks:bool=True)->dict[str,Any]:
        if not isinstance(name,str) or not name.strip(): raise ValueError('Name darf nicht leer sein')
        original=name.strip(); nfc=unicodedata.normalize('NFC',original); nfkc=unicodedata.normalize('NFKC',original)
        folded=nfkc.casefold(); cleaned=SPACE_RE.sub(' ',PUNCT_RE.sub(' ',folded)).strip()
        markless=''.join(c for c in unicodedata.normalize('NFKD',cleaned) if not unicodedata.combining(c)) if strip_marks else cleaned
        scripts=sorted({_script(c) for c in original if c.isalpha()})
        latin=self.transliterate(original)
        tokens=[t for t in SPACE_RE.split(markless) if t]
        core_tokens=[t for t in tokens if t not in PARTICLES] or tokens
        variants=sorted({markless,' '.join(tokens), ' '.join(reversed(tokens)) if len(tokens)>1 else markless, latin,' '.join(core_tokens),' '.join(reversed(core_tokens)) if len(core_tokens)>1 else ' '.join(core_tokens)})
        mixed=len([s for s in scripts if s not in {'Common','Other'}])>1
        skeleton=''.join(CONFUSABLES.get(c,c) for c in nfkc)
        security={'mixed_script':mixed,'confusable_skeleton':skeleton.casefold(),'bidi_controls':any(unicodedata.category(c)=='Cf' for c in original),'invisible_controls':[f'U+{ord(c):04X}' for c in original if unicodedata.category(c)=='Cf'],'script_count':len([s for s in scripts if s not in {'Common','Other'}])}
        return {'original':original,'locale':locale,'nfc':nfc,'nfkc':nfkc,'casefolded':folded,'comparison_key':markless,'tokens':tokens,'scripts':scripts,'latin_transliteration':latin,'variants':variants,'security':security}

    def transliterate(self,text:str)->str:
        out=[]
        for c in unicodedata.normalize('NFKD',text):
            if unicodedata.combining(c): continue
            low=c.lower()
            if c in HEBREW: out.append(HEBREW[c])
            elif c in ARABIC: out.append(ARABIC[c])
            elif low in CYRILLIC: out.append(CYRILLIC[low])
            else: out.append(low)
        return SPACE_RE.sub(' ', ''.join(out)).strip()

    def store_name(self,name:str,*,case_id:str|None=None,locale:str|None=None,actor:str|None=None)->dict[str,Any]:
        normalized=self.normalize_name(name,locale=locale); nid=new_id('mname158'); ts=now_ts()
        payload={'name_id':nid,'case_id':case_id,'normalized':normalized}
        self.db.execute('INSERT INTO multilingual_names_158 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(nid,case_id,name,locale,dumps(normalized['scripts']),dumps(normalized),dumps([normalized['latin_transliteration']]),dumps(normalized['security']),actor or self.actor,ts,_digest(payload)))
        self.audit.log('multilingual_name_stored_158','multilingual_name',nid,case_id,{'scripts':normalized['scripts'],'review_required':True})
        return {'name_id':nid,**normalized,'review_required':True}

    def compare(self,left:str|Mapping[str,Any],right:str|Mapping[str,Any],*,left_locale:str|None=None,right_locale:str|None=None)->dict[str,Any]:
        l=self.normalize_name(str(left.get('name','')) if isinstance(left,Mapping) else left,locale=left_locale)
        r=self.normalize_name(str(right.get('name','')) if isinstance(right,Mapping) else right,locale=right_locale)
        exact=l['comparison_key']==r['comparison_key']; trans=l['latin_transliteration']==r['latin_transliteration']
        token=set(l['tokens']); rtoken=set(r['tokens']); jac=len(token&rtoken)/len(token|rtoken) if token|rtoken else 0
        seq=SequenceMatcher(None,l['latin_transliteration'],r['latin_transliteration']).ratio()
        order_insensitive=sorted(l['tokens'])==sorted(r['tokens']) and bool(l['tokens'])
        particle_insensitive=sorted(t for t in l['tokens'] if t not in PARTICLES)==sorted(t for t in r['tokens'] if t not in PARTICLES) and bool(l['tokens']) and bool(r['tokens'])
        score=max(1.0 if exact else 0, .94 if trans else 0, .88 if order_insensitive else 0, .84 if particle_insensitive else 0, .55*seq+.45*jac)
        warnings=[]
        if l['security']['mixed_script'] or r['security']['mixed_script']: warnings.append('mixed_script_input')
        if l['security']['confusable_skeleton']==r['security']['confusable_skeleton'] and not exact: warnings.append('unicode_confusable')
        band='high' if score>=.88 else 'medium' if score>=.65 else 'low'
        signals={'exact_normalized':exact,'same_transliteration':trans,'token_jaccard':jac,'sequence_similarity':seq,'order_insensitive_match':order_insensitive,'particle_insensitive_match':particle_insensitive,'left_scripts':l['scripts'],'right_scripts':r['scripts']}
        payload={'left':l,'right':r,'score':score,'signals':signals,'warnings':warnings}; cid=new_id('mcmp158')
        self.db.execute('INSERT INTO multilingual_comparisons_158 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,None,None,dumps(l),dumps(r),score,band,dumps(signals),dumps(warnings),1,now_ts(),_digest(payload)))
        self.audit.log('multilingual_identity_compared_158','multilingual_comparison',cid,None,{'score':score,'band':band,'warnings':warnings})
        return {'comparison_id':cid,'score':score,'confidence_band':band,'signals':signals,'warnings':warnings,'left':l,'right':r,'review_required':True,'automatic_identity_confirmation':False}
