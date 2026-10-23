"""Deterministic policy fixtures. No LLM inference or semantic quality claim."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
import platform
from pathlib import Path
import time
from .assistant471 import Summary, validate_quote_bindings
from .question472 import Answer472
from .hypotheses473 import Analysis473
from .review474 import validate_assessments


def fixtures():
    citation={'anchor_id':'synthetic-anchor','quote':'company was founded in 2001.'}
    statement={'text':'Die Quelle nennt 2001.','citations':[citation]}
    summary={'statements':[statement],'uncertainties':['Unabhängige Bestätigung fehlt.']}
    answer={**deepcopy(summary),'answer_status':'source_bound'}
    abstention={'answer_status':'insufficient_evidence','statements':[],'uncertainties':[],
                'gap_reasons':['not_in_selected_excerpts']}
    hypothesis={'title':'Historische Gründung','explanation':'Die historische Gründung könnte 2001 erfolgt sein.',
        'supporting':[citation],'contradicting':[],
        'missing_evidence':'Die originale Gründungsurkunde fehlt.',
        'verification_question':'Was nennt die originale Gründungsurkunde?'}
    alternative=deepcopy(hypothesis);alternative['title']='Spätere Registrierung'
    analysis={**deepcopy(answer),'alternatives':[hypothesis,alternative]}
    cases=[]
    def add(name,schema,payload,accepted):
        cases.append({'name':name,'schema':schema,'payload':deepcopy(payload),'accepted':accepted})
    add('summary_control','summary',summary,True)
    add('answer_control','answer',answer,True)
    add('abstention_control','answer',abstention,True)
    add('alternatives_control','analysis',analysis,True)
    bad=deepcopy(summary);bad['unknown_field']='invented';add('unknown_field','summary',bad,False)
    bad=deepcopy(summary);bad['statements'][0]['citations']=[];add('uncited_statement','summary',bad,False)
    bad=deepcopy(summary);bad['statements'][0]['citations'][0]['anchor_id']='foreign';add('foreign_anchor','summary',bad,False)
    bad=deepcopy(summary);bad['statements'][0]['citations'][0]['quote']='An invented quote outside the source.';add('invented_quote','summary',bad,False)
    bad=deepcopy(summary);bad['uncertainties']=[];add('missing_uncertainty','summary',bad,False)
    bad=deepcopy(summary);bad['statements'][0]['text']=True;add('wrong_type','summary',bad,False)
    bad=deepcopy(summary);bad['statements']*=13;add('statement_budget','summary',bad,False)
    bad=deepcopy(answer);bad['answer_status']='confirmed_fact';add('fact_status','answer',bad,False)
    bad=deepcopy(answer);bad['gap_reasons']=['not_in_selected_excerpts'];add('answer_with_gap','answer',bad,False)
    bad=deepcopy(abstention);bad['statements']=summary['statements'];add('abstention_with_prose','answer',bad,False)
    bad=deepcopy(abstention);bad['uncertainties']=['Unsupported factual prose'];add('abstention_uncertainty_prose','answer',bad,False)
    bad=deepcopy(abstention);bad['gap_reasons']=['arbitrary'];add('unknown_gap','answer',bad,False)
    bad=deepcopy(analysis);bad['alternatives']=bad['alternatives'][:1];add('single_hypothesis','analysis',bad,False)
    bad=deepcopy(analysis);bad['alternatives'][1]['title']=bad['alternatives'][0]['title'];add('duplicate_hypothesis','analysis',bad,False)
    bad=deepcopy(analysis);bad['alternatives'][0]['supporting']=[];add('uncited_hypothesis','analysis',bad,False)
    bad=deepcopy(analysis);bad['alternatives'][0]['contradicting']=[citation];add('duplicate_quote_roles','analysis',bad,False)
    bad=deepcopy(analysis);bad['alternatives'][0]['contradicting']=[{**citation,'anchor_id':'second-anchor'}];add('duplicate_quote_distinct_anchor','analysis',bad,False)
    bad=deepcopy(analysis);bad['alternatives'][0]['verification_question']='';add('missing_verification','analysis',bad,False)
    bad=deepcopy(abstention);bad['alternatives']=analysis['alternatives'];add('abstention_hypotheses','analysis',bad,False)
    # Positive limitation control: literal binding is deliberately not semantic entailment.
    bad=deepcopy(summary);bad['statements'][0]['text']='Das Unternehmen wurde 2099 gegründet.'
    add('semantic_entailment_not_enforced','summary',bad,True)
    return cases


def policy_benchmark():
    cases=fixtures()
    sources=[{'anchor_id':'synthetic-anchor','text':'The synthetic company was founded in 2001.'},
             {'anchor_id':'second-anchor','text':'The synthetic company was founded in 2001.'}]
    schemas={'summary':Summary,'answer':Answer472,'analysis':Analysis473}
    outcomes=[];durations=[]
    for case in cases:
        start=time.perf_counter_ns()
        try:
            result=schemas[case['schema']].model_validate(case['payload'])
            validate_quote_bindings(result,sources)
            accepted=True
        except ValueError:
            accepted=False
        durations.append((time.perf_counter_ns()-start)/1e6)
        outcomes.append({'name':case['name'],'expected_accept':case['accepted'],
                         'actual_accept':accepted,'pass':accepted==case['accepted']})
    fixture_bytes=json.dumps({'cases':cases,'sources':sources},sort_keys=True,ensure_ascii=False).encode()
    return {'name':'build475_deterministic_policy_checks','build':'475.0',
        'fixture_sha256':hashlib.sha256(fixture_bytes).hexdigest(),
        'runtime':{'python':platform.python_version(),'platform':platform.platform()},
        'case_count':len(outcomes),'passed':sum(x['pass'] for x in outcomes),'outcomes':outcomes,
        'validation_latency_ms':{'mean':sum(durations)/len(durations),'max':max(durations)},
        'llm_evaluated':False,'semantic_entailment_enforced':False,'production_release_ready':False,
        'limitations':['No model inference; these counts measure schema and literal quote rules only.',
                       'A true quotation can accompany an unsupported claim; human assessment remains required.',
                       'Model hallucination rate, prompt-injection resistance and i5 inference latency: N/A.']}


def review_inventory(service,identity,case_id):
    """Read every record under the canonical case boundary, including integrity checks."""
    # Authorization emits audit records, so reserve the writer before any read.
    # The shared connection lock and SQLite reservation keep count/pages/reviews stable.
    with service.db.transaction(immediate=True):
        service.authorize(identity,case_id)
        counts={'total':0,'review_required':0,'acknowledged':0,'rejected':0,'complete_item_reviews':0,
                'acknowledged_without_item_reviews':0}
        # Count in SQL so history pagination never silently truncates the inventory.
        total=service.db.one('SELECT COUNT(*) AS n FROM phase20_ai_summary_471 WHERE case_id=?',(case_id,))['n']
        if total>100000:
            raise ValueError('Prüfbestand überschreitet die unterstützte Grenze; Archivierung erforderlich.')
        for offset in range(0,total,20):
            for run in service.history(identity,case_id,offset=offset):
                counts['total']+=1
                if run['status'] not in {'review_required','acknowledged','rejected'}:
                    raise ValueError('Unbekannter Prüfstatus.')
                counts[run['status']]+=1
                if run['status']=='acknowledged':
                    try:
                        validate_assessments(run,(run.get('review') or {}).get('assessments'))
                        counts['complete_item_reviews']+=1
                    except ValueError:
                        counts['acknowledged_without_item_reviews']+=1
        if counts["total"]!=total:
            raise ValueError("Prüfbestand ist unvollständig.")
        return counts



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='checkpoint475-policy.json')
    args=parser.parse_args();report=policy_benchmark()
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'report':args.output,'passed':report['passed'],'case_count':report['case_count'],
                      'llm_evaluated':False,'production_release_ready':False}))
    return 0 if report['passed']==report['case_count'] else 1

if __name__=='__main__':
    raise SystemExit(main())
