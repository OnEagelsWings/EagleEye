from __future__ import annotations
import hashlib, html, json
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


class Build251InfluenceResearchFoundationService:
    BUILD = '251.0'
    ENTITY_TYPES = (
        'person','company','ngo','think_tank','foundation','party_affiliated_foundation','party',
        'ministry_or_authority','parliament_or_committee','media_company','editorial_office','university',
        'intelligence_service','program','project','grant','contract','delegation_trip','event','study_or_publication',
        'court_or_investigation_case'
    )
    RELATION_TYPES = (
        'funded','received_grant','awarded_contract','donated','co_financed','covered_in_kind_costs',
        'funded_travel','board_member_of','employed_by','fellow_or_alumni_of','advised','met_with',
        'commissioned_study','organized_event','media_partner_of','cited_or_adopted','supervised',
        'officially_assessed_as_directed','convicted_of_espionage','suspected_of'
    )
    ASSERTION_CLASSES = ('documented_fact','institutional_proximity','allegation','official_assessment','judicial_finding')
    LEGAL_SENSITIVITY = ('normal','elevated','high','very_high')
    PUBLICATION_STATUSES = ('internal_unverified','internal_verified','external_editorial_review','external_legal_review')

    def __init__(self, db: Any, audit: Any, *, kernel: Any, evidence_vault: Any, verified_loop: Any,
                 conversation: Any, actor: str='local-analyst') -> None:
        self.db, self.audit, self.kernel = db, audit, kernel
        self.evidence_vault, self.verified_loop, self.conversation, self.actor = evidence_vault, verified_loop, conversation, actor
        setattr(conversation, '_influence251', self)

    def _case(self, case_id: str) -> None:
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(case_id,)): raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str,Any], actor: str) -> None:
        prev=self.db.one('SELECT event_hash FROM influence_events_251 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,))
        ph=(prev or {}).get('event_hash',''); eid, now=new_id('inf_evt251'), now_ts()
        eh=_hash({'previous':ph,'event_id':eid,'event_type':event_type,'object_id':object_id,'payload':payload,'actor':actor,'at':now})
        self.db.execute('INSERT INTO influence_events_251 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,event_type,object_type,object_id,actor,dumps(payload),ph,eh,now))
        try: self.audit.log('build251_'+event_type,object_type,object_id,case_id,payload)
        except Exception: pass

    def initialize_case(self, *, case_id: str, objective: str, jurisdictions: list[str], research_scope: str,
                        actor: str, confirmation: str) -> dict[str,Any]:
        self._case(case_id)
        if confirmation != f'INFLUENCE CASE 251 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        existing=self.db.one('SELECT * FROM influence_case_profiles_251 WHERE case_id=?',(case_id,))
        if existing: return dict(existing)
        obj=_text(objective); scope=_text(research_scope)
        if len(obj)<15 or len(scope)<15: raise ValueError('objective and research scope must be substantive')
        js=list(dict.fromkeys(_text(x,80) for x in jurisdictions if _text(x,80)))[:30] or ['DE/EU']
        pid, now=new_id('infcase251'), now_ts()
        payload={'profile_id':pid,'case_id':case_id,'objective':obj,'jurisdictions':js,'research_scope':scope,
                 'publication_posture':'internal_unverified','no_agent_scoring':True,'no_autonomous_publication':True,
                 'no_private_mass_collection':True,'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO influence_case_profiles_251 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (pid,case_id,obj,dumps(js),scope,'internal_unverified',1,1,1,actor,now,_hash(payload)))
        self._event(case_id,'influence_case_initialized','case',case_id,{'jurisdictions':js,'non_goals':['agent_probability_scoring','autonomous_publication','private_mass_collection']},actor)
        return payload

    def register_entity(self, *, case_id: str, entity_type: str, display_name: str, jurisdiction: str='', official_domain: str='',
                        identifiers: dict[str,Any]|None=None, former_names: list[str]|None=None, parent_refs: list[str]|None=None,
                        notes: str='', actor: str, confirmation: str) -> dict[str,Any]:
        self._case(case_id)
        if confirmation != f'INFLUENCE ENTITY 251 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        if entity_type not in self.ENTITY_TYPES: raise ValueError('unsupported influence entity type')
        name=_text(display_name,1000)
        if len(name)<2: raise ValueError('display name required')
        ids=dict(identifiers or {})
        allowed_id_keys={'commercial_register','association_register','lei','tax_or_charity_id','fara_registration','official_domain_id','other_public_id'}
        ids={_text(k,80):_text(v,500) for k,v in ids.items() if _text(k,80) in allowed_id_keys and _text(v,500)}
        kernel=self.kernel.create_entity(case_id=case_id,label=name,entity_type='influence_'+entity_type,
                                         attributes={'jurisdiction':_text(jurisdiction,200),'official_domain':_text(official_domain,500),'identifiers':ids},
                                         confidence=.5,actor=actor,confirmation=f'KERNEL OBJECT 235 {case_id} ANLEGEN')
        iid, now=new_id('infent251'), now_ts()
        payload={'influence_entity_id':iid,'case_id':case_id,'kernel_object_id':kernel['object_id'],'entity_type':entity_type,
                 'display_name':name,'jurisdiction':_text(jurisdiction,200),'official_domain':_text(official_domain,500),
                 'identifiers':ids,'former_names':list(former_names or [])[:50],'parent_refs':list(parent_refs or [])[:50],
                 'notes':_text(notes,5000),'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO influence_entities_251 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (iid,case_id,kernel['object_id'],entity_type,name,payload['jurisdiction'],payload['official_domain'],dumps(ids),dumps(payload['former_names']),dumps(payload['parent_refs']),payload['notes'],actor,now,_hash(payload)))
        self._event(case_id,'influence_entity_registered','entity',iid,{'entity_type':entity_type,'kernel_object_id':kernel['object_id']},actor)
        return payload

    def _entity(self, iid: str) -> dict[str,Any]:
        r=self.db.one('SELECT * FROM influence_entities_251 WHERE influence_entity_id=?',(iid,))
        if not r: raise KeyError(iid)
        d=dict(r); d['identifiers']=_loads(d.pop('identifiers_json'),{}); d['former_names']=_loads(d.pop('former_names_json'),[]); d['parent_refs']=_loads(d.pop('parent_refs_json'),[])
        return d

    def propose_relation(self, *, case_id: str, source_id: str, target_id: str, relation_type: str, assertion_class: str,
                         confidence: float, evidence_refs: list[str], temporal_from: str='', temporal_to: str='', notes: str='',
                         actor: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f'INFLUENCE EDGE 251 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        src,dst=self._entity(source_id),self._entity(target_id)
        if src['case_id']!=case_id or dst['case_id']!=case_id: raise ValueError('cross-case edge prohibited')
        if source_id==target_id: raise ValueError('self-edge prohibited')
        if relation_type not in self.RELATION_TYPES: raise ValueError('unsupported relation type')
        if assertion_class not in self.ASSERTION_CLASSES: raise ValueError('unsupported assertion class')
        if relation_type=='suspected_of' and assertion_class!='allegation': raise ValueError('suspected_of must remain allegation')
        if relation_type=='officially_assessed_as_directed' and assertion_class!='official_assessment': raise ValueError('official assessment relation requires official_assessment class')
        if relation_type=='convicted_of_espionage' and assertion_class!='judicial_finding': raise ValueError('conviction relation requires judicial_finding class')
        refs=list(dict.fromkeys(_text(x,300) for x in evidence_refs if _text(x,300)))[:100]
        if assertion_class in {'official_assessment','judicial_finding'} and not refs: raise ValueError('high-impact assertion requires evidence reference')
        eid, now=new_id('infedge251'), now_ts(); conf=max(0.0,min(1.0,float(confidence)))
        payload={'edge_id':eid,'case_id':case_id,'source_influence_entity_id':source_id,'target_influence_entity_id':target_id,
                 'relation_type':relation_type,'assertion_class':assertion_class,'confidence':conf,'evidence_refs':refs,
                 'temporal_from':_text(temporal_from,80),'temporal_to':_text(temporal_to,80),'notes':_text(notes,5000),
                 'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO influence_edges_251 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (eid,case_id,source_id,target_id,relation_type,assertion_class,conf,dumps(refs),payload['temporal_from'],payload['temporal_to'],payload['notes'],actor,now,_hash(payload)))
        self._event(case_id,'influence_edge_proposed','relationship',eid,{'relation_type':relation_type,'assertion_class':assertion_class,'candidate_only':True},actor)
        return {**payload,'review_status':'pending','candidate_only':True}

    def review_relation(self, *, edge_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM influence_edges_251 WHERE edge_id=?',(edge_id,))
        if not row: raise KeyError(edge_id)
        if confirmation != f'INFLUENCE EDGE REVIEW 251 {edge_id} SPEICHERN': raise PermissionError('explicit approval required')
        if reviewer==row['created_by']: raise PermissionError('independent reviewer required')
        if decision not in {'accepted','rejected','needs_more_evidence'}: raise ValueError('invalid decision')
        if len(_text(rationale))<15: raise ValueError('substantive rationale required')
        if self.db.one('SELECT review_id FROM influence_edge_reviews_251 WHERE edge_id=?',(edge_id,)): raise ValueError('already reviewed')
        kernel_link=''
        if decision=='accepted':
            src=self._entity(row['source_influence_entity_id']); dst=self._entity(row['target_influence_entity_id'])
            k=self.kernel.create_link(case_id=row['case_id'],source_object_id=src['kernel_object_id'],relation_type='relationship:'+row['relation_type'],
                                      target_object_id=dst['kernel_object_id'],confidence=float(row['confidence']),evidence_refs=_loads(row['evidence_refs_json'],[]),
                                      actor=reviewer,confirmation=f"KERNEL LINK 235 {row['case_id']} ANLEGEN")
            kernel_link=k['link_id']
        rid, now=new_id('infedgerev251'), now_ts()
        payload={'review_id':rid,'edge_id':edge_id,'case_id':row['case_id'],'decision':decision,'rationale':_text(rationale,5000),'reviewer':reviewer,'reviewed_at':now,'kernel_link_id':kernel_link}
        self.db.execute('INSERT INTO influence_edge_reviews_251 VALUES(?,?,?,?,?,?,?,?,?)',(rid,edge_id,row['case_id'],decision,payload['rationale'],reviewer,now,kernel_link,_hash(payload)))
        self._event(row['case_id'],'influence_edge_reviewed','relationship',edge_id,{'decision':decision,'kernel_candidate_link':kernel_link,'kernel_review_still_required':bool(kernel_link)},reviewer)
        return {**payload,'kernel_review_still_required':bool(kernel_link)}

    def set_claim_control(self, *, case_id: str, kernel_claim_id: str, legal_sensitivity: str, assertion_class: str,
                          primary_evidence_required: bool, hearing_status: str, response_ref: str, publication_status: str,
                          publication_note: str, actor: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f'INFLUENCE CLAIM CONTROL 251 {case_id} SPEICHERN': raise PermissionError('explicit approval required')
        obj=self.kernel.get_object(kernel_claim_id)
        if obj['case_id']!=case_id or obj['object_type']!='claim': raise ValueError('kernel claim required')
        if legal_sensitivity not in self.LEGAL_SENSITIVITY or assertion_class not in self.ASSERTION_CLASSES: raise ValueError('invalid sensitivity/assertion class')
        if publication_status not in self.PUBLICATION_STATUSES: raise ValueError('publication release is reserved for Build 259 human gate')
        if legal_sensitivity in {'high','very_high'} and publication_status.startswith('external_') and not primary_evidence_required:
            raise ValueError('high-sensitivity external claim requires primary evidence')
        cid, now=new_id('infclaim251'), now_ts()
        payload={'control_id':cid,'case_id':case_id,'kernel_claim_id':kernel_claim_id,'legal_sensitivity':legal_sensitivity,
                 'assertion_class':assertion_class,'primary_evidence_required':bool(primary_evidence_required),'hearing_status':_text(hearing_status,120),
                 'response_ref':_text(response_ref,500),'publication_status':publication_status,'publication_note':_text(publication_note,5000),'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO influence_claim_controls_251 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (cid,case_id,kernel_claim_id,legal_sensitivity,assertion_class,1 if primary_evidence_required else 0,payload['hearing_status'],payload['response_ref'],publication_status,payload['publication_note'],actor,now,_hash(payload)))
        self._event(case_id,'claim_control_recorded','claim',kernel_claim_id,{'legal_sensitivity':legal_sensitivity,'assertion_class':assertion_class,'publication_status':publication_status,'autonomous_publication':False},actor)
        return {**payload,'autonomous_publication':False,'final_publication_gate_available':False}

    def case_summary(self, case_id: str) -> dict[str,Any]:
        profile=self.db.one('SELECT * FROM influence_case_profiles_251 WHERE case_id=?',(case_id,))
        entities=self.db.all('SELECT * FROM influence_entities_251 WHERE case_id=? ORDER BY created_at DESC',(case_id,))
        edges=self.db.all('SELECT e.*,r.decision review_decision,r.kernel_link_id FROM influence_edges_251 e LEFT JOIN influence_edge_reviews_251 r ON r.edge_id=e.edge_id WHERE e.case_id=? ORDER BY e.created_at DESC',(case_id,))
        controls=self.db.all('SELECT * FROM influence_claim_controls_251 WHERE case_id=? ORDER BY created_at DESC',(case_id,))
        return {'profile':dict(profile) if profile else None,'entities':entities,'edges':edges,'claim_controls':controls,
                'rules':['Suspicion, official assessment and judicial finding are distinct assertion classes.',
                         'Semantic or network proximity alone never proves coordination or control.',
                         'No agent/loyalty/corruption probability scoring.',
                         'No autonomous publication; final publication release is reserved for a later human legal gate.']}

    def co_ai_context(self, case_id: str) -> dict[str,Any]:
        s=self.case_summary(case_id)
        accepted=[]; candidates=[]
        for e in s['edges']:
            item={'edge_id':e['edge_id'],'relation_type':e['relation_type'],'assertion_class':e['assertion_class'],'confidence':e['confidence']}
            (accepted if e.get('review_decision')=='accepted' else candidates).append(item)
        return {'influence_funding_context_251':{'accepted_relationships':accepted[:100],'candidate_relationships_not_facts':candidates[:100],'rules':s['rules']}}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e=html.escape; s=self.case_summary(case_id); profile=s['profile']; ents=s['entities']; edges=s['edges']; controls=s['claim_controls']
        profile_state='initialized' if profile else 'not initialized'
        entity_opts=''.join(f"<option value='{e(x['influence_entity_id'])}'>{e(x['display_name'])} · {e(x['entity_type'])}</option>" for x in ents)
        entity_rows=''.join(f"<tr><td>{e(x['display_name'])}</td><td>{e(x['entity_type'])}</td><td>{e(x['jurisdiction'])}</td><td><code>{e(x['influence_entity_id'])}</code></td></tr>" for x in ents[:50]) or '<tr><td colspan=4>Keine spezialisierten Entitäten.</td></tr>'
        edge_rows=''.join(f"<tr><td>{e(x['relation_type'])}</td><td>{e(x['assertion_class'])}</td><td>{e(x.get('review_decision') or 'pending')}</td><td>{float(x['confidence']):.2f}</td></tr>" for x in edges[:50]) or '<tr><td colspan=4>Keine Beziehungen.</td></tr>'
        return f"""<section class='card' id='build251'><h2>Influence &amp; Funding Investigation Pack · Build 251</h2><p>Phase-10-Grundlage: spezialisiertes Entitäts-/Beziehungsmodell mit strikter Trennung von Fakt, Nähe, Verdacht, behördlicher Bewertung und gerichtlicher Feststellung.</p><div class='metrics'><div class='metric'><div class='label'>Profile</div><div class='value'>{e(profile_state)}</div></div><div class='metric'><div class='label'>Entities</div><div class='value'>{len(ents)}</div></div><div class='metric'><div class='label'>Edges</div><div class='value'>{len(edges)}</div></div><div class='metric'><div class='label'>Claim controls</div><div class='value'>{len(controls)}</div></div></div>
<div class='grid'><div class='card'><h3>Influence-Fall initialisieren</h3><form method='post' action='/build251/init'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='objective' placeholder='Untersuchungsziel' required><input name='jurisdictions' value='DE,EU' placeholder='DE,EU,US'><textarea name='research_scope' placeholder='Sachlich/rechtlich eingegrenzter Rechercheumfang' required></textarea><button>Falltemplate aktivieren</button></form></div>
<div class='card'><h3>Spezialisierte Entität</h3><form method='post' action='/build251/entity'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='entity_type'>{''.join(f'<option>{e(t)}</option>' for t in self.ENTITY_TYPES)}</select><input name='display_name' placeholder='Name' required><input name='jurisdiction' placeholder='Sitz/Rechtsordnung'><input name='official_domain' placeholder='Offizielle Domain'><input name='lei' placeholder='LEI / öffentlicher Identifier'><textarea name='notes' placeholder='Notiz'></textarea><button>Entität anlegen</button></form></div>
<div class='card'><h3>Beziehung als Kandidat</h3><form method='post' action='/build251/edge'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='source_id'>{entity_opts}</select><select name='relation_type'>{''.join(f'<option>{e(t)}</option>' for t in self.RELATION_TYPES)}</select><select name='target_id'>{entity_opts}</select><select name='assertion_class'>{''.join(f'<option>{e(t)}</option>' for t in self.ASSERTION_CLASSES)}</select><input name='confidence' value='0.50'><input name='evidence_refs' placeholder='Evidence-Refs, komma-getrennt'><textarea name='notes' placeholder='Begründung/Abgrenzung'></textarea><button>Kandidat anlegen</button></form><p class='muted'>Verdacht, behördliche Bewertung und gerichtliche Feststellung sind technisch getrennt. Kein automatischer Merge oder Faktstatus.</p></div>
<div class='card'><h3>Vier-Augen-Review Beziehung</h3><form method='post' action='/build251/edge-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='edge_id' placeholder='Edge-ID' required><select name='decision'><option>accepted</option><option>needs_more_evidence</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Review-Begründung' required></textarea><button>Prüfen</button></form></div>
<div class='card'><h3>Claim-/Publikationskontrolle</h3><form method='post' action='/build251/claim-control'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='kernel_claim_id' placeholder='Canonical Claim-ID' required><select name='legal_sensitivity'>{''.join(f'<option>{e(t)}</option>' for t in self.LEGAL_SENSITIVITY)}</select><select name='assertion_class'>{''.join(f'<option>{e(t)}</option>' for t in self.ASSERTION_CLASSES)}</select><label><input type='checkbox' name='primary_evidence_required' value='1' checked> Primärbeleg erforderlich</label><select name='hearing_status'><option>not_requested</option><option>requested</option><option>response_received</option><option>declined</option><option>not_applicable</option></select><input name='response_ref' placeholder='Anhörungs-/Antwort-Referenz'><select name='publication_status'>{''.join(f'<option>{e(t)}</option>' for t in self.PUBLICATION_STATUSES)}</select><textarea name='publication_note' placeholder='Publikations-/Rechtsnotiz'></textarea><button>Kontrolle speichern</button></form><p class='muted'>„Zur Veröffentlichung freigegeben“ existiert in Build 251 bewusst nicht; der finale Human-/Legal-Gate folgt erst in Build 259.</p></div></div>
<div class='card'><h3>Entitäten</h3><table><tr><th>Name</th><th>Typ</th><th>Jurisdiktion</th><th>ID</th></tr>{entity_rows}</table></div><div class='card'><h3>Beziehungen</h3><table><tr><th>Relation</th><th>Aussageklasse</th><th>Review</th><th>Confidence</th></tr>{edge_rows}</table></div>
<div class='card'><h3>Analytische Grenzen</h3><ul>{''.join(f'<li>{e(r)}</li>' for r in s['rules'])}</ul></div></section>"""
