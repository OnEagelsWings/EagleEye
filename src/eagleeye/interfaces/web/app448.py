from __future__ import annotations

import hashlib
import html
import inspect
import json
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from .app379 import COOKIE
from .app447 import create_workspace_app447

VIEWS = (
    ("overview", "Übersicht"),
    ("research", "Recherche"),
    ("ai", "AI-Ermittlung"),
    ("evidence", "Evidence"),
    ("claims", "Claims & Hypothesen"),
    ("analysis", "Graph & Timeline"),
    ("dossier", "Dossier"),
    ("operations", "OPSEC & Team"),
)


def _e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _short(value, limit=140):
    text = str(value if value is not None else "")
    return text if len(text) <= limit else text[:limit] + "…"


CSS = r"""
:root{--bg:#07101d;--panel:#0d1a2a;--panel2:#122338;--line:#263a52;--text:#edf4ff;--muted:#9eb0c5;--accent:#62d7c3;--accent2:#7aaeff;--warn:#ffc76b;--danger:#ff7c88;--ok:#76dfa0;--shadow:0 14px 42px rgba(0,0,0,.28)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:linear-gradient(160deg,#07101d,#091525 45%,#060d17);color:var(--text);font-family:Inter,Segoe UI,system-ui,sans-serif;min-height:100vh}.app{display:grid;grid-template-columns:232px minmax(0,1fr);min-height:100vh}.side{position:sticky;top:0;height:100vh;padding:20px 15px;background:#07111f;border-right:1px solid var(--line);overflow:auto}.brand{display:flex;align-items:center;gap:10px;margin-bottom:18px}.logo{display:grid;place-items:center;width:40px;height:40px;border-radius:12px;background:linear-gradient(145deg,var(--accent),var(--accent2));color:#06111c;font-weight:900}.brand b{display:block}.brand small{color:var(--muted)}.nav{display:grid;gap:5px}.nav a{color:var(--muted);text-decoration:none;padding:9px 10px;border:1px solid transparent;border-radius:9px;font-size:13px}.nav a:hover,.nav a.active{color:#fff;background:#13243a;border-color:#31506b}.side-foot{margin-top:20px;padding-top:15px;border-top:1px solid var(--line);font-size:11px;color:var(--muted);line-height:1.5}.main{padding:22px 28px 48px;min-width:0}.top{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:15px}.top h1{font-size:24px;margin:0 0 4px}.top p{margin:0;color:var(--muted);font-size:12px}.case-switch{display:flex;gap:8px;align-items:center}.case-switch select{max-width:340px}.notice{border-left:4px solid var(--accent2);background:rgba(122,174,255,.08);padding:11px 13px;border-radius:8px;margin-bottom:14px;color:#cad9ea;font-size:12px}.notice.warn{border-color:var(--warn);background:rgba(255,199,107,.08)}.notice.error{border-color:var(--danger);background:rgba(255,124,136,.08)}.panel{background:linear-gradient(145deg,rgba(14,28,45,.98),rgba(10,21,35,.98));border:1px solid var(--line);border-radius:14px;padding:17px;margin-bottom:14px;box-shadow:var(--shadow)}.panel h2{font-size:17px;margin:0 0 11px}.panel h3{font-size:14px;margin:0 0 8px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:9px}.metric{padding:13px;border:1px solid #29435f;border-radius:11px;background:var(--panel2)}.metric .n{font-size:24px;font-weight:800}.metric .k{font-size:11px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:11px}.two{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr);gap:13px}.card{border:1px solid var(--line);background:#102037;border-radius:11px;padding:13px}.card p{font-size:12px;color:#c4d3e4;line-height:1.5}.action{display:block;text-decoration:none;color:var(--text);border:1px solid var(--line);background:#102037;border-radius:10px;padding:11px}.action:hover{border-color:var(--accent)}.action.high{border-color:rgba(255,124,136,.55)}.action.medium{border-color:rgba(255,199,107,.48)}.badge{display:inline-flex;align-items:center;padding:3px 7px;border-radius:999px;background:#203653;color:#d5e4f5;font-size:10px}.badge.ok{background:rgba(118,223,160,.12);color:#a5f0bf}.badge.warn{background:rgba(255,199,107,.12);color:#ffdc99}.badge.bad{background:rgba(255,124,136,.12);color:#ffb6be}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px}table{width:100%;border-collapse:collapse;font-size:11px}th{position:sticky;top:0;background:#13253c;color:#aebfd2;text-align:left;padding:9px}td{padding:9px;border-top:1px solid #23374e;vertical-align:top;max-width:360px;overflow-wrap:anywhere}tr:hover td{background:rgba(122,174,255,.025)}input,select,textarea{width:100%;background:#091625;color:var(--text);border:1px solid #304963;border-radius:8px;padding:8px;font:inherit}textarea{resize:vertical}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.field label{display:block;color:var(--muted);font-size:10px;margin-bottom:4px}.button,button{display:inline-flex;align-items:center;justify-content:center;border:1px solid transparent;border-radius:8px;padding:8px 11px;background:linear-gradient(135deg,var(--accent),#49bce9);color:#06111c;text-decoration:none;font-weight:800;font-size:11px;cursor:pointer}.button.ghost,button.ghost{background:#162a43;color:#dce9f8;border-color:#36516f}.button.danger,button.danger{background:rgba(255,124,136,.14);color:#ffbdc4;border-color:rgba(255,124,136,.42)}.button:focus-visible,button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #9ed7ff;outline-offset:2px}.inline{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.inline>*{width:auto}.muted{color:var(--muted);font-size:11px}.statusline{position:sticky;bottom:10px;margin-top:12px;min-height:0;z-index:5}.statusline>div{padding:9px 12px;border-radius:9px;background:#102944;border:1px solid #315778;font-size:11px}.statusline .err{background:#391a25;border-color:#7b3547}.flow{display:grid;grid-template-columns:repeat(6,minmax(100px,1fr));gap:6px;margin-bottom:14px}.flow a{text-decoration:none;color:var(--muted);padding:8px 9px;border-radius:9px;border:1px solid var(--line);background:#0b192a;font-size:10px}.flow a b{display:block;color:var(--text);font-size:11px}.flow a.ready{border-color:#3f806f;background:rgba(98,215,195,.06)}details{border:1px solid var(--line);border-radius:10px;padding:10px;background:#0d1c2e}details+details{margin-top:8px}summary{cursor:pointer;font-weight:700;font-size:12px}.footer{margin-top:20px;color:var(--muted);font-size:10px;line-height:1.5}.empty{padding:20px;border:1px dashed #34506c;border-radius:10px;text-align:center;color:var(--muted);font-size:12px}.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10px}.mobile-title{display:none}
@media(max-width:1000px){.app{grid-template-columns:1fr}.side{position:relative;height:auto;padding:13px}.brand{margin-bottom:10px}.nav{grid-template-columns:repeat(4,minmax(0,1fr))}.nav a{text-align:center;padding:8px 5px;font-size:11px}.side-foot{display:none}.main{padding:15px}.two,.form-grid{grid-template-columns:1fr}.top{align-items:stretch;flex-direction:column}.case-switch{align-items:stretch;flex-direction:column}.case-switch select{max-width:none}.flow{grid-template-columns:repeat(3,1fr)}}
@media(max-width:620px){.nav{grid-template-columns:repeat(2,1fr)}.metrics{grid-template-columns:repeat(2,1fr)}.flow{grid-template-columns:repeat(2,1fr)}.main{padding:11px}.panel{padding:13px}.top h1{font-size:20px}}
"""


