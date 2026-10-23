"""Escaped, source-linked display for provisional alternatives."""
from html import escape
from urllib.parse import urlencode

def render_alternatives(run, case_id):
    sources={s['anchor_id']:s for s in run['sources']}
    result=''
    for alternative in run['summary'].get('alternatives',[]):
        evidence=''
        for key,label in [('supporting','Stützende Fundstellen'),('contradicting','Widersprechende Fundstellen')]:
            evidence+='<h5>'+label+'</h5>'
            if not alternative[key]:evidence+='<p>Keine in dieser Auswahl benannt.</p>'
            for citation in alternative[key]:
                source=sources[citation['anchor_id']]
                url='/documents458?'+urlencode({'case_id':case_id,'document_id':source['document_id']})+'#anchor-'+source['anchor_id']
                evidence+='<blockquote>'+escape(citation['quote'])+'</blockquote><a href="'+escape(url,quote=True)+'">'+escape(source['title'])+' · '+escape(source['locator'])+'</a>'
        result+='<section><h4>Ungeprüfte Hypothese: '+escape(alternative['title'])+'</h4><p>'+escape(alternative['explanation'])+'</p>'+evidence+'<h5>Fehlende Belege</h5><p>'+escape(alternative['missing_evidence'])+'</p><h5>Prüffrage</h5><p>'+escape(alternative['verification_question'])+'</p></section>'
    return result
