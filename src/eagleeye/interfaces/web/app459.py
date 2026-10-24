from __future__ import annotations

import hashlib
import re
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app458 import create_workspace_app458
from .app448 import COOKIE, render_workspace
from .app364 import CSRF_COOKIE
from .app449 import _drop


def visible_operational_cases(ctx,identity):
    marked={str(row['case_id']) for row in ctx.db.all('SELECT case_id FROM phase20_qualification_case_450')}
    return [case for case in ctx.team_governance_359.visible_cases(identity)
            if str(case['case_id']) not in marked]


def create_workspace_app459(*, base_dir=None, workspace_build="459.0", workspace_title="Investigator Navigation"):
    """Build 459: case-scoped documents in the primary investigator navigation."""
    app = create_workspace_app458(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    app.title = f"EagleEye Build {workspace_build} — {workspace_title}"
    app.version = workspace_build
    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health459():
        integrity = bool(ctx.build458.build458_status().get("integrity_valid", False))
        return {"ok": True, "build": workspace_build, "status": "ok" if integrity else "hold",
                "integrity_valid": integrity, "production_release_ready": False,
                "next_checkpoint": "460.0" if workspace_build == "459.0" else ("470.0" if workspace_build == "466.0" else "465.0")}


    @app.middleware("http")
    async def operational_case_destination(request: Request, call_next):
        # Keep the canonical POST /cases authorization and CSRF boundary.
        response = await call_next(request)
        if request.method == "POST" and request.url.path == "/cases" and response.status_code == 303:
            match = re.fullmatch(r"/cases/([A-Za-z0-9_-]+)", response.headers.get("location", ""))
            if match:
                response.headers["location"] = "/?" + urlencode({"case_id": match.group(1)})
                response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/new-case", response_class=HTMLResponse)
    def new_operational_case(request: Request):
        """Usable, authenticated first-case entrypoint; no test fixture creation."""
        fingerprint = hashlib.sha256("|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        )).encode()).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        csrf = str(request.cookies.get(CSRF_COOKIE, "")).strip()
        if not csrf or not team.csrf_token_valid(identity, csrf):
            raise HTTPException(403, "Sitzungsschutz fehlt. Bitte erneut über den lokalen Launcher anmelden.")
        existing = visible_operational_cases(ctx,identity)
        back = '<a href="/">Zur Fallübersicht</a>' if existing else ""
        page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EagleEye · Neuen Ermittlungsfall anlegen</title>
<style>
body{{font:1rem system-ui, sans-serif;max-width:730px;margin:2rem auto;padding:0 1rem;background:#102137;color:#eff7fb}}
main{{background:#192e47;padding:1.5rem;border-radius:12px;border:1px solid #49627c}}
label{{display:block;margin-top:1rem;font-weight:600}}input,textarea{{box-sizing:border-box;width:100%;padding:.7rem;margin-top:.3rem;border:1px solid #98acc2;border-radius:5px}}
button{{margin-top:1.3rem;padding:.8rem 1.2rem;font-weight:700}}a{{color:#9be9d5}}
.notice{{background:#273e58;border-left:4px solid #ffcb70;padding:.8rem}}
</style></head><body><main><h1>Neuen Ermittlungsfall anlegen</h1>
<p>Lege einen regulären, fallbezogenen Arbeitsbereich an. Hier speicherst du deinen Rechercheauftrag und die zugehörigen Belege.</p>
<p class="notice"><strong>Entwicklungsstand:</strong> Noch keine Produktivfreigabe. Bis zur unabhängigen
Sicherheits- und Wiederherstellungsprüfung nur öffentliche oder synthetische, unkritische
Quellen verarbeiten. KI-Ausgaben bleiben prüfpflichtige Entwürfe.</p>
<form method="post" action="/cases">
<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">
<label for="title">Falltitel</label><input id="title" name="title" required maxlength="200">
<label for="client">Auftraggeber (optional)</label><input id="client" name="client" maxlength="200">
<label for="purpose">Rechercheauftrag / Zweck</label><textarea id="purpose" name="purpose" required rows="4"></textarea>
<label for="legal_basis">Rechtsgrundlage / Berechtigung</label>
<textarea id="legal_basis" name="legal_basis" required rows="3"></textarea>
<button type="submit">Fall anlegen</button>
</form><p>Nach dem Anlegen öffnet sich dein Arbeitsbereich mit Dokumentimport, öffentlichen
Quellen und Graph.</p>
<p>{back}</p></main></body></html>"""
        return HTMLResponse(page, headers={"Cache-Control": "no-store"})

    @app.get("/", response_class=HTMLResponse)
    def investigator_home(request: Request, view: str = "overview", case_id: str = ""):
        fingerprint = hashlib.sha256("|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        )).encode()).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = visible_operational_cases(ctx,identity)
        selected = next((item for item in cases if str(item.get("case_id")) == str(case_id)), None)
        if selected is None:
            selected = cases[0] if cases else None
        if selected is None:
            return RedirectResponse("/new-case", status_code=303)
        selected_id = str(selected["case_id"])
        snapshot = ctx.workspace_reliability_457.snapshot(identity=identity, case_id=selected_id)
        snapshot = dict(snapshot, workspace_build=workspace_build)
        audits = ctx.investigator_workspace_448.audit_history(selected_id, limit=15)
        html = render_workspace(snapshot, view=view, cases=cases, audits=audits, ui_name_override=workspace_title)
        link = (
            '<a href="/new-case">Neuen Fall anlegen</a>'
            '<a href="/documents458?'
            + escape(urlencode({"case_id": selected_id}), quote=True)
            + '">Dokumente &amp; Quellenprüfung</a>'
        )
        if workspace_build in {"461.0", "462.0", "463.0", "464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            guide_url = "/workflow461?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(guide_url, quote=True) + '">Ermittlungsweg · Anleitung</a>'
        if workspace_build in {"462.0", "463.0", "464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            graph_url = "/entities462?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(graph_url, quote=True) + '">Entitäten &amp; Beziehungen</a>'
        if workspace_build in {"463.0", "464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            proof_url = "/source-links463?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(proof_url, quote=True) + '">Dokumentgebundene Beziehungen</a>'
        if workspace_build in {"464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            graph_url = "/graph464?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(graph_url, quote=True) + '">Netzwerkanalyse</a>'
        if workspace_build in {"465.0","466.0","467.0", "468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            review_url = "/review465?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(review_url,quote=True) + '">Integrierte Fallprüfung</a>'
        if workspace_build in {"466.0","467.0", "468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            url = "/provenance466?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(url, quote=True) + '">Belegherkunft &amp; Integrität</a>'
        if workspace_build in {"468.0", "469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            link += '<a href="/benchmark468">Messprotokoll</a>'
        if workspace_build in {"469.0", "470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            source_url = "/collect469?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(source_url, quote=True) + '">Öffentliche Quellen</a>'
        if workspace_build in {"470.0", "471.0", "472.0", "473.0", "474.0", "475.0", "476.0"}:
            readiness_url = "/readiness470?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(readiness_url, quote=True) + '">Qualitätsprüfung 470</a>'
        if int(workspace_build.split(".")[0]) >= 471:
            ai_url = "/assistant471?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(ai_url, quote=True) + '">Lokaler KI-Ermittler</a>'
        if int(workspace_build.split(".")[0]) >= 475:
            checkpoint_url = "/ai-checkpoint475?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(checkpoint_url, quote=True) + '">KI-Prüfpunkt 475</a>'
        html = html.replace("</nav>", link + "</nav>", 1)
        return HTMLResponse(html)

    return app


create_app = create_workspace_app459