JS = r"""
(function(){
 const status=document.getElementById('workspace-status');
 function show(msg,err){
   status.innerHTML='<div class="'+(err?'err':'')+'">'+String(msg||'')+'</div>';
   status.scrollIntoView({block:'nearest'});
 }
 function splitList(v){return String(v||'').split(/[\n,]+/).map(x=>x.trim()).filter(Boolean);}
 function payload(form){
   const out={};
   form.querySelectorAll('[name]').forEach(el=>{
     if(el.disabled)return;
     if(el.type==='checkbox'){out[el.name]=!!el.checked;return;}
     if(el.dataset.array==='true'){const vals=splitList(el.value);if(vals.length||el.required)out[el.name]=vals;return;}
     if(el.dataset.number==='true'){out[el.name]=Number(el.value||0);return;}
     out[el.name]=el.value;
   });
   return out;
 }
 document.addEventListener('submit',async ev=>{
   const form=ev.target.closest('form[data-json-form]');
   if(!form)return;
   ev.preventDefault();
   const button=form.querySelector('button[type=submit],button:not([type])');
   if(button)button.disabled=true;
   show('Aktion läuft …',false);
   try{
     const res=await fetch(form.dataset.endpoint,{
       method:'POST',
       headers:{'Content-Type':'application/json'},
       body:JSON.stringify(payload(form)),
       credentials:'same-origin'
     });
     const text=await res.text();
     let data={};try{data=JSON.parse(text)}catch(_){data={detail:text}}
     if(!res.ok)throw new Error(data.detail||('HTTP '+res.status));
     show(form.dataset.success||'Aktion erfolgreich.',false);
     if(form.dataset.reload!=='false')setTimeout(()=>location.reload(),350);
   }catch(err){show(err.message||String(err),true);if(button)button.disabled=false;}
 });
 document.addEventListener('click',ev=>{
   const el=ev.target.closest('[data-copy]');
   if(!el)return;
   navigator.clipboard&&navigator.clipboard.writeText(el.dataset.copy||'');
   show('Bestätigungstext kopiert.',false);
 });
})();
"""


def _route_inventory(app):
    out = []
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path:
            for method in methods:
                out.append((str(method).upper(), str(path)))
    return out


def _metric(label, value):
    return f'<div class="metric"><div class="n">{_e(value)}</div><div class="k">{_e(label)}</div></div>'


def _table(rows, columns):
    if not rows:
        return '<div class="empty">Keine Einträge.</div>'
    head = "".join(f"<th>{_e(label)}</th>" for _key, label in columns)
    body = []
    for row in rows:
        body.append(
            "<tr>"
            + "".join(f"<td>{_e(_short(row.get(key)))}</td>" for key, _label in columns)
            + "</tr>"
        )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _flow(snapshot, case_id):
    m = snapshot["metrics"]
    steps = [
        ("research", "1 · Recherche", m["dispatches"] + m["executions"]),
        ("ai", "2 · AI-Loop", m["loops"]),
        ("evidence", "3 · Evidence", m["evidence"]),
        ("claims", "4 · Claims", m["claims"]),
        ("analysis", "5 · Analyse", m["timeline_events"] + m["relationship_edges"]),
        ("dossier", "6 · Dossier", m["dossiers"]),
    ]
    return '<div class="flow">' + "".join(
        f'<a class="{"ready" if count else ""}" href="/?{urlencode({"view":key,"case_id":case_id})}"><b>{_e(label)}</b>{int(count)} Elemente</a>'
        for key, label, count in steps
    ) + "</div>"


