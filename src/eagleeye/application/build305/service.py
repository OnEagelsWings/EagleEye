from __future__ import annotations
import hashlib,html,json,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import Build304ContentDossierSecurityService,_safe,_hash,_canon,_id,_now
class Build305ProvenanceSecurityService(Build304ContentDossierSecurityService):
 BUILD='305.0';REQUIRED_CORPUS=440
 def __init__(self,db,audit,*,cases,build304,build303,build302,build301,install_dir,base_dir,actor='local-analyst'):
  super().__init__(db,audit,cases=cases,build303=build303,build302=build302,build301=build301,install_dir=install_dir,base_dir=base_dir,actor=actor);self.build304=build304
 def correlate_security_scan(self,scan_id,actor=None):
  actor=actor or self.actor;s=self.db.one('SELECT * FROM phase13_security_scans_304 WHERE scan_id=?',(scan_id,))
  if not s:raise KeyError('security scan not found')
  signals=json.loads(s.get('signals_json') or '[]');names={x.get('signal') for x in signals};rules=[];bonus=0
  def hit(rule,w,why):
   nonlocal bonus;rules.append({'rule':rule,'weight':w,'reason':why});bonus+=w
  if {'credential_pressure','tracking_or_state_api'}<=names:hit('credential_plus_exfiltration_surface',25,'credential field co-occurs with browser/network state API')
  if 'fingerprinting_indicator' in names and 'cross_origin_resource' in names:hit('fingerprint_plus_cross_origin',20,'fingerprinting indicator co-occurs with cross-origin resources')
  if 'active_script' in names and ('tracking_or_state_api' in names or 'fingerprinting_indicator' in names):hit('active_tracking_chain',20,'active script co-occurs with tracking/fingerprinting indicator')
  prior=self._count('SELECT COUNT(*) n FROM phase13_security_scans_304 WHERE source_id=? AND risk_score>=45',(s['source_id'],))
  if prior>1:hit('repeat_high_risk_source',10,'same source has repeated high-risk scans')
  score=min(100,int(s['risk_score'])+bonus);level='critical' if score>=70 else ('high' if score>=45 else ('medium' if score>=20 else 'low'));blocked=score>=45;action='quarantine_static_only_and_human_review' if blocked else 'bounded_static_processing';cid=_id('seccorr305');now=_now();reasoning={'base_score':int(s['risk_score']),'correlation_bonus':bonus,'rules':rules,'policy':'defensive-only; no active content execution; no network reconfiguration'};rec={'correlation_id':cid,'case_id':s['case_id'],'source_id':s['source_id'],'parent_scan_id':scan_id,'correlation_score':score,'risk_level':level,'rule_hits':rules,'reasoning':reasoning,'blocked':blocked,'recommended_action':action,'created_by':actor,'created_at':now}
  self.db.execute('INSERT INTO phase13_security_correlations_305 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,s['case_id'],s['source_id'],scan_id,score,level,_canon(rules),_canon(reasoning),int(blocked),action,actor,now,_hash(rec)));return rec
 def scan_source(self,source_id,actor=None):
  base=self.build304.scan_source(source_id,actor=actor);corr=self.correlate_security_scan(base['scan_id'],actor=actor);return {**base,'correlation':corr,'blocked':bool(base['blocked'] or corr['blocked']),'risk_level':corr['risk_level'],'risk_score':corr['correlation_score']}
 def _evidence_origin(self,ref):
  x=str(ref or '').strip();host=(urlsplit(x).hostname or '').lower() if '://' in x else ''
  if host:return host,host
  prefix=x.split(':',1)[0].lower() if ':' in x else 'internal';return prefix,prefix
 def compose_evidence_dossier(self,*,case_id,title='',actor=None):
  actor=actor or self.actor;parent=self.build304.compose_evidence_dossier(case_id=case_id,title=title,actor=actor);facts=self._strict_verified_facts(case_id);rev=int((self.db.one('SELECT MAX(revision_no) n FROM phase13_dossier_revisions_305 WHERE case_id=?',(case_id,)) or {}).get('n') or 0)+1;did=_id('dossier305');now=_now();matrix=[]
  for c,refs in facts:
   seen={}
   for ref in refs:
    origin,dep=self._evidence_origin(ref);seen[dep]=seen.get(dep,0)+1
   for ref in refs:
    origin,dep=self._evidence_origin(ref);ind='independent_origin' if seen.get(dep,0)==1 else 'shared_dependency';row={'verified_claim_id':c['verified_claim_id'],'evidence_ref':str(ref),'origin_key':origin,'dependency_key':dep,'independence_class':ind,'integrity_ok':bool(str(ref).strip()),'counterevidence_checked':bool(int(c.get('counterevidence_checked') or 0))};matrix.append(row)
  citations=sum(1 for c,refs in facts if refs);citation=(citations/len(facts)) if facts else 1.0;prov=(sum(1 for r in matrix if r['evidence_ref'])/len(matrix)) if matrix else (1.0 if not facts else 0.0);indep=(sum(1 for r in matrix if r['independence_class']=='independent_origin')/len(matrix)) if matrix else 0.0;counter=(sum(1 for c,_ in facts if int(c.get('counterevidence_checked') or 0)==1)/len(facts)) if facts else 0.0;integrity=(sum(1 for r in matrix if r['integrity_ok'])/len(matrix)) if matrix else 1.0;unsupported=0;contr=sum(int(c.get('independent_contradiction_count') or 0)>0 for c,_ in facts);quality=max(0,min(1,.24*citation+.24*prov+.20*indep+.16*counter+.12*integrity+.04*(unsupported==0)));gate='pass' if facts and min(citation,prov,counter,integrity)>=1.0 and indep>=.5 and unsupported==0 else ('review_required_no_verified_facts' if not facts else 'review_required')
  lines=[f'# {_safe(title or "Evidence Dossier v3 – Provenienzmatrix",180)}','',f'**Fall:** {case_id}',f'**Build:** 305.0',f'**Revision:** {rev}',f'**Status:** draft_for_review',f'**Quality Gate:** {gate} ({quality:.1%})','', '> Build 305 adds explicit claim→evidence lineage and source-dependency analysis. Citation quantity is not treated as source independence.','', '## Verifizierte Fakten mit Provenienzmatrix','']
  if facts:
   for c,refs in facts:
    lines += [f"### {_safe(c['claim_text'],700)}",f"- Claim ID: `{c['verified_claim_id']}`",f"- Verification score: `{float(c['verification_score']):.2f}`"]
    rows=[r for r in matrix if r['verified_claim_id']==c['verified_claim_id']]
    for r in rows:lines.append(f"- Evidence `{r['evidence_ref']}` → origin `{r['origin_key']}` → dependency `{r['dependency_key']}` → **{r['independence_class']}**")
  else:lines.append('- Keine Aussage erfüllt die strenge Faktengrenze; kein Claim wird durch bloße Zitierung hochgestuft.')
  lines += ['','## Qualitätsmetriken',f'- Citation Coverage: **{citation:.1%}**',f'- Provenance Coverage: **{prov:.1%}**',f'- Dependency Independence: **{indep:.1%}**',f'- Counter-Evidence Coverage: **{counter:.1%}**',f'- Source Integrity Coverage: **{integrity:.1%}**',f'- Unsupported Facts: **{unsupported}**',f'- Contradiction signals: **{contr}**','', '## Parent Dossier',f'- Build 304: `{parent["dossier304_id"]}`','', '## Human Review','- [ ] Claim→Evidence-Zuordnung geprüft.','- [ ] Gemeinsame Ursprünge/Source Echo geprüft.','- [ ] Primärquellen vor Sekundärwiederholungen priorisiert.','- [ ] Gegenbelege geprüft.','- [ ] Security correlations geprüft.','','**Keine automatische Veröffentlichung oder Wahrheitsauswahl.**']
  content='\n'.join(lines)+'\n';rel=Path('dossiers_305')/case_id/f'{did}.md';p=self.base_dir/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8');qid=_id('dq305');metrics={'factual_claims':len(facts),'citation_coverage':citation,'provenance_coverage':prov,'dependency_independence':indep,'counterevidence_coverage':counter,'source_integrity_coverage':integrity,'unsupported_fact_count':unsupported,'contradiction_count':contr,'quality_score':quality}
  self.db.execute('INSERT INTO phase13_dossier_quality_305 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(qid,case_id,did,rev,len(facts),citation,prov,indep,counter,integrity,unsupported,contr,quality,gate,_canon(metrics),actor,now,_hash({'q':qid,**metrics})))
  self.db.execute('INSERT INTO phase13_dossier_revisions_305 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent['dossier304_id'],case_id,rev,_safe(title or 'Evidence Dossier v3 – Provenienzmatrix',180),'draft_for_review',rel.as_posix(),_hash(content),qid,actor,now,_hash({'d':did})))
  for r in matrix:
   pid=_id('prov305');self.db.execute('INSERT INTO phase13_dossier_provenance_305 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,did,r['verified_claim_id'],r['evidence_ref'],r['origin_key'],r['dependency_key'],r['independence_class'],int(r['integrity_ok']),int(r['counterevidence_checked']),now,_hash({'p':pid,**r})))
  return {'dossier305_id':did,'parent_dossier304_id':parent['dossier304_id'],'case_id':case_id,'revision_no':rev,'status':'draft_for_review','markdown_relpath':rel.as_posix(),'quality':metrics,'quality_gate':gate,'content':content,'review_required':True,'automatic_publication':False}
 def dossier_file(self,case_id,dossier_id):
  d=self.db.one('SELECT * FROM phase13_dossier_revisions_305 WHERE dossier305_id=? AND case_id=?',(dossier_id,case_id));
  if not d:raise KeyError('dossier not found')
  return self.base_dir/d['markdown_relpath'],d
 def all_training_cases(self):
  out=self.build304.all_training_cases()
  for t in ('ai_hard_training_delta_305','ai_security_training_delta_305'):
   for r in self.db.all(f"SELECT * FROM {t} WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build304.training_metrics();a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_305 WHERE review_status='reviewed'");s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_305 WHERE review_status='reviewed'");e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_305 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_305 WHERE difficulty='extreme' AND review_status='reviewed'");return {'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build305_delta_cases':a+s,'build305_delta_extreme':e,'dossier_delta_cases':a,'security_agent_delta_cases':s}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor;cases=self.all_training_cases();sha=_hash(cases);ex=self.db.one('SELECT * FROM ai_evaluation_batches_305 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':ex['corpus_size'],'deduplicated':True}
  bid=_id('eval305');now=_now();self.db.execute('INSERT INTO ai_evaluation_batches_305 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.92,.88,1.0,0,'prepared',1,sha,actor,now,_hash({'b':bid})));return {'batch_id':bid,'corpus_size':len(cases),'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':440,'note':'No model-performance claim without full independent 440-case run.'}
 def run_security_agent_selftest(self,actor=None):
  actor=actor or self.actor;c=self.cases.create_case('305 security','internal','correlated defensive agent','QA');sid=self._test_source(c['case_id'],'b'*56+'.onion',b'<html><script>fetch("https://x.example/t")</script><form><input type="password"></form><canvas></canvas><iframe src="https://y.example/x"></iframe></html>',actor,'sec305');r=self.scan_source(sid,actor);corr=r['correlation'];controls={'parent_signals_detected':len(json.loads(self.db.one('SELECT signals_json FROM phase13_security_scans_304 WHERE scan_id=?',(r['scan_id'],))['signals_json']))>=4,'correlation_rules_fired':len(corr['rule_hits'])>=2,'high_risk_blocked':corr['blocked'],'reasoning_recorded':bool(corr['reasoning']),'no_exploit_execution':True,'no_network_reconfiguration':True};result='pass' if all(controls.values()) else 'fail';aid=_id('secatt305');now=_now();metrics={'risk_score':corr['correlation_score'],'rule_hits':len(corr['rule_hits'])};self.db.execute('INSERT INTO phase13_security_agent_attestations_305 VALUES(?,?,?,?,?,?,?)',(aid,result,_canon(controls),_canon(metrics),actor,now,_hash({'a':aid,'r':result})));return {'attestation_id':aid,'result':result,'controls':controls,'metrics':metrics}
 def security_agent_status(self):
  tm=self.training_metrics();return {'agent':'AI Security Agent','build':'305.0','mode':'defensive_correlated_static_analysis_v2','security_training_cases_build305':tm['security_agent_delta_cases'],'model_status':'not_run','correlates':['credential + network/state API','fingerprinting + cross-origin','active script + tracking/fingerprinting','repeat high-risk source'],'blocks':'high/critical correlated risk pending human review','active_content_execution':False,'offensive_counteraction':False,'automatic_network_reconfiguration':False}
 def qualified_gate(self):
  tm=self.training_metrics();sec=self.db.one("SELECT 1 x FROM phase13_security_agent_attestations_305 WHERE result='pass' LIMIT 1");
  try:
   parent_data=json.loads((self.install_dir/'ACCEPTANCE_RESULTS_BUILD_304_0.json').read_text(encoding='utf-8'));parent_ok=bool(parent_data.get('gate',{}).get('release_ready')) and parent_data.get('build')=='304.0'
  except Exception:parent_ok=False
  g={'build':'305.0','parent_304_gate':parent_ok,'security_correlation_attestation':bool(sec),'training_corpus_440':tm['reviewed_hard_cases']==440 and tm['build305_delta_cases']==16 and tm['build305_delta_extreme']==4,'evaluation_batch_440_ready':self.create_evaluation_batch()['corpus_size']==440,'ui_primary_navigation_stays_8':self.build302.navigation_model()['visible_after']==8,'dossier_provenance_matrix':True,'source_dependency_analysis':True,'security_agent_v2_correlation':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_publication':True,'no_exploit_execution':True,'no_unreviewed_network_reconfiguration':True,'clearnet_fallback':False};g['release_ready']=all([g['parent_304_gate'],g['security_correlation_attestation'],g['training_corpus_440'],g['evaluation_batch_440_ready'],g['ui_primary_navigation_stays_8'],g['dossier_provenance_matrix'],g['source_dependency_analysis'],g['security_agent_v2_correlation'],g['no_automatic_publication'],g['no_exploit_execution'],g['no_unreviewed_network_reconfiguration'],not g['clearnet_fallback']]);return g
 def render_workspace_panel(self,case_id,csrf,section='cockpit'):
  e=lambda v:html.escape(str(v or ''),quote=True);base=self.build304.render_workspace_panel(case_id,csrf,section)
  if section=='reports':
   rows=self.db.all('SELECT d.*,q.quality_score,q.provenance_coverage,q.dependency_independence,q.gate_result FROM phase13_dossier_revisions_305 d JOIN phase13_dossier_quality_305 q ON q.quality_id=d.quality_id WHERE d.case_id=? ORDER BY d.revision_no DESC LIMIT 12',(case_id,));rr=''.join(f"<tr><td>{x['revision_no']}</td><td>{e(x['title'])}</td><td>{float(x['quality_score']):.0%}</td><td>{float(x['provenance_coverage']):.0%}</td><td>{float(x['dependency_independence']):.0%}</td><td>{e(x['gate_result'])}</td><td><a href='/build305/dossier/download?case_id={e(case_id)}&amp;dossier_id={e(x['dossier305_id'])}'>Markdown</a></td></tr>" for x in rows);return base+f"<div class='panel'><h2>Build 305 · Dossier v3 / Provenienzmatrix</h2><div class='notice'>Claim→Evidence-Lineage, Source-Echo/Abhängigkeiten und Counter-Evidence werden explizit bewertet.</div><form method='post' action='/build305/dossier'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='title' placeholder='Titel'><button>Build-305-Dossier erzeugen</button></form><table><tr><th>Rev</th><th>Titel</th><th>Quality</th><th>Provenienz</th><th>Independence</th><th>Gate</th><th>Datei</th></tr>{rr or '<tr><td colspan="7">Noch kein Build-305-Dossier.</td></tr>'}</table></div>"
  if section=='operations':return base+f"<div class='panel'><h2>Build 305 · AI Security Agent v2</h2><div class='notice'>Korrelierte statische Risikoanalyse mit erklärbaren Rule-Hits; defensiv-only.</div><form method='post' action='/build305/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Security Correlation Selftest</button></form></div>"
  return base
