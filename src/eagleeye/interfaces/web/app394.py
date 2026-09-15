from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app393 import create_workspace_app393
from eagleeye_pro.phase17.discussion_revision394 import (
    CONFIRM_REVISION_REVIEW,
    CONFIRM_APPLY_REVISION,
    CONFIRM_KERNEL_ADMISSION,
)


def create_workspace_app394(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app393(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    _ = ctx.build394
    app.title = 'EagleEye Intelligence Platform – Build 394.0 Investigator Discussion & Versioned Revision'
    app.version = '394.0'
    base_health = next((r.endpoint for r in app.router.routes if getattr(r, 'path', None) == '/health' and 'GET' in set(getattr(r, 'methods', set()) or set())), None)
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/health' and 'GET' in set(getattr(r, 'methods', set()) or set()))]

    def fp(request: Request) -> str:
        material = '|'.join((request.headers.get('user-agent', ''), request.headers.get('accept-language', ''), (request.client.host if request.client else '')))
        return hashlib.sha256(material.encode()).hexdigest()

    def auth(request: Request) -> dict[str, Any]:
        ident = team_identity.validate_session(request.cookies.get(COOKIE, ''), client_fingerprint=fp(request), touch=True)
        if not ident:
            raise HTTPException(401, 'Anmeldung erforderlich oder Sitzung abgelaufen')
        return ident

    def caseauth(request: Request, case_id: str, capability: str = 'case.read') -> dict[str, Any]:
        ident = auth(request)
        try:
            ctx.build380.authorize(ident, case_id=case_id, capability=capability, object_type='phase17_v394', object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return ident

    @app.get('/health')
    def health394():
        prev = dict(base_health() if callable(base_health) else {'ok': True})
        prev.update({
            'build': '394.0', 'phase17_builds_completed': 14, 'phase17_integrated': True,
            'investigator_discussion_workspace': True, 'versioned_revision_lineage': True,
            'automatic_upstream_mutation': False, 'automatic_go_issuance': False,
            'execution_authority': False, 'truth_probability': False,
        })
        return prev

    @app.get('/api/build394/phase17-status')
    def status(request: Request):
        auth(request)
        return ctx.build394.phase17_status()

    @app.post('/api/cases/{case_id}/phase17/discussion/sessions')
    async def create_session(case_id: str, request: Request):
        ident = caseauth(request, case_id, 'dossier.write'); body = await request.json()
        try:
            return ctx.build394.create_investigator_discussion(case_id=case_id, dialogue_session_id=str(body.get('dialogue_session_id') or ''), identity=ident)
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.get('/api/cases/{case_id}/phase17/discussion/sessions/{discussion_id}')
    def get_session(case_id: str, discussion_id: str, request: Request):
        ident = caseauth(request, case_id, 'case.read')
        try: return ctx.build394.investigator_discussion(case_id=case_id, discussion_id=discussion_id, identity=ident)
        except KeyError: raise HTTPException(404, 'Discussion session not found')

    @app.post('/api/cases/{case_id}/phase17/discussion/sessions/{discussion_id}/turns')
    async def discuss(case_id: str, discussion_id: str, request: Request):
        ident = caseauth(request, case_id, 'dossier.write'); body = await request.json()
        try:
            return ctx.build394.discuss_case(
                case_id=case_id, discussion_id=discussion_id, prompt=str(body.get('prompt') or ''), identity=ident,
                turn_type=str(body.get('turn_type') or 'argument'), parent_turn_id=str(body.get('parent_turn_id') or ''),
                object_refs=list(body.get('object_refs') or []),
            )
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.post('/api/cases/{case_id}/phase17/discussion/sessions/{discussion_id}/compare-hypotheses')
    async def compare(case_id: str, discussion_id: str, request: Request):
        ident = caseauth(request, case_id, 'case.read'); body = await request.json()
        try: return ctx.build394.compare_discussion_hypotheses(case_id=case_id, discussion_id=discussion_id, hypothesis_ids=list(body.get('hypothesis_ids') or []), identity=ident)
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.post('/api/cases/{case_id}/phase17/discussion/sessions/{discussion_id}/revision-proposals')
    async def propose_revision(case_id: str, discussion_id: str, request: Request):
        ident = caseauth(request, case_id, 'dossier.write'); body = await request.json()
        try:
            return ctx.build394.create_versioned_revision_proposal(
                case_id=case_id, discussion_id=discussion_id, target_type=str(body.get('target_type') or ''),
                target_id=str(body.get('target_id') or ''), patch=dict(body.get('patch') or {}), rationale=str(body.get('rationale') or ''),
                identity=ident, source_turn_id=str(body.get('source_turn_id') or ''),
                source_challenge_proposal_id=str(body.get('source_challenge_proposal_id') or ''),
            )
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.post('/api/cases/{case_id}/phase17/discussion/revision-proposals/{proposal_id}/review')
    async def review_revision(case_id: str, proposal_id: str, request: Request):
        ident = caseauth(request, case_id, 'dossier.write'); body = await request.json()
        try:
            return ctx.build394.review_versioned_revision(case_id=case_id, proposal_id=proposal_id, identity=ident, disposition=str(body.get('disposition') or ''), rationale=str(body.get('rationale') or ''), confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.post('/api/cases/{case_id}/phase17/discussion/revision-proposals/{proposal_id}/apply')
    async def apply_revision(case_id: str, proposal_id: str, request: Request):
        ident = caseauth(request, case_id, 'dossier.write'); body = await request.json()
        try: return ctx.build394.apply_versioned_revision(case_id=case_id, proposal_id=proposal_id, identity=ident, confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.post('/api/cases/{case_id}/phase17/discussion/versions/{version_id}/kernel')
    async def kernel(case_id: str, version_id: str, request: Request):
        ident = caseauth(request, case_id, 'dossier.write'); body = await request.json()
        try: return ctx.build394.admit_versioned_revision_to_kernel(case_id=case_id, version_id=version_id, identity=ident, confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc: raise HTTPException(400, str(exc))

    @app.get('/api/cases/{case_id}/phase17/ai-discussion-feed')
    def feed(case_id: str, request: Request):
        ident = caseauth(request, case_id, 'case.read')
        return ctx.build394.ai_investigator_discussion_feed(case_id=case_id, identity=ident)

    return app
