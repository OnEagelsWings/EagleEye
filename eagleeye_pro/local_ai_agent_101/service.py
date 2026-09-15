from __future__ import annotations
import re
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

OVERCLAIM_RE = re.compile(r"\b(definitiv|bewiesen|ist sicher|eindeutig|schuldig|gehört zu|belongs to|confirmed)\b", re.I)
IDENTIFIER_RE = re.compile(r"([\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://[^\s<>\"')]+|@[A-Za-z0-9_]{3,})")

class LocalAIAgent101Service:
    """Build 101.0: local, controlled investigation assistant foundation.

    This is intentionally not an autonomous internet agent. It is a local analyst helper that
    reads only the local case database and produces suggestions, checklists and warnings.
    It never upgrades candidates to claims and never confirms identity.
    """
    def __init__(self, db: Database, audit: AuditService, *, security: Any=None, graph: Any=None, evidence: Any=None, claims: Any=None, reliability: Any=None):
        self.db = db
        self.audit = audit
        self.security = security
        self.graph = graph
        self.evidence = evidence
        self.claims = claims
        self.reliability = reliability
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS local_ai_agent_101_runs(
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, assist_type TEXT NOT NULL,
          status TEXT NOT NULL, prompt TEXT DEFAULT '', output_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_localai101_case ON local_ai_agent_101_runs(case_id, created_at);
        ''')
        self.db.conn.commit()

    def status(self) -> Dict[str, Any]:
        return {
            'mode': 'local_controlled_assistant_foundation',
            'external_model': 'not_required',
            'autonomous_web_access': False,
            'may_confirm_identity': False,
            'may_create_claims': False,
            'allowed_outputs': ['triage','next_steps','counter_evidence_questions','query_suggestions','report_wording_draft_with_uncertainty'],
            'blocked_outputs': ['final_identity_confirmation','guilt_claim','private_account_access','captcha_or_login_bypass','doxxing_export']
        }

    def build_case_context(self, case_id: str) -> Dict[str, Any]:
        ctx = {'case_id': case_id}
        for table, key in [
            ('pasted_findings_91','pasted_findings'), ('local_evidence_items_75','evidence_items'),
            ('investigation_graph_nodes_68','graph_nodes'), ('investigation_graph_edges_68','graph_edges'),
            ('claims_v3_80','claims'), ('source_reliability_98','source_ratings'),
            ('counter_evidence_79','counter_evidence')]:
            try:
                ctx[key] = self.db.all(f'SELECT * FROM {table} WHERE case_id=? ORDER BY rowid DESC LIMIT 50', [case_id])
            except Exception:
                ctx[key] = []
        try:
            ctx['security'] = self.security.assess_case_security(case_id, scope='local_ai_context_101') if self.security else None
        except Exception as e:
            ctx['security'] = {'decision':'review_required','error':str(e)}
        return ctx

    def triage_pasted_finding(self, case_id: str, paste_id: str) -> Dict[str, Any]:
        r = self.db.one('SELECT * FROM pasted_findings_91 WHERE paste_id=? AND case_id=?', [paste_id, case_id])
        if not r:
            raise KeyError(paste_id)
        text = (r.get('content_excerpt') or '')[:4000]
        identifiers = IDENTIFIER_RE.findall(text)
        warnings = []
        if not r.get('canonical_url'):
            warnings.append('missing_source_url')
        if OVERCLAIM_RE.search(text):
            warnings.append('overclaiming_language_detected')
        if len(text.strip()) < 30:
            warnings.append('thin_context')
        suggestions = [
            'Quelle/Capture prüfen, bevor daraus ein Claim entsteht.',
            'Identitätsfit separat prüfen: Name, Ort, Zeit, Rolle, Username/E-Mail-Kontext.',
            'Mindestens einen Gegenbeleg-Check formulieren: Welche alternative Person/Quelle könnte gemeint sein?',
        ]
        if identifiers:
            suggestions.append('Gefundene Identifier nur als Pivot-Kandidaten verwenden, nicht als Beweis.')
        out = {'paste_id': paste_id, 'classification': 'candidate_not_claim', 'identifiers_found': identifiers[:20], 'warnings': warnings, 'suggestions': suggestions, 'next_action': 'review_board_or_identity_resolution'}
        self._store(case_id, 'paste_triage', 'triage pasted public finding', out)
        return out

    def suggest_next_steps(self, case_id: str, prompt: str='') -> Dict[str, Any]:
        ctx = self.build_case_context(case_id)
        steps: List[str] = []
        if not ctx.get('pasted_findings'):
            steps.append('Zuerst öffentliche URL/Text-Funde über Intake Console aufnehmen.')
        if ctx.get('pasted_findings') and not ctx.get('evidence_items'):
            steps.append('Evidence Vault prüfen: Für jeden Fund sollte ein Hash-Artefakt existieren.')
        if ctx.get('graph_edges'):
            unreviewed = [e for e in ctx['graph_edges'] if (e.get('review_status') or '').lower() in {'candidate','unreviewed',''}]
            if unreviewed:
                steps.append(f'{len(unreviewed)} Graph-Kanten reviewen, bevor sie in Claims eingehen.')
        if not ctx.get('source_ratings'):
            steps.append('Quellenverlässlichkeit bewerten: source_reliability_98 für zentrale Quellen ausführen.')
        if not ctx.get('claims'):
            steps.append('Noch keine Claims erstellen, bis Identitätsfit und Quellenlage geprüft sind.')
        sec = ctx.get('security') or {}
        if sec.get('decision') in {'blocked','critical_review_required','review_required'}:
            steps.append('Security Complex Warnungen bearbeiten, bevor Export/Report erfolgt.')
        if not steps:
            steps.append('Review Board öffnen und stärkste Claims gegen Counter-Evidence prüfen.')
        out = {'case_id': case_id, 'prompt': prompt, 'mode': 'suggestions_only', 'next_steps': steps, 'context_counts': {k: len(v) for k,v in ctx.items() if isinstance(v, list)}}
        self._store(case_id, 'next_steps', prompt, out)
        return out

    def _store(self, case_id: str, assist_type: str, prompt: str, out: Dict[str,Any]) -> Dict[str, Any]:
        run_id = new_id('lai101')
        self.db.execute('INSERT INTO local_ai_agent_101_runs(run_id,case_id,assist_type,status,prompt,output_json,created_at) VALUES(?,?,?,?,?,?,?)', [run_id,case_id,assist_type,'suggestions_only',prompt,dumps(out),now_ts()])
        self.audit.log('suggest', 'local_ai_agent_101', run_id, case_id, {'assist_type':assist_type, 'mode':'suggestions_only'})
        out['run_id'] = run_id
        return out

    def list_runs(self, case_id: str, limit: int=20) -> Dict[str, Any]:
        rows = self.db.all('SELECT * FROM local_ai_agent_101_runs WHERE case_id=? ORDER BY created_at DESC LIMIT ?', [case_id, int(limit)])
        for r in rows:
            r['output'] = loads(r.pop('output_json','{}'), {})
        return {'count': len(rows), 'runs': rows}
