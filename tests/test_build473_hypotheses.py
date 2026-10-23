from copy import deepcopy
from unittest.mock import patch
import pytest
from eagleeye.application.hypotheses473 import Analysis473
from test_build471_local_ai import workspace, provider


def analysis(service,user,case_id,doc_id):
    other=service.documents.import_bytes(identity=user,case_id=case_id,filename='register.txt',
        raw=b'The registry entry started in 2002.',title='Registry Source',source_url='https://example.org/registry')
    sources=service.sources(user,case_id,[doc_id,other['document_id']])
    a=next(s for s in sources if s['document_id']==doc_id)
    b=next(s for s in sources if s['document_id']==other['document_id'])
    ca={'anchor_id':a['anchor_id'],'quote':'company was founded in 2001.'}
    cb={'anchor_id':b['anchor_id'],'quote':'registry entry started in 2002.'}
    return {'answer_status':'source_bound','statements':[{'text':'Die Quellen nennen unterschiedliche Bezugsdaten.','citations':[ca,cb]}],
        'uncertainties':['Gründung und Registrierung sind nicht unabhängig abgeglichen.'],
        'alternatives':[
            {'title':'Betriebsgründung im Jahr 2001','explanation':'Der frühere Zeitpunkt könnte den Betriebsbeginn beschreiben.',
             'supporting':[ca],'contradicting':[cb], 'missing_evidence':'Ein unabhängiger Gründungsnachweis fehlt.',
             'verification_question':'Welches Ereignis bezeichnet die Originalquelle als Gründung?'},
            {'title':'Registrierung im Jahr 2002','explanation':'Der spätere Zeitpunkt könnte die Registrierung beschreiben.',
             'supporting':[cb],'contradicting':[ca], 'missing_evidence':'Ein vollständiger Registerauszug fehlt noch.',
             'verification_question':'Unterscheidet der Registerauszug Beginn und Eintragung?'}]},other['document_id']


def test_counter_hypotheses_persist_with_both_evidence_roles(workspace):
    app,client,user,case_id,doc_id,*_=workspace
    service=app.state.assistant471
    answer,other=analysis(service,user,case_id,doc_id)
    calls=[]
    with patch.object(service,'request',side_effect=provider(answer,calls)):
        run=service.generate(user,case_id,[doc_id,other],'mistral:latest',question='Wie lässt sich das Gründungsdatum erklären?',analysis_mode='alternatives')
    assert run['task']=='alternatives' and len(run['summary']['alternatives'])==2
    assert not run['truth_determined'] and run['claims_created']==0
    page=client.get('/assistant471',params={'case_id':case_id})
    assert 'Stützende Fundstellen' in page.text and 'Widersprechende Fundstellen' in page.text
    assert 'Ungeprüfte Hypothese' in page.text and 'Registry Source' in page.text
    assert service.history(user,case_id)[0]['summary']==Analysis473.model_validate(answer).model_dump()


@pytest.mark.parametrize('invalid',['uncited','duplicate','same_quote_both_roles','foreign_anchor','false_quote','abstention_prose'])
def test_invalid_alternatives_are_rejected(workspace,invalid):
    app,_,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    answer,other=analysis(service,user,case_id,doc_id)
    if invalid=='uncited':answer['alternatives'][0].update(supporting=[],contradicting=[])
    if invalid=='duplicate':answer['alternatives'][1]['title']=answer['alternatives'][0]['title']
    if invalid=='same_quote_both_roles':answer['alternatives'][0]['contradicting']=deepcopy(answer['alternatives'][0]['supporting'])
    if invalid=='foreign_anchor':answer['alternatives'][0]['supporting'][0]['anchor_id']='foreign-case-anchor'
    if invalid=='false_quote':answer['alternatives'][0]['supporting'][0]['quote']='This quotation is not in the source.'
    if invalid=='abstention_prose':answer.update(answer_status='insufficient_evidence',statements=[],uncertainties=[],gap_reasons=['not_in_selected_excerpts'])
    with patch.object(service,'request',side_effect=provider(answer,[])):
        with pytest.raises(ValueError):
            service.generate(user,case_id,[doc_id,other],'mistral:latest',question='Welche Erklärung trägt die Auswahl?',analysis_mode='alternatives')
    assert service.history(user,case_id)==[]


def test_alternatives_require_question_before_network(workspace):
    app,_,user,case_id,doc_id,*_=workspace;service=app.state.assistant471
    with patch.object(service,'request') as call:
        with pytest.raises(ValueError):service.generate(user,case_id,[doc_id],'mistral:latest',analysis_mode='alternatives')
    call.assert_not_called()
