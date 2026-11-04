"""Build 488: review-only view over real Build-462 case entities."""
from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.application.build488.candidates import suggest_case_pairs
from eagleeye.application.build488.reviews import initialize, reviews_for_case, record_review
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page


def current_candidates(ctx, base_dir, case_id):
    path = (Path(base_dir) if base_dir is not None else Path.home() / ".eagleeye") / "entity_registry_462.sqlite3"
    with EntityRegistry461(path) as store:
        graph = store.graph(case_id)
    entities = [{"case_id": case_id, "entity_id": str(n["id"]),
                 "name": n["label"], "entity_type": n["kind"]}
                for n in graph["entities"]]
    return suggest_case_pairs(case_id, entities)


def attach_entities488(app, build, base_dir):
    ctx = app.state.context
    initialize(ctx)

    @app.get("/workbench/entities488", response_class=HTMLResponse)
    def review_page(request: Request, case_id: str = ""):
        user, case = case_access(app, request, case_id)
        candidates = current_candidates(ctx, base_dir, case_id)
        reviewed = {(r["left_entity_id"], r["right_entity_id"]): r
                    for r in reviews_for_case(ctx, user, case_id)}
        cards = []
        for candidate in candidates:
            left, right = sorted((candidate["left_entity_id"], candidate["right_entity_id"]))
            prior = reviewed.get((left, right))
            if prior:
                cards.append("<section class='card'><b>" + escape(candidate["left_name"]) +
                             " ↔ " + escape(candidate["right_name"]) + "</b><p>Manuell: " +
                             escape(prior["decision"]) + " · " + escape(prior["rationale"]) +
                             "</p></section>")
                continue
            options = "".join('<option value="' + escape(d) + '">' + escape(label) +
                              "</option>" for d, label in (
                                  ("needs_evidence", "Weitere Belege erforderlich"),
                                  ("possible_match", "Mögliche Übereinstimmung (nicht bestätigt)"),
                                  ("not_same", "Nicht dieselbe Entität")))
            cards.append(
                '<section class="card"><h2>' + escape(candidate["left_name"]) + " ↔ " +
                escape(candidate["right_name"]) + '</h2><p>Ähnlichkeit: ' +
                escape(str(candidate["similarity_score"])) + ' · ' +
                escape(candidate["reason"]) + '</p>'
                '<form method="post" action="/workbench/entities488">'
                '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' +
                escape(request.cookies.get(CSRF_COOKIE, ""), quote=True) + '">'
                '<input type="hidden" name="left_entity_id" value="' + escape(left, quote=True) + '">'
                '<input type="hidden" name="right_entity_id" value="' + escape(right, quote=True) + '">'
                '<label>Prüfentscheidung<select name="decision">' + options + '</select></label>'
                '<label>Begründung (20–1200 Zeichen)<textarea name="rationale" minlength="20" maxlength="1200" required></textarea></label>'
                '<label><input type="checkbox" name="confirm" value="yes" required> Keine Identität oder Beweislage automatisch bestätigt.</label>'
                '<button type="submit">Manuelle Prüfung protokollieren</button></form></section>')
        # Retain visibility of audited decisions if a pair stops matching.
        active_pairs = {tuple(sorted((c["left_entity_id"], c["right_entity_id"])))
                        for c in candidates}
        for pair, prior in reviewed.items():
            if pair not in active_pairs:
                cards.append(
                    '<section class="card warn"><h2>Historische Prüfentscheidung – Kandidat nicht mehr aktuell</h2>'
                    '<p>Entitäten: ' + escape(pair[0]) + ' ↔ ' + escape(pair[1]) +
                    '</p><p>Entscheidung: ' + escape(prior["decision"]) +
                    ' · ' + escape(prior["rationale"]) +
                    '</p><p>Vor weiterer Verwendung Entitäten und Quellen erneut prüfen.</p></section>')
        body = ('<p>Fall: ' + escape(str(case.get("title") or "")) +
                '. Vorschläge sind keine Identitätsnachweise. Keine automatischen Zusammenführungen.</p>' +
                '<p><a href="/entities462?' + escape(urlencode({"case_id": case_id}), quote=True) +
                '">Entitäten bearbeiten</a> · <a href="/workbench/sources487?' +
                escape(urlencode({"case_id": case_id}), quote=True) +
                '">Geprüfte Quellenzuordnungen ansehen</a></p>' +
                ("".join(cards) or "<p>Keine passenden Kandidaten vorhanden.</p>"))
        return HTMLResponse(page("Entity-Prüfung 488", case_id, body, build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.post("/workbench/entities488")
    async def review_post(request: Request):
        form = await bounded_form(request, max_bytes=24576)
        case_id = str(form.get("case_id") or "")
        user, _case = case_access(app, request, case_id, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        if form.get("confirm") != "yes":
            raise HTTPException(422, "Manuelle Prüfbestätigung erforderlich.")
        left = str(form.get("left_entity_id") or "")
        right = str(form.get("right_entity_id") or "")
        if not left or not right or left == right:
            raise HTTPException(422, "Zwei verschiedene Entitäten erforderlich.")
        pair = tuple(sorted((left, right)))
        candidates = current_candidates(ctx, base_dir, case_id)
        candidate = next((c for c in candidates if
                          tuple(sorted((c["left_entity_id"], c["right_entity_id"]))) == pair), None)
        if candidate is None:
            raise HTTPException(409, "Kandidat nicht mehr aktuell oder nicht fallzugehörig.")
        record_review(ctx, user, case_id, candidate, str(form.get("decision") or ""),
                      form.get("rationale"))
        return RedirectResponse("/workbench/entities488?" + urlencode({"case_id": case_id}),
                                status_code=303)