def _overview(snapshot):
    c = snapshot["case"]
    m = snapshot["metrics"]
    metric_html = "".join(
        [
            _metric("Aktive AI-Loops", m["active_loops"]),
            _metric("Acquisition Executions", m["executions"]),
            _metric("Evidence", m["evidence"]),
            _metric("Ungeprüfte Evidence", m["evidence_unreviewed"]),
            _metric("Claims akzeptiert", m["claims_accepted"]),
            _metric("Dossier-Revisionen", m["dossiers"]),
            _metric("Timeline Events", m["timeline_events"]),
            _metric("Relationship Edges", m["relationship_edges"]),
        ]
    )
    actions = "".join(
        f'<a class="action {_e(x["priority"])}" href="/?{urlencode({"view":x["view"],"case_id":c["case_id"]})}"><b>{_e(x["label"])}</b></a>'
        for x in snapshot["next_actions"]
    )
    loop = snapshot["latest_loop"] or {}
    return f"""
<div class="notice"><b>Case-first Workspace.</b> Beobachtung → Evidence → Claim → Analyse → Dossier. Hypothesen, Gegenbelege und Unsicherheiten bleiben getrennt; keine automatische Wahrheitsfeststellung.</div>
<div class="two">
<section class="panel"><h2>{_e(c.get("title"))}</h2><p><span class="badge">{_e(c.get("status"))}</span></p><p><b>Zweck:</b> {_e(c.get("purpose"))}</p><p><b>Rechtsgrundlage:</b> {_e(c.get("legal_basis"))}</p><p class="muted">Fall-ID: {_e(c.get("case_id"))}</p></section>
<section class="panel"><h2>Aktueller AI-Loop</h2>{f'<p><b>{_e(loop.get("objective"))}</b></p><p><span class="badge">{_e(loop.get("state"))}</span> · Zyklus {_e(loop.get("current_cycle"))}/{_e(loop.get("max_cycles"))}</p>' if loop else '<div class="empty">Noch kein AI-Ermittlungsloop.</div>'}</section>
</div>
<section class="panel"><h2>Ermittlungslage</h2><div class="metrics">{metric_html}</div></section>
<section class="panel"><h2>Nächste sinnvolle Schritte</h2><div class="grid">{actions}</div></section>
"""


def _research(snapshot):
    loop = snapshot["latest_loop"] or {}
    sources = snapshot["sources"]
    dispatches = snapshot["dispatches"]
    loop_id = loop.get("loop_id", "")
    prepare = ""
    recommended = snapshot.get("recommended_dispatch_source_ids") or []
    recommended_text = "\n".join(recommended)
    if loop and loop.get("state") == "active":
        prepare = f"""
<form data-json-form data-endpoint="/api/build446/loops/{_e(loop_id)}/dispatches/prepare" data-success="Dispatch-Tickets vorbereitet.">
<div class="field"><label>Source-IDs für diesen Zyklus. Vorauswahl ist auf das autorisierte Zyklusbudget begrenzt.</label><textarea name="source_ids" data-array="true" rows="3">{_e(recommended_text)}</textarea></div>
<p class="muted">{len(recommended)} Quelle(n) vorausgewählt; Auswahl kann innerhalb des autorisierten Loop-Scopes geändert werden.</p>
<p><button type="submit">Dispatch vorbereiten</button></p>
</form>"""
    rows = []
    for d in dispatches:
        action = ""
        if d.get("state") == "awaiting_path_confirmation":
            action = f"""
<form data-json-form data-endpoint="/api/build446/dispatches/{_e(d["dispatch_id"])}/execute" data-success="Acquisition ausgeführt.">
<div class="field"><label>Bestätigung exakt eingeben</label><input name="confirmation" placeholder="{_e(d.get("required_confirmation"))}"></div>
<div class="inline"><button type="submit">Einzelne Quelle ausführen</button><button class="ghost" type="button" data-copy="{_e(d.get("required_confirmation"))}">Text kopieren</button></div>
</form>"""
        elif d.get("state") == "replay_ready":
            action = '<span class="badge warn">Fixture · nur Replay/Selftest</span>'
        else:
            action = f'<span class="badge">{_e(d.get("state"))}</span>'
        rows.append({
            "loop_id": d.get("loop_id"),
            "source_id": d.get("source_id"),
            "route": d.get("route"),
            "state": d.get("state"),
            "confirmation": d.get("required_confirmation"),
            "action": action,
        })
    dispatch_html = '<div class="empty">Noch keine Dispatch-Tickets.</div>' if not rows else '<div class="table-wrap"><table><thead><tr><th>Loop</th><th>Quelle</th><th>Route</th><th>Status</th><th>Aktion</th></tr></thead><tbody>' + "".join(
        f'<tr><td class="mono">{_e(r["loop_id"])}</td><td class="mono">{_e(r["source_id"])}</td><td>{_e(r["route"])}</td><td>{_e(r["state"])}</td><td>{r["action"]}</td></tr>'
        for r in rows
    ) + '</tbody></table></div>'
    return f"""
<section class="panel"><h2>Quellenlage</h2><p class="muted">Nur registrierte und freigegebene Quellen. Live-Ausführung bleibt pro Quelle bestätigt.</p>{_table(sources,[("name","Quelle"),("source_type","Typ"),("access_mode","Zugriff"),("source_id","Source-ID")])}</section>
<section class="panel"><h2>AI-Loop → Acquisition</h2>{prepare or '<div class="empty">Ein aktiver AI-Loop ist erforderlich.</div>'}</section>
<section class="panel"><h2>Dispatches</h2>{dispatch_html}</section>
<section class="panel"><h2>Acquisition-Verlauf</h2>{_table(snapshot["executions"],[("created_at","Zeit"),("route","Route"),("source_id","Quelle"),("state","Status"),("external_network","Extern")])}</section>
"""


