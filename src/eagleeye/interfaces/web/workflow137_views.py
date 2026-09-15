from __future__ import annotations

from typing import Any, Callable

from eagleeye.application.build137.service import TASK_STATUSES, WORKFLOW_OBJECTIVES


def render_workflow137(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str]) -> str:
    targets = ctx.targets.list_targets(case_id)
    target_options = "".join(f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets) or '<option value="">Zuerst Person/Entität anlegen</option>'
    objective_options = "".join(f'<option value="{esc(key)}">{esc(label)}</option>' for key, label in WORKFLOW_OBJECTIVES.items())
    workflows = ctx.build137.list_workflows(case_id=case_id, limit=12)
    workflow_sections: list[str] = []
    for summary in workflows:
        flow = ctx.build137.workflow(workflow_id=summary["workflow_id"], case_id=case_id)
        stage_html: list[str] = []
        for stage in flow["stages"]:
            task_rows: list[str] = []
            for task in stage["tasks"]:
                status_options = "".join(
                    f'<option value="{esc(status)}"{" selected" if status == task.get("status") else ""}>{esc(status)}</option>'
                    for status in ("planned", "opened", "completed", "unresolved", "blocked", "skipped")
                )
                launch = ""
                if task.get("search_task_id"):
                    launch = f'''<form method="post" action="/workflow137/launch"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="workflow_task_id" value="{esc(task["workflow_task_id"])}"><button class="small">Im Fallbrowser öffnen</button></form>'''
                task_rows.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(task["title"])}</h3><div class="inline"><span class="badge candidate">candidate_only</span><span class="badge">Priorität {esc(task["priority"])}</span><span class="badge">{esc(task["task_type"])}</span></div></div><span class="badge">{esc(task["status"])}</span></div><p><b>Zweck:</b> {esc(task["rationale"])}</p><p><b>Erwartung:</b> {esc(task["expected_output"])}</p><div class="inline">{launch}<form method="post" action="/workflow137/task"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="workflow_task_id" value="{esc(task["workflow_task_id"])}"><select name="status">{status_options}</select><input name="outcome_note" value="{esc(task.get("outcome_note") or "")}" placeholder="Ergebnis, Gegenbeleg oder offene Frage"><button class="small ghost">Status speichern</button></form></div></div>''')
            stage_html.append(f'''<details class="panel"{" open" if stage["stage_order"] <= 2 else ""}><summary><b>{esc(stage["title"])}</b> · {esc(stage["completed_count"])} erledigt · {esc(stage["open_count"])} offen</summary><p>{esc(stage["purpose"])}</p>{"".join(task_rows) if task_rows else '<div class="empty">Für diese Stufe wurden keine Aufgaben benötigt.</div>'}</details>''')
        workflow_sections.append(f'''<section class="panel"><div class="intake-head"><div><h2>{esc(summary["target_name"])} · {esc(WORKFLOW_OBJECTIVES.get(flow["objective_key"], flow["objective_key"]))}</h2><p>{esc(flow["objective_text"])}</p></div><span class="badge {"ok" if flow["status"] == "completed" else "candidate"}">{esc(flow["status"])}</span></div><div class="metrics"><div class="metric"><div class="label">Aufgaben</div><div class="value">{esc(flow["task_count"])}</div></div><div class="metric"><div class="label">Erledigt</div><div class="value">{esc(flow["completed_count"])}</div></div><div class="metric"><div class="label">Ungeklärt/blockiert</div><div class="value">{esc(flow["unresolved_count"])}</div></div><div class="metric"><div class="label">Identitätsbehauptungen</div><div class="value">0</div></div></div><p class="footer">Namensvarianten: {esc(", ".join(flow["name_variants"]))}. Jede Aufgabe verlangt manuelle Quellenprüfung; Treffer werden nicht automatisch derselben Person zugeordnet.</p>{"".join(stage_html)}</section>''')

    return f'''
<div class="notice"><b>Geführter Ermittlungsworkflow · Build 137:</b> EagleEye zerlegt ein Ermittlungsziel in reproduzierbare Stufen, erzeugt kontrollierte Suchvarianten und dokumentiert offene sowie erledigte Schritte. Es erfolgt keine automatische Personengleichsetzung.</div>
<div class="two-col"><div class="panel"><h2>Neuen Workflow anlegen</h2><form method="post" action="/workflow137/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson</label><select name="target_id" required>{target_options}</select></div><div class="field"><label>Ermittlungsziel</label><select name="objective_key">{objective_options}</select></div><div class="field"><label>Konkrete Fragestellung</label><textarea name="objective_text" rows="4" placeholder="Welche Frage soll beantwortet oder widerlegt werden?"></textarea></div><p><button>Workflow erzeugen</button></p></form></div><div class="panel"><h2>Methodische Grenzen</h2><ul><li>Treffer bleiben Kandidaten, bis Quellen und Gegenbelege geprüft wurden.</li><li>Namensvarianten sind Suchhilfen, keine Identitätsaussagen.</li><li>Quellenaufgaben öffnen sich ausschließlich im fallgebundenen Firefox.</li><li>Übersprungene und ungeklärte Schritte bleiben im Audit sichtbar.</li></ul></div></div>
{"".join(workflow_sections) if workflow_sections else '<div class="panel"><div class="empty">Noch kein Build-137-Ermittlungsworkflow in diesem Fall.</div></div>'}
'''
