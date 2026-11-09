"""HTTP-API und Auslieferung der Weboberfläche."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Body, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .db import Database
from .demo import seed_demo
from .dossier import build_dossier, build_poster, render_graph_png, safe_filename
from .service import (CASE_TYPES, ENTITY_TYPES, EVENT_KINDS, IDENTIFIER_KINDS, MISSING_FIELDS, PERSON_FIELDS, RELATIONS,
                      RISK_FACTORS, Invalid, NotFound, Platform)
from .sources import Http

STATIC = Path(__file__).parent / "static"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def default_data_dir() -> Path:
    env = os.environ.get("EAGLEEYE_PERSONOSINT_DATA")
    if env:
        return Path(env)
    base = Path(os.environ.get("APPDATA") or Path.home() / ".local" / "share")
    return base / "EagleEye-PersonOSINT"


def _download(content: bytes, filename: str, media: str) -> Response:
    ascii_name = filename.encode("ascii", "replace").decode().replace("?", "_")
    return Response(content, media_type=media, headers={
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"})


def create_app(data_dir: Path | str | None = None, http: Http | None = None, auto_geocode: bool = True,
               allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")) -> FastAPI:
    data = Path(data_dir) if data_dir else default_data_dir()
    db = Database(data / "personosint.sqlite3")
    p = Platform(db, data, http=http, auto_geocode=auto_geocode)
    app = FastAPI(title="EagleEye PersonOSINT", version=__version__, docs_url="/api/docs", redoc_url=None)
    app.state.platform = p
    extra_hosts = tuple(h.strip() for h in os.environ.get("EAGLEEYE_ALLOWED_HOSTS", "").split(",") if h.strip())

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in allowed_hosts + extra_hosts:
            return JSONResponse({"detail": "Unzulässiger Host"}, status_code=400)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path.startswith("/api/") \
                and request.headers.get("x-requested-with") != "EagleEye":
            return JSONResponse({"detail": "Anfrage ohne gültige Client-Kennung abgelehnt"}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Invalid)
    async def _inv(_: Request, exc: Invalid):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    # ---------------------------------------------------------------- Meta
    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {"version": __version__, "case_types": CASE_TYPES, "entity_types": ENTITY_TYPES, "identifier_kinds": IDENTIFIER_KINDS,
                "relations": RELATIONS, "event_kinds": EVENT_KINDS,
                "risk_factors": {k: v[0] for k, v in RISK_FACTORS.items() if k not in {"kind", "jugendlich", "senior"}},
                "person_fields": PERSON_FIELDS, "missing_fields": MISSING_FIELDS, "sources": p.available_sources(),
                "data_dir": str(data)}

    # ---------------------------------------------------------------- Fälle
    @app.get("/api/cases")
    def cases() -> list[dict]:
        return p.list_cases()

    @app.post("/api/cases", status_code=201)
    def create_case(payload: dict = Body(...)) -> dict:
        return p.create_case(payload)

    @app.post("/api/demo", status_code=201)
    def demo() -> dict:
        return p.get_case(seed_demo(p))

    @app.get("/api/cases/{cid}")
    def get_case(cid: int) -> dict:
        return p.get_case(cid)

    @app.patch("/api/cases/{cid}")
    def update_case(cid: int, payload: dict = Body(...)) -> dict:
        return p.update_case(cid, payload)

    @app.delete("/api/cases/{cid}", status_code=204)
    def delete_case(cid: int) -> Response:
        p.delete_case(cid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/overview")
    def overview(cid: int) -> dict:
        return p.overview(cid)

    # ---------------------------------------------------------------- Einträge
    @app.get("/api/cases/{cid}/entities")
    def entities(cid: int) -> list[dict]:
        return p.list_entities(cid)

    @app.post("/api/cases/{cid}/entities", status_code=201)
    def create_entity(cid: int, payload: dict = Body(...)) -> dict:
        return p.create_entity(cid, payload)

    @app.get("/api/cases/{cid}/entities/{eid}")
    def get_entity(cid: int, eid: int) -> dict:
        return p.get_entity(cid, eid)

    @app.patch("/api/cases/{cid}/entities/{eid}")
    def update_entity(cid: int, eid: int, payload: dict = Body(...)) -> dict:
        return p.update_entity(cid, eid, payload)

    @app.delete("/api/cases/{cid}/entities/{eid}", status_code=204)
    def delete_entity(cid: int, eid: int) -> Response:
        p.delete_entity(cid, eid)
        return Response(status_code=204)

    @app.post("/api/cases/{cid}/entities/{eid}/photo")
    async def upload_photo(cid: int, eid: int, file: UploadFile = File(...)) -> dict:
        return p.set_photo(cid, eid, await file.read(), file.filename or "foto.jpg")

    @app.get("/api/cases/{cid}/entities/{eid}/photo")
    def photo(cid: int, eid: int):
        path = p.photo_path(cid, eid)
        if not path:
            raise NotFound("Kein Foto vorhanden.")
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    @app.post("/api/cases/{cid}/entities/{eid}/identifiers", status_code=201)
    def add_identifier(cid: int, eid: int, payload: dict = Body(...)) -> dict:
        return p.add_identifier(cid, eid, payload)

    @app.delete("/api/cases/{cid}/identifiers/{iid}", status_code=204)
    def delete_identifier(cid: int, iid: int) -> Response:
        p.delete_identifier(cid, iid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/entities/{eid}/research-links")
    def research(cid: int, eid: int) -> list[dict]:
        return p.links_for(cid, eid)

    # ---------------------------------------------------------------- Suche & Treffer
    @app.post("/api/cases/{cid}/search")
    def search(cid: int, payload: dict = Body(...)) -> dict:
        return p.run_search(cid, int(payload.get("entity_id") or 0), payload.get("sources") or None)

    @app.get("/api/cases/{cid}/searches")
    def searches(cid: int) -> list[dict]:
        return p.list_searches(cid)

    @app.get("/api/cases/{cid}/findings")
    def findings(cid: int, status: str | None = None, entity_id: int | None = None) -> list[dict]:
        return p.list_findings(cid, status, entity_id)

    @app.post("/api/cases/{cid}/findings", status_code=201)
    def manual_finding(cid: int, payload: dict = Body(...)) -> dict:
        return p.add_manual_finding(cid, payload)

    @app.patch("/api/cases/{cid}/findings/{fid}")
    def review(cid: int, fid: int, payload: dict = Body(...)) -> dict:
        return p.review_finding(cid, fid, payload)

    # ---------------------------------------------------------------- Verbindungen
    @app.get("/api/cases/{cid}/links")
    def links(cid: int) -> list[dict]:
        return p.list_links(cid)

    @app.post("/api/cases/{cid}/links", status_code=201)
    def create_link(cid: int, payload: dict = Body(...)) -> dict:
        return p.create_link(cid, payload)

    @app.delete("/api/cases/{cid}/links/{lid}", status_code=204)
    def delete_link(cid: int, lid: int) -> Response:
        p.delete_link(cid, lid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/graph")
    def graph(cid: int, min_confidence: int = 0) -> dict:
        return p.graph(cid, min_confidence)

    @app.get("/api/cases/{cid}/graph.png")
    def graph_png(cid: int, min_confidence: int = 0) -> Response:
        gr = p.graph(cid, min_confidence)
        subj = p.subject(cid)
        return _download(render_graph_png(gr, highlight={subj["id"]} if subj else None),
                         f"Netzwerk_{safe_filename(p.get_case(cid)['reference'])}.png", "image/png")

    @app.get("/api/cases/{cid}/paths")
    def paths(cid: int, a: int, b: int, max_len: int = 5) -> dict:
        return p.find_paths(cid, a, b, max(1, min(max_len, 8)))

    @app.get("/api/cases/{cid}/suggestions")
    def suggestions(cid: int) -> list[dict]:
        return p.suggestions(cid)

    # ---------------------------------------------------------------- Zeitleiste & Aufgaben
    @app.get("/api/cases/{cid}/events")
    def events(cid: int) -> list[dict]:
        return p.list_events(cid)

    @app.post("/api/cases/{cid}/events", status_code=201)
    def create_event(cid: int, payload: dict = Body(...)) -> dict:
        return p.create_event(cid, payload)

    @app.delete("/api/cases/{cid}/events/{evid}", status_code=204)
    def delete_event(cid: int, evid: int) -> Response:
        p.delete_event(cid, evid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/tasks")
    def tasks(cid: int) -> list[dict]:
        return p.list_tasks(cid)

    @app.post("/api/cases/{cid}/tasks", status_code=201)
    def create_task(cid: int, payload: dict = Body(...)) -> dict:
        return p.create_task(cid, payload)

    @app.post("/api/cases/{cid}/tasks/generate")
    def generate_tasks(cid: int) -> list[dict]:
        return p.generate_tasks(cid)

    @app.patch("/api/cases/{cid}/tasks/{tid}")
    def update_task(cid: int, tid: int, payload: dict = Body(...)) -> dict:
        return p.update_task(cid, tid, payload)

    @app.delete("/api/cases/{cid}/tasks/{tid}", status_code=204)
    def delete_task(cid: int, tid: int) -> Response:
        p.delete_task(cid, tid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/audit")
    def audit(cid: int) -> list[dict]:
        return p.audit(cid)

    # ---------------------------------------------------------------- Export
    @app.get("/api/cases/{cid}/export/dossier.docx")
    def export_dossier(cid: int, include_unreviewed: bool = False, include_audit: bool = True, include_graph: bool = True) -> Response:
        case = p.get_case(cid)
        subj = p.subject(cid)
        content = build_dossier(p, cid, {"include_unreviewed": include_unreviewed, "include_audit": include_audit, "include_graph": include_graph})
        name = f"Dossier_{safe_filename(subj['label'] if subj else case['title'])}_{case['reference']}.docx"
        return _download(content, name, DOCX)

    @app.get("/api/cases/{cid}/export/poster.docx")
    def export_poster(cid: int) -> Response:
        case = p.get_case(cid)
        try:
            content = build_poster(p, cid)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        subj = p.subject(cid)
        return _download(content, f"Suchplakat_{safe_filename(subj['label'] if subj else case['title'])}.docx", DOCX)

    @app.get("/api/cases/{cid}/export/case.json")
    def export_json(cid: int) -> Response:
        payload = {"case": p.get_case(cid), "entities": p.list_entities(cid), "links": p.list_links(cid),
                   "findings": p.list_findings(cid), "events": p.list_events(cid), "tasks": p.list_tasks(cid), "audit": p.audit(cid)}
        p.log(cid, "Datenexport (JSON)", "Vollständiger Fallexport")
        return _download(json.dumps(payload, ensure_ascii=False, indent=2).encode(), f"Fall_{p.get_case(cid)['reference']}.json", "application/json")

    # ---------------------------------------------------------------- Oberfläche
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    return app