def _ai(snapshot):
    case_id = snapshot["case"]["case_id"]
    sources = snapshot["sources"]
    source_hint = "\n".join(str(x.get("source_id")) for x in sources[:8])
    loop_cards = []
    for loop in reversed(snapshot["loops"]):
        controls = ""
        if loop.get("state") == "awaiting_human_authorization":
            controls = f"""
<form data-json-form data-endpoint="/api/build439/cases/{_e(case_id)}/investigation/loops/{_e(loop["loop_id"])}/authorize" data-success="AI-Loop autorisiert.">
<div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="AUTHORIZE INVESTIGATION LOOP"></div>
<div class="inline"><button type="submit">Loop autorisieren</button><button class="ghost" type="button" data-copy="AUTHORIZE INVESTIGATION LOOP">Text kopieren</button></div>
</form>"""
        elif loop.get("state") == "active":
            controls = f"""
<form data-json-form data-endpoint="/api/build439/cases/{_e(case_id)}/investigation/loops/{_e(loop["loop_id"])}/advance" data-success="Ein begrenzter Investigation-Zyklus abgeschlossen.">
<button type="submit">Einen Zyklus ausführen</button>
</form>"""
        loop_cards.append(f"""
<details {'open' if loop is snapshot["latest_loop"] else ''}><summary>{_e(loop.get("objective"))} · {_e(loop.get("state"))}</summary>
<p class="muted">Loop {_e(loop.get("loop_id"))} · Zyklus {_e(loop.get("current_cycle"))}/{_e(loop.get("max_cycles"))}</p>
{controls}
</details>""")
    matrix = snapshot.get("matrix") or {}
    return f"""
<section class="panel"><h2>Neue AI-Ermittlung</h2>
<form data-json-form data-endpoint="/api/build439/cases/{_e(case_id)}/investigation/loops" data-success="AI-Ermittlung angelegt; separate Freigabe erforderlich.">
<div class="field"><label>Ermittlungsziel</label><textarea name="objective" rows="3" required></textarea></div>
<div class="form-grid"><div class="field"><label>Teilfragen, eine pro Zeile</label><textarea name="subquestions" data-array="true" rows="5" required></textarea></div><div class="field"><label>Freigegebene Source-IDs, optional</label><textarea name="allowed_source_ids" data-array="true" rows="5" placeholder="{_e(source_hint)}"></textarea></div>
<div class="field"><label>Max. Zyklen</label><input name="max_cycles" data-number="true" type="number" min="1" max="12" value="4"></div><div class="field"><label>Max. Collection Tasks/Zyklus</label><input name="max_collection_tasks_per_cycle" data-number="true" type="number" min="1" max="12" value="4"></div></div>
<p><button type="submit">Loop anlegen</button></p></form></section>
<section class="panel"><h2>Investigation Loops</h2>{''.join(loop_cards) if loop_cards else '<div class="empty">Noch keine AI-Ermittlung.</div>'}</section>
<section class="panel"><h2>Hypothesenlage</h2><div class="metrics">{_metric("Hypothesen",len(matrix.get("hypotheses") or []))}{_metric("Gaps",len(matrix.get("gaps") or []))}{_metric("Konflikte",len(matrix.get("conflicts") or []))}</div><p class="muted">Hypothesen sind Arbeitsmodelle, keine Fakten.</p></section>
"""


def _active_team_review(snapshot, object_type, object_id):
    team = snapshot.get("team_review449") or {}
    rows = team.get("queue") or []
    candidates = [
        x for x in rows
        if x.get("object_type") == object_type
        and str(x.get("object_id")) == str(object_id)
        and x.get("state") in {"pending", "claimed", "completed", "stale"}
    ]
    return candidates[0] if candidates else None


def _reviewer_options(snapshot, object_type):
    team = snapshot.get("team_review449") or {}
    current = str(snapshot.get("actor") or "").casefold()
    rows = (team.get("eligible_reviewers") or {}).get(object_type, [])
    options = ['<option value="">Offene Review-Queue</option>']
    for row in rows:
        username = str(row.get("username") or "")
        if not username or username.casefold() == current:
            continue
        label = row.get("display_name") or username
        roles = ", ".join(row.get("case_roles") or [])
        options.append(
            f'<option value="{_e(username)}">{_e(label)} · {_e(roles or "Reviewer")}</option>'
        )
    return "".join(options)


def _review_request_form(snapshot, object_type, object_id, *, label="Review anfordern"):
    existing = _active_team_review(snapshot, object_type, object_id)
    if existing and existing.get("state") in {"pending", "claimed"}:
        return (
            f'<div class="notice warn"><b>Team-Review {_e(existing.get("state"))}</b><br>'
            f'Review-ID: <span class="mono">{_e(existing.get("review_id"))}</span> · '
            f'angefordert von {_e(existing.get("requested_by"))}'
            f'{" · zugewiesen an " + _e(existing.get("assigned_to")) if existing.get("assigned_to") else ""}'
            '</div>'
        )
    if existing and existing.get("state") == "stale":
        stale = '<div class="notice error">Die vorige Review-Anforderung ist veraltet, weil sich das Objekt geändert hat. Neue Prüfung erforderlich.</div>'
    else:
        stale = ""
    return stale + f"""
<form data-json-form data-endpoint="/api/build449/reviews" data-success="Team-Review angefordert.">
<input type="hidden" name="object_type" value="{_e(object_type)}">
<input type="hidden" name="object_id" value="{_e(object_id)}">
<div class="field"><label>Warum ist die Prüfung jetzt erforderlich?</label><input name="note" required placeholder="Review-Auftrag kurz dokumentieren"></div>
<div class="field"><label>Reviewer, optional</label><select name="assigned_to">{_reviewer_options(snapshot, object_type)}</select></div>
<button type="submit">{_e(label)}</button>
</form>"""


