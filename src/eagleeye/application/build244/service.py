from __future__ import annotations
import hashlib, html, json
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _hash(v: Any) -> str:
    raw = v if isinstance(v, bytes) else _canon(v).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def _text(v: Any, n: int = 8000) -> str:
    return str(v or '').replace('\x00', '').strip()[:n]

def _loads(v: Any, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default


class Build244InvestigatorCockpitService:
    BUILD = '244.0'
    SECTIONS = ('overview','people','evidence','graph','timeline','research','coai','opsec','reports')
    FEEDBACK_CATEGORIES = ('coai','opsec','workflow','evidence','research','ui')

    def __init__(self, db: Any, audit: Any, *, kernel: Any, source_fabric: Any, social: Any, graph: Any,
                 evidence_vault: Any, co_ai: Any, reasoning: Any, orchestration: Any, opsec: Any,
                 training: Any, conversation: Any, actor: str = 'local-analyst') -> None:
        self.db, self.audit = db, audit
        self.kernel, self.source_fabric, self.social, self.graph = kernel, source_fabric, social, graph
        self.evidence_vault, self.co_ai, self.reasoning = evidence_vault, co_ai, reasoning
        self.orchestration, self.opsec, self.training, self.conversation = orchestration, opsec, training, conversation
        self.actor = actor
        conversation._cockpit244 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?', (case_id,)):
            raise KeyError(case_id)

    def _one(self, sql: str, case_id: str) -> int:
        try: return int((self.db.one(sql, (case_id,)) or {'n': 0})['n'])
        except Exception: return 0

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one('SELECT event_hash FROM build244_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1', (case_id,))
        previous_hash = (prev or {}).get('event_hash', '')
        eid, now = new_id('evt244'), now_ts()
        event_hash = _hash({'previous': previous_hash, 'event_id': eid, 'event_type': event_type, 'object_id': object_id, 'payload': payload, 'actor': actor, 'at': now})
        self.db.execute('INSERT INTO build244_events VALUES(?,?,?,?,?,?,?,?,?,?)', (eid, case_id, event_type, object_type, object_id, actor, dumps(payload), previous_hash, event_hash, now))
        try: self.audit.log('build244_' + event_type, object_type, object_id, case_id, payload)
        except Exception: pass

    def case_state(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        kernel = self.kernel.dashboard(case_id=case_id)
        evidence = self.evidence_vault.dashboard(case_id=case_id)
        graph = self.graph.dashboard(case_id=case_id)
        coai = self.co_ai.dashboard(case_id=case_id)
        reasoning = self.reasoning.dashboard(case_id=case_id)
        agents = self.orchestration.dashboard(case_id=case_id)
        opsec = self.opsec.dashboard(case_id)
        research = self._one('SELECT COUNT(*) n FROM source_intelligence_queries_226 WHERE case_id=?', case_id)
        social_profiles = self._one('SELECT COUNT(*) n FROM social_profiles_237 WHERE case_id=?', case_id)
        reports = self._one('SELECT COUNT(*) n FROM report_drafts_131 WHERE case_id=?', case_id)
        feedback = self._one('SELECT COUNT(*) n FROM cockpit_feedback_244 WHERE case_id=?', case_id)
        training = self._one('SELECT COUNT(*) n FROM cockpit_training_links_244 WHERE case_id=?', case_id)
        monitoring = {'watchlists': 0, 'targets': 0, 'due': 0, 'changes': 0}
        monitor_service = getattr(self, '_monitoring246', None)
        if monitor_service is not None:
            try: monitoring = monitor_service.dashboard(case_id=case_id)
            except Exception: pass
        entity_count = int(kernel.get('object_counts', {}).get('entity', 0))
        accepted_evidence = int(evidence.get('accepted', 0))
        contradictions = int(coai.get('contradictions', 0))
        open_tasks = int(coai.get('open_tasks', 0))
        opsec_health = opsec.get('health') or {}
        risk = opsec_health.get('risk_level', 'not_assessed')
        readiness_points = 0
        readiness_points += 20 if kernel.get('integrity', {}).get('ok') else 0
        readiness_points += 20 if accepted_evidence else 0
        readiness_points += 15 if entity_count else 0
        readiness_points += 15 if coai.get('verified_claims', 0) else 0
        readiness_points += 15 if reasoning.get('accepted_cycles', 0) else 0
        readiness_points += 15 if risk in {'low','moderate','not_assessed'} else 0
        state = {
            'build': self.BUILD, 'case_id': case_id, 'readiness_score': min(100, readiness_points),
            'entities': entity_count, 'social_profiles': social_profiles, 'accepted_evidence': accepted_evidence,
            'evidence_items': int(evidence.get('items', 0)), 'graph_links': int(kernel.get('link_count', 0)),
            'accepted_graph_edges': int(coai.get('accepted_edges', 0)), 'research_queries': research,
            'verified_claims': int(coai.get('verified_claims', 0)), 'contradictions': contradictions,
            'open_tasks': open_tasks, 'reasoning_cycles': int(reasoning.get('accepted_cycles', 0)),
            'pending_reasoning': int(reasoning.get('pending_cycles', 0)), 'agent_runs': int(agents.get('runs', 0)),
            'active_agent_runs': int(agents.get('active_runs', 0)), 'opsec_risk': risk,
            'opsec_exposure': opsec_health.get('exposure_score', None), 'opsec_efficiency': opsec_health.get('efficiency_score', None),
            'reports': reports, 'feedback': feedback, 'training': training,
            'monitor_watchlists': int(monitoring.get('watchlists',0)), 'monitor_targets': int(monitoring.get('targets',0)),
            'monitor_due': int(monitoring.get('due',0)), 'monitor_changes': int(monitoring.get('changes',0)),
            'kernel_integrity': kernel.get('integrity', {}), 'state_sha256': '',
        }
        state['state_sha256'] = _hash({k: v for k, v in state.items() if k != 'state_sha256'})
        return state

    def create_snapshot(self, *, case_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f'COCKPIT SNAPSHOT 244 {case_id} SPEICHERN': raise PermissionError('explicit approval required')
        summary = self.case_state(case_id=case_id)
        sid, now = new_id('cockpitsnap244'), now_ts()
        payload = {'snapshot_id': sid, 'case_id': case_id, 'state_sha256': summary['state_sha256'], 'summary': summary, 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO cockpit_snapshots_244 VALUES(?,?,?,?,?,?,?)', (sid, case_id, summary['state_sha256'], dumps(summary), actor, now, _hash(payload)))
        self._event(case_id, 'snapshot_created', 'cockpit_snapshot', sid, {'state_sha256': summary['state_sha256']}, actor)
        return payload

    def record_feedback(self, *, case_id: str, category: str, rating: int, outcome: str, note: str, related_ref: str,
                        actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f'COCKPIT FEEDBACK 244 {case_id} SPEICHERN': raise PermissionError('explicit approval required')
        if category not in self.FEEDBACK_CATEGORIES: raise ValueError('invalid feedback category')
        rating = int(rating)
        if rating < 1 or rating > 5: raise ValueError('rating must be 1..5')
        if outcome not in {'helpful','mixed','unhelpful','false_positive','missed_issue'}: raise ValueError('invalid outcome')
        if len(_text(note)) < 12: raise ValueError('substantive note required')
        fid, now = new_id('feedback244'), now_ts()
        payload = {'feedback_id': fid, 'case_id': case_id, 'category': category, 'rating': rating, 'outcome': outcome, 'note': _text(note), 'related_ref': _text(related_ref, 500), 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO cockpit_feedback_244 VALUES(?,?,?,?,?,?,?,?,?,?)', (fid, case_id, category, rating, outcome, payload['note'], payload['related_ref'], actor, now, _hash(payload)))
        self._event(case_id, 'feedback_recorded', 'cockpit_feedback', fid, {'category': category, 'rating': rating, 'outcome': outcome}, actor)
        return {**payload, 'review_status': 'pending'}

    def review_feedback(self, *, feedback_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self.db.one('SELECT * FROM cockpit_feedback_244 WHERE feedback_id=?', (feedback_id,))
        if not row: raise KeyError(feedback_id)
        if confirmation != f'COCKPIT FEEDBACK 244 {feedback_id} PRUEFEN': raise PermissionError('explicit approval required')
        if reviewer == row['created_by']: raise PermissionError('independent reviewer required')
        if decision not in {'accepted','rejected','needs_context'}: raise ValueError('invalid decision')
        if len(_text(rationale)) < 15: raise ValueError('substantive rationale required')
        if self.db.one('SELECT review_id FROM cockpit_feedback_reviews_244 WHERE feedback_id=?', (feedback_id,)): raise ValueError('already reviewed')
        rid, now = new_id('feedbackrev244'), now_ts()
        payload = {'review_id': rid, 'feedback_id': feedback_id, 'case_id': row['case_id'], 'decision': decision, 'rationale': _text(rationale), 'reviewer': reviewer, 'reviewed_at': now}
        self.db.execute('INSERT INTO cockpit_feedback_reviews_244 VALUES(?,?,?,?,?,?,?,?)', (rid, feedback_id, row['case_id'], decision, payload['rationale'], reviewer, now, _hash(payload)))
        self._event(row['case_id'], 'feedback_reviewed', 'cockpit_feedback', feedback_id, {'decision': decision}, reviewer)
        return payload

    def stage_training(self, *, case_id: str, actor: str, limit: int = 50, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f'COCKPIT TRAINING 244 {case_id} VORBEREITEN': raise PermissionError('explicit approval required')
        rows = self.db.all("""SELECT f.*,r.decision,r.rationale,r.reviewer FROM cockpit_feedback_244 f
            JOIN cockpit_feedback_reviews_244 r ON r.feedback_id=f.feedback_id
            LEFT JOIN cockpit_training_links_244 l ON l.feedback_id=f.feedback_id
            WHERE f.case_id=? AND r.decision='accepted' AND l.feedback_id IS NULL
            ORDER BY r.reviewed_at LIMIT ?""", (case_id, max(1, min(200, int(limit)))))
        created = []
        for row in rows:
            instruction = 'Bewerte eine Ermittlerunterstützung anhand reviewten Analystenfeedbacks. Verbessere Klarheit, Grounding, Priorisierung und OPSEC ohne Kandidaten als Fakten oder Risikosignale als bewiesene Angriffe darzustellen.'
            response = _canon({'category': row['category'], 'rating': row['rating'], 'outcome': row['outcome'], 'analyst_feedback': row['note'], 'independent_review': row['rationale']})
            ex = self.training.add_example(case_id=case_id, instruction=instruction, response=response,
                context={'build': self.BUILD, 'category': row['category'], 'related_ref': row['related_ref'], 'reviewer': row['reviewer']},
                evidence_refs=([row['related_ref']] if row['related_ref'] else []), language='de', source_type='investigator_cockpit_244',
                source_ref=row['feedback_id'], created_by=actor, confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')
            lid, now = new_id('cockpittrain244'), now_ts()
            self.db.execute('INSERT INTO cockpit_training_links_244 VALUES(?,?,?,?,?,?,?)', (lid, case_id, row['feedback_id'], ex['example_id'], actor, now, _hash({'link': lid, 'feedback': row['feedback_id'], 'training': ex['example_id']})))
            created.append(ex['example_id'])
        self._event(case_id, 'training_staged', 'case', case_id, {'count': len(created), 'automatic_activation': False}, actor)
        return {'case_id': case_id, 'created': len(created), 'training_example_ids': created, 'review_status': 'pending', 'automatic_activation': False}

    def conversation_context(self, *, case_id: str) -> dict[str, Any]:
        s = self.case_state(case_id=case_id)
        return {'investigator_cockpit_244': s, 'rules': [
            'The cockpit is a navigation and prioritization layer; it does not upgrade candidates into facts.',
            'Use accepted hash-intact evidence for factual claims and name contradictions explicitly.',
            'OPSEC risk indicators are signals, not proof of tracking or an attacker.',
            'Recommended next steps remain proposals and require the existing human/OPSEC gates.'
        ]}

    def _recent_entities(self, case_id: str) -> list[dict[str, Any]]:
        return [dict(x) for x in self.db.all("SELECT object_id,subtype,label,created_at FROM canonical_objects_235 WHERE case_id=? AND object_type='entity' ORDER BY created_at DESC LIMIT 30", (case_id,))]

    def _recent_evidence(self, case_id: str) -> list[dict[str, Any]]:
        return [dict(x) for x in self.db.all("""SELECT i.vault_item_id,i.media_type,i.source_url,i.captured_at,COALESCE(r.decision,'pending') decision
            FROM evidence_vault_items_239 i LEFT JOIN evidence_reviews_239 r ON r.vault_item_id=i.vault_item_id
            WHERE i.case_id=? ORDER BY i.captured_at DESC LIMIT 30""", (case_id,))]

    def _recent_timeline(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT post_id,profile_id,content_original,observed_at FROM social_posts_237 WHERE case_id=? ORDER BY observed_at DESC LIMIT 20", (case_id,))
        return [dict(x) for x in rows]

    def _table(self, rows: list[dict[str, Any]], columns: list[tuple[str,str]]) -> str:
        e = lambda x: html.escape(str(x if x is not None else ''), quote=True)
        if not rows: return "<div class='empty'>Noch keine passenden Falldaten.</div>"
        head = ''.join(f'<th>{e(label)}</th>' for _, label in columns)
        body = ''.join('<tr>' + ''.join(f'<td>{e(row.get(k,""))}</td>' for k,_ in columns) + '</tr>' for row in rows)
        return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"

    def _subnav(self, case_id: str, section: str) -> str:
        labels = {'overview':'Overview','people':'People','evidence':'Evidence','graph':'Graph','timeline':'Timeline','research':'Research','coai':'Co-AI Investigator','opsec':'OPSEC','reports':'Reports'}
        keys = {'overview':'cockpit244','people':'people244','evidence':'evidence244','graph':'graph244','timeline':'timeline244','research':'research244','coai':'coai244','opsec':'opsec244','reports':'reports244'}
        return "<div class='cockpit-tabs'>" + ''.join(f"<a class='{'active' if section==s else ''}' href='/?tab={keys[s]}&case_id={html.escape(case_id,quote=True)}'>{labels[s]}</a>" for s in self.SECTIONS) + '</div>'

    def render_section(self, *, case_id: str, section: str, csrf: str) -> str:
        self._case(case_id)
        if section not in self.SECTIONS: section = 'overview'
        e = lambda x: html.escape(str(x if x is not None else ''), quote=True)
        s = self.case_state(case_id=case_id)
        nav = self._subnav(case_id, section)
        status = f"<div class='cockpit-status'><span class='badge ok'>Readiness {s['readiness_score']}%</span><span class='badge'>OPSEC {e(s['opsec_risk'])}</span><span class='badge'>Evidence {s['accepted_evidence']}</span><span class='badge'>Contradictions {s['contradictions']}</span><span class='badge'>Open tasks {s['open_tasks']}</span></div>"
        if section == 'overview':
            body = f"""<div class='metrics'><div class='metric'><div class='label'>People / Entities</div><div class='value'>{s['entities']}</div></div><div class='metric'><div class='label'>Accepted Evidence</div><div class='value'>{s['accepted_evidence']}</div></div><div class='metric'><div class='label'>Verified Claims</div><div class='value'>{s['verified_claims']}</div></div><div class='metric'><div class='label'>Research Queries</div><div class='value'>{s['research_queries']}</div></div><div class='metric'><div class='label'>Agent Runs</div><div class='value'>{s['agent_runs']}</div></div><div class='metric'><div class='label'>Reports</div><div class='value'>{s['reports']}</div></div></div>
            <div class='grid'><a class='action-card' href='/?tab=people244&case_id={e(case_id)}'><b>People</b><br><span class='muted'>Identitäten und Social-Accounts prüfen</span></a><a class='action-card' href='/?tab=evidence244&case_id={e(case_id)}'><b>Evidence</b><br><span class='muted'>Hash-intakte Belege und Änderungen</span></a><a class='action-card' href='/?tab=monitor246&case_id={e(case_id)}'><b>Monitoring</b><br><span class='muted'>{s['monitor_due']} fällige Targets · {s['monitor_changes']} Change Candidates</span></a><a class='action-card' href='/?tab=coai244&case_id={e(case_id)}'><b>Co-AI Investigator</b><br><span class='muted'>Fallzustand, Hypothesen und nächste Schritte</span></a><a class='action-card {'high' if s['opsec_risk'] in {'high','critical'} else ''}' href='/?tab=opsec244&case_id={e(case_id)}'><b>OPSEC</b><br><span class='muted'>Risiko, Exposure und Agenten-Gates</span></a></div>
            <div class='grid'><div class='card'><h3>Fallzustand einfrieren</h3><form method='post' action='/build244/snapshot'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Cockpit-Snapshot erzeugen</button></form><p class='muted'>State SHA-256: <code>{e(s['state_sha256'])}</code></p></div>{self._feedback_form(case_id,csrf)}</div>"""
        elif section == 'people':
            body = self._table(self._recent_entities(case_id), [('object_id','Entity-ID'),('subtype','Typ'),('label','Name / Label'),('created_at','Erfasst')]) + f"<p><a class='button ghost' href='/?tab=entities&case_id={e(case_id)}'>Personen-/Entity-Werkzeuge öffnen</a> <a class='button ghost' href='/?tab=build214&case_id={e(case_id)}#build237'>Social Intelligence öffnen</a></p>"
        elif section == 'evidence':
            body = self._table(self._recent_evidence(case_id), [('vault_item_id','Vault-ID'),('decision','Review'),('media_type','Typ'),('source_url','Ursprung'),('captured_at','Capture')]) + f"<p><a class='button ghost' href='/?tab=evidence138&case_id={e(case_id)}'>Evidence-Ansicht</a> <a class='button ghost' href='/?tab=build214&case_id={e(case_id)}#build239_vault'>Evidence Vault 239</a></p>"
        elif section == 'graph':
            body = f"<div class='metrics'><div class='metric'><div class='label'>Links</div><div class='value'>{s['graph_links']}</div></div><div class='metric'><div class='label'>Accepted edges</div><div class='value'>{s['accepted_graph_edges']}</div></div></div><p>Graphpfade bleiben analytische Hinweise; Nähe ist weder Beziehung noch Kausalität.</p><p><a class='button' href='/?tab=graph_lab&case_id={e(case_id)}'>Interaktiven Graph öffnen</a> <a class='button ghost' href='/?tab=build214&case_id={e(case_id)}#build238_graph'>Graph 3.0 Details</a></p>"
        elif section == 'timeline':
            body = self._table(self._recent_timeline(case_id), [('observed_at','Zeit'),('profile_id','Profil'),('content_original','Öffentliche Beobachtung'),('post_id','Post-ID')]) + f"<p><a class='button ghost' href='/?tab=timeline&case_id={e(case_id)}'>Legacy-Timeline öffnen</a></p>"
        elif section == 'research':
            body = f"<div class='metrics'><div class='metric'><div class='label'>Source-Intelligence Queries</div><div class='value'>{s['research_queries']}</div></div><div class='metric'><div class='label'>Open tasks</div><div class='value'>{s['open_tasks']}</div></div></div><p><a class='button' href='/?tab=research147&case_id={e(case_id)}'>Recherche starten / fortsetzen</a> <a class='button ghost' href='/?tab=sourceops187&case_id={e(case_id)}'>Quellenbetrieb</a></p><p class='muted'>Source Fabric / Ranking bleiben review-first; das Cockpit führt keine Quelle autonom aus.</p>"
        elif section == 'coai':
            body = f"<div class='metrics'><div class='metric'><div class='label'>Verified Claims</div><div class='value'>{s['verified_claims']}</div></div><div class='metric'><div class='label'>Contradictions</div><div class='value'>{s['contradictions']}</div></div><div class='metric'><div class='label'>Accepted reasoning</div><div class='value'>{s['reasoning_cycles']}</div></div><div class='metric'><div class='label'>Pending reasoning</div><div class='value'>{s['pending_reasoning']}</div></div></div><p><a class='button' href='/?tab=build214&case_id={e(case_id)}#build227_conversation'>Co-AI Ermittler öffnen</a> <a class='button ghost' href='/?tab=build214&case_id={e(case_id)}#build241_reasoning'>Reasoning Workflow</a></p><p class='muted'>Fakten brauchen akzeptierte Evidence; Kandidaten und Hypothesen bleiben ausdrücklich Nicht-Fakten.</p>"
        elif section == 'opsec':
            body = f"<div class='metrics'><div class='metric'><div class='label'>Risk</div><div class='value'>{e(s['opsec_risk'])}</div></div><div class='metric'><div class='label'>Exposure</div><div class='value'>{e(s['opsec_exposure'] if s['opsec_exposure'] is not None else '-')}</div></div><div class='metric'><div class='label'>Efficiency</div><div class='value'>{e(s['opsec_efficiency'] if s['opsec_efficiency'] is not None else '-')}</div></div><div class='metric'><div class='label'>Active agents</div><div class='value'>{s['active_agent_runs']}</div></div></div><form method='post' action='/build243/health-scan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>OPSEC-Health analysieren</button></form><p><a class='button ghost' href='/?tab=build214&case_id={e(case_id)}#build243'>OPSEC 3.0 Details</a></p><p class='muted'>Niedrige Exposition ist kein Unsichtbarkeitsbeweis; der Sentinel verändert keine OS-/Netzwerkparameter autonom.</p>"
        else:
            body = f"<div class='metrics'><div class='metric'><div class='label'>Report drafts</div><div class='value'>{s['reports']}</div></div></div><p><a class='button' href='/?tab=reports142&case_id={e(case_id)}'>Reports &amp; Übergabe öffnen</a> <a class='button ghost' href='/?tab=handover168&case_id={e(case_id)}'>Akte &amp; Übergabe</a></p>"
        return f"<section class='panel cockpit244'><h2>Investigator Cockpit · Build 244</h2><p class='muted'>Fallzentrierte Oberfläche über Kernel, Evidence, Graph, Co-AI, Agenten und OPSEC. Technische Build-IDs bleiben im Hintergrund verfügbar, sind aber nicht mehr der primäre Arbeitsfluss.</p>{nav}{status}{body}</section>"

    def _feedback_form(self, case_id: str, csrf: str) -> str:
        e = lambda x: html.escape(str(x), quote=True)
        return f"""<div class='card'><h3>Analystenfeedback → Training</h3><form method='post' action='/build244/feedback'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='category'><option>coai</option><option>opsec</option><option>workflow</option><option>evidence</option><option>research</option><option>ui</option></select><select name='rating'><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select><select name='outcome'><option>helpful</option><option>mixed</option><option>unhelpful</option><option>false_positive</option><option>missed_issue</option></select><input name='related_ref' placeholder='Optional: Turn-/Alert-/Evidence-ID'><textarea name='note' placeholder='Was war hilfreich oder falsch?' required></textarea><button>Feedback speichern</button></form><p class='muted'>Erst unabhängiges Review macht Feedback trainingsfähig.</p></div>"""

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        return self.render_section(case_id=case_id, section='overview', csrf=csrf)
