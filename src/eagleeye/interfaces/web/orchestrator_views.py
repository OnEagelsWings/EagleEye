from __future__ import annotations

import json
from typing import Any, Callable


def render_orchestrator(
    ctx: Any,
    case_id: str,
    csrf: str,
    *,
    esc: Callable[[Any], str],
    table: Callable[..., str],
) -> str:
    svc = ctx.intelligence_orchestrator_127
    data = svc.dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    target_options = '<option value="">Gesamter Fall</option>' + "".join(
        f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets
    )
    metrics = data["metrics"]
    metric_html = "".join(
        f'<div class="metric"><div class="label">{esc(label)}</div><div class="value">{int(metrics.get(key, 0))}</div></div>'
        for key, label in (
            ("plans", "Pläne"),
            ("approved", "Freigegeben"),
            ("completed_runs", "Abgeschlossene Läufe"),
            ("pending_outputs", "Offene Outputs"),
            ("injection_events", "Injection-Quarantäne"),
        )
    )
    agent_cards = "".join(
        f'''<div class="action-card"><b>{esc(agent["role_name"])}</b><p>{esc(agent["description"])}</p><span class="badge">{esc(agent["execution_mode"])}</span><p class="footer">Verboten: {esc(", ".join(agent.get("prohibited", [])))}</p></div>'''
        for agent in data["agents"]
    )
    plan_cards: list[str] = []
    for plan in data["plans"]:
        status = str(plan.get("status") or "")
        plan_id = str(plan["plan_id"])
        flags = json.loads(plan.get("injection_flags_json") or "[]")
        forms = ""
        if status == "draft":
            forms += f'''<form method="post" action="/orchestrator/approve"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(plan_id)}"><input type="hidden" name="confirmation" value="PLAN FREIGEBEN"><input name="reason" placeholder="Freigabebegründung"><button type="submit">Plan freigeben</button></form>'''
        if status == "approved":
            forms += f'''<form method="post" action="/orchestrator/execute"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(plan_id)}"><button type="submit">Lokal ausführen</button></form>'''
            forms += f'''<form method="post" action="/orchestrator/pause"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(plan_id)}"><input type="hidden" name="reason" value="Vom Ermittler pausiert"><button class="ghost" type="submit">Pausieren</button></form>'''
        if status == "paused":
            forms += f'''<form method="post" action="/orchestrator/resume"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(plan_id)}"><button type="submit">Fortsetzen</button></form>'''
        if status in {"draft", "review_required", "approved", "paused"}:
            forms += f'''<form method="post" action="/orchestrator/cancel"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(plan_id)}"><input name="reason" value="Vom Ermittler abgebrochen" required><button class="danger" type="submit">Abbrechen</button></form>'''
        plan_cards.append(
            f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(plan_id)}</h3><p>{esc(plan.get("objective"))}</p></div><span class="badge {"candidate" if status in {"draft","review_required"} else "ok"}">{esc(status)}</span></div><p>Budget: {int(plan.get("max_tasks") or 0)} Tasks · {int(plan.get("max_runtime_seconds") or 0)} Sekunden · externe Aktionen 0</p>{f'<div class="notice error">Quarantäne: {esc(", ".join(flags))}</div>' if flags else ''}<div class="inline">{forms}</div></div>'''
        )
    output_cards: list[str] = []
    for row in data["outputs"]:
        content = json.loads(row.get("content_json") or "{}")
        refs = json.loads(row.get("source_refs_json") or "[]")
        output_id = str(row["output_id"])
        review_form = ""
        if row.get("review_status") == "pending":
            review_form = f'''<form method="post" action="/orchestrator/review-output"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="output_id" value="{esc(output_id)}"><div class="decision"><select name="decision"><option value="accepted_for_working_notes">Als Arbeitsnotiz akzeptieren</option><option value="needs_revision">Überarbeitung erforderlich</option><option value="rejected">Verwerfen</option></select><input name="reason" placeholder="Reviewbegründung" required><button type="submit">Review speichern</button></div></form>'''
        output_cards.append(
            f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("agent_key"))} · {esc(row.get("output_type"))}</h3><p>{esc(row.get("created_at"))}</p></div><span class="badge candidate">{esc(row.get("trust_state"))} / {esc(row.get("review_status"))}</span></div><pre>{esc(json.dumps(content, ensure_ascii=False, indent=2))}</pre><p class="footer">Quellenbindungen: {esc(json.dumps(refs, ensure_ascii=False))}</p>{review_form}</div>'''
        )
    return f'''
<div class="notice warn"><b>Phase 3 · kontrollierte Intelligence-Orchestrierung:</b> Build 127 führt keine autonome Webrecherche aus. Jeder Plan benötigt Freigabe; alle Ergebnisse bleiben <code>suggestions_only</code> und dürfen weder Identität noch Evidence, Kausalität, Schuld oder Risiko automatisch bestätigen.</div>
<div class="metrics">{metric_html}</div>
<div class="two-col"><div class="panel"><h2>Neuen Intelligence-Plan erstellen</h2><form method="post" action="/orchestrator/plans"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Person/Entität</label><select name="target_id">{target_options}</select></div><div class="field"><label>Begrenzter Analyseauftrag</label><textarea name="objective" rows="5" required placeholder="Strukturiere die offenen Recherche-, Verifikations- und Quellenfragen dieses Falls."></textarea></div><div class="form-grid"><div class="field"><label>Maximale Tasks</label><input type="number" name="max_tasks" min="1" max="12" value="7"></div><div class="field"><label>Maximale Laufzeit in Sekunden</label><input type="number" name="max_runtime_seconds" min="10" max="300" value="120"></div></div><p><button type="submit">Planentwurf erzeugen</button></p></form></div><div class="panel"><h2>Unveränderliche Grenzen</h2><ul><li>Keine autonome Netzwerkverbindung</li><li>Keine automatische Evidence-Promotion</li><li>Keine automatische Identitätsbestätigung</li><li>Keine Schuld- oder Risikobewertung</li><li>Jeder Plan und jedes Ergebnis benötigt menschliche Entscheidung</li><li>Externe Inhalte gelten als untrusted und werden nicht als Instruktionen ausgeführt</li></ul><p class="footer">Hard Limits: {int(data["status"]["max_tasks_hard"])} Tasks · {int(data["status"]["max_runtime_seconds_hard"])} Sekunden · 0 externe Aktionen.</p></div></div>
<div class="panel"><h2>Spezialisierte Rollen</h2><div class="actions">{agent_cards}</div></div>
<div class="panel"><h2>Pläne und Freigaben</h2>{''.join(plan_cards) or '<div class="empty">Noch keine Intelligence-Pläne.</div>'}</div>
<div class="two-col"><div class="panel"><h2>Läufe</h2>{table(data["runs"], [("started_at","Start"),("status","Status"),("tasks_completed","Tasks"),("runtime_ms","Laufzeit ms"),("external_actions","Extern")])}</div><div class="panel"><h2>Sicherheitsstatus</h2><pre>{esc(json.dumps(data["status"], ensure_ascii=False, indent=2))}</pre></div></div>
<div class="panel"><h2>Quellengebundene Outputs</h2>{''.join(output_cards) or '<div class="empty">Noch keine Orchestrator-Ausgaben.</div>'}</div>
'''