def _team_review_queue_panel(snapshot):
    team = snapshot.get("team_review449") or {}
    if not team:
        return ""
    metrics = team.get("metrics") or {}
    decision_options = {
        "evidence": [("accepted", "accepted"), ("context_only", "context_only"), ("rejected", "rejected")],
        "claim": [("accepted_for_dossier", "accepted_for_dossier"), ("needs_more_evidence", "needs_more_evidence"), ("rejected", "rejected")],
        "dossier": [("approved_for_export", "approved_for_export"), ("changes_required", "changes_required")],
        "dossier_export": [("approve", "approve"), ("deny", "deny")],
    }
    confirmations = {
        "evidence": "REVIEW EVIDENCE 447",
        "claim": "REVIEW CLAIM 447",
        "dossier": "APPROVE DOSSIER 447",
        "dossier_export": "APPROVE DOSSIER EXPORT 449",
    }
    cards = []
    for row in team.get("queue") or []:
        state = str(row.get("state") or "")
        actions = ""
        if row.get("can_claim"):
            actions += f"""
<form data-json-form data-endpoint="/api/build449/reviews/{_e(row.get("review_id"))}/claim" data-success="Review übernommen.">
<button type="submit">Review übernehmen</button>
</form>"""
        if row.get("can_complete"):
            opts = "".join(
                f'<option value="{_e(value)}">{_e(label)}</option>'
                for value, label in decision_options.get(row.get("object_type"), [])
            )
            confirm = confirmations.get(row.get("object_type"), "")
            actions += f"""
<form data-json-form data-endpoint="/api/build449/reviews/{_e(row.get("review_id"))}/complete" data-success="Review abgeschlossen.">
<div class="field"><label>Entscheidung</label><select name="decision">{opts}</select></div>
<div class="field"><label>Begründung</label><input name="note" required></div>
<div class="field"><label>Bestätigung exakt</label><input name="confirmation" placeholder="{_e(confirm)}"></div>
<div class="inline"><button type="submit">Review abschließen</button><button class="ghost" type="button" data-copy="{_e(confirm)}">Text kopieren</button></div>
</form>"""
        comment_form = ""
        if state in {"pending", "claimed"}:
            comment_form = f"""
<form data-json-form data-endpoint="/api/build449/reviews/{_e(row.get("review_id"))}/comments" data-success="Review-Kommentar gespeichert.">
<div class="form-grid"><div class="field"><label>Typ</label><select name="kind"><option value="comment">Kommentar</option><option value="challenge">Challenge</option><option value="agreement">Agreement</option><option value="counter_hypothesis">Gegenhypothese</option></select></div><div class="field"><label>Text</label><input name="body" required></div></div>
<button class="ghost" type="submit">Zum Review protokollieren</button>
</form>"""
        comments = "".join(
            f'<li><b>{_e(x.get("kind"))}</b> · {_e(x.get("created_by"))}: {_e(x.get("body"))}</li>'
            for x in row.get("comments") or []
        )
        cards.append(f"""
<details {"open" if row.get("assigned_to_me") else ""}>
<summary>{_e(row.get("object_type"))} · {_e(_short(row.get("object_id"),48))} · {_e(state)}</summary>
<p><b>Angefordert:</b> {_e(row.get("requested_by"))} · <b>Zugewiesen:</b> {_e(row.get("assigned_to") or "offene Queue")} · <b>Claimed:</b> {_e(row.get("claimed_by") or "—")}</p>
<p class="muted">{_e(row.get("request_note"))}</p>
{actions}{comment_form}
{"<ul>" + comments + "</ul>" if comments else ""}
</details>""")
    membership_rows = [
        x for x in team.get("memberships") or [] if x.get("active")
    ]
    return f"""
<section class="panel"><h2>Team Review · Build 449</h2>
<div class="metrics">{_metric("Offen",metrics.get("pending",0))}{_metric("Übernommen",metrics.get("claimed",0))}{_metric("Für mich",metrics.get("assigned_to_me",0))}{_metric("Veraltet",metrics.get("stale",0))}</div>
<p class="muted">Vier-Augen-Prinzip: Antragsteller bzw. Objekt-Ersteller dürfen die eigene Review-Aufgabe nicht abschließen. Änderungen nach Review-Anforderung machen den Auftrag veraltet.</p>
{''.join(cards) if cards else '<div class="empty">Keine Review-Aufgaben in diesem Fall.</div>'}
</section>
<section class="panel"><h2>Fallteam</h2>{_table(membership_rows,[("display_name","Name"),("username","Benutzer"),("case_role","Rolle"),("granted_by","Zugewiesen von")])}</section>
"""


def _evidence(snapshot):
    case_id = snapshot["case"]["case_id"]
    rows = []
    for item in reversed(snapshot["evidence"]):
        controls = ""
        if item.get("review_state") == "unreviewed":
            if snapshot.get("team_review449"):
                controls = _review_request_form(
                    snapshot, "evidence", item["evidence_id"], label="Evidence-Review anfordern"
                )
            else:
                controls = f"""
<form data-json-form data-endpoint="/api/build447/evidence/{_e(item["evidence_id"])}/review" data-success="Evidence-Review gespeichert.">
<div class="field"><label>Entscheidung</label><select name="decision"><option value="accepted">accepted</option><option value="context_only">context_only</option><option value="rejected">rejected</option></select></div>
<div class="field"><label>Review-Notiz</label><input name="note" required></div>
<div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="REVIEW EVIDENCE 447"></div>
<button type="submit">Review speichern</button>
</form>"""
        rows.append(f"""
<details><summary>{_e(item.get("title") or item.get("evidence_id"))} · {_e(item.get("review_state"))}</summary>
<div class="grid"><div><p><b>Evidence-ID:</b> <span class="mono">{_e(item.get("evidence_id"))}</span></p><p><b>Typ:</b> {_e(item.get("evidence_kind"))}</p><p><b>Quelle:</b> {_e(item.get("source_id"))}</p><p><b>SHA-256:</b> <span class="mono">{_e(item.get("content_sha256"))}</span></p></div><div><p><b>URL:</b> {_e(item.get("canonical_url"))}</p><p><b>Observed:</b> {_e(item.get("observed_at"))}</p><p><b>Duplicate:</b> {_e(item.get("duplicate_kind"))}</p></div></div>{controls}
</details>""")
    return f"""
<section class="panel"><h2>Evidence synchronisieren</h2><form data-json-form data-endpoint="/api/build447/cases/{_e(case_id)}/evidence/sync" data-success="Evidence synchronisiert."><button type="submit">Neue Acquisition-Daten synchronisieren</button></form></section>
<section class="panel"><h2>Evidence Viewer</h2><p class="muted">Quelle, Provenienz, Hash und Reviewstatus bleiben sichtbar. Rohpayloads werden hier nicht dupliziert.</p>{''.join(rows) if rows else '<div class="empty">Noch keine Build-447-Evidence.</div>'}</section>
"""


