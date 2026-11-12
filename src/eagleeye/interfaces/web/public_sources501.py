"""Case-scoped source catalog and executable multi-source search packages."""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application import public_sources501 as sources
from eagleeye.infrastructure.providers import ProviderFrameworkError
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page
from .research483 import propose

PATH = "/workbench/public-sources"
ACCESS = {"api": "Automatischer Adapter", "manual": "Öffentliche Recherche",
          "setup": "Kostenloser Zugang einzurichten", "download": "Öffentliche Suche / Dateidownload"}


def _hidden(name, value):
    return '<input type="hidden" name="' + escape(name, quote=True) + '" value="' + escape(str(value), quote=True) + '">'


def _form(path, request, cid, **fields):
    return ('<form method="post" action="' + path + '">' + _hidden("case_id", cid) +
            _hidden("csrf", request.cookies.get(CSRF_COOKIE, "")) +
            "".join(_hidden(k, v) for k, v in fields.items()))


def _redirect(cid, plan_id=""):
    return RedirectResponse(PATH + "?" + urlencode({"case_id": cid, "plan_id": plan_id}), status_code=303)


def attach_public_sources501(app, build):
    ctx = app.state.context
    app.state.public_sources501 = True

    @app.get("/api/research/public-sources")
    def source_catalog(request: Request, case_id: str = "", kind: str = "topic"):
        case_access(app, request, case_id)
        try:
            rows = sources.catalog(ctx, kind)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"case_id": case_id, "network_executed": False, "sources": [
            {"id": row["source"].key, "label": row["source"].label,
             "access": row["source"].access, "adapter_available": row["ready"],
             "provider_key": row["source"].provider, "terms": row["source"].terms,
             "description": row["source"].description, "url": row["url"]} for row in rows]}

    @app.get(PATH, response_class=HTMLResponse)
    def workbench(request: Request, case_id: str = "", kind: str = "topic", term: str = "", plan_id: str = ""):
        user, _ = case_access(app, request, case_id)
        try:
            rows = sources.catalog(ctx, kind, term)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        caps = set(ctx.team_governance_359.effective_capabilities(user, case_id))
        options = "".join('<option value="' + key + '"' + (' selected' if kind == key else '') +
                          '>' + escape(label) + '</option>' for key, label in sources.KINDS.items())
        body = ('<p>Öffentliche Quellen nach Thema, Person, Unternehmen, Benutzername, Webadresse oder Ort auswählen. '
                'Die Auswahl und die Vorbereitung eines Suchpakets lösen keine externen Abfragen aus.</p>'
                '<p>Treffer bleiben ungeprüfte Hinweise. Bei Personen sind Namensvarianten, Kennungen, '
                'beruflicher Kontext und zeitliche Gültigkeit am Original abzugleichen.</p>'
                '<form method="get" action="' + PATH + '">' + _hidden("case_id", case_id) +
                '<label>Rechercheart<select name="kind">' + options + '</select></label>'
                '<label>Suchbegriff<input name="term" maxlength="190" value="' + escape(term, quote=True) +
                '"></label><button>Passende Quellen anzeigen</button></form>')
        if "research.run" in caps:
            body += (_form(PATH + "/prepare", request, case_id, kind=kind) +
                     '<h2>Suchpaket vorbereiten</h2><label>Konkrete Suchanfrage'
                     '<input name="term" minlength="3" maxlength="190" required value="' + escape(term, quote=True) + '"></label>'
                     '<label>Fallbezogener Zweck<textarea name="purpose" minlength="20" maxlength="400" required></textarea></label>')
            if kind == "url":
                body += ('<label>Common-Crawl-Sammlung (nur für diesen Adapter, z. B. CC-MAIN-2026-43)'
                         '<input name="collection" maxlength="15"></label>'
                         '<p>Verfügbare Sammlungen: <a href="https://index.commoncrawl.org/" target="_blank" '
                         'rel="noopener noreferrer">Common-Crawl-Index öffnen</a></p>')
        for row in rows:
            src = row["source"]
            body += '<section class="card"><h3>' + escape(src.label) + '</h3>'
            body += '<p>' + escape(src.description) + '</p><p>' + escape(src.terms) + '</p>'
            body += '<p><strong>' + escape(ACCESS[src.access]) + '</strong>'
            if row["ready"]:
                body += ' · Adapter verfügbar; Erreichbarkeit wird erst beim Lauf geprüft'
                if "research.run" in caps:
                    body += ('</p><label><input style="width:auto" type="checkbox" name="source" value="' + src.key +
                             '"> In das Suchpaket aufnehmen</label><p>')
            body += ('</p><a href="' + escape(row["url"], quote=True) + '" target="_blank" '
                     'rel="noopener noreferrer">Quelle öffnen</a></section>')
        if "research.run" in caps:
            body += '<p>Bis zu acht Quellen je Paket.</p><button>Suchpaket als Entwurf anlegen</button></form>'
        if plan_id:
            try:
                plan, queries = sources.package(ctx, user, case_id, plan_id)
            except (ValueError, KeyError) as exc:
                raise HTTPException(404, "Suchpaket nicht verfügbar") from exc
            body += '<h2>Vorbereitetes Suchpaket</h2><p>' + escape(plan["objective"]) + '</p><p>' + escape(plan["scope"]) + '</p>'
            for row in queries:
                provider = ctx.provider_collection_120.provider(row["provider"])
                body += ('<section class="card"><h3>' + escape(provider["label"]) + '</h3><p>Exakte Abfrage: <strong>' +
                         escape(row["query_text"]) + '</strong></p><p>' + escape(row["rationale"]) + '</p>')
                if row["execution"]:
                    result = row["execution"]
                    body += '<p>Ausführung: ' + escape(result["state"]) + ' · ' + escape(result["mode"]) + '</p>'
                    if result["provider_run_id"]:
                        run = ctx.provider_collection_120.get_run(result["provider_run_id"])
                        for item in run.get("intake", []):
                            body += ('<p><a href="' + escape(item["url"], quote=True) + '" target="_blank" rel="noopener noreferrer">' +
                                     escape(item["title"]) + '</a><br>' + escape(item["snippet"]) + '</p>')
                            if "research.run" in caps and item["url"].startswith("https://"):
                                body += (_form(PATH + "/lead", request, case_id, plan_id=plan_id, intake_id=item["intake_id"]) +
                                    '<label>Zuordnung, Unterschiede und offene Fragen<textarea name="note" minlength="20" maxlength="800" required></textarea></label>'
                                    '<label><input style="width:auto" type="checkbox" name="confirm" value="yes" required> '
                                    'Originalquelle geöffnet; als ungeprüften Fallhinweis übernehmen.</label>'
                                    '<button>Im Fall weiterbearbeiten</button></form>')
                        body += '<p>Gespeicherte Kandidaten: ' + str(run.get("result_count", 0)) + '</p>'
                    if result["state"] == "failed":
                        body += '<p>Quelle nicht erfolgreich abgefragt; kein negativer Sachnachweis. Fehler ist im Laufprotokoll dokumentiert.</p>'
                elif plan["state"] == "approved" and "research.run" in caps:
                    body += _form(PATH + "/run", request, case_id, plan_id=plan_id, query_id=row["query_id"])
                    body += '<label>Ausführung<select name="mode"><option value="live">Genehmigte Live-Abfrage</option>'
                    if provider["supports_replay"]:
                        body += '<option value="replay">Gespeicherte Antwort offline wiedergeben</option>'
                    body += ('</select></label><label><input style="width:auto" type="checkbox" name="confirm" value="yes" required> '
                             'Diese konkrete Abfrage jetzt ausführen.</label><button>Quelle einmalig abfragen</button></form>')
                body += '</section>'
            if plan["state"] == "draft" and "source.review" in caps:
                body += (_form(PATH + "/approve", request, case_id, plan_id=plan_id, expected_hash=sources.snapshot(plan, queries)) +
                    '<label>Prüfbegründung<textarea name="reason" minlength="20" maxlength="1200" required></textarea></label>'
                    '<label><input style="width:auto" type="checkbox" name="confirm" value="yes" required> '
                    'Den Plan und ausschließlich die oben gezeigten Suchanfragen freigeben.</label>'
                    '<button>Konkrete Suchanfragen freigeben</button></form>')
        body += ('<p><a href="/workbench/leads483?' + escape(urlencode({"case_id": case_id}), quote=True) +
                 '">Recherchefunde im gemeinsamen Fall prüfen</a></p>'
                 '<p><a href="/workbench/intel/web?' + escape(urlencode({"case_id": case_id}), quote=True) +
                 '">Original-Webseite als Beleg sichern</a></p>')
        return HTMLResponse(page("Öffentliche Quellen und Personenrecherche", case_id, body, build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.post(PATH + "/{action}")
    async def action(request: Request, action: str):
        form = await bounded_form(request, max_bytes=14000)
        cid = str(form.get("case_id") or "")
        user, _ = case_access(app, request, cid, capability="source.review" if action == "approve" else "research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        pid = str(form.get("plan_id") or "")
        try:
            if action == "prepare":
                plan = sources.prepare(ctx, user, cid, str(form.get("kind") or ""), str(form.get("term") or ""),
                    [str(x) for x in form.getlist("source")], str(form.get("purpose") or ""), str(form.get("collection") or ""))
                pid = plan["plan_id"]
            elif action == "approve":
                if form.get("confirm") != "yes":
                    raise HTTPException(422, "Bestätigung der konkreten Suchanfragen fehlt")
                sources.approve(ctx, user, cid, pid, str(form.get("expected_hash") or ""), str(form.get("reason") or ""))
            elif action == "run":
                if form.get("confirm") != "yes":
                    raise HTTPException(422, "Ausführungsbestätigung fehlt")
                sources.run(ctx, user, cid, pid, str(form.get("query_id") or ""), str(form.get("mode") or ""))
            elif action == "lead":
                if form.get("confirm") != "yes":
                    raise HTTPException(422, "Bestätigung der Originalsichtung fehlt")
                item = ctx.db.one("SELECT * FROM provider_intake_120 WHERE intake_id=? AND case_id=?",
                                  (str(form.get("intake_id") or ""), cid))
                if not item or item["review_status"] in {"rejected", "duplicate"}:
                    raise HTTPException(404, "Verfügbarer Falltreffer nicht gefunden")
                note = sources.plan496._safe_text(str(form.get("note") or ""), field="note", minimum=20, maximum=800)
                provenance = ("Ungeprüfter Provider-Fund: " + item["provider_key"] + "; Kandidat: " + item["intake_id"] +
                              "; Lauf: " + item["run_id"] + "; Abruf: " + item["created_at"] +
                              ". Identität und Inhalt nicht bestätigt. Prüfvermerk: " + note)
                propose(ctx, user, cid, item["url"], item["title"][:240], provenance)
            else:
                raise HTTPException(404, "Unbekannte Quellenaktion")
        except PermissionError:
            raise HTTPException(403, "Fehlende Fallberechtigung") from None
        except KeyError:
            raise HTTPException(404, "Suchpaket oder Quelle nicht gefunden") from None
        except ProviderFrameworkError:
            if action != "run":
                raise HTTPException(422, "Suchanfrage passt nicht zur ausgewählten Quelle") from None
            # Provider engine already persisted status/error in its canonical run
            # log. Do not render arbitrary response text or credentials here.
            return _redirect(cid, pid)
        except ValueError as exc:
            raise HTTPException(409, str(exc)[:240]) from exc
        return _redirect(cid, pid)
