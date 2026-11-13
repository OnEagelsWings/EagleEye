"""Build 492 UI: readable error pages for browser navigation.

Only requests that ask for a page (``Accept: text/html``, not an API path and not a
``fetch()`` call) get an HTML page in the shared layout. Everything else keeps the
JSON error body, so API clients and scripts are unaffected. Status codes and headers
(including the security middleware's headers) are preserved.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode, urlsplit

from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .operations476 import page

TITLES = {
    400: "Anfrage nicht verständlich", 401: "Bitte anmelden", 403: "Kein Zugriff",
    404: "Nicht gefunden", 405: "Aktion nicht erlaubt", 409: "Der Stand hat sich geändert",
    413: "Zu groß", 415: "Dateiart nicht unterstützt", 422: "Bitte Eingaben prüfen",
    429: "Zu viele Anfragen",
}
HINTS = {
    401: "Deine Sitzung ist abgelaufen oder du bist nicht angemeldet.",
    403: "Für diese Aktion fehlt dir in diesem Fall die Berechtigung, oder der Formularschutz ist abgelaufen. "
         "Seite neu laden und erneut versuchen.",
    404: "Das Gesuchte gibt es nicht (mehr) oder es gehört zu einem anderen Fall.",
    409: "Während du gearbeitet hast, wurde etwas verändert. Seite neu laden, den aktuellen Stand prüfen und erneut versuchen.",
    413: "Die Eingabe oder Datei ist größer als erlaubt.",
    422: "Eine Eingabe fehlt oder passt nicht. Bitte zurückgehen und die Angaben prüfen.",
    429: "Bitte kurz warten und dann erneut versuchen.",
}


def wants_html(request) -> bool:
    if request.url.path.startswith(("/api/", "/assets/")) or request.url.path.endswith((".js", ".json", ".md", ".gexf")):
        return False
    if request.headers.get("sec-fetch-mode", "").lower() == "cors":  # fetch()/XHR from our own scripts
        return False
    return "text/html" in request.headers.get("accept", "").lower()


def _back_link(request) -> str:
    referer = request.headers.get("referer", "")
    try:
        ref, here = urlsplit(referer), urlsplit(str(request.base_url))
    except ValueError:
        return ""
    if referer and ref.scheme in ("http", "https") and ref.netloc == here.netloc and ref.path != request.url.path:
        return '<a href="' + escape(referer, quote=True) + '">← Zurück zur vorherigen Seite</a>'
    return ""


def error_page(request, status: int, detail, build: str) -> HTMLResponse:
    case_id = request.query_params.get("case_id", "")
    title = TITLES.get(status, "Das hat nicht geklappt")
    message = detail if isinstance(detail, str) and detail.strip() else ""
    links = [link for link in (_back_link(request),) if link]
    if status == 401:
        links.append('<a href="/security/login">Anmelden</a>')
    elif case_id:
        links.append('<a href="' + escape("/workbench?" + urlencode({"case_id": case_id}), quote=True) + '">Zum Arbeitsablauf</a>')
    links.append('<a href="/">Zur Hauptansicht</a>')
    body = ('<section class="card" role="alert"><p><strong>' + escape(message or HINTS.get(status, "Bitte erneut versuchen.")) +
            '</strong></p>' + ('<p>' + escape(HINTS[status]) + '</p>' if message and status in HINTS else '') +
            '<p class="muted">Fehlercode ' + str(int(status)) + '</p><p>' + ' · '.join(links) + '</p></section>')
    return HTMLResponse(page(title, case_id, body, build), status_code=status, headers={"Cache-Control": "no-store"})


def attach_error_pages(app, build: str) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if not wants_html(request):
            return await http_exception_handler(request, exc)
        response = error_page(request, exc.status_code, exc.detail, build)
        for key, value in (exc.headers or {}).items():
            response.headers[key] = value
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if not wants_html(request):
            return await request_validation_exception_handler(request, exc)
        return error_page(request, 422, "Die Anfrage ist unvollständig oder enthält ungültige Werte.", build)
