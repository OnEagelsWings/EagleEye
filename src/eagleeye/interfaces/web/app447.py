from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app446 import create_workspace_app446


def create_workspace_app447(*, base_dir=None):
    app = create_workspace_app446(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build447
    app.title = "EagleEye Build 447.0"
    app.version = "447.0"

    old = next(
        (
            r.endpoint
            for r in app.router.routes
            if getattr(r, "path", None) == "/health"
            and "GET" in set(getattr(r, "methods", set()) or set())
        ),
        None,
    )
    app.router.routes[:] = [
        r for r in app.router.routes
        if not (
            getattr(r, "path", None) == "/health"
            and "GET" in set(getattr(r, "methods", set()) or set())
        )
    ]

    def auth(req):
        import hashlib
        fingerprint = hashlib.sha256(
            "|".join(
                (
                    req.headers.get("user-agent", ""),
                    req.headers.get("accept-language", ""),
                    req.client.host if req.client else "",
                )
            ).encode()
        ).hexdigest()
        identity = team.validate_session(
            req.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def case_auth(req, case_id, capability="case.read"):
        identity = auth(req)
        try:
            ctx.team_governance_359.authorize(
                identity,
                case_id=str(case_id),
                capability=capability,
                object_type="evidence_claims_dossier_447",
                object_id=str(case_id),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return identity

    def same_origin(req):
        site = str(req.headers.get("sec-fetch-site") or "").strip().lower()
        if site and site not in {"same-origin", "none"}:
            raise HTTPException(403, "Cross-origin mutation blocked")
        origin = str(req.headers.get("origin") or "").strip().rstrip("/")
        if origin:
            expected = (
                str(req.url.scheme) + "://" + str(req.headers.get("host") or "")
            ).rstrip("/")
            if origin != expected:
                raise HTTPException(403, "Cross-origin mutation blocked")

    @app.get("/health")
    def health():
        payload = dict(old() if callable(old) else {"ok": True})
        status = ctx.build447.evidence_claims_dossier_status_447()
        payload.update(
            {
                "build": "447.0",
                "phase": 20,
                "phase20_builds_completed": 7,
                "evidence_to_claims_to_dossier_closed": True,
                "living_dossier_revisions": True,
                "docx_export": True,
                "pdf_export": True,
                "case_package_export": True,
                "automatic_truth_determination": False,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build447/status")
    def status447(request: Request):
        auth(request)
        return ctx.build447.evidence_claims_dossier_status_447()

    @app.get("/api/build447/cases/{case_id}/evidence")
    def evidence447(case_id: str, request: Request):
        case_auth(request, case_id, "dossier.read")
        return {"items": ctx.build447.case_evidence_447(case_id)}

    @app.post("/api/build447/cases/{case_id}/evidence/sync")
    def sync447(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "dossier.write")
        try:
            return ctx.build447.sync_case_evidence_447(identity=identity, case_id=case_id)
        except (PermissionError, RuntimeError, ValueError) as exc:
            raise HTTPException(409 if isinstance(exc, RuntimeError) else 403 if isinstance(exc, PermissionError) else 400, str(exc))

    @app.post("/api/build447/evidence/{evidence_id}/review")
    async def review_evidence447(evidence_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            item = ctx.evidence_claims_dossier_447.evidence(evidence_id)
            case_auth(request, item["case_id"], "source.review")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build447.review_evidence_447(
                identity=identity,
                evidence_id=evidence_id,
                decision=body.get("decision", ""),
                note=body.get("note", ""),
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/build447/cases/{case_id}/claims")
    def claims447(case_id: str, request: Request):
        case_auth(request, case_id, "dossier.read")
        return {"items": ctx.build447.case_claims_447(case_id)}

    @app.post("/api/build447/cases/{case_id}/claims")
    async def create_claim447(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "dossier.write")
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
        try:
            return ctx.build447.propose_claim_447(
                identity=identity,
                case_id=case_id,
                statement=body.get("statement", ""),
                support_evidence_ids=body.get("support_evidence_ids") or [],
                contradiction_evidence_ids=body.get("contradiction_evidence_ids") or [],
                context_evidence_ids=body.get("context_evidence_ids") or [],
                uncertainty_note=body.get("uncertainty_note", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build447/claims/{claim_id}/review")
    async def review_claim447(claim_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            claim = ctx.evidence_claims_dossier_447.claim(claim_id)
            case_auth(request, claim["case_id"], "dossier.review")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build447.review_claim_447(
                identity=identity,
                claim_id=claim_id,
                decision=body.get("decision", ""),
                note=body.get("note", ""),
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/build447/cases/{case_id}/dossiers")
    def dossiers447(case_id: str, request: Request):
        case_auth(request, case_id, "dossier.read")
        return {"items": ctx.build447.case_dossiers_447(case_id)}

    @app.post("/api/build447/cases/{case_id}/dossiers")
    async def build_dossier447(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "dossier.write")
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
        try:
            return ctx.build447.build_dossier_447(
                identity=identity,
                case_id=case_id,
                title=body.get("title", ""),
                loop_id=body.get("loop_id", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409 if isinstance(exc, RuntimeError) else 400, str(exc))

    @app.post("/api/build447/dossiers/{revision_id}/review")
    async def review_dossier447(revision_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            dossier = ctx.evidence_claims_dossier_447.dossier(revision_id)
            case_auth(request, dossier["case_id"], "dossier.review")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build447.review_dossier_447(
                identity=identity,
                revision_id=revision_id,
                decision=body.get("decision", ""),
                note=body.get("note", ""),
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build447/dossiers/{revision_id}/export")
    async def export447(revision_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            dossier = ctx.evidence_claims_dossier_447.dossier(revision_id)
            case_auth(request, dossier["case_id"], "dossier.export.execute")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build447.export_dossier_447(
                identity=identity,
                revision_id=revision_id,
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build447/cases/{case_id}/selftest")
    def selftest447(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "dossier.write")
        try:
            return ctx.build447.run_evidence_claims_dossier_case_selftest(
                identity=identity,
                case_id=case_id,
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc))

    return app


create_app = create_workspace_app447
