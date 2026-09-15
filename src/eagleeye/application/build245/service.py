from __future__ import annotations
import hashlib, html, json
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _hash(v: Any) -> str:
    raw = v if isinstance(v, bytes) else _canon(v).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def _text(v: Any, n: int = 10000) -> str:
    return str(v or '').replace('\x00', '').strip()[:n]

def _loads(v: Any, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default


class Build245InvestigativeWorkflowEngineService:
    BUILD = '245.0'
    STAGES = ('intake','question','plan','research','evidence','verification','analysis','review','report')
    AGENT_ROLES = ('','planner','retriever','source_analyst','identity_analyst','verifier','critic','reporter')

    def __init__(self, db: Any, audit: Any, *, cockpit: Any, kernel: Any, evidence_vault: Any,
                 co_ai: Any, reasoning: Any, orchestration: Any, opsec: Any, sentinel: Any,
                 training: Any, conversation: Any, actor: str = 'local-analyst') -> None:
        self.db, self.audit = db, audit
        self.cockpit, self.kernel, self.evidence_vault = cockpit, kernel, evidence_vault
        self.co_ai, self.reasoning, self.orchestration = co_ai, reasoning, orchestration
        self.opsec, self.sentinel, self.training = opsec, sentinel, training
        self.conversation, self.actor = conversation, actor
        conversation._workflow245 = self
        cockpit._workflow245 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?', (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one('SELECT event_hash FROM workflow_events_245 WHERE case_id=? ORDER BY rowid DESC LIMIT 1', (case_id,))
        ph = (prev or {}).get('event_hash', '')
        eid, now = new_id('wf_evt245'), now_ts()
        eh = _hash({'previous': ph, 'event_id': eid, 'event_type': event_type, 'object_id': object_id, 'payload': payload, 'actor': actor, 'at': now})
        self.db.execute('INSERT INTO workflow_events_245 VALUES(?,?,?,?,?,?,?,?,?,?)', (eid, case_id, event_type, object_type, object_id, actor, dumps(payload), ph, eh, now))
        try: self.audit.log('build245_' + event_type, object_type, object_id, case_id, payload)
        except Exception: pass

    def create_workflow(self, *, case_id: str, objective: str, primary_question: str, owner: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f'WORKFLOW 245 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        objective, primary_question = _text(objective), _text(primary_question)
        if len(objective) < 12 or len(primary_question) < 12: raise ValueError('objective and primary question must be substantive')
        existing = self.db.one("SELECT workflow_id FROM workflow_runs_245 WHERE case_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", (case_id,))
        if existing: return self.workflow(existing['workflow_id'])
        wid, now = new_id('workflow245'), now_ts()
        payload = {'workflow_id': wid, 'case_id': case_id, 'objective': objective, 'primary_question': primary_question, 'owner': _text(owner, 200) or actor, 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO workflow_runs_245 VALUES(?,?,?,?,?,?,?,?,?,?)', (wid, case_id, objective, primary_question, payload['owner'], 'active', actor, now, now, _hash(payload)))
        self._stage_event(wid, case_id, '', 'intake', 'workflow_started', 'Workflow initialized; no external action executed.', actor)
        self._event(case_id, 'workflow_created', 'workflow', wid, {'objective': objective, 'primary_question': primary_question}, actor)
        return self.workflow(wid)

    def _stage_event(self, workflow_id: str, case_id: str, from_stage: str, to_stage: str, decision: str, rationale: str, actor: str) -> None:
        prev = self.db.one('SELECT event_hash FROM workflow_stage_events_245 WHERE workflow_id=? ORDER BY rowid DESC LIMIT 1', (workflow_id,))
        ph = (prev or {}).get('event_hash', '')
        eid, now = new_id('wfstage245'), now_ts()
        payload = {'event_id': eid, 'workflow_id': workflow_id, 'from_stage': from_stage, 'to_stage': to_stage, 'decision': decision, 'rationale': rationale, 'actor': actor, 'at': now}
        eh = _hash({'previous': ph, **payload})
        self.db.execute('INSERT INTO workflow_stage_events_245 VALUES(?,?,?,?,?,?,?,?,?,?,?)', (eid, workflow_id, case_id, from_stage, to_stage, decision, _text(rationale, 5000), actor, now, ph, eh))

    def current_stage(self, workflow_id: str) -> str:
        r = self.db.one('SELECT to_stage FROM workflow_stage_events_245 WHERE workflow_id=? ORDER BY rowid DESC LIMIT 1', (workflow_id,))
        return (r or {}).get('to_stage', 'intake')

    def workflow(self, workflow_id: str) -> dict[str, Any]:
        row = self.db.one('SELECT * FROM workflow_runs_245 WHERE workflow_id=?', (workflow_id,))
        if not row: raise KeyError(workflow_id)
        d = dict(row); d['current_stage'] = self.current_stage(workflow_id)
        d['checkpoints'] = [dict(x) for x in self.db.all('SELECT * FROM workflow_checkpoints_245 WHERE workflow_id=? ORDER BY created_at', (workflow_id,))]
        d['work_items'] = [dict(x) for x in self.db.all('SELECT * FROM workflow_work_items_245 WHERE workflow_id=? ORDER BY priority DESC,created_at', (workflow_id,))]
        return d

    def active_workflow(self, case_id: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT workflow_id FROM workflow_runs_245 WHERE case_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", (case_id,))
        return self.workflow(row['workflow_id']) if row else None

    def submit_checkpoint(self, *, workflow_id: str, stage: str, summary: str, related_refs: list[str], quality_score: float,
                          actor: str, confirmation: str) -> dict[str, Any]:
        wf = self.workflow(workflow_id)
        if confirmation != f'WORKFLOW CHECKPOINT 245 {workflow_id} SPEICHERN': raise PermissionError('explicit approval required')
        if stage != wf['current_stage']: raise ValueError('checkpoint must match current stage')
        summary = _text(summary)
        if len(summary) < 20: raise ValueError('checkpoint summary too short')
        refs = [_text(x, 500) for x in related_refs if _text(x, 500)][:100]
        q = max(0.0, min(1.0, float(quality_score)))
        cid, now = new_id('wfcp245'), now_ts()
        payload = {'checkpoint_id': cid, 'workflow_id': workflow_id, 'case_id': wf['case_id'], 'stage': stage, 'summary': summary, 'related_refs': refs, 'quality_score': q, 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO workflow_checkpoints_245 VALUES(?,?,?,?,?,?,?,?,?,?)', (cid, workflow_id, wf['case_id'], stage, summary, dumps(refs), q, actor, now, _hash(payload)))
        self._event(wf['case_id'], 'checkpoint_submitted', 'workflow_checkpoint', cid, {'stage': stage, 'quality_score': q}, actor)
        return {**payload, 'review_status': 'pending'}

    def review_checkpoint(self, *, checkpoint_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        cp = self.db.one('SELECT * FROM workflow_checkpoints_245 WHERE checkpoint_id=?', (checkpoint_id,))
        if not cp: raise KeyError(checkpoint_id)
        if confirmation != f'WORKFLOW CHECKPOINT 245 {checkpoint_id} PRUEFEN': raise PermissionError('explicit approval required')
        if reviewer == cp['created_by']: raise PermissionError('independent reviewer required')
        if decision not in {'accepted','rejected','needs_work'}: raise ValueError('invalid decision')
        if len(_text(rationale)) < 15: raise ValueError('substantive rationale required')
        if self.db.one('SELECT review_id FROM workflow_checkpoint_reviews_245 WHERE checkpoint_id=?', (checkpoint_id,)): raise ValueError('already reviewed')
        rid, now = new_id('wfcp_rev245'), now_ts()
        payload = {'review_id': rid, 'checkpoint_id': checkpoint_id, 'workflow_id': cp['workflow_id'], 'case_id': cp['case_id'], 'decision': decision, 'rationale': _text(rationale), 'reviewer': reviewer, 'reviewed_at': now}
        self.db.execute('INSERT INTO workflow_checkpoint_reviews_245 VALUES(?,?,?,?,?,?,?,?,?)', (rid, checkpoint_id, cp['workflow_id'], cp['case_id'], decision, payload['rationale'], reviewer, now, _hash(payload)))
        self._event(cp['case_id'], 'checkpoint_reviewed', 'workflow_checkpoint', checkpoint_id, {'decision': decision, 'stage': cp['stage']}, reviewer)
        return payload

    def _accepted_checkpoint(self, workflow_id: str, stage: str) -> dict[str, Any] | None:
        r = self.db.one("""SELECT c.*,r.review_id,r.rationale review_rationale,r.reviewer FROM workflow_checkpoints_245 c
            JOIN workflow_checkpoint_reviews_245 r ON r.checkpoint_id=c.checkpoint_id
            WHERE c.workflow_id=? AND c.stage=? AND r.decision='accepted' ORDER BY r.reviewed_at DESC LIMIT 1""", (workflow_id, stage))
        return dict(r) if r else None

    def _gate_counts(self, case_id: str) -> dict[str, int]:
        def one(sql: str) -> int:
            try: return int((self.db.one(sql, (case_id,)) or {'n': 0})['n'])
            except Exception: return 0
        return {
            'research_queries': one('SELECT COUNT(*) n FROM source_intelligence_queries_226 WHERE case_id=?'),
            'accepted_evidence': one("SELECT COUNT(*) n FROM evidence_vault_items_239 i JOIN evidence_reviews_239 r ON r.vault_item_id=i.vault_item_id WHERE i.case_id=? AND r.decision='accepted'"),
            'verified_claims': one("SELECT COUNT(*) n FROM verified_claims_229 WHERE case_id=? AND status='verified'"),
            'accepted_reasoning': one("SELECT COUNT(*) n FROM reasoning_cycles_241 c JOIN reasoning_reviews_241 r ON r.cycle_id=c.cycle_id WHERE c.case_id=? AND r.decision='accepted'"),
            'reports': one('SELECT COUNT(*) n FROM report_drafts_131 WHERE case_id=?'),
        }

    def _record_opsec_gate_signal(self, wf: dict[str, Any], stage: str, risk: str, score: float) -> None:
        ref = f"{wf['workflow_id']}:{stage}:{risk}"
        exists = self.db.one("SELECT observation_id FROM opsec_observations_242 WHERE case_id=? AND source_type='workflow_engine_245' AND source_ref=?", (wf['case_id'], ref))
        if exists: return
        sev = 'critical' if risk == 'critical' else 'high' if risk == 'high' else 'medium'
        try:
            self.sentinel.record_observation(case_id=wf['case_id'], category='workflow_opsec_gate', severity=sev,
                confidence=max(.5, min(1.0, float(score or .5))), source_type='workflow_engine_245', source_ref=ref,
                details={'workflow_id': wf['workflow_id'], 'stage': stage, 'risk_level': risk, 'safe_boundary': 'app_internal_defensive_gate'},
                detector='workflow-engine-245', confirmation=f"OPSEC OBSERVATION 242 {wf['case_id']} SPEICHERN")
        except Exception: pass

    def advance(self, *, workflow_id: str, actor: str, rationale: str, confirmation: str) -> dict[str, Any]:
        wf = self.workflow(workflow_id)
        if confirmation != f'WORKFLOW 245 {workflow_id} ADVANCE': raise PermissionError('explicit approval required')
        if wf['status'] != 'active': raise ValueError('workflow not active')
        stage = wf['current_stage']
        cp = self._accepted_checkpoint(workflow_id, stage)
        if not cp: raise PermissionError('accepted independent checkpoint review required')
        ass = self.sentinel.scan_case(case_id=wf['case_id'], actor='workflow-engine-245', auto_contain=True)
        if ass['risk_level'] in {'high','critical'}:
            self._record_opsec_gate_signal(wf, stage, ass['risk_level'], ass.get('risk_score', .8))
            raise PermissionError('high/critical OPSEC risk blocks workflow advancement')
        counts = self._gate_counts(wf['case_id'])
        requirements = {
            'research': ('research_queries', 'at least one research query required before Evidence'),
            'evidence': ('accepted_evidence', 'accepted hash-intact evidence required before Verification'),
            'verification': ('verified_claims', 'at least one verified claim required before Analysis'),
            'analysis': ('accepted_reasoning', 'accepted reasoning cycle required before Review'),
            'report': ('reports', 'at least one report draft required before workflow completion'),
        }
        if stage in requirements:
            key, msg = requirements[stage]
            if counts[key] < 1: raise PermissionError(msg)
        idx = self.STAGES.index(stage)
        now = now_ts()
        if idx == len(self.STAGES) - 1:
            self._stage_event(workflow_id, wf['case_id'], stage, 'completed', 'completed', _text(rationale, 5000), actor)
            self.db.execute("UPDATE workflow_runs_245 SET status='completed',updated_at=? WHERE workflow_id=?", (now, workflow_id))
            self._event(wf['case_id'], 'workflow_completed', 'workflow', workflow_id, {'stage': stage}, actor)
            return self.workflow(workflow_id)
        nxt = self.STAGES[idx + 1]
        self._stage_event(workflow_id, wf['case_id'], stage, nxt, 'advanced', _text(rationale, 5000), actor)
        self.db.execute('UPDATE workflow_runs_245 SET updated_at=? WHERE workflow_id=?', (now, workflow_id))
        self._event(wf['case_id'], 'workflow_advanced', 'workflow', workflow_id, {'from': stage, 'to': nxt, 'opsec_risk': ass['risk_level']}, actor)
        return self.workflow(workflow_id)

    def propose_work_item(self, *, workflow_id: str, title: str, description: str, priority: int, owner_role: str,
                          agent_role: str, actor: str, confirmation: str) -> dict[str, Any]:
        wf = self.workflow(workflow_id)
        if confirmation != f'WORKFLOW ITEM 245 {workflow_id} ANLEGEN': raise PermissionError('explicit approval required')
        if agent_role not in self.AGENT_ROLES: raise ValueError('invalid agent role')
        if len(_text(title, 500)) < 4 or len(_text(description)) < 12: raise ValueError('work item too short')
        iid, now = new_id('wfitem245'), now_ts(); p = max(1, min(100, int(priority)))
        payload = {'item_id': iid, 'workflow_id': workflow_id, 'case_id': wf['case_id'], 'stage': wf['current_stage'], 'title': _text(title,500), 'description': _text(description), 'priority': p, 'owner_role': _text(owner_role,200) or 'analyst', 'agent_role': agent_role, 'status': 'proposed', 'created_by': actor, 'created_at': now}
        self.db.execute('INSERT INTO workflow_work_items_245 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (iid, workflow_id, wf['case_id'], wf['current_stage'], payload['title'], payload['description'], p, payload['owner_role'], agent_role, 'proposed', actor, now, now, _hash(payload)))
        self._item_event(iid, workflow_id, wf['case_id'], 'proposed', 'Work item proposed; no action executed.', actor)
        return payload

    def _item_event(self, item_id: str, workflow_id: str, case_id: str, status: str, note: str, actor: str) -> None:
        eid, now = new_id('wfitemevt245'), now_ts(); payload = {'event_id': eid, 'item_id': item_id, 'status': status, 'note': _text(note,5000), 'actor': actor, 'at': now}
        self.db.execute('INSERT INTO workflow_work_item_events_245 VALUES(?,?,?,?,?,?,?,?,?)', (eid, item_id, workflow_id, case_id, status, payload['note'], actor, now, _hash(payload)))

    def set_work_item_status(self, *, item_id: str, status: str, note: str, actor: str, confirmation: str) -> dict[str, Any]:
        row = self.db.one('SELECT * FROM workflow_work_items_245 WHERE item_id=?', (item_id,))
        if not row: raise KeyError(item_id)
        if confirmation != f'WORKFLOW ITEM 245 {item_id} STATUS': raise PermissionError('explicit approval required')
        if status not in {'approved','in_progress','completed','deferred','cancelled'}: raise ValueError('invalid status')
        now = now_ts(); self.db.execute('UPDATE workflow_work_items_245 SET status=?,updated_at=? WHERE item_id=?', (status, now, item_id))
        self._item_event(item_id, row['workflow_id'], row['case_id'], status, note, actor)
        return dict(self.db.one('SELECT * FROM workflow_work_items_245 WHERE item_id=?', (item_id,)))

    def request_agent_support(self, *, item_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        item = self.db.one('SELECT * FROM workflow_work_items_245 WHERE item_id=?', (item_id,))
        if not item: raise KeyError(item_id)
        if confirmation != f'WORKFLOW AGENT 245 {item_id} STARTEN': raise PermissionError('explicit approval required')
        if not item['agent_role']: raise ValueError('work item has no agent role')
        ass = self.sentinel.scan_case(case_id=item['case_id'], actor='workflow-engine-245', auto_contain=True)
        if ass['risk_level'] in {'high','critical'}:
            wf = self.workflow(item['workflow_id']); self._record_opsec_gate_signal(wf, item['stage'], ass['risk_level'], ass.get('risk_score', .8))
            raise PermissionError('OPSEC risk blocks agent support')
        run = self.orchestration.create_run(case_id=item['case_id'], objective=f"Workflow {item['stage']}: {item['title']} — {item['description']}", priority=item['priority'], actor=actor, confirmation=f"AGENT RUN 242 {item['case_id']} ANLEGEN")
        lid, now = new_id('wfagent245'), now_ts(); self.db.execute('INSERT INTO workflow_agent_links_245 VALUES(?,?,?,?,?,?,?,?)', (lid, item['workflow_id'], item_id, item['case_id'], run['run_id'], actor, now, _hash({'link': lid, 'run': run['run_id'], 'item': item_id})))
        self._event(item['case_id'], 'agent_support_requested', 'workflow_item', item_id, {'agent_run_id': run['run_id'], 'agent_role': item['agent_role']}, actor)
        return {'item_id': item_id, 'agent_run_id': run['run_id'], 'automatic_external_action': False, 'human_gates_preserved': True}

    def stage_training(self, *, case_id: str, actor: str, limit: int = 50, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f'WORKFLOW TRAINING 245 {case_id} VORBEREITEN': raise PermissionError('explicit approval required')
        rows = self.db.all("""SELECT c.*,r.rationale review_rationale,r.reviewer FROM workflow_checkpoints_245 c
            JOIN workflow_checkpoint_reviews_245 r ON r.checkpoint_id=c.checkpoint_id
            LEFT JOIN workflow_training_links_245 l ON l.checkpoint_id=c.checkpoint_id
            WHERE c.case_id=? AND r.decision='accepted' AND l.checkpoint_id IS NULL
            ORDER BY r.reviewed_at LIMIT ?""", (case_id, max(1, min(200, int(limit)))))
        created = []
        for x in rows:
            refs = _loads(x['related_refs_json'], [])
            context = {'stage': x['stage'], 'quality_score': x['quality_score'], 'related_refs': refs, 'review_rationale': x['review_rationale'], 'safe_boundary': 'human_reviewed_workflow_no_autonomous_external_action'}
            instruction = 'Bewerte diesen Ermittlungs-Checkpoint. Trenne Beobachtung, Hypothese und Beleg; benenne offene Lücken und priorisiere den nächsten rechtmäßigen, evidenzgebundenen Schritt unter Beachtung von OPSEC.'
            response = f"Checkpoint {x['stage']}: {x['summary']} Review: {x['review_rationale']}"
            ex = self.training.add_example(case_id=case_id, instruction=instruction, response=response, context=context, source_type='investigative_workflow_245', source_ref=x['checkpoint_id'], created_by=actor, confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')
            lid, now = new_id('wftrain245'), now_ts(); self.db.execute('INSERT INTO workflow_training_links_245 VALUES(?,?,?,?,?,?,?,?)', (lid, x['workflow_id'], x['checkpoint_id'], case_id, ex['example_id'], actor, now, _hash({'link': lid, 'example': ex['example_id']})))
            created.append(ex['example_id'])
        return {'case_id': case_id, 'created': len(created), 'training_example_ids': created, 'review_status': 'pending', 'automatic_model_activation': False}

    def dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id); wf = self.active_workflow(case_id); state = self.cockpit.case_state(case_id=case_id)
        if not wf:
            return {'build': self.BUILD, 'case_id': case_id, 'workflow': None, 'current_stage': 'not_started', 'progress_pct': 0, 'cockpit': state, 'opsec': self.sentinel.opsec_state(case_id), 'next_action': 'create_workflow'}
        stage = wf['current_stage']; idx = self.STAGES.index(stage) if stage in self.STAGES else len(self.STAGES)
        accepted = sum(1 for s in self.STAGES if self._accepted_checkpoint(wf['workflow_id'], s))
        open_items = self.db.one("SELECT COUNT(*) n FROM workflow_work_items_245 WHERE workflow_id=? AND status NOT IN ('completed','cancelled')", (wf['workflow_id'],))['n']
        agent_runs = self.db.one('SELECT COUNT(*) n FROM workflow_agent_links_245 WHERE workflow_id=?', (wf['workflow_id'],))['n']
        return {'build': self.BUILD, 'case_id': case_id, 'workflow': wf, 'current_stage': stage, 'progress_pct': 100 if wf['status']=='completed' else round((idx / len(self.STAGES))*100), 'accepted_checkpoints': accepted, 'open_work_items': int(open_items), 'agent_runs': int(agent_runs), 'cockpit': state, 'opsec': self.sentinel.opsec_state(case_id), 'gate_counts': self._gate_counts(case_id), 'automatic_external_action': False}

    def context(self, case_id: str) -> dict[str, Any]:
        d = self.dashboard(case_id)
        return {'investigative_workflow_245': d, 'rules': ['Workflow stages are governance states, not truth states.', 'A checkpoint requires independent review before stage advancement.', 'Agents may support work items but cannot approve workflow gates or external actions.', 'High/critical OPSEC risk blocks advancement and agent support.', 'Training examples remain pending until Build 228 review and qualification.']}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id); e = lambda x: html.escape(str(x or ''), quote=True); wf = d.get('workflow')
        if not wf:
            return f"""<section class='panel'><h2>Investigative Workflow Engine · Build 245</h2><p class='muted'>Intake → Fragestellung → Plan → Research → Evidence → Verification → Analysis → Review → Report. Jeder Übergang braucht einen unabhängig akzeptierten Checkpoint.</p><form method='post' action='/build245/create'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='objective' placeholder='Ermittlungsziel' required><textarea name='primary_question' placeholder='Primäre Fragestellung' required></textarea><input name='owner' value='analyst'><button>Workflow anlegen</button></form></section>"""
        wid, stage = wf['workflow_id'], wf['current_stage']; op = d['opsec']; items = wf['work_items']
        bar = ''.join(f"<span class='badge {'ok' if self.STAGES.index(s)<self.STAGES.index(stage) else ''}'>{e(s)}</span>" for s in self.STAGES)
        item_rows = ''.join(f"<tr><td><code>{e(x['item_id'])}</code></td><td>{e(x['title'])}</td><td>{e(x['priority'])}</td><td>{e(x['owner_role'])}</td><td>{e(x['agent_role'])}</td><td>{e(x['status'])}</td></tr>" for x in items) or "<tr><td colspan='6' class='muted'>Keine Work Items.</td></tr>"
        return f"""<section class='panel'><h2>Investigative Workflow Engine · Build 245</h2><p class='muted'>Verbindlicher Fallprozess mit Human-Checkpoints, Agentenunterstützung, OPSEC-Gates und kontinuierlichem Training.</p><div class='cockpit-status'><span class='badge ok'>Stage {e(stage)}</span><span class='badge'>Progress {e(d['progress_pct'])}%</span><span class='badge'>OPSEC {e(op.get('last_risk_level','low'))}</span><span class='badge'>Open items {e(d['open_work_items'])}</span><span class='badge'>Agent runs {e(d['agent_runs'])}</span></div><div class='cockpit-status'>{bar}</div>
        <div class='grid'><div class='card'><h3>Checkpoint · {e(stage)}</h3><form method='post' action='/build245/checkpoint'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='workflow_id' value='{e(wid)}'><input type='hidden' name='stage' value='{e(stage)}'><textarea name='summary' placeholder='Was ist in dieser Phase belastbar erreicht, was bleibt offen?' required></textarea><input name='related_refs' placeholder='Evidence-/Claim-IDs, kommagetrennt'><input name='quality_score' value='0.8'><button>Checkpoint speichern</button></form><p class='muted'>Danach unabhängiges Review erforderlich.</p></div>
        <div class='card'><h3>Phase weiterführen</h3><form method='post' action='/build245/advance'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='workflow_id' value='{e(wid)}'><textarea name='rationale'>Accepted checkpoint reviewed; proceed only if evidence and OPSEC gates are satisfied.</textarea><button>Nächste Phase prüfen</button></form><p class='muted'>Kein automatisches Überspringen. High/Critical OPSEC blockiert.</p></div>
        <div class='card'><h3>Work Item</h3><form method='post' action='/build245/work-item'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='workflow_id' value='{e(wid)}'><input name='title' placeholder='Aufgabe' required><textarea name='description' placeholder='Konkreter Prüfschritt' required></textarea><input name='priority' value='60'><input name='owner_role' value='analyst'><select name='agent_role'><option value=''>kein Agent</option><option>planner</option><option>retriever</option><option>source_analyst</option><option>identity_analyst</option><option>verifier</option><option>critic</option><option>reporter</option></select><button>Work Item anlegen</button></form></div>
        <div class='card'><h3>Training</h3><form method='post' action='/build245/training-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte Checkpoints fürs Training</button></form><p class='muted'>Training bleibt pending; keine automatische Modell- oder Policy-Aktivierung.</p></div></div>
        <div class='card'><h3>Work Items</h3><table><thead><tr><th>ID</th><th>Aufgabe</th><th>Prio</th><th>Owner</th><th>Agent</th><th>Status</th></tr></thead><tbody>{item_rows}</tbody></table></div></section>"""
