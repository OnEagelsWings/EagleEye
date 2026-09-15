from __future__ import annotations

import json
from typing import Any


def render_synthesis(ctx: Any, case_id: str, csrf: str, *, esc, table) -> str:
    svc = ctx.investigative_synthesis_131
    data = svc.dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    target_options = '<option value="">Gesamter Fall</option>' + ''.join(
        f'<option value="{esc(t["target_id"])}">{esc(t["name"])}</option>' for t in targets
    )
    metrics = data["metrics"]
    metric_html = ''.join(
        f'<div class="metric"><div class="label">{esc(label)}</div><div class="value">{int(value)}</div></div>'
        for label, value in (
            ("Synthesen", metrics["runs"]),
            ("Berichte", metrics["reports"]),
            ("Veraltet", metrics["stale_reports"]),
            ("Offene Gaps", metrics["open_gaps"]),
            ("Review offen", metrics["pending_reviews"]),
            ("Unbelegt", metrics["unsubstantiated_claims"]),
            ("Umstritten", metrics["contested_claims"]),
        )
    )

    reports: list[str] = []
    for row in data.get("reports") or []:
        stale = bool(row.get("stale"))
        state_badge = '<span class="badge danger">veraltet</span>' if stale else '<span class="badge">aktuell</span>'
        actions = f'''<a class="button ghost small" href="/api/report131?case_id={esc(case_id)}&report_id={esc(row['report_id'])}">JSON-Ansicht</a>
<form class="inline" method="post" action="/synthesis/verify"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="report_id" value="{esc(row['report_id'])}"><button class="ghost small">Claims prüfen</button></form>'''
        if row.get("status") == "draft" and not stale:
            actions += f'''<form class="inline" method="post" action="/synthesis/request-review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="report_id" value="{esc(row['report_id'])}"><button class="small">Review anfordern</button></form>'''
        if row.get("status") == "needs_review" and not stale:
            actions += f'''<form method="post" action="/synthesis/review" class="decision"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="report_id" value="{esc(row['report_id'])}"><select name="decision"><option value="accepted_for_working_use">Für Arbeitsgebrauch annehmen</option><option value="needs_revision">Überarbeitung</option><option value="deferred">Zurückstellen</option><option value="rejected">Verwerfen</option></select><input name="reason" minlength="12" required placeholder="Substanzielle Reviewbegründung"><button>Review speichern</button></form>'''
        reports.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('title'))}</h3><span class="badge candidate">{esc(row.get('status'))}</span> {state_badge}</div><div class="footer">Version {int(row.get('version_no') or 1)} · {esc(row.get('updated_at'))}</div></div><p>Trust State: <code>{esc(row.get('trust_state'))}</code> · automatische Tatsachenpromotion: nein · automatischer Export: nein</p>{'<div class="notice warn">Fallobjekte haben sich seit dieser Synthese verändert. Bericht neu erzeugen.</div>' if stale else ''}<div class="inline">{actions}</div></div>''')

    gap_cards = ''.join(
        f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('title'))}</h3><span class="badge candidate">Priorität {int(row.get('priority') or 0)}</span></div><span class="badge">{esc(row.get('gap_type'))}</span></div><p>{esc(row.get('rationale'))}</p><p><b>Nächster kontrollierter Schritt:</b> {esc(row.get('recommended_action'))}</p></div>'''
        for row in data.get("gaps") or []
    ) or '<div class="empty">Noch keine Intelligence Gaps erzeugt.</div>'

    suggestions: list[str] = []
    for row in data.get("suggestions") or []:
        try:
            content = json.loads(row.get("content_json") or "{}")
        except Exception:
            content = {}
        gaps = content.get("priority_gaps") or []
        suggestions.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>Case Analyst Brief</h3><span class="badge candidate">{esc(row.get('trust_state'))}</span></div><span class="badge">{esc(row.get('review_status'))}</span></div><p>{esc(' · '.join(str(item.get('title') or '') for item in gaps[:5]))}</p><div class="footer">Modell: {esc(row.get('model_key'))} {esc(row.get('model_version'))} · externe Aktionen: 0</div></div>''')

    return f'''
<div class="notice warn"><b>Build 131 · Investigative Synthesis & Case Analyst:</b> Berichte werden ausschließlich aus intern gespeicherten Fallobjekten erzeugt. Quellenbindung beweist Herkunft, nicht Wahrheit. Jede Aussage bleibt reviewpflichtig; keine automatische Identitäts-, Evidence-, Graph-, Timeline-, Tatsachen- oder Schuld-Promotion.</div>
<div class="metrics">{metric_html}</div>
<div class="two-col"><div class="panel"><h2>Neue quellengebundene Fallanalyse</h2><form method="post" action="/synthesis/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Analyseziel</label><textarea name="objective" required minlength="12" rows="5" placeholder="Welche Frage soll auf Basis der gespeicherten Fallobjekte strukturiert beantwortet werden?"></textarea></div><button>Candidate-only Synthese erzeugen</button></form><p class="footer">Lokal, deterministisch, 0 externe Aktionen. Berichtsentwurf, Claims und Gaps werden objektgebunden gespeichert.</p></div>
<div class="panel"><h2>AI- und OPSEC-Status</h2><ul><li>AI-Ausgaben: <code>suggestions_only</code></li><li>Externe Modell- oder Provideraktionen: <b>0</b></li><li>Automatischer Export: nein</li><li>Automatische Tatsachenpromotion: nein</li><li>Claimtext und Berichtstext werden nicht ins Sicherheits-Audit kopiert.</li><li>Staleness basiert auf einem kryptografischen Snapshot der Fallobjekte.</li></ul></div></div>
<div class="panel"><h2>Berichtsentwürfe</h2>{''.join(reports) or '<div class="empty">Noch keine Build-131-Synthese.</div>'}</div>
<div class="two-col"><div class="panel"><h2>Priorisierte Intelligence Gaps</h2>{gap_cards}</div><div class="panel"><h2>Case Analyst Suggestions</h2>{''.join(suggestions) or '<div class="empty">Noch kein AI-Ermittlungsbrief.</div>'}</div></div>
'''