def _claims(snapshot):
    case_id = snapshot["case"]["case_id"]
    claim_cards = []
    for claim in reversed(snapshot["claims"]):
        links = ", ".join(f'{x.get("stance")}:{x.get("evidence_id")}' for x in claim.get("links") or [])
        controls = ""
        if claim.get("state") == "candidate_review_required":
            if snapshot.get("team_review449"):
                controls = _review_request_form(
                    snapshot, "claim", claim["claim_id"], label="Claim-Review anfordern"
                )
            else:
                controls = f"""
<form data-json-form data-endpoint="/api/build447/claims/{_e(claim["claim_id"])}/review" data-success="Claim-Review gespeichert.">
<div class="field"><label>Entscheidung</label><select name="decision"><option value="accepted_for_dossier">accepted_for_dossier</option><option value="needs_more_evidence">needs_more_evidence</option><option value="rejected">rejected</option></select></div>
<div class="field"><label>Review-Notiz</label><input name="note" required></div>
<div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="REVIEW CLAIM 447"></div>
<button type="submit">Claim reviewen</button>
</form>"""
        claim_cards.append(f"""
<details><summary>{_e(_short(claim.get("statement"),100))} · {_e(claim.get("state"))}</summary>
<p>{_e(claim.get("statement"))}</p><p class="muted">Claim-ID: {_e(claim.get("claim_id"))}<br>Links: {_e(links or "keine")}<br>Unsicherheit: {_e(claim.get("uncertainty_note") or "keine explizite")}</p>{controls}
</details>""")
    matrix = snapshot.get("matrix") or {}
    gap_lines = "".join(f"<li>{_e(_short(x,220))}</li>" for x in (matrix.get("gaps") or [])) or "<li>Keine Gaps im aktuellen Matrix-Snapshot.</li>"
    conflict_lines = "".join(f"<li>{_e(_short(x,220))}</li>" for x in (matrix.get("conflicts") or [])) or "<li>Keine Konflikte im aktuellen Matrix-Snapshot.</li>"
    return f"""
<section class="panel"><h2>Claim anlegen</h2>
<form data-json-form data-endpoint="/api/build447/cases/{_e(case_id)}/claims" data-success="Claim als Review-Kandidat angelegt.">
<div class="field"><label>Proposition / Claim</label><textarea name="statement" rows="3" required></textarea></div>
<div class="form-grid"><div class="field"><label>Supporting Evidence-IDs</label><textarea name="support_evidence_ids" data-array="true" rows="3" required></textarea></div><div class="field"><label>Contradicting Evidence-IDs</label><textarea name="contradiction_evidence_ids" data-array="true" rows="3"></textarea></div><div class="field"><label>Context Evidence-IDs</label><textarea name="context_evidence_ids" data-array="true" rows="3"></textarea></div><div class="field"><label>Unsicherheitsnotiz</label><textarea name="uncertainty_note" rows="3"></textarea></div></div>
<button type="submit">Claim als Kandidat anlegen</button></form></section>
<section class="two"><div class="panel"><h2>Claims</h2>{''.join(claim_cards) if claim_cards else '<div class="empty">Noch keine Claims.</div>'}</div><div class="panel"><h2>Gaps & Konflikte</h2><h3>Gaps</h3><ul>{gap_lines}</ul><h3>Konflikte</h3><ul>{conflict_lines}</ul></div></section>
"""


def _analysis(snapshot):
    f = snapshot["latest_fusion"] or {}
    m = snapshot["metrics"]
    synth = snapshot["latest_synthesis"] or {}
    return f"""
<section class="panel"><h2>Temporal-/Relationship-Fusion</h2><div class="metrics">{_metric("Entities",m["entities"])}{_metric("Timeline Events",m["timeline_events"])}{_metric("Relationships",m["relationship_edges"])}{_metric("Unresolved",m["unresolved_relationships"])}</div><p class="muted">Nur explizite Quellenbeziehungen; keine Beziehung aus bloßer Text-Kookkurrenz, keine Kausalitätsableitung.</p></section>
<section class="panel"><h2>Letzte Synthese</h2>{f'<p><b>{_e(synth.get("title"))}</b></p><p class="muted">Synthesis-ID: {_e(synth.get("synthesis_id"))}</p><pre class="mono">{_e(json.dumps(synth.get("summary") or {},ensure_ascii=False,indent=2,default=str))}</pre>' if synth else '<div class="empty">Noch keine Synthese.</div>'}</section>
<section class="panel"><h2>Vertiefte Graph-/Timeline-Werkzeuge</h2><p>Die komplexen Graph- und Timeline-Ansichten bleiben verfügbar, sind aber aus der Hauptnavigation entfernt.</p><a class="button ghost" href="/legacy?case_id={_e(snapshot["case"]["case_id"])}">Erweiterte Fallansicht öffnen</a></section>
"""


def _dossier(snapshot):
    case_id = snapshot["case"]["case_id"]
    latest_loop = snapshot["latest_loop"] or {}
    cards = []
    for d in reversed(snapshot["dossiers"]):
        controls = ""
        if d.get("state") == "draft_for_review":
            if snapshot.get("team_review449"):
                controls = _review_request_form(
                    snapshot, "dossier", d["revision_id"], label="Dossier-Review anfordern"
                )
            else:
                controls = f"""
<form data-json-form data-endpoint="/api/build447/dossiers/{_e(d["revision_id"])}/review" data-success="Dossier-Review gespeichert.">
<div class="field"><label>Entscheidung</label><select name="decision"><option value="approved_for_export">approved_for_export</option><option value="changes_required">changes_required</option></select></div>
<div class="field"><label>Review-Notiz</label><input name="note" required></div>
<div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="APPROVE DOSSIER 447"></div><button type="submit">Dossier reviewen</button></form>"""
        elif d.get("state") == "approved_for_export":
            if snapshot.get("team_review449"):
                export_review = _active_team_review(snapshot, "dossier_export", d["revision_id"])
                executions = (snapshot.get("team_review449") or {}).get("export_executions") or []
                executed = next(
                    (x for x in executions if x.get("review_id") == (export_review or {}).get("review_id")),
                    None,
                )
                if executed:
                    controls = f'<div class="notice"><b>Vier-Augen-Export ausgeführt.</b><br>Package SHA-256: <span class="mono">{_e(executed.get("package_hash"))}</span></div>'
                elif export_review and export_review.get("state") == "completed" and export_review.get("decision") == "approve":
                    controls = f"""
<form data-json-form data-endpoint="/api/build449/reviews/{_e(export_review.get("review_id"))}/export" data-success="Vier-Augen-Dossierexport ausgeführt.">
<div class="field"><label>Bestätigung exakt</label><input name="confirmation" placeholder="EXPORT DOSSIER 447"></div>
<div class="inline"><button type="submit">Freigegebenes Dossier exportieren</button><button class="ghost" type="button" data-copy="EXPORT DOSSIER 447">Text kopieren</button></div>
</form>"""
                else:
                    controls = _review_request_form(
                        snapshot, "dossier_export", d["revision_id"], label="Exportfreigabe anfordern"
                    )
            else:
                controls = f"""
<form data-json-form data-endpoint="/api/build447/dossiers/{_e(d["revision_id"])}/export" data-success="Dossier exportiert.">
<div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="EXPORT DOSSIER 447"></div><button type="submit">JSON · DOCX · PDF · ZIP exportieren</button></form>"""
        cards.append(f"""
<details><summary>Revision {_e(d.get("revision_no"))} · {_e(d.get("state"))}</summary><p><b>{_e(d.get("title"))}</b></p><p class="muted">Revision-ID: {_e(d.get("revision_id"))} · Claims: {len((d.get("snapshot") or {}).get("claims") or [])}</p>{controls}</details>""")
    return f"""
<section class="panel"><h2>Neue Living-Dossier-Revision</h2><form data-json-form data-endpoint="/api/build447/cases/{_e(case_id)}/dossiers" data-success="Dossier-Revision erzeugt.">
<div class="form-grid"><div class="field"><label>Titel</label><input name="title" placeholder="Living Dossier"></div><div class="field"><label>AI-Loop-ID, optional</label><input name="loop_id" value="{_e(latest_loop.get("loop_id",""))}"></div></div><button type="submit">Revision erzeugen</button></form></section>
<section class="panel"><h2>Dossier-Revisionen</h2>{''.join(cards) if cards else '<div class="empty">Noch kein Living Dossier. Mindestens ein akzeptierter Claim ist erforderlich.</div>'}</section>
<section class="panel"><h2>Exporte</h2>{_table(snapshot["exports"],[("created_at","Zeit"),("revision_id","Revision"),("package_hash","Package SHA-256"),("export_id","Export-ID")])}</section>
"""


