from __future__ import annotations

import json
from typing import Any, Callable


def _option(value: str, label: str, esc: Callable[[Any], str]) -> str:
    return f'<option value="{esc(value)}">{esc(label)}</option>'


def render_graph_hypothesis(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    svc = ctx.graph_hypothesis_130
    data = svc.dashboard(case_id)
    metrics = data["metrics"]
    metric_html = "".join(
        f'<div class="metric"><div class="label">{esc(label)}</div><div class="value">{int(metrics.get(key, 0))}</div></div>'
        for key, label in (
            ("analysis_runs", "Graphanalysen"),
            ("stored_paths", "Gespeicherte Pfade"),
            ("hypotheses", "Hypothesen"),
            ("pending_reviews", "Review offen"),
            ("red_team_pending", "Red-Team offen"),
            ("ai_suggestions_pending", "AI-Vorschläge"),
        )
    )
    projection = svc.graph_projection(case_id, limit_nodes=700, limit_edges=1600)
    node_options = "".join(
        _option(str(row["id"]), f'{row.get("label") or row["id"]} · {row.get("type")}', esc)
        for row in sorted(projection.get("nodes") or [], key=lambda item: (str(item.get("type")), str(item.get("label"))))[:700]
    )
    target_options = '<option value="">Ohne Zielbindung</option>' + "".join(
        _option(str(row["target_id"]), str(row["name"]), esc) for row in ctx.targets.list_targets(case_id)
    )

    evidence_options: list[str] = []
    for object_type, table_name, key, label_field in (
        ("evidence", "evidence_packages_121", "package_id", "title"),
        ("capture", "browser_captures_129", "capture_id", "title"),
        ("relation", "graph_relations_116", "relation_id", "predicate"),
        ("timeline_event", "timeline_events_117", "event_id", "title"),
        ("contradiction", "contradictions_118", "contradiction_id", "title"),
        ("source", "graph_sources_116", "source_id", "title"),
        ("entity", "resolution_entities_115", "resolution_entity_id", "display_name"),
    ):
        if ctx.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)):
            for row in ctx.db.all(f"SELECT {key},{label_field} FROM {table_name} WHERE case_id=? ORDER BY rowid DESC LIMIT 120", (case_id,)):
                evidence_options.append(_option(f"{object_type}|{row[key]}", f"{object_type}: {row.get(label_field) or row[key]}", esc))
    evidence_select = "".join(evidence_options)

    latest = data.get("latest_run") or {}
    latest_summary = latest.get("summary") or {}
    latest_html = '<div class="empty">Noch keine Graphanalyse ausgeführt.</div>'
    if latest:
        latest_html = f'''<div class="metrics"><div class="metric"><div class="label">Knoten</div><div class="value">{int(latest.get("node_count") or 0)}</div></div><div class="metric"><div class="label">Kanten</div><div class="value">{int(latest.get("edge_count") or 0)}</div></div><div class="metric"><div class="label">Komponenten</div><div class="value">{int(latest_summary.get("component_count") or 0)}</div></div><div class="metric"><div class="label">Communities</div><div class="value">{int(latest_summary.get("community_count") or 0)}</div></div></div><div class="notice warn">{esc(latest_summary.get("interpretation_warning") or "Graphmetriken sind nur Strukturhinweise.")}</div>'''

    hypothesis_cards: list[str] = []
    for row in data.get("hypotheses") or []:
        summary = row.get("matrix_summary") or {}
        actions = f'''<form method="post" action="/graph-lab/red-team" class="inline"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="hypothesis_id" value="{esc(row["hypothesis_id"])}"><button class="ghost">Red-Team-Prüfung</button></form>'''
        if row.get("state") == "candidate":
            actions += f'''<form method="post" action="/graph-lab/request-review" class="inline"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="hypothesis_id" value="{esc(row["hypothesis_id"])}"><button>Review anfordern</button></form>'''
        elif row.get("state") == "needs_review":
            actions += f'''<form method="post" action="/graph-lab/review" class="decision"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="hypothesis_id" value="{esc(row["hypothesis_id"])}"><select name="decision"><option value="supported_for_working_use">Als Arbeitshypothese stützen</option><option value="insufficient_evidence">Evidence unzureichend</option><option value="rejected">Verwerfen</option><option value="deferred">Zurückstellen</option></select><input name="reason" minlength="12" required placeholder="Substanzielle Reviewbegründung"><button>Entscheiden</button></form>'''
        hypothesis_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("title"))}</h3><p>{esc(row.get("statement"))}</p></div><span class="badge candidate">{esc(row.get("state"))}</span></div><p>Claims: {int(summary.get("claim_count") or 0)} · Evidence-Links: {int(summary.get("evidence_links") or 0)} · ohne Evidence: {int(summary.get("unsubstantiated_claims") or 0)} · umstritten: {int(summary.get("contested_claims") or 0)}</p><div class="notice warn">Hypothese bleibt candidate-only. Keine automatische Relation-, Timeline-, Identitäts- oder Tatsachenpromotion.</div><div class="inline">{actions}</div><details><summary>Claim oder Evidence ergänzen</summary><div class="two-col"><form method="post" action="/graph-lab/claim"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="hypothesis_id" value="{esc(row["hypothesis_id"])}"><div class="field"><label>Claim-Typ</label><select name="claim_type"><option>identity</option><option>temporal</option><option>location</option><option>relationship</option><option>source</option><option>causality</option><option>other</option></select></div><div class="field"><label>Claim</label><textarea name="statement" required minlength="10"></textarea></div><button>Claim ergänzen</button></form><form method="post" action="/graph-lab/evidence"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="hypothesis_id" value="{esc(row["hypothesis_id"])}"><div class="field"><label>Claim-ID</label><input name="claim_id" required placeholder="claim130_..."></div><div class="field"><label>Fallobjekt</label><select name="object_ref" required>{evidence_select}</select></div><div class="field"><label>Stance</label><select name="stance"><option>supports</option><option>contradicts</option><option>neutral</option><option>context</option></select></div><div class="field"><label>Gewicht 0–1</label><input type="number" step="0.05" min="0" max="1" name="weight" value="0.7"></div><div class="field"><label>Einordnung</label><textarea name="summary" required minlength="8"></textarea></div><button>Evidence verknüpfen</button></form></div></details></div>''')

    red_cards_list: list[str] = []
    for row in data.get("red_team") or []:
        review_form = ""
        if row.get("review_status") == "pending":
            review_form = f'''<form method="post" action="/graph-lab/review-red-team" class="decision"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="red_team_id" value="{esc(row["red_team_id"])}"><select name="decision"><option value="accepted_for_working_notes">Als Arbeitsnotiz annehmen</option><option value="needs_revision">Überarbeiten</option><option value="rejected">Verwerfen</option><option value="deferred">Zurückstellen</option></select><input name="reason" minlength="10" required placeholder="Reviewbegründung"><button>Review</button></form>'''
        red_cards_list.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>Gegenhypothese</h3><p>{esc(row.get("counter_hypothesis"))}</p></div><span class="badge candidate">{esc(row.get("review_status"))}</span></div><p>Falsifikation: {esc(" · ".join(json.loads(row.get("falsification_tests_json") or "[]")[:3]))}</p><p>Bias-Warnungen: {esc(" · ".join(json.loads(row.get("bias_warnings_json") or "[]")))}</p>{review_form}</div>''')
    red_cards = "".join(red_cards_list) or '<div class="empty">Noch keine Red-Team-Prüfung.</div>'


    return f'''
<div class="notice warn"><b>Build 130 · Graph Analytics & Hypothesis Lab:</b> Graphmetriken beschreiben ausschließlich die Struktur gespeicherter Kandidaten. Sie sind keine Bewertung von Einfluss, Schuld, Gefährlichkeit oder tatsächlicher Beziehung. AI-Ausgaben bleiben <code>suggestions_only</code>.</div>
<div class="metrics">{metric_html}</div>
<div class="two-col"><div class="panel"><h2>Strukturelle Graphanalyse</h2><form method="post" action="/graph-lab/analyse"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Knotentypen optional, kommasepariert</label><input name="node_types" placeholder="person,organization,domain"></div><div class="form-grid"><div class="field"><label>Gültig ab</label><input type="date" name="date_from"></div><div class="field"><label>Gültig bis</label><input type="date" name="date_to"></div></div><div class="field"><label>Ortsfilter optional</label><input name="location_query"></div><div class="inline"><label><input type="checkbox" name="include_candidates" value="1" checked> Candidate-Knoten einbeziehen</label></div><p><button>Graphanalyse starten</button></p></form>{latest_html}</div>
<div class="panel"><h2>Kürzeste erklärbare Pfade</h2><form method="post" action="/graph-lab/path"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Start</label><select name="source_node_id" required>{node_options}</select></div><div class="field"><label>Ziel</label><select name="target_node_id" required>{node_options}</select></div><div class="form-grid"><div class="field"><label>Max. Tiefe</label><input type="number" name="max_depth" min="1" max="10" value="6"></div><div class="field"><label>Max. Pfade</label><input type="number" name="max_paths" min="1" max="10" value="5"></div></div><button>Pfade berechnen</button></form><p class="footer">Ein struktureller Pfad bestätigt keine direkte oder kausale reale Beziehung.</p></div></div>
<div class="panel"><h2>Analytics-Graph</h2><div class="graph-toolbar"><input id="graph130-search" placeholder="Knoten suchen"><button id="graph130-fit" class="ghost" type="button">Einpassen</button><button id="graph130-reset" class="ghost" type="button">Auswahl löschen</button><span id="graph130-count" class="badge">Lade…</span></div><div class="graph-shell"><div id="graph130" class="graph-stage" data-case-id="{esc(case_id)}"><svg role="img" aria-label="Graph Analytics"><rect class="graph-bg" width="100%" height="100%" fill="transparent"></rect><g class="graph-viewport"><g class="graph-edges"></g><g class="graph-nodes"></g></g></svg></div><aside class="graph-side"><div id="graph130-detail" class="panel"><div class="graph-detail-type">Graph 130</div><h3>Knoten auswählen</h3><p>Zentralität, Komponente, Community und Provenienz erscheinen hier.</p></div><div class="panel"><h3>Source Independence</h3><p>{int(data["source_independence"]["meta"]["source_count"])} Quellen · {int(data["source_independence"]["meta"]["cluster_count"])} mögliche Abhängigkeitscluster</p><p class="footer">Mögliche gemeinsame Ursprünge müssen menschlich geprüft werden.</p></div></aside></div></div><script src="/assets/graph130.js" defer></script>
<div class="two-col"><div class="panel"><h2>Neue Hypothese</h2><form method="post" action="/graph-lab/hypothesis"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Titel</label><input name="title" required minlength="4"></div><div class="field"><label>Claim-Typ</label><select name="claim_type"><option>identity</option><option>temporal</option><option>location</option><option>relationship</option><option>source</option><option>causality</option><option>other</option></select></div><div class="field"><label>Hypothese</label><textarea name="statement" required minlength="12"></textarea></div><div class="field"><label>Warum wird sie geprüft?</label><textarea name="rationale" required minlength="12"></textarea></div><button>Candidate-only Hypothese anlegen</button></form></div><div class="panel"><h2>Topologische Hinweise</h2>{table(data.get("top_metrics") or [], [("label","Knoten"),("node_type","Typ"),("degree","Grad"),("degree_centrality","Degree-C"),("betweenness","Betweenness"),("component_id","Komponente"),("community_id","Community")])}</div></div>
<div class="panel"><h2>Hypothesen und Claim-Evidence-Matrix</h2>{''.join(hypothesis_cards) or '<div class="empty">Noch keine Build-130-Hypothesen.</div>'}</div>
<div class="two-col"><div class="panel"><h2>Red-Team-Prüfungen</h2>{red_cards}</div><div class="panel"><h2>Gespeicherte Pfade</h2>{table(data.get("paths") or [], [("created_at","Zeit"),("source_node_id","Start"),("target_node_id","Ziel"),("hop_count","Hops"),("path_rank","Rang")])}</div></div>
'''
