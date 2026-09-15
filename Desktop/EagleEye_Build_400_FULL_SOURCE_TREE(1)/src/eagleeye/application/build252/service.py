from __future__ import annotations
import hashlib, html, json
from decimal import Decimal, InvalidOperation
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _text(v: Any, n: int = 10000) -> str:
    return str(v or '').replace('\x00','').strip()[:n]

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()

def _loads(v: Any, default: Any):
    try: return json.loads(v) if v else default
    except Exception: return default

def _money(v: Any) -> str:
    s=_text(v,80).replace(' ','').replace(',','.')
    if not s: return ''
    try:
        d=Decimal(s)
    except InvalidOperation as exc:
        raise ValueError('invalid amount') from exc
    if d < 0: raise ValueError('amount must be non-negative')
    return format(d.normalize(), 'f')


class Build252FinancialFlowAccountingService:
    BUILD='252.0'
    INSTRUMENTS=('grant','contract_payment','donation','membership_fee','sponsorship','travel_support','in_kind_support','subgrant','loan','equity_investment','other_publicly_documented_transfer')
    ASSERTION_CLASSES=('documented_transaction','reported_transaction','derived_funding_chain')
    SOURCE_QUALITY=('primary_audited','primary_official','primary_filing','secondary_reputable','secondary_unverified')
    REVIEW_DECISIONS=('accepted','needs_more_evidence','rejected')
    DERIVATION_CLASSES=('same_program_pass_through','earmarked_subgrant','temporal_sequence_only','shared_funder_only','other_documented_derivation')

    def __init__(self, db: Any, audit: Any, *, influence: Any, kernel: Any, evidence_vault: Any, verified_loop: Any,
                 training: Any, opsec: Any, conversation: Any, actor: str='local-analyst') -> None:
        self.db,self.audit,self.influence,self.kernel=db,audit,influence,kernel
        self.evidence_vault,self.verified_loop,self.training,self.opsec=evidence_vault,verified_loop,training,opsec
        self.conversation,self.actor=conversation,actor
        setattr(conversation,'_financial252',self)

    def _case(self, case_id: str) -> None:
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(case_id,)): raise KeyError(case_id)

    def _entity(self, iid: str) -> dict[str,Any]:
        return self.influence._entity(iid)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str,Any], actor: str) -> None:
        prev=self.db.one('SELECT event_hash FROM financial_events_252 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,))
        ph=(prev or {}).get('event_hash',''); eid,now=new_id('fin_evt252'),now_ts()
        eh=_hash({'previous':ph,'event_id':eid,'event_type':event_type,'object_id':object_id,'payload':payload,'actor':actor,'at':now})
        self.db.execute('INSERT INTO financial_events_252 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,event_type,object_type,object_id,actor,dumps(payload),ph,eh,now))
        try: self.audit.log('build252_'+event_type,object_type,object_id,case_id,payload)
        except Exception: pass

    def record_flow(self, *, case_id: str, payer_id: str, payee_id: str, instrument: str, assertion_class: str,
                    amount_min: Any='', amount_max: Any='', currency: str='', amount_basis: str='exact',
                    transaction_date: str='', period_from: str='', period_to: str='', purpose: str='', program_or_contract_ref: str='',
                    evidence_refs: list[str], source_quality: str, notes: str='', actor: str, confirmation: str) -> dict[str,Any]:
        self._case(case_id)
        if confirmation != f'FINANCIAL FLOW 252 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        payer,payee=self._entity(payer_id),self._entity(payee_id)
        if payer['case_id']!=case_id or payee['case_id']!=case_id: raise ValueError('cross-case flow prohibited')
        if payer_id==payee_id: raise ValueError('self-flow prohibited')
        if instrument not in self.INSTRUMENTS: raise ValueError('unsupported instrument')
        if assertion_class not in self.ASSERTION_CLASSES: raise ValueError('unsupported financial assertion class')
        if source_quality not in self.SOURCE_QUALITY: raise ValueError('unsupported source quality')
        refs=list(dict.fromkeys(_text(x,300) for x in evidence_refs if _text(x,300)))[:100]
        amin,amax=_money(amount_min),_money(amount_max)
        if amin and amax and Decimal(amin)>Decimal(amax): raise ValueError('amount_min exceeds amount_max')
        if assertion_class=='documented_transaction' and not refs: raise ValueError('documented transaction requires evidence')
        if assertion_class=='documented_transaction' and source_quality in {'secondary_unverified'}: raise ValueError('documented transaction cannot rely on unverified secondary source')
        if assertion_class=='derived_funding_chain': raise ValueError('derived funding chains must be created with propose_chain_link')
        if not (transaction_date or period_from or period_to): raise ValueError('transaction date or period required')
        fid,now=new_id('finflow252'),now_ts()
        payload={'flow_id':fid,'case_id':case_id,'payer_influence_entity_id':payer_id,'payee_influence_entity_id':payee_id,
                 'instrument':instrument,'assertion_class':assertion_class,'amount_min':amin,'amount_max':amax,'currency':_text(currency,12).upper(),
                 'amount_basis':_text(amount_basis,80),'transaction_date':_text(transaction_date,40),'period_from':_text(period_from,40),'period_to':_text(period_to,40),
                 'purpose':_text(purpose,3000),'program_or_contract_ref':_text(program_or_contract_ref,1000),'evidence_refs':refs,
                 'source_quality':source_quality,'notes':_text(notes,5000),'created_by':actor,'created_at':now,'candidate_only':True}
        self.db.execute('INSERT INTO financial_flows_252 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (fid,case_id,payer_id,payee_id,instrument,assertion_class,amin,amax,payload['currency'],payload['amount_basis'],payload['transaction_date'],payload['period_from'],payload['period_to'],payload['purpose'],payload['program_or_contract_ref'],dumps(refs),source_quality,payload['notes'],actor,now,_hash(payload)))
        self._event(case_id,'flow_recorded','financial_flow',fid,{'assertion_class':assertion_class,'instrument':instrument,'evidence_count':len(refs),'candidate_only':True},actor)
        return payload

    def review_flow(self, *, flow_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM financial_flows_252 WHERE flow_id=?',(flow_id,))
        if not row: raise KeyError(flow_id)
        d=dict(row); case_id=d['case_id']
        if confirmation != f'FINANCIAL FLOW REVIEW 252 {flow_id} SPEICHERN': raise PermissionError('explicit approval required')
        if decision not in self.REVIEW_DECISIONS: raise ValueError('unsupported review decision')
        if reviewer==d['created_by']: raise PermissionError('four-eyes review requires another reviewer')
        if len(_text(rationale,5000))<20: raise ValueError('substantive review rationale required')
        existing=self.db.one('SELECT * FROM financial_flow_reviews_252 WHERE flow_id=?',(flow_id,))
        if existing: return dict(existing)
        relation_edge_id=''
        if decision=='accepted':
            relation='funded' if d['instrument'] in {'grant','donation','sponsorship','subgrant','travel_support','in_kind_support'} else 'awarded_contract' if d['instrument']=='contract_payment' else 'co_financed'
            edge=self.influence.propose_relation(case_id=case_id,source_id=d['payer_influence_entity_id'],target_id=d['payee_influence_entity_id'],relation_type=relation,assertion_class='documented_fact' if d['assertion_class']=='documented_transaction' else 'allegation',confidence=.75 if d['assertion_class']=='documented_transaction' else .45,evidence_refs=_loads(d['evidence_refs_json'],[]),temporal_from=d['period_from'] or d['transaction_date'],temporal_to=d['period_to'],notes=f'Generated from reviewed Build 252 flow {flow_id}; canonical relation remains separately review-gated.',actor=reviewer,confirmation=f'INFLUENCE EDGE 251 {case_id} ANLEGEN')
            relation_edge_id=edge['edge_id']
        rid,now=new_id('finrev252'),now_ts(); payload={'review_id':rid,'flow_id':flow_id,'case_id':case_id,'decision':decision,'rationale':_text(rationale,5000),'reviewer':reviewer,'reviewed_at':now,'relation_edge_id':relation_edge_id,'kernel_review_still_required':True}
        self.db.execute('INSERT INTO financial_flow_reviews_252 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,flow_id,case_id,decision,payload['rationale'],reviewer,now,relation_edge_id,1,_hash(payload)))
        self._event(case_id,'flow_reviewed','financial_flow',flow_id,{'decision':decision,'relation_edge_id':relation_edge_id,'kernel_review_still_required':True},reviewer)
        return payload

    def propose_chain_link(self, *, case_id: str, upstream_flow_id: str, downstream_flow_id: str, derivation_class: str,
                           evidence_refs: list[str], rationale: str, actor: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f'FINANCIAL CHAIN 252 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        up=self.db.one('SELECT * FROM financial_flows_252 WHERE flow_id=?',(upstream_flow_id,)); down=self.db.one('SELECT * FROM financial_flows_252 WHERE flow_id=?',(downstream_flow_id,))
        if not up or not down: raise KeyError('flow missing')
        if up['case_id']!=case_id or down['case_id']!=case_id: raise ValueError('cross-case chain prohibited')
        if upstream_flow_id==downstream_flow_id: raise ValueError('self-chain prohibited')
        if derivation_class not in self.DERIVATION_CLASSES: raise ValueError('unsupported derivation class')
        refs=list(dict.fromkeys(_text(x,300) for x in evidence_refs if _text(x,300)))[:100]
        if derivation_class in {'same_program_pass_through','earmarked_subgrant'} and not refs: raise ValueError('documented derivation requires evidence')
        lid,now=new_id('finchain252'),now_ts(); status='hypothesis_candidate'
        payload={'chain_link_id':lid,'case_id':case_id,'upstream_flow_id':upstream_flow_id,'downstream_flow_id':downstream_flow_id,'derivation_class':derivation_class,'evidence_refs':refs,'rationale':_text(rationale,5000),'status':status,'created_by':actor,'created_at':now,'not_a_proven_transaction':True}
        self.db.execute('INSERT INTO financial_flow_links_252 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(lid,case_id,upstream_flow_id,downstream_flow_id,derivation_class,dumps(refs),payload['rationale'],status,actor,now,_hash(payload)))
        self._event(case_id,'chain_candidate_created','financial_chain',lid,{'derivation_class':derivation_class,'not_a_proven_transaction':True},actor)
        return payload

    def training_continuity(self, *, case_id: str) -> dict[str,Any]:
        flows=self.db.all('SELECT assertion_class,source_quality FROM financial_flows_252 WHERE case_id=?',(case_id,))
        reviews=self.db.all('SELECT decision FROM financial_flow_reviews_252 WHERE case_id=?',(case_id,))
        counts={k:0 for k in self.ASSERTION_CLASSES}
        for r in flows: counts[r['assertion_class']]=counts.get(r['assertion_class'],0)+1
        accepted=sum(1 for r in reviews if r['decision']=='accepted')
        return {'build':'252.0','reviewed_examples':len(reviews),'accepted_examples':accepted,'assertion_class_coverage':counts,
                'qualification_gate':'reviewed_only','auto_model_activation':False,'opsec_changes_autonomous':False}

    def status(self, *, case_id: str) -> dict[str,Any]:
        flows=self.db.all('SELECT * FROM financial_flows_252 WHERE case_id=? ORDER BY created_at DESC',(case_id,))
        reviews=self.db.all('SELECT * FROM financial_flow_reviews_252 WHERE case_id=?',(case_id,))
        chains=self.db.all('SELECT * FROM financial_flow_links_252 WHERE case_id=? ORDER BY created_at DESC',(case_id,))
        return {'build':'252.0','flows':flows,'reviews':reviews,'chains':chains,'rules':['A payment record is not evidence of influence by itself.','Documented, reported and derived flows remain separate assertion classes.','Derived chains remain hypotheses until independently evidenced and reviewed.','No autonomous publication, source contact, model activation or OPSEC/system change.']}

    def render_workspace_panel(self, *, case_id: str, csrf: str='') -> str:
        e=lambda x: html.escape(str(x or '')); s=self.status(case_id=case_id)
        ents=self.db.all('SELECT influence_entity_id,display_name FROM influence_entities_251 WHERE case_id=? ORDER BY display_name',(case_id,))
        opts=''.join(f"<option value='{e(x['influence_entity_id'])}'>{e(x['display_name'])}</option>" for x in ents)
        rows=''.join(f"<tr><td>{e(x['instrument'])}</td><td>{e(x['assertion_class'])}</td><td>{e(x['amount_min'])}{'–'+e(x['amount_max']) if x['amount_max'] else ''} {e(x['currency'])}</td><td>{e(x['transaction_date'] or x['period_from'])}</td><td>{e(x['flow_id'])}</td></tr>" for x in s['flows'][:50]) or '<tr><td colspan="5">Noch keine Geldflüsse erfasst.</td></tr>'
        return f"""<section class='cockpit244'><h2>Influence &amp; Funding Investigation Pack · Financial Flow Accounting 252</h2><p class='muted'>Dokumentierte Geldflüsse werden quellennah erfasst. Eine Zahlung beweist für sich allein weder Steuerung noch Einfluss.</p><div class='grid'><div class='card'><h3>Geldfluss erfassen</h3><form method='post' action='/build252/flow'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='payer_id'>{opts}</select><select name='payee_id'>{opts}</select><select name='instrument'>{''.join(f'<option>{e(x)}</option>' for x in self.INSTRUMENTS)}</select><select name='assertion_class'><option>documented_transaction</option><option>reported_transaction</option></select><input name='amount_min' placeholder='Betrag / Minimum'><input name='amount_max' placeholder='Maximum bei Spanne'><input name='currency' value='EUR' placeholder='Währung'><input name='transaction_date' placeholder='YYYY-MM-DD'><input name='period_from' placeholder='Periode von'><input name='period_to' placeholder='Periode bis'><input name='purpose' placeholder='Zweck'><input name='program_or_contract_ref' placeholder='Programm/Vertrag'><input name='evidence_refs' placeholder='Evidence-Refs, komma-getrennt'><select name='source_quality'>{''.join(f'<option>{e(x)}</option>' for x in self.SOURCE_QUALITY)}</select><textarea name='notes' placeholder='Notiz'></textarea><button>Flow als Kandidat erfassen</button></form></div><div class='card'><h3>Vier-Augen-Review</h3><form method='post' action='/build252/flow-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='flow_id' placeholder='Flow-ID' required><select name='decision'>{''.join(f'<option>{e(x)}</option>' for x in self.REVIEW_DECISIONS)}</select><textarea name='rationale' placeholder='Review-Begründung' required></textarea><button>Flow prüfen</button></form></div><div class='card'><h3>Finanzierungskette als Hypothese</h3><form method='post' action='/build252/chain'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='upstream_flow_id' placeholder='Upstream Flow-ID' required><input name='downstream_flow_id' placeholder='Downstream Flow-ID' required><select name='derivation_class'>{''.join(f'<option>{e(x)}</option>' for x in self.DERIVATION_CLASSES)}</select><input name='evidence_refs' placeholder='Evidence-Refs'><textarea name='rationale' placeholder='Warum diese Kette geprüft werden soll' required></textarea><button>Hypothese anlegen</button></form><p class='muted'>Diese Funktion erzeugt ausdrücklich keinen bewiesenen Transaktionspfad.</p></div></div><div class='card'><h3>Financial Ledger</h3><table><tr><th>Instrument</th><th>Aussageklasse</th><th>Betrag</th><th>Zeit</th><th>ID</th></tr>{rows}</table></div><div class='card'><h3>Analytische Grenzen</h3><ul>{''.join(f'<li>{e(x)}</li>' for x in s['rules'])}</ul></div></section>"""