def _operations(snapshot, audits):
    m = snapshot["metrics"]
    hist = _table(audits,[("created_at","Zeit"),("result","Result"),("route_count","Routes"),("markup_sha256","Markup SHA-256")])
    team_panel = _team_review_queue_panel(snapshot)
    team449 = bool(snapshot.get("team_review449"))
    audit_build = "449" if team449 else "448"
    audit_endpoint = f'/api/build{audit_build}/cases/{_e(snapshot["case"]["case_id"])}/ui-audit'
    audit_text = (
        "Build 449 prüft zusätzlich den Team-Review-Routenkontrakt und stellt sicher, "
        "dass direkte Build-447-Review-/Export-Bypass-Routen im aktuellen App fehlen."
        if team449 else
        "Build 448 prüft Hauptnavigation, Accessibility-Basics, Responsive Layout und die Registrierung der operativen Build-439/446/447-Routen."
    )
    return f"""
{team_panel}
<section class="panel"><h2>UI-Funktionsprüfung</h2><p>{audit_text}</p><form data-json-form data-endpoint="{audit_endpoint}" data-success="UI-Audit abgeschlossen."><button type="submit">UI jetzt prüfen</button></form></section>
<section class="panel"><h2>Audit-Historie</h2>{hist}</section>
<section class="panel"><h2>Operations-Sicht</h2><div class="metrics">{_metric("Quellen",m["sources"])}{_metric("Dispatches",m["dispatches"])}{_metric("Executions",m["executions"])}{_metric("Exports",m["exports"])}</div><p class="muted">Build 448 verändert keine OPSEC-/Netzwerkbefugnisse.</p></section>
<section class="panel"><h2>Experten-/Legacy-Werkzeuge</h2><p>Die historische Oberfläche bleibt für Spezialfunktionen verfügbar, ist aber nicht mehr die primäre Ermittlernavigation.</p><a class="button ghost" href="/legacy?case_id={_e(snapshot["case"]["case_id"])}">Legacy/Expert Workspace öffnen</a></section>
"""


def render_workspace(snapshot, *, view, cases, audits):
    case = snapshot["case"]
    case_id = case["case_id"]
    view = view if view in {x[0] for x in VIEWS} else "overview"
    nav = "".join(
        f'<a class="{"active" if key==view else ""}" href="/?{urlencode({"view":key,"case_id":case_id})}">{_e(label)}</a>'
        for key, label in VIEWS
    )
    options = "".join(
        f'<option value="{_e(x.get("case_id"))}" {"selected" if x.get("case_id")==case_id else ""}>{_e(x.get("title"))} · {_e(x.get("status"))}</option>'
        for x in cases
    )
    selector = f'<form class="case-switch" method="get" action="/"><input type="hidden" name="view" value="{_e(view)}"><select name="case_id">{options}</select><button class="ghost" type="submit">Fall öffnen</button></form>'
    content = {
        "overview": _overview,
        "research": _research,
        "ai": _ai,
        "evidence": _evidence,
        "claims": _claims,
        "analysis": _analysis,
        "dossier": _dossier,
        "operations": lambda s: _operations(s, audits),
    }[view](snapshot)
    team449 = bool(snapshot.get("team_review449"))
    ui_build = "449" if team449 else "448"
    ui_name = "Human Review & Team Workflow" if team449 else "Investigator Workspace"
    review_note = " · formales Vier-Augen-Review aktiv" if team449 else ""
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EagleEye Build {ui_build} · {_e(case.get("title"))}</title><style>{CSS}</style></head><body><div class="app"><aside class="side"><div class="brand"><div class="logo">EE</div><div><b>EagleEye</b><small>Build {ui_build} · {ui_name}</small></div></div><nav class="nav" aria-label="Hauptnavigation">{nav}</nav><div class="side-foot">Case-first · provenance-first · review-first{review_note}<br><a href="/legacy">Legacy/Expert Workspace</a><br>Build 447 Evidence/Claims/Dossier integriert.</div></aside><main class="main"><header class="top"><div><h1>{_e(dict(VIEWS).get(view))}</h1><p>{_e(case.get("title"))} · Benutzer: {_e(snapshot.get("actor"))}</p></div>{selector}</header>{_flow(snapshot,case_id)}{content}<div id="workspace-status" class="statusline" aria-live="polite"></div><footer class="footer">Anzeige gespeicherter Daten ≠ unabhängige Verifikation. Evidence, Claims und Hypothesen bleiben unterscheidbar; keine automatische Wahrheitsfeststellung, Identitätsbestätigung, Kausalitäts- oder Schuldzuweisung.</footer></main></div><script src="/assets/build448/workspace.js"></script></body></html>'''


def create_workspace_app448(*, base_dir=None):
    app = create_workspace_app447(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build448
    app.title = "EagleEye Build 448.0 Investigator Workspace"
    app.version = "448.0"

    home_candidates = [
        r.endpoint
        for r in app.router.routes
        if getattr(r, "path", None) == "/"
        and "GET" in set(getattr(r, "methods", set()) or set())
    ]
    old_home = next(
        (
            endpoint
            for endpoint in reversed(home_candidates)
            if "tab" in inspect.signature(endpoint).parameters
            and "case_id" in inspect.signature(endpoint).parameters
        ),
        home_candidates[-1] if home_candidates else None,
    )
    app.router.routes[:] = [
        r
        for r in app.router.routes
        if not (
            getattr(r, "path", None) == "/"
            and "GET" in set(getattr(r, "methods", set()) or set())
        )
    ]

    old_health = next(
        (
            r.endpoint
            for r in app.router.routes
            if getattr(r, "path", None) == "/health"
            and "GET" in set(getattr(r, "methods", set()) or set())
        ),
        None,
    )
    app.router.routes[:] = [
        r
        for r in app.router.routes
        if not (
            getattr(r, "path", None) == "/health"
            and "GET" in set(getattr(r, "methods", set()) or set())
        )
    ]

    def auth(request):
        fingerprint = hashlib.sha256(
            "|".join(
                (
                    request.headers.get("user-agent", ""),
                    request.headers.get("accept-language", ""),
                    request.client.host if request.client else "",
                )
            ).encode()
        ).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def same_origin(request):
        site = str(request.headers.get("sec-fetch-site") or "").strip().lower()
        if site and site not in {"same-origin", "none"}:
            raise HTTPException(403, "Cross-origin mutation blocked")
        origin = str(request.headers.get("origin") or "").strip().rstrip("/")
        if origin:
            expected = (
                str(request.url.scheme) + "://" + str(request.headers.get("host") or "")
            ).rstrip("/")
            if origin != expected:
                raise HTTPException(403, "Cross-origin mutation blocked")

    def visible_cases(identity):
        return ctx.team_governance_359.visible_cases(identity)

    def choose_case(cases, requested):
        if requested:
            for item in cases:
                if str(item.get("case_id")) == str(requested):
                    return item
        return cases[0] if cases else None

    @app.get("/assets/build448/workspace.js", response_class=PlainTextResponse)
    def workspace_js448():
        return PlainTextResponse(JS, media_type="application/javascript; charset=utf-8")

    @app.get("/", response_class=HTMLResponse)
    def workspace448(request: Request, view: str = "overview", case_id: str = "", token: str = ""):
        if token and callable(old_home):
            return old_home(request)
        try:
            identity = auth(request)
        except HTTPException:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = visible_cases(identity)
        selected = choose_case(cases, case_id)
        if not selected:
            return RedirectResponse("/legacy", status_code=303)
        snap = ctx.investigator_workspace_448.snapshot(
            identity=identity,
            case_id=selected["case_id"],
        )
        audits = ctx.investigator_workspace_448.audit_history(selected["case_id"], limit=15)
        return HTMLResponse(render_workspace(snap, view=view, cases=cases, audits=audits))

    @app.get("/legacy", response_class=HTMLResponse)
    def legacy448(request: Request, case_id: str = ""):
        if case_id:
            return RedirectResponse(f"/cases/{case_id}", status_code=303)
        if not callable(old_home):
            raise HTTPException(404, "Legacy workspace unavailable")
        return old_home(request)

    @app.get("/health")
    def health448():
        payload = dict(old_health() if callable(old_health) else {"ok": True})
        status = ctx.build448.investigator_workspace_status_448()
        payload.update(
            {
                "build": "448.0",
                "phase": 20,
                "phase20_builds_completed": 8,
                "investigator_workspace": True,
                "ui_route_contract_audited": True,
                "legacy_expert_workspace_preserved": True,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build448/status")
    def status448(request: Request):
        auth(request)
        return ctx.build448.investigator_workspace_status_448()

    @app.get("/api/build448/cases/{case_id}/snapshot")
    def snapshot448(case_id: str, request: Request):
        identity = auth(request)
        return ctx.build448.investigator_workspace_snapshot_448(
            identity=identity,
            case_id=case_id,
        )

    @app.get("/api/build448/cases/{case_id}/ui-audits")
    def audits448(case_id: str, request: Request):
        identity = auth(request)
        ctx.team_governance_359.authorize(
            identity,
            case_id=case_id,
            capability="case.read",
            object_type="ui_audit_448",
            object_id=case_id,
        )
        return {"items": ctx.investigator_workspace_448.audit_history(case_id)}

    @app.post("/api/build448/cases/{case_id}/ui-audit")
    def audit448(case_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        cases = visible_cases(identity)
        selected = choose_case(cases, case_id)
        if not selected or str(selected.get("case_id")) != str(case_id):
            raise HTTPException(403, "case access denied")
        snapshot = ctx.investigator_workspace_448.snapshot(
            identity=identity,
            case_id=case_id,
        )
        markup = render_workspace(
            snapshot,
            view="overview",
            cases=cases,
            audits=ctx.investigator_workspace_448.audit_history(case_id, limit=15),
        )
        result = ctx.build448.run_ui_audit_448(
            identity=identity,
            case_id=case_id,
            markup=markup,
            route_inventory=_route_inventory(app),
        )
        code = 200 if result["result"] == "PASS" else 409
        return JSONResponse(result, status_code=code)

    return app


create_app = create_workspace_app448
