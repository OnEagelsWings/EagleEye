from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from eagleeye.application.workspace.service import WorkspaceConflictError, WorkspaceValidationError
from eagleeye_pro.version import BUILD, BUILD_NAME
from eagleeye_pro.core.database import now_ts

from .security_views import render_security
from .reliability_views import render_reliability
from .release_views import render_release
from .orchestrator_views import render_orchestrator
from .research_strategy_views import render_research_strategy
from .capture_identity_views import render_capture_identity
from .graph_hypothesis_views import render_graph_hypothesis
from .synthesis_views import render_synthesis
from .governance_views import render_governance
from .phase3_release_views import render_phase3_release
from .phase4_operations_views import render_phase4_operations
from .photo141_views import render_photo141
from .identity139_views import render_identity139
from .assistant140_views import render_assistant140
from .quality141_views import render_quality141
from .reports142_views import render_reports142
from .security143_views import render_security143
from .final144_views import render_final144
from .final145_views import render_final145
from .auth146_views import render_auth146
from .build147_views import render_research147
from .build148_views import render_connectors148
from .build149_views import render_ecosystem149
from .build150_views import render_capture150
from .evidence138_views import render_evidence138
from .workflow137_views import render_workflow137
from .investigation167_views import render_investigation167
from .handover168_views import render_handover168
from .build343_routes import mount_build343_routes

MAX_FORM_BYTES = 512 * 1024
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
_FLASH_LOCK = threading.RLock()
_FLASH_MESSAGES: dict[str, tuple[str, str, float]] = {}


def _put_flash(message: str = "", error: str = "") -> str:
    token = secrets.token_urlsafe(24)
    now = time.time()
    with _FLASH_LOCK:
        expired = [key for key, value in _FLASH_MESSAGES.items() if value[2] < now]
        for key in expired:
            _FLASH_MESSAGES.pop(key, None)
        _FLASH_MESSAGES[token] = (str(message or "")[:2000], str(error or "")[:2000], now + 120.0)
    return token


def _take_flash(token: str) -> tuple[str, str]:
    if not token:
        return "", ""
    with _FLASH_LOCK:
        item = _FLASH_MESSAGES.pop(token, None)
    if not item or item[2] < time.time():
        return "", ""
    return item[0], item[1]


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _token(root: Path) -> str:
    target = root / "data" / "security_124_0" / "local_session_token"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        current = target.read_text(encoding="utf-8").strip()
        if len(current) >= 32:
            return current
    value = secrets.token_urlsafe(40)
    target.write_text(value, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return value


def _csrf(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"eagleeye-workspace-143.0-csrf", hashlib.sha256).hexdigest()


async def _form(request: Request) -> dict[str, str]:
    raw = await request.body()
    if len(raw) > MAX_FORM_BYTES:
        raise HTTPException(status_code=413, detail="Formular ist zu groß")
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _safe_case(ctx: Any, requested: str = "", actor: str = "") -> dict[str, Any] | None:
    cases = ctx.collaboration_governance_132.list_accessible_cases(actor) if actor else ctx.cases.list_cases()
    if not cases:
        return None
    if requested:
        for case in cases:
            if case["case_id"] == requested:
                return case
    return cases[0]


def _link(tab: str, case_id: str, **extra: str) -> str:
    clean = {k: v for k, v in extra.items() if v and k not in {"message", "error"}}
    message = str(extra.get("message") or "")
    error = str(extra.get("error") or "")
    if message or error:
        clean["flash"] = _put_flash(message, error)
    query = {"tab": tab, "case_id": case_id, **clean}
    return "/?" + urlencode(query)


def _short(value: Any, limit: int = 160) -> str:
    text = str(value if value is not None else "")
    return text if len(text) <= limit else text[:limit] + "…"


def _table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    *,
    object_type: str = "",
    id_column: str = "",
    case_id: str = "",
) -> str:
    if not rows:
        return '<div class="empty">Keine Einträge in diesem Fall.</div>'
    head = "".join(f"<th>{_esc(label)}</th>" for _key, label in columns)
    if object_type:
        head += "<th>Details</th>"
    body: list[str] = []
    for row in rows:
        cells = "".join(f"<td>{_esc(_short(row.get(key)))}</td>" for key, _label in columns)
        if object_type:
            oid = str(row.get(id_column, ""))
            href = f"/workspace/detail/{quote(object_type)}/{quote(oid)}?case_id={quote(case_id)}"
            cells += f'<td><a class="button ghost small" href="{href}">Öffnen</a></td>'
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


CSS = r"""
:root{--bg:#08111f;--panel:#101d2f;--panel2:#14243a;--line:#263a54;--text:#edf4ff;--muted:#9db0c7;--accent:#5dd6c0;--accent2:#6ea8ff;--warn:#ffc86b;--danger:#ff7d88;--ok:#70df9b;--shadow:0 18px 50px rgba(0,0,0,.28)}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#162943 0,#08111f 38%,#060c16 100%);color:var(--text);font-family:Inter,Segoe UI,system-ui,sans-serif;min-height:100vh}.shell{display:grid;grid-template-columns:255px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;padding:24px 18px;background:rgba(7,16,29,.93);border-right:1px solid var(--line);backdrop-filter:blur(14px)}.brand{display:flex;gap:12px;align-items:center;margin-bottom:24px}.logo{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,var(--accent),var(--accent2));color:#06101b;font-weight:900;font-size:20px;box-shadow:0 8px 28px rgba(93,214,192,.25)}.brand b{display:block;font-size:15px}.brand span{font-size:11px;color:var(--muted)}.nav{display:grid;gap:5px}.nav a{padding:10px 12px;border-radius:9px;color:var(--muted);text-decoration:none;font-size:13px;border:1px solid transparent}.nav a:hover{background:#14243a;color:var(--text)}.nav a.active{background:linear-gradient(90deg,rgba(93,214,192,.18),rgba(110,168,255,.12));border-color:#31536d;color:#fff}.side-note{position:absolute;bottom:18px;left:18px;right:18px;font-size:11px;color:var(--muted);line-height:1.5}.main{padding:25px 32px 52px;min-width:0}.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:18px}.title h1{font-size:25px;margin:0 0 5px}.title p{margin:0;color:var(--muted);font-size:13px}.case-switch{display:flex;gap:9px;align-items:center}.case-switch select{max-width:360px}.panel{background:linear-gradient(145deg,rgba(17,31,50,.96),rgba(12,24,40,.96));border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:var(--shadow);margin-bottom:16px}.panel h2,.panel h3{margin-top:0}.notice{border-left:4px solid var(--accent2);background:rgba(110,168,255,.09);padding:12px 15px;border-radius:8px;margin-bottom:16px;color:#cbdcf1}.notice.warn{border-color:var(--warn);background:rgba(255,200,107,.09)}.notice.error{border-color:var(--danger);background:rgba(255,125,136,.09)}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px}.metric{padding:16px;border-radius:13px;background:var(--panel2);border:1px solid #29415e}.metric .value{font-size:28px;font-weight:800;margin-top:5px}.metric .label{font-size:12px;color:var(--muted)}.actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{padding:14px;border-radius:12px;background:#122238;border:1px solid var(--line)}.action-card{display:block;text-decoration:none;color:var(--text);padding:14px;border-radius:12px;background:#122238;border:1px solid var(--line)}.action-card:hover{border-color:var(--accent)}.action-card.high{border-color:rgba(255,125,136,.6)}.badge{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:#203653;color:#cfe0f4;font-size:11px}.badge.candidate{background:rgba(255,200,107,.14);color:#ffd991}.badge.ok{background:rgba(112,223,155,.12);color:#9cf0ba}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px}table{border-collapse:collapse;width:100%;font-size:12px}th{text-align:left;padding:11px;background:#13253c;color:#a9bdd4;position:sticky;top:0}td{padding:11px;border-top:1px solid #23374f;vertical-align:top;max-width:340px}tr:hover td{background:rgba(110,168,255,.035)}input,select,textarea{width:100%;background:#0c1829;color:var(--text);border:1px solid #304762;border-radius:8px;padding:9px;font:inherit}textarea{resize:vertical}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.field label{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}.button,button{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:8px;padding:9px 13px;background:linear-gradient(135deg,var(--accent),#48b9e9);color:#06121d;text-decoration:none;font-weight:750;cursor:pointer;font-size:12px}.button.ghost,button.ghost{background:#172a43;color:#dbe9f8;border:1px solid #36506e}.button.danger,button.danger{background:rgba(255,125,136,.16);color:#ffb8bf;border:1px solid rgba(255,125,136,.45)}.button.small,button.small{padding:6px 9px}.inline{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.inline>*{width:auto}.inline label{display:flex;gap:5px;align-items:center;color:var(--muted);font-size:11px}.inline input[type=checkbox]{width:auto}.intake-card{padding:16px;border:1px solid var(--line);border-radius:13px;background:#102037;margin-bottom:11px}.intake-head{display:flex;justify-content:space-between;gap:15px}.intake-card h3{margin:0 0 6px;font-size:15px}.intake-card p{color:#c1d0e1;font-size:12px}.decision{display:grid;grid-template-columns:180px 1fr auto;gap:8px;margin-top:11px}.empty{padding:28px;text-align:center;color:var(--muted);border:1px dashed #304762;border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#07101c;border:1px solid #263b55;padding:15px;border-radius:10px;color:#cfe0f2;font-size:12px}.two-col{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.flowbar{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:7px;margin-bottom:16px}.flowstep{display:block;padding:10px;border:1px solid var(--line);border-radius:10px;background:#0d1a2c;color:var(--muted);text-decoration:none;font-size:11px}.flowstep b{display:block;color:var(--text);font-size:12px;margin-bottom:3px}.flowstep.ready{border-color:var(--accent);background:rgba(93,214,192,.08)}.footer{color:var(--muted);font-size:11px;margin-top:24px}@media(max-width:950px){.flowbar{grid-template-columns:repeat(2,1fr)}.shell{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.nav{grid-template-columns:repeat(3,1fr)}.side-note{display:none}.main{padding:18px}.topbar,.case-switch{align-items:stretch;flex-direction:column}.two-col,.form-grid{grid-template-columns:1fr}.decision{grid-template-columns:1fr}}
.photo-drop{min-height:220px;border:2px dashed #3a5c7e;border-radius:14px;display:grid;place-content:center;text-align:center;gap:8px;background:#0b1829;cursor:pointer;color:#cfe0f2;padding:24px}.photo-drop span{font-size:12px;color:var(--muted)}.photo-drop.dragging{border-color:var(--accent);background:rgba(93,214,192,.1)}.photo-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.photo-card{background:#0d1b2d;border:1px solid var(--line);border-radius:14px;overflow:hidden}.photo-thumb{width:100%;height:250px;object-fit:contain;background:#050b13;display:block}.photo-reference{height:250px;display:flex;flex-direction:column;gap:8px;align-items:center;justify-content:center;background:linear-gradient(145deg,#14243a,#0a1422);color:#dce9f7;padding:20px;text-align:center}.photo-reference span,.photo-reference small{color:var(--muted)}.photo-body{padding:15px}.photo-body h3{margin:0 0 8px}.photo-body code{font-size:10px;overflow-wrap:anywhere}

.graph-shell{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:14px}.graph-stage{height:680px;min-height:520px;background:radial-gradient(circle at center,#111c31 0,#080e1a 72%);border:1px solid #253853;border-radius:14px;overflow:hidden;position:relative}.graph-stage svg{width:100%;height:100%;display:block;touch-action:none;cursor:grab}.graph-stage svg:active{cursor:grabbing}.graph-edge{stroke:#51657f;stroke-width:1}.graph-edge.connected{stroke:#71d7ff;stroke-width:1.8;opacity:.9!important}.graph-node circle{stroke:#09111e;stroke-width:2.2;filter:drop-shadow(0 0 7px rgba(117,203,255,.35))}.graph-node circle.candidate{stroke-dasharray:3 2}.graph-node text{fill:#dce9f7;font-size:10px;pointer-events:none;text-shadow:0 1px 3px #000}.graph-node{cursor:pointer}.graph-node:hover circle,.graph-node.selected circle{stroke:#fff;stroke-width:3}.graph-node.dimmed{opacity:.12}.graph-toolbar{display:flex;gap:8px;align-items:center;margin-bottom:10px}.graph-toolbar input{max-width:440px}.graph-side{display:grid;gap:12px;align-content:start}.graph-detail-type{text-transform:uppercase;letter-spacing:.12em;color:var(--accent);font-size:10px}.graph-side dl{display:grid;grid-template-columns:90px 1fr;gap:8px;font-size:11px}.graph-side dt{color:var(--muted)}.graph-side dd{margin:0;overflow-wrap:anywhere}.precision{font-weight:800;color:var(--accent)}.profile-meter{height:8px;background:#091525;border-radius:99px;overflow:hidden}.profile-meter span{display:block;height:100%;background:linear-gradient(90deg,var(--accent2),var(--accent));border-radius:99px}.pagination{display:flex;gap:7px;align-items:center;justify-content:flex-end;margin-top:12px}.provider-ready{color:var(--ok)}.provider-down{color:var(--danger)}@media(max-width:1100px){.graph-shell{grid-template-columns:1fr}.graph-stage{height:560px}}
.cockpit-tabs{display:flex;gap:7px;flex-wrap:wrap;margin:14px 0}.cockpit-tabs a{padding:8px 11px;border:1px solid var(--line);border-radius:9px;color:var(--muted);text-decoration:none;background:#0d1a2c;font-size:12px}.cockpit-tabs a.active,.cockpit-tabs a:hover{color:#fff;border-color:var(--accent);background:rgba(93,214,192,.09)}.cockpit-status{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}.cockpit244 .action-card b{font-size:14px}.cockpit244 .muted{color:var(--muted)}
"""

ADVANCED_NAV = [
    ("cockpit244", "Cockpit"),
    ("workflow245", "Workflow"),
    ("monitor246", "Monitoring"),
    ("runtime247", "AI Runtime"),
    ("production248", "Production"),
    ("stress249", "Stress/Release"),
    ("influence251", "Influence Pack"),
    ("finance252", "Financial Flows"),
    ("sources253", "German Sources"),
    ("sources254", "Global Sources"),
    ("documents255", "Documents 255"),
    ("entities256", "Entity Resolution 256"),
    ("framing257", "Framing/Chain 257"),
    ("claims258", "Claims/Sources 258"),
    ("publication259", "Publication/Legal 259"),
    ("qualification260", "Phase 10 RC 260"),
    ("caseintelligence261", "Case Intelligence 261"),
    ("taskgraph262", "Task Graph 262"),
    ("research263", "AI Research/Dossier 263"),
    ("execution264", "AI Execution/Timeline 264"),
    ("temporal265", "Temporal/OPSEC 265"),
    ("network266", "Network/OPSEC 266"),
    ("paths267", "Paths/OPSEC 267"),
    ("hypothesis268", "Hypothesis/OPSEC 268"),
    ("ach269", "ACH/Leak Preflight 269"),
    ("collection270", "Gaps/Collection 270"),
    ("source271", "Source Independence 271"),
    ("narrative272", "Narrative Diffusion 272"),
    ("documents273", "Document Corpus 273"),
    ("knowledge274", "Cross-Case Knowledge 274"),
    ("reasoning275", "Reasoning Ledger 275"),
    ("agents276", "Co-Analyst Agents 276"),
    ("redteam277", "Red-Team Analyst 277"),
    ("product278", "Intelligence Product 278"),
    ("qualification279", "Full Case Qualification 279"),
    ("release280", "Phase-11 Release Candidate 280"),
    ("phase12_281", "Phase-12 Mission Controller 281"),
    ("phase12_282", "Mission Queue / AI Training 282"),
    ("phase12_283", "Mission Integrity / AI Training 283"),
    ("phase12_284", "Foundation Freeze / Failure Containment 284"),
    ("phase12_285", "Geführte Controlled Collection 285"),
    ("phase12_286", "Isolated Collection Gateway 286"),
    ("phase12_287", "Capture Worker 287"),
    ("phase12_288", "Capture Integrity & Replay 288"),
    ("phase12_289", "AI Investigation Depth 289"),
    ("phase12_290", "Discriminating Evidence 290"),
    ("phase12_291", "Adaptive Orchestration 291"),
    ("phase12_292", "Cross-Surface Fusion 292"),
    ("phase12_293", "Operational Strength 293"),
    ("phase12_294", "Operational Resilience 294"),
    ("phase12_295", "Operational Continuity 295"),
    ("phase12_296", "Operational Strength Freeze 296"),
    ("phase12_297", "Field Qualification 297"),
    ("phase12_298", "Field Pressure 298"),
    ("phase12_299", "Pre-RC 299"),
    ("phase12_300", "Phase-12 RC 300"),
    ("phase13_301", "Phase 13 · Direct Tor 301"),
    ("people244", "People"),
    ("evidence244", "Evidence"),
    ("graph244", "Graph"),
    ("timeline244", "Timeline"),
    ("research244", "Research"),
    ("coai244", "Co-AI Investigator"),
    ("opsec244", "OPSEC"),
    ("reports244", "Reports"),
 ]

NAV = [
    ("cockpit302", "Cockpit"),
    ("intake3061", "Personen & Firmen"),
    ("research3061", "Recherche"),
    ("investigation302", "AI-Ermittlung"),
    ("evidence302", "Evidenz & Daten"),
    ("analysis302", "Graph & Timeline"),
    ("operations302", "OPSEC & Betrieb"),
    ("reports302", "Dossier"),
]
ADVANCED_KEYS = {key for key, _ in ADVANCED_NAV}
TAB_LABELS = dict(ADVANCED_NAV + NAV)
LEGACY_TABS = {"overview","investigation167","handover168","research147","sourceops187","monitor210","build214","graph_lab","assistant140","reports142","security143","evidence211","build212","build213","capture150","entities","identity139","quality141","final144","final145","auth146","connectors148","ecosystem149","research","workflow137","research_intelligence","intake","capture_identity","photos","evidence","evidence138","graph","timeline","contradictions","assistant","orchestrator","synthesis","governance","review","security","reliability","operations","release","export","audit"}



def _case_selector(cases: list[dict[str, Any]], selected: str, tab: str) -> str:
    options = "".join(
        f'<option value="{_esc(c["case_id"])}" {"selected" if c["case_id"] == selected else ""}>{_esc(c["title"])} · {_esc(c["status"])}</option>'
        for c in cases
    )
    return f'''<form class="case-switch" method="get" action="/"><input type="hidden" name="tab" value="{_esc(tab)}"><select name="case_id" onchange="this.form.submit()">{options}</select><noscript><button>Fall öffnen</button></noscript></form>'''


def _flowbar(ctx: Any, case_id: str) -> str:
    state = ctx.investigation_flow_1222.case_flow(case_id)
    targets = ctx.targets.list_targets(case_id)
    research_tasks = int((ctx.db.one("SELECT COUNT(*) AS n FROM search_tasks WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
    ai_count = int(state.get("local_ai_runs") or 0) + int(state.get("web_ai_runs") or 0)
    dossier_count = int((ctx.db.one("SELECT COUNT(*) AS n FROM phase13_dossier_revisions_306 WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
    steps = [
        ("intake3061", "1. Person/Firma", len(targets)),
        ("research3061", "2. Recherche", research_tasks),
        ("investigation302", "3. AI-Ermittlung", ai_count),
        ("reports302", "4. Dossier", dossier_count),
    ]
    return '<div class="flowbar simplified">' + "".join(
        f'<a class="flowstep {"ready" if count else ""}" href="{_link(key, case_id)}"><b>{_esc(label)}</b>{int(count)} Hinweise</a>'
        for key, label, count in steps
    ) + "</div>"


def _overview(ctx: Any, case_id: str) -> str:
    snap = ctx.investigation_workspace_122.case_snapshot(case_id)
    flow = ctx.investigation_flow_1222.case_flow(case_id)
    labels = {
        "open_search_tasks": "Offene Rechercheaufgaben", "new_intake": "Neuer Intake",
        "evidence_packages": "Evidence Packages", "evidence_integrity_attention": "Integritätshinweise",
        "entities": "Entitäten", "merge_reviews": "Entity-Matches", "relations_review": "Graph-Reviews",
        "timeline_review": "Timeline-Reviews", "open_contradictions": "Offene Widersprüche",
        "pending_reviews": "Wartende Reviews", "recovery_attention": "Recovery-Hinweise",
    }
    cards = "".join(
        f'<div class="metric"><div class="label">{_esc(labels.get(k, k))}</div><div class="value">{int(v)}</div></div>'
        for k, v in snap["metrics"].items()
    )
    actions = "".join(
        f'<a class="action-card {_esc(a["priority"])}" href="{_link(a["section"], case_id)}"><b>{_esc(a["label"])}</b><br><span class="badge">{int(a["count"])} offen</span></a>'
        for a in snap["next_actions"]
    )
    next_label = TAB_LABELS.get(flow["next_step"], flow["next_step"])
    case = snap["case"]
    return f'''<div class="notice">{_esc(snap["epistemic_notice"])}</div>
<div class="panel"><h2>{_esc(case["title"])}</h2><div class="form-grid"><div><span class="badge">{_esc(case["status"])}</span><p><b>Zweck:</b> {_esc(case["purpose"])}</p></div><div><p><b>Rechtsgrundlage:</b> {_esc(case["legal_basis"])}</p><p><b>Jurisdiktion:</b> {_esc(case.get("jurisdiction"))}</p></div></div><p><a class="button" href="{_link(flow['next_step'], case_id)}">Weiter mit: {_esc(next_label)}</a></p></div>
<div class="panel"><h2>Workflow-Lage</h2><div class="metrics">{cards}</div></div>
<div class="panel"><h2>Priorisierte nächste Schritte</h2><div class="actions">{actions}</div></div>'''


def _entities(ctx: Any, case_id: str, csrf: str) -> str:
    targets = ctx.targets.list_targets(case_id)
    entities = ctx.investigation_workspace_122.list_objects(case_id, "entity", limit=300)
    profiles: list[str] = []
    marital_labels = {"single":"ledig","married":"verheiratet","separated":"getrennt","divorced":"geschieden","widowed":"verwitwet","unknown":"unbekannt"}
    life_labels = {"alive":"lebend","deceased":"verstorben","unknown":"unbekannt"}
    for target in targets:
        profile = ctx.build135.profile(case_id, target["target_id"])
        attrs = profile.get("attributes") or {}
        occupation = (attrs.get("occupation") or {}).get("value") or {}
        birth = (attrs.get("birth_date") or {}).get("value") or ""
        age = profile.get("calculated_age")
        age_est = (attrs.get("age_estimate") or {}).get("value") or {}
        age_text = str(age) if age is not None else ""
        if not age_text and (age_est.get("min") or age_est.get("max")):
            age_text = f'{age_est.get("min") or "?"}–{age_est.get("max") or "?"} (geschätzt)'
        marital = (attrs.get("marital_status") or {}).get("value") or "unknown"
        life = (attrs.get("life_status") or {}).get("value") or "unknown"
        height = (attrs.get("height_cm") or {}).get("value")
        children = (attrs.get("children") or {}).get("value") or {}
        if children.get("unknown", True):
            child_text = "unbekannt"
        elif children.get("none_known"):
            child_text = "keine Kinder bekannt"
        else:
            child_text = str(children.get("count", 0))
        occupation_text = " · ".join(x for x in [str(occupation.get("title") or ""), str(occupation.get("organisation") or "")] if x) or "unbekannt"
        profiles.append(f'''<div class="panel"><h3>{_esc(target["name"])}</h3><div class="form-grid"><div><b>Beruf:</b> {_esc(occupation_text)}<br><b>Familienstand:</b> {_esc(marital_labels.get(str(marital), marital))}<br><b>Lebensstatus:</b> {_esc(life_labels.get(str(life), life))}</div><div><b>Geburtsdatum:</b> {_esc(birth or "unbekannt")}<br><b>Alter:</b> {_esc(age_text or "unbekannt")}<br><b>Größe:</b> {_esc(str(height) + " cm" if height else "unbekannt")}<br><b>Kinder:</b> {_esc(child_text)}</div></div><div class="footer">{len(attrs)} Profilattribute · {len(profile.get("contradictions") or [])} offene Widersprüche · dynamische Altersberechnung</div></div>''')
    return f'''<div class="notice warn">Die Angaben sind Rechercheanker und Kandidaten. Das Anlegen bestätigt keine Identität. Sensible Profilangaben werden mit Quelle, Zeitpunkt, Confidence, Reviewstatus und Änderungshistorie gespeichert.</div>
<div class="panel"><h2>Person oder Firma aufnehmen</h2><p>Nach dem Speichern führt EagleEye direkt in die Recherche. Die Identität bleibt bis zur Prüfung <code>candidate_only</code>.</p><form method="post" action="/subjects/create"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="form-grid"><div class="field"><label>Zieltyp</label><select name="subject_type"><option value="person">Person</option><option value="organization">Firma / Organisation</option></select></div><div class="field"><label>Name / Firmenname</label><input name="name" required placeholder="Vorname Nachname oder Firmenname"></div><div class="field"><label>Rechercheauftrag/Ziel</label><input name="objective" placeholder="Was soll geklärt werden?"></div><div class="field"><label>Aliasse</label><textarea name="aliases" rows="2"></textarea></div><div class="field"><label>Usernames</label><textarea name="usernames" rows="2"></textarea></div><div class="field"><label>E-Mail-Adressen</label><textarea name="emails" rows="2"></textarea></div><div class="field"><label>Orte</label><textarea name="locations" rows="2"></textarea></div><div class="field"><label>Firmen/Organisationen</label><textarea name="companies" rows="2"></textarea></div><div class="field"><label>Domains</label><textarea name="domains" rows="2"></textarea></div></div>
<details open><summary><b>Person Profile Pro · Build 140</b></summary><div class="form-grid">
<div class="field"><label>Beruf</label><input name="occupation_title" placeholder="Berufsbezeichnung"><label><input type="checkbox" name="occupation_known" value="1"> Angabe bekannt</label><label><input type="checkbox" name="occupation_approximate" value="1"> ungefähr</label></div>
<div class="field"><label>Organisation / Arbeitgeber</label><input name="occupation_organisation"><div class="inline"><input name="occupation_from" placeholder="von, z. B. 2018"><input name="occupation_to" placeholder="bis"></div><label><input type="checkbox" name="occupation_current" value="1"> aktueller Beruf</label></div>
<div class="field"><label>Familienstand</label><select name="marital_status"><option value="unknown">unbekannt</option><option value="single">ledig</option><option value="married">verheiratet</option><option value="separated">getrennt</option><option value="divorced">geschieden</option><option value="widowed">verwitwet</option></select><label><input type="checkbox" name="marital_known" value="1"> Angabe bekannt</label><label><input type="checkbox" name="marital_approximate" value="1"> ungefähr</label></div>
<div class="field"><label>Lebensstatus</label><select name="life_status"><option value="unknown">unbekannt</option><option value="alive">lebend</option><option value="deceased">verstorben</option></select><label><input type="checkbox" name="life_known" value="1"> Angabe bekannt</label><label><input type="checkbox" name="life_approximate" value="1"> ungefähr</label></div>
<div class="field"><label>Geburtsdatum</label><input name="birth_date" placeholder="YYYY, YYYY-MM oder YYYY-MM-DD"><label><input type="checkbox" name="birth_known" value="1"> Angabe bekannt</label><label><input type="checkbox" name="birth_approximate" value="1"> ungefähr</label></div>
<div class="field"><label>Geschätztes Alter</label><div class="inline"><input type="number" name="age_estimate_min" min="0" max="130" placeholder="von"><input type="number" name="age_estimate_max" min="0" max="130" placeholder="bis"></div><label><input type="checkbox" name="age_known" value="1"> Schätzung erfasst</label></div>
<div class="field"><label>Körpergröße in cm</label><input type="number" name="height_cm" min="80" max="250"><label><input type="checkbox" name="height_known" value="1"> Angabe bekannt</label><label><input type="checkbox" name="height_approximate" value="1"> ungefähr</label></div>
<div class="field"><label>Anzahl Kinder</label><input type="number" name="children_count" min="0" max="30"><label><input type="checkbox" name="children_known" value="1"> Anzahl bekannt</label><label><input type="checkbox" name="no_children_known" value="1"> keine Kinder bekannt</label><label><input type="checkbox" name="children_approximate" value="1"> ungefähr</label></div>
<div class="field"><label>Reviewstatus</label><select name="profile_review_status"><option value="unconfirmed">unbestätigt</option><option value="supported">belegt</option><option value="contradictory">widersprüchlich</option></select><label>Confidence 0–1</label><input name="profile_confidence" type="number" min="0" max="1" step="0.05" value="0.5"></div>
<div class="field"><label>Quellentitel</label><input name="profile_source_title" value="Ermittlerangabe"><label>Öffentliche HTTPS-Quelle, optional</label><input name="profile_source_url" type="url" placeholder="https://..."></div>
</div><div class="field"><label>Ermittlernotiz zum Profil</label><textarea name="profile_note" rows="3"></textarea></div></details>
<div class="field"><label>Allgemeine Notizen</label><textarea name="notes" rows="3"></textarea></div><p><button>Aufnehmen und direkt zur Recherche</button></p></form></div>
<div class="panel"><h2>Personenprofile</h2>{''.join(profiles) if profiles else '<div class="empty">Noch kein Personenprofil.</div>'}</div>
<div class="panel"><h2>Personen-/Firmen-Rechercheprofile</h2>{_table(targets, [("name","Name/Anker"),("aliases_json","Aliasse"),("usernames_json","Usernames"),("emails_json","E-Mails"),("created_at","Zeit")])}</div>
<div class="panel"><h2>Resolution-Entitäten</h2>{_table(entities, [("display_name","Name"),("entity_type","Typ"),("candidate_only","Candidate"),("created_by","Erstellt von"),("created_at","Zeit")], object_type="entity", id_column="resolution_entity_id", case_id=case_id)}</div>'''

def _research(ctx: Any, case_id: str, csrf: str, *, page: int = 1, min_precision: int = 0, target_filter: str = "") -> str:
    targets = ctx.targets.list_targets(case_id)
    packages = ctx.search_workbench.list_packages(case_id)
    svc = ctx.scale_performance_123
    if target_filter and not any(t["target_id"] == target_filter for t in targets):
        target_filter = ""
    task_page = svc.list_tasks(case_id, target_id=target_filter, page=page, page_size=50, min_precision=min_precision)
    rows = task_page["rows"]
    target_options = "".join(f'<option value="{_esc(t["target_id"])}" {"selected" if t["target_id"] == target_filter else ""}>{_esc(t["name"])}</option>' for t in targets) or '<option value="">Zuerst Person oder Firma aufnehmen</option>'
    filter_options = '<option value="">Alle Ziele</option>' + "".join(f'<option value="{_esc(t["target_id"])}" {"selected" if t["target_id"] == target_filter else ""}>{_esc(t["name"])}</option>' for t in targets)
    profiles = []
    for target in targets:
        profile = svc.build_profile(case_id, target["target_id"])
        profiles.append(f'''<div class="metric"><div class="label">{_esc(target["name"])}</div><div class="value">{profile["completeness"]}%</div><div class="profile-meter"><span style="width:{profile["completeness"]}%"></span></div><div class="footer">{profile["anchor_count"]} Anker · {profile["type_count"]} Typen</div></div>''')
    task_rows: list[str] = []
    for row in rows:
        launch_form = f'''<form class="inline" method="post" action="/research/launch"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><input type="hidden" name="task_id" value="{_esc(row.get('task_id'))}"><button class="small">In bestehendem Firefox-Tab öffnen</button></form><form class="inline" method="post" action="/research/launch-parallel"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><input type="hidden" name="task_id" value="{_esc(row.get('task_id'))}"><button class="small ghost">5 Quellen parallel</button></form>'''
        task_rows.append(f'''<tr><td class="precision">{int(row.get("precision_score") or 0)}</td><td>{_esc(row.get("package_name"))}</td><td>{_esc(row.get("category"))}</td><td>{_esc(row.get("query"))}<div class="footer">{_esc(row.get("rationale"))}</div></td><td>{_esc(row.get("engine"))}</td><td>{_esc(row.get("status"))}</td><td>{launch_form}</td></tr>''')
    tasks_html = '<div class="empty">Noch keine Rechercheaufgaben. Lege zuerst eine Person an oder erzeuge eine adaptive Recherche.</div>'
    if task_rows:
        tasks_html = '<div class="table-wrap"><table><thead><tr><th>Präzision</th><th>Paket</th><th>Kategorie</th><th>Suchabfrage</th><th>Engine</th><th>Status</th><th>Geschützter Rechercheausstieg</th></tr></thead><tbody>' + "".join(task_rows) + '</tbody></table></div>'
    prev_link = _link("research3061", case_id, page=str(max(1, task_page["page"] - 1)), min_precision=str(min_precision), target_id=target_filter)
    next_link = _link("research3061", case_id, page=str(min(task_page["pages"], task_page["page"] + 1)), min_precision=str(min_precision), target_id=target_filter)
    pagination = f'''<div class="pagination"><a class="button ghost small" href="{prev_link}">←</a><span>Seite {task_page["page"]}/{task_page["pages"]} · {task_page["total"]} Aufgaben</span><a class="button ghost small" href="{next_link}">→</a></div>'''
    return f'''<div class="notice">Je mehr <b>geprüfte Rechercheanker</b> zum Ziel vorliegen, desto spezifischer werden die Queries. Suchziele werden als neue Tabs im bereits laufenden Firefox geöffnet; bestehende Anmeldungen bleiben erhalten. Mit „5 Quellen parallel“ startet dieselbe zielbezogene Query gleichzeitig in Google, Bing, DuckDuckGo, Brave und Startpage. Alle Ziele öffnen sich als neue Tabs in der bereits laufenden Firefox-Sitzung. Das persönliche Firefox-Profil bleibt unberührt.</div>
<div class="panel"><h2>Adaptive Rechercheprofile</h2><div class="metrics">{"".join(profiles) if profiles else '<div class="empty">Noch kein Rechercheprofil.</div>'}</div></div>
<div class="panel"><h2>AI-Ermittlung · Investigation Crawler v2</h2><p>Build 309 verknüpft den autorisierten Crawl zusätzlich mit einem mehrsprachigen, provenance-gebundenen Query-Plan: AI-Suche/Seed-URLs → Frontier Queue → OPSEC-Prüfung → read-only Abruf → candidate-only Intake → Evidenz-Triage. Entdeckte Links werden nur innerhalb des jeweils autorisierten Root-Hosts verfolgt. Keine Logins, Formulare, Uploads, Kontaktaktionen oder automatische Identitätsbestätigung.</p><form method="post" action="/build309/crawl"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="form-grid"><div class="field"><label>Zielperson / Firma</label><select name="target_id" required>{target_options}</select></div><div class="field"><label>Suchprovider</label><select name="provider"><option value="auto">Auto (SearXNG/Brave/Ollama-Web)</option><option value="searxng">SearXNG</option><option value="brave">Brave API</option><option value="ollama_web">Ollama Web Search</option><option value="browser_queue">Nur Seed-URLs</option></select></div><div class="field"><label>Max. AI-Queries</label><input type="number" name="max_queries" min="1" max="12" value="6"></div><div class="field"><label>Treffer pro Query</label><input type="number" name="max_results" min="1" max="20" value="6"></div><div class="field"><label>Max. Seiten/Dokumente</label><input type="number" name="max_pages" min="1" max="40" value="12"></div><div class="field"><label>Crawl-Tiefe</label><input type="number" name="max_depth" min="0" max="3" value="2"></div><div class="field"><label>Frontier-Limit</label><input type="number" name="max_frontier" min="20" max="1000" value="250"></div><div class="field"><label>Gesamtbudget Bytes</label><input type="number" name="max_total_bytes" min="65536" max="20000000" value="4000000"></div></div><div class="field"><label>Rechercheauftrag / Zweck</label><textarea name="purpose" rows="3" required placeholder="Welche Frage soll der autorisierte Crawl anhand öffentlich zugänglicher Quellen untersuchen?"></textarea></div><div class="field"><label>Öffentliche Seed-URLs (optional, eine pro Zeile)</label><textarea name="seed_urls" rows="3" placeholder="https://example.org/person
https://example.org/document.pdf"></textarea></div><div class="field"><label>Freigabephrase</label><input name="confirmation" required placeholder="CRAWL FREIGEBEN"></div><p><button>Crawl einmalig freigeben und ausführen</button></p></form></div>
<div class="panel"><h2>Build 309 · AI Query Generation / Translation</h2><p>Erzeugt mehrsprachige, provenance-gebundene Suchpläne aus vorhandenen Zielankern. Enthält eigene Gegenbeleg-Suchen und lokale Begriffe für Register, Firmen- und Finanzdokumente.</p><form method="post" action="/build309/query-plan"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="form-grid"><div class="field"><label>Zielperson / Firma</label><select name="target_id" required>{target_options}</select></div><div class="field"><label>Max. Queries</label><input type="number" name="max_queries" min="4" max="80" value="24"></div></div><div class="field"><label>Ermittlungsfrage</label><textarea name="purpose" rows="3" required></textarea></div><p><button>Mehrsprachigen Query-Plan erzeugen</button></p></form></div>
<div class="two-col"><div class="panel"><h2>Geprüften Rechercheanker ergänzen</h2><form method="post" action="/research/anchor"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="field"><label>Zielperson / Firma</label><select name="target_id" required>{target_options}</select></div><div class="form-grid"><div class="field"><label>Ankertyp</label><select name="anchor_type"><option>alias</option><option>username</option><option>email</option><option>location</option><option>organisation</option><option>role</option><option>domain</option><option>birth_year</option><option>identifier</option><option>keyword</option></select></div><div class="field"><label>Zuverlässigkeit 0,1–1,0</label><input name="reliability" type="number" step="0.05" min="0.1" max="1" value="0.75"></div></div><div class="field"><label>Vom Ermittler geprüfter Wert</label><input name="value" required></div><p><button>Anker prüfen und speichern</button></p></form></div>
<div class="panel"><h2>Adaptive Recherche erzeugen</h2><form method="post" action="/research/adaptive"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="field"><label>Zielperson / Firma</label><select name="target_id" required>{target_options}</select></div><div class="field"><label>Suchmaschinen</label><div class="inline"><label><input type="checkbox" name="engine_google" value="1" checked> Google</label><label><input type="checkbox" name="engine_bing" value="1" checked> Bing</label><label><input type="checkbox" name="engine_duckduckgo" value="1" checked> DuckDuckGo</label><label><input type="checkbox" name="engine_brave" value="1" checked> Brave</label><label><input type="checkbox" name="engine_startpage" value="1" checked> Startpage</label></div></div><div class="field"><label>Maximale Queryzahl</label><input type="number" min="10" max="150" name="limit" value="80"></div><p><button>Recherche als kontrollierten Job starten</button></p></form></div></div>
<div class="panel"><h2>Recherchefilter</h2><form method="get" action="/" class="inline"><input type="hidden" name="tab" value="research"><input type="hidden" name="case_id" value="{_esc(case_id)}"><select name="target_id">{filter_options}</select><label>Min. Präzision <input style="width:90px" type="number" min="0" max="100" name="min_precision" value="{int(min_precision)}"></label><button class="ghost">Filtern</button></form></div>
<div class="panel"><h2>Suchpakete</h2>{_table(packages, [("name","Paket"),("objective","Ziel"),("task_count","Aufgaben"),("status","Status")])}</div>
<div class="panel"><h2>Suchaufgaben</h2>{tasks_html}{pagination}</div><div class="panel"><h2>Nächster Schritt · AI-Ermittlung</h2><p>Sobald Suchaufgaben gestartet und relevante Treffer in Intake/Evidenz übernommen wurden, wird der Fall an die AI-Ermittlung übergeben.</p><a class="button" href="{_link('investigation302', case_id)}">Weiter zur AI-Ermittlung →</a></div>'''


def _intake(ctx: Any, case_id: str, csrf: str) -> str:
    rows = ctx.investigation_workspace_122.intake(case_id, status="all", limit=300)
    targets = ctx.targets.list_targets(case_id)
    target_options = '<option value="">Ohne Zielbindung</option>' + "".join(f'<option value="{_esc(t["target_id"])}">{_esc(t["name"])}</option>' for t in targets)
    cards: list[str] = []
    for row in rows:
        status = row.get("review_status", "new")
        decision = ""
        if status == "new":
            decision = f'''<form class="decision" method="post" action="/workspace/intake/decision"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><input type="hidden" name="intake_id" value="{_esc(row["intake_id"])}"><select name="decision"><option value="accepted_for_evidence">Für Evidence sichern</option><option value="deferred">Zurückstellen</option><option value="duplicate">Duplikat</option><option value="rejected">Verwerfen</option></select><input name="reason" minlength="8" required placeholder="Nachvollziehbare Begründung"><button>Entscheidung speichern</button></form>'''
        detail = f'/workspace/detail/intake/{quote(str(row["intake_id"]))}?case_id={quote(case_id)}'
        cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{_esc(row.get("title") or "Unbenannter Kandidat")}</h3><span class="badge candidate">candidate_only</span> <span class="badge">{_esc(status)}</span></div><a class="button ghost small" href="{detail}">Details</a></div><p>{_esc(_short(row.get("snippet"), 600))}</p><div class="footer">Provider: {_esc(row.get("provider_key"))} · {_esc(row.get("canonical_url"))} · {_esc(row.get("created_at"))}</div>{decision}</div>''')
    return f'''<div class="panel"><h2>Öffentlichen Fund aufnehmen</h2><p>Ein Treffer wird in den kontrollierten Intake überführt und zugleich durch die bestehende Capture-, Security- und lokale Triage-Pipeline verarbeitet.</p><form method="post" action="/intake/manual"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="form-grid"><div class="field"><label>Zielperson optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Titel</label><input name="title" placeholder="Fundtitel"></div><div class="field"><label>Öffentliche URL</label><input name="url" placeholder="https://..."></div><div class="field"><label>Quellbezeichnung</label><input name="source_label" value="browser_workspace_1222"></div></div><div class="field"><label>Sichtbarer Text/Snippet</label><textarea name="text" rows="8" placeholder="Text aus dem Suchtreffer oder Browser einfügen"></textarea></div><div class="field"><label>HTML-Auszug optional</label><textarea name="html_snapshot" rows="4"></textarea></div><p><button>Als Kandidat in Intake übernehmen</button></p></form></div>
<div class="notice warn">Eine Annahme sichert den unveränderten Payload als candidate-only Evidence. Sie bestätigt weder Identität noch Aussageinhalt.</div><div class="panel"><h2>Kontrollierte Intake-Inbox</h2>{"".join(cards) if cards else '<div class="empty">Keine Intake-Einträge.</div>'}</div>'''


def _objects(ctx: Any, case_id: str, object_type: str) -> str:
    configs = {
        "evidence": ("Evidence Packages", [("title","Titel"),("source_kind","Quelle"),("status","Status"),("candidate_only","Candidate"),("raw_sha256","SHA-256"),("captured_at","Erfasst")], "package_id"),
        "relation": ("Knowledge Graph", [("predicate","Prädikat"),("subject_entity_id","Subjekt"),("object_entity_id","Objekt"),("state","Status"),("candidate_only","Candidate")], "relation_id"),
        "timeline": ("Timeline", [("start_date","Beginn"),("end_date","Ende"),("title","Ereignis"),("state","Status"),("confidence","Konfidenz")], "event_id"),
        "contradiction": ("Widersprüche", [("conflict_type","Typ"),("title","Titel"),("severity","Schwere"),("impact","Auswirkung"),("state","Status")], "contradiction_id"),
    }
    title, columns, id_column = configs[object_type]
    rows = ctx.investigation_workspace_122.list_objects(case_id, object_type, limit=300)
    return f'<div class="notice">Gespeicherte Kandidaten werden angezeigt. Der Workspace nimmt keine automatische Bestätigung oder Promotion vor.</div><div class="panel"><h2>{_esc(title)}</h2>{_table(rows, columns, object_type=object_type, id_column=id_column, case_id=case_id)}</div>'


def _graph(ctx: Any, case_id: str) -> str:
    payload = ctx.scale_performance_123.graph_payload(case_id, limit_nodes=600, limit_edges=1200)
    counts = " · ".join(f"{_esc(k)} {int(v)}" for k, v in sorted(payload["meta"]["type_counts"].items()))
    return f'''<div class="notice">Obsidian-orientierte Arbeitsansicht: Zoomen mit Mausrad, verschieben durch Ziehen, Knoten auswählen oder suchen. Kandidaten bleiben gestrichelt markiert; die Darstellung bestätigt keine Beziehung.</div>
<div class="panel"><div class="graph-toolbar"><input id="graph-search" placeholder="Knoten, Person, Domain oder Quelle suchen"><button id="graph-fit" class="ghost" type="button">Einpassen</button><button id="graph-reset" class="ghost" type="button">Auswahl löschen</button><span id="graph-count" class="badge">{payload["meta"]["node_count"]} Knoten · {payload["meta"]["edge_count"]} Kanten</span></div><div class="graph-shell"><div id="graph123" class="graph-stage" data-case-id="{_esc(case_id)}"><svg role="img" aria-label="Interaktiver Knowledge Graph"><rect class="graph-bg" width="100%" height="100%" fill="transparent"></rect><g class="graph-viewport"><g class="graph-edges"></g><g class="graph-nodes"></g></g></svg></div><aside class="graph-side"><div id="graph-detail" class="panel"><div class="graph-detail-type">Graph</div><h3>Knoten auswählen</h3><p>Details und Herkunft des ausgewählten Objekts erscheinen hier.</p></div><div class="panel"><h3>Typen</h3><p class="footer">{counts or 'Noch keine Graphobjekte.'}</p></div></aside></div></div><script src="/assets/graph123.js" defer></script>'''


def _assistant(ctx: Any, case_id: str, csrf: str, actor: str) -> str:
    targets = ctx.targets.list_targets(case_id)
    target_options = "".join(f'<option value="{_esc(t["target_id"])}">{_esc(t["name"])}</option>' for t in targets) or '<option value="">Zuerst Person oder Firma aufnehmen</option>'
    svc = ctx.ai_analyst_107
    cfg = svc.get_config()
    status = ctx.scale_performance_123.check_provider(case_id=case_id, provider=cfg.search_provider)
    auths = svc.list_authorizations(case_id, 50)
    ready = [a for a in auths if a.get("status") == "approved_once" and int(a.get("expires_at") or 0) >= int(time.time())]
    auth_options = "".join(f'<option value="{_esc(a["authorization_id"])}">{_esc(a["approved_by"])} · {_esc(a["provider"])} · {_esc(a["authorization_id"])}</option>' for a in ready) or '<option value="">Keine aktive Einmalfreigabe</option>'
    local_runs = ctx.local_ai_agent_101.list_runs(case_id, 20).get("runs", [])
    web_runs = svc.list_runs(case_id, 30)
    results = svc.list_results(case_id, 200)
    jobs = ctx.scale_performance_123.list_jobs(case_id, 30)
    external_ai = ctx.production_candidate_126.recent_external_ai(case_id, 30)
    provider_class = "provider-ready" if status.get("ready") else "provider-down"
    provider_note = _esc(status.get("detail"))
    return f'''<div class="notice">Der sichere Standard ist <b>Browser-Queue</b>: Query-Planung und Suchaufgaben funktionieren ohne SearXNG, Ollama oder API-Key. Externe Provider werden erst nach erfolgreichem Verbindungstest angesprochen.</div>
<div class="panel"><h2>Weitere Recherche mit ChatGPT</h2><p>Öffnet ausschließlich die offizielle ChatGPT-Startseite. EagleEye überträgt dabei <b>keine</b> Fall-ID, Personendaten, Suchanfrage, Prompt oder Evidence. Prüfe vor jedem manuellen Einfügen, ob die Daten dafür freigegeben und datenschutzrechtlich zulässig sind.</p><div class="inline"><a class="button ghost" href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">ChatGPT direkt öffnen</a><form method="post" action="/assistant/chatgpt-protected"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><button type="submit">In isoliertem Firefox-Profil öffnen</button></form></div><p class="footer">Der direkte Link ist bewusst leer und enthält keine automatisch vorbefüllten Falldaten. Der geschützte Start verwendet das fallgetrennte Investigator-Protection-Profil.</p></div>
<div class="panel"><h2>Providerstatus</h2><p class="{provider_class}"><b>{_esc(status.get("provider"))}:</b> {provider_note}</p></div>
<div class="two-col"><div class="panel"><h2>Lokaler Fallassistent</h2><form method="post" action="/assistant/local"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="field"><label>Fragestellung oder gewünschter nächster Schritt</label><textarea name="prompt" rows="5" placeholder="Analysiere die bisherige Falllage und priorisiere die nächsten Recherchehandlungen."></textarea></div><p><button>Fallassistent ausführen</button></p></form><h3>Letzte Assistentenläufe</h3>{_table(local_runs, [("created_at","Zeit"),("assist_type","Typ"),("status","Status"),("prompt","Auftrag")])}</div>
<div class="panel"><h2>Provider-Konfiguration</h2><form method="post" action="/assistant/config"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="field"><label>Suchprovider</label><select name="search_provider"><option value="browser_queue" {"selected" if cfg.search_provider == "browser_queue" else ""}>Browser-Queue – empfohlen, keine Zusatzdienste</option><option value="searxng" {"selected" if cfg.search_provider == "searxng" else ""}>SearXNG – lokale Installation erforderlich</option><option value="brave" {"selected" if cfg.search_provider == "brave" else ""}>Brave API</option><option value="ollama_web" {"selected" if cfg.search_provider == "ollama_web" else ""}>Ollama Web Search API</option></select></div><div class="field"><label>Lokale SearXNG-URL</label><input name="searxng_url" value="{_esc(cfg.searxng_url)}"></div><div class="field"><label>Lokale Ollama-URL – nur optionale Query-Planung</label><input name="ollama_url" value="{_esc(cfg.ollama_url)}"></div><div class="field"><label>Ollama-Modell optional</label><input name="ollama_model" value="{_esc(cfg.ollama_model)}"></div><div class="form-grid"><div class="field"><label>Land</label><input name="country" value="{_esc(cfg.country)}"></div><div class="field"><label>Sprache</label><input name="language" value="{_esc(cfg.language)}"></div></div><p><button>Konfiguration speichern und prüfen</button></p></form></div></div>
<div class="panel"><h2>Kontrollierte AI-gestützte Recherche</h2><div class="form-grid"><form method="post" action="/assistant/authorize"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="field"><label>Zielperson / Firma</label><select name="target_id" required>{target_options}</select></div><div class="field"><label>Leitender Ermittler</label><input name="approved_by" value="{_esc(actor)}" required></div><div class="field"><label>Dokumentierter Zweck</label><textarea name="purpose" rows="3" required></textarea></div><div class="field"><label>Provider</label><select name="provider"><option value="browser_queue" {"selected" if cfg.search_provider == "browser_queue" else ""}>browser_queue</option><option value="searxng" {"selected" if cfg.search_provider == "searxng" else ""}>searxng</option><option value="brave" {"selected" if cfg.search_provider == "brave" else ""}>brave</option><option value="ollama_web" {"selected" if cfg.search_provider == "ollama_web" else ""}>ollama_web</option></select></div><div class="form-grid"><div class="field"><label>Max. Queries</label><input type="number" min="1" max="12" name="max_queries" value="8"></div><div class="field"><label>Treffer/Query bei externem Provider</label><input type="number" min="1" max="20" name="max_results_per_query" value="10"></div></div><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="SUCHE FREIGEBEN" required></div><p><button>Einmalfreigabe anlegen</button></p></form>
<form method="post" action="/assistant/search"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}"><div class="field"><label>Freigabeticket</label><select name="authorization_id" required>{auth_options}</select></div><p><button>Recherche ausführen</button></p><p class="footer">Browser-Queue legt personalisierte Suchaufgaben an. Externe Provider übertragen gefundene Kandidaten in Intake.</p></form></div></div>
<div class="two-col"><div class="panel"><h2>Kontrollierte Jobs</h2>{_table(jobs, [("created_at","Zeit"),("job_type","Typ"),("status","Status"),("attempts","Versuche"),("error_text","Fehler")])}</div><div class="panel"><h2>AI-Suchläufe</h2>{_table(web_runs, [("created_at","Zeit"),("provider","Provider"),("status","Status"),("query_count","Queries"),("result_count","Treffer"),("error","Fehler")])}</div></div>
<div class="panel"><h2>Externe AI-Aufrufe</h2>{_table(external_ai, [("created_at","Zeit"),("tool_key","Werkzeug"),("destination_host","Ziel"),("launch_mode","Modus"),("status","Status")])}</div>
<div class="panel"><h2>Gefundene Kandidaten</h2>{_table(results, [("relevance","Score"),("title","Treffer"),("url","URL"),("query","Query"),("rationale","Begründung")])}</div>'''


def _review(ctx: Any, case_id: str) -> str:
    rows = ctx.db.all("SELECT item_id,title,provider,url,status,quality_score,sensitivity_level,created_at FROM review_items WHERE case_id=? ORDER BY created_at DESC LIMIT 300", (case_id,))
    return f'<div class="panel"><h2>Review-Warteschlange</h2>{_table(rows, [("title","Titel"),("provider","Provider"),("status","Status"),("quality_score","Qualität"),("sensitivity_level","Sensitivität"),("created_at","Zeit")])}</div>'


def _export(ctx: Any, case_id: str) -> str:
    rows = ctx.db.all("SELECT export_id,package_count,redaction_profile,manifest_sha256,created_by,created_at FROM evidence_exports_121 WHERE case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
    return f'''<div class="notice warn">Exports bleiben an Evidence-Integrität, Freigabe, Redaktionsprofil und Fallgrenze gebunden.</div><div class="panel"><h2>Evidence-Exports</h2>{_table(rows, [("export_id","Export-ID"),("package_count","Pakete"),("redaction_profile","Redaktion"),("manifest_sha256","Manifest"),("created_by","Erstellt von"),("created_at","Zeit")])}</div>'''


def _audit(ctx: Any, case_id: str) -> str:
    actions = ctx.investigation_workspace_122.recent_actions(case_id, 200)
    recovery = ctx.investigation_workspace_122.recovery_events(case_id, 100)
    audits = ctx.audit.list_for_case(case_id, 200)
    return f'''<div class="two-col"><div class="panel"><h2>Workspace-Aktionen</h2>{_table(actions, [("created_at","Zeit"),("actor","Akteur"),("action_type","Aktion"),("object_type","Objekt"),("object_id","ID")])}</div><div class="panel"><h2>Recovery</h2>{_table(recovery, [("created_at","Zeit"),("operation","Operation"),("state","Status"),("error_type","Fehler"),("cleanup_ok","Cleanup")])}</div></div><div class="panel"><h2>Globales Fallaudit</h2>{_table(audits, [("timestamp","Zeit"),("actor","Akteur"),("action","Aktion"),("object_type","Objekt"),("object_id","ID")])}</div>'''



def _sourceops187(ctx: Any, case_id: str, actor: str) -> str:
    dash = ctx.build187.dashboard(principal=actor)
    try:
        activation = ctx.build188.activation_board()
    except Exception:
        activation = {"counts": {"total": 0, "active": 0, "ready": 0, "live_validated": 0}, "sources": []}
    counts = dash["counts"]
    cards = []
    for source in dash["sources"]:
        technical = ""
        if dash["experience_mode"] == "expert":
            technical = '<div class="muted">{} · Limit {}/min · {} ms</div>'.format(
                _esc(source.get("mode", "")), _esc(source.get("rate_limit_per_minute", "")), _esc(source.get("average_latency_ms", 0))
            )
        cards.append('<div class="action-card"><div class="inline"><b>{}</b><span class="badge">{}</span><span class="badge">{}</span></div><p>{}</p><div class="inline"><span>Qualität: {}/100</span><span>Terms: {}</span><span>Parser: {}</span></div>{}</div>'.format(
            _esc(source["title"]), _esc(source["status"]), _esc(source["health"]), _esc(source["next_action"]),
            _esc(source["quality_score"]), _esc(source["terms_status"]), _esc(source["parser_status"]), technical
        ))
    cards_html = "".join(cards) if cards else '<div class="empty">Quellenprofile zuerst synchronisieren.</div>'
    message = dash["beginner_message"] if dash["experience_mode"] == "guided" else dash["expert_message"]
    ac = activation["counts"]
    return '<div class="notice"><b>Quellenbetrieb 188</b><br>{}<br><b>Schrittweise Produktivsetzung:</b> {} aktiv · {} bereit · {} live-validiert.</div><div class="metrics"><div class="metric"><div class="label">Quellenprofile</div><div class="value">{}</div></div><div class="metric"><div class="label">Production Ready</div><div class="value">{}</div></div><div class="metric"><div class="label">Gesund</div><div class="value">{}</div></div><div class="metric"><div class="label">Handlungsbedarf</div><div class="value">{}</div></div></div><div class="panel"><h2>Ein gemeinsamer Quellenarbeitsplatz</h2><p>Fragestellung → passende Quelle → Zugriff → Treffer als Kandidat → Prüfung. Technische Details bleiben in der Expertenansicht; der globale Ermittlungsworkflow bleibt unverändert.</p><div class="actions">{}</div></div>'.format(
        _esc(message), ac["active"], ac["ready"], ac["live_validated"], counts["total"], counts["production_ready"], counts["healthy"], counts["action_required"], cards_html
    )

def _create_case(csrf: str) -> str:
    return f'''<div class="panel"><h2>Ersten Fall anlegen</h2><p>Der Workspace arbeitet strikt fallgebunden.</p><form method="post" action="/cases/create"><input type="hidden" name="csrf" value="{_esc(csrf)}"><div class="form-grid"><div class="field"><label>Falltitel</label><input name="title" required></div><div class="field"><label>Mandant/Auftraggeber</label><input name="client"></div><div class="field"><label>Zweck</label><input name="purpose" required></div><div class="field"><label>Rechtsgrundlage</label><input name="legal_basis" required></div></div><p><button>Fall anlegen</button></p></form></div>'''


def _page(ctx: Any, *, tab: str, case_id: str, csrf: str, actor: str, message: str = "", error: str = "", page: int = 1, min_precision: int = 0, target_filter: str = "") -> str:
    cases = ctx.collaboration_governance_132.list_accessible_cases(actor)
    case = _safe_case(ctx, case_id, actor)
    selected = case["case_id"] if case else ""
    tab = tab if tab in ({key for key, _ in NAV} | ADVANCED_KEYS | LEGACY_TABS) else "cockpit302"
    nav = "".join(f'<a class="{"active" if key == tab else ""}" href="{_link(key, selected)}">{_esc(label)}</a>' for key, label in NAV) if selected else f'<a class="{"active" if tab == "auth146" else ""}" href="{_link("auth146", "")}">Benutzer &amp; Zugriff 146</a>'
    if not case and tab == "auth146":
        content = render_auth146(ctx, "", csrf, actor=actor, esc=_esc, table=_table)
    elif not case:
        content = _create_case(csrf)
    elif tab == "cockpit302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="cockpit")
    elif tab == "intake3061":
        content = _entities(ctx, selected, csrf)
    elif tab == "research3061":
        content = _research(ctx, selected, csrf, page=page, min_precision=min_precision, target_filter=target_filter)
    elif tab == "investigation302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="investigation")
    elif tab == "evidence302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="evidence")
    elif tab == "sources302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="sources")
    elif tab == "analysis302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="analysis")
    elif tab == "operations302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="operations")
    elif tab == "reports302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="reports")
    elif tab == "expert302":
        content = ctx.build343.render_workspace_panel(case_id=selected, csrf=csrf, section="expert")
    elif tab == "cockpit244":
        content = ctx.build244.render_section(case_id=selected, section="overview", csrf=csrf)
    elif tab == "workflow245":
        content = ctx.build245.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "monitor246":
        content = ctx.build246.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "runtime247":
        content = ctx.build247.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "production248":
        content = ctx.build248.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "stress249":
        content = ctx.build249.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "influence251":
        content = ctx.build251.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "finance252":
        content = ctx.build252.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "sources253":
        content = ctx.build253.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "sources254":
        content = ctx.build254.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "documents255":
        content = ctx.build255.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "entities256":
        content = ctx.build256.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "framing257":
        content = ctx.build257.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "claims258":
        content = ctx.build258.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "publication259":
        content = ctx.build259.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "qualification260":
        content = ctx.build260.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "caseintelligence261":
        content = ctx.build261.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "taskgraph262":
        content = ctx.build262.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "research263":
        content = ctx.build263.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "execution264":
        content = ctx.build264.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "temporal265":
        content = ctx.build265.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "network266":
        content = ctx.build266.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "paths267":
        content = ctx.build267.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "hypothesis268":
        content = ctx.build268.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "ach269":
        content = ctx.build269.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "collection270":
        content = ctx.build270.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "source271":
        content = ctx.build271.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "narrative272":
        content = ctx.build272.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "documents273":
        content = ctx.build273.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "knowledge274":
        content = ctx.build274.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "reasoning275":
        content = ctx.build275.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "agents276":
        content = ctx.build276.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "redteam277":
        content = ctx.build277.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "product278":
        content = ctx.build278.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "qualification279":
        content = ctx.build279.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "release280":
        content = ctx.build280.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_281":
        content = ctx.build281.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_282":
        content = ctx.build282.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_283":
        content = ctx.build283.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_284":
        content = ctx.build284.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_285":
        content = ctx.build285.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_286":
        content = ctx.build286.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_287":
        content = ctx.build287.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_288":
        content = ctx.build288.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_289":
        content = ctx.build289.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_290":
        content = ctx.build290.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_291":
        content = ctx.build291.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_292":
        content = ctx.build292.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_293":
        content = ctx.build293.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_294":
        content = ctx.build294.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_295":
        content = ctx.build295.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_296":
        content = ctx.build296.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_297":
        content = ctx.build297.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_298":
        content = ctx.build298.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_299":
        content = ctx.build299.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase12_300":
        content = ctx.build300.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "phase13_301":
        content = ctx.build301.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "people244":
        content = ctx.build244.render_section(case_id=selected, section="people", csrf=csrf)
    elif tab == "evidence244":
        content = ctx.build244.render_section(case_id=selected, section="evidence", csrf=csrf)
    elif tab == "graph244":
        content = ctx.build244.render_section(case_id=selected, section="graph", csrf=csrf)
    elif tab == "timeline244":
        content = ctx.build244.render_section(case_id=selected, section="timeline", csrf=csrf)
    elif tab == "research244":
        content = ctx.build244.render_section(case_id=selected, section="research", csrf=csrf)
    elif tab == "coai244":
        content = ctx.build244.render_section(case_id=selected, section="coai", csrf=csrf)
    elif tab == "opsec244":
        content = ctx.build244.render_section(case_id=selected, section="opsec", csrf=csrf)
    elif tab == "reports244":
        content = ctx.build244.render_section(case_id=selected, section="reports", csrf=csrf)
    elif tab == "overview":
        content = _overview(ctx, selected)
    elif tab == "investigation167":
        content = render_investigation167(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "handover168":
        content = render_handover168(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "entities":
        content = _entities(ctx, selected, csrf)
    elif tab == "identity139":
        content = render_identity139(ctx, selected, csrf, esc=_esc)
    elif tab == "assistant140":
        content = render_assistant140(ctx, selected, csrf, esc=_esc)
    elif tab == "quality141":
        content = render_quality141(ctx, selected, csrf, esc=_esc)
    elif tab == "reports142":
        content = render_reports142(ctx, selected, csrf, esc=_esc)
    elif tab == "security143":
        content = render_security143(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "final144":
        content = render_final144(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "final145":
        content = render_final145(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "auth146":
        content = render_auth146(ctx, selected, csrf, actor=actor, esc=_esc, table=_table)
    elif tab == "research147":
        content = render_research147(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "sourceops187":
        content = _sourceops187(ctx, selected, actor)
    elif tab == "monitor210":
        content = ctx.build210.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "evidence211":
        content = ctx.build211.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "build212":
        content = ctx.build212.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "build213":
        content = ctx.build213.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "build214":
        content = ctx.build223.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build224.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build225.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build226.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build227.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build228.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build229.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build230.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build231.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build232.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build233.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build234.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build235.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build236.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build237.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build238.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build239.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build240.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build241.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build242.render_workspace_panel(case_id=selected, csrf=csrf) + ctx.build243.render_workspace_panel(case_id=selected, csrf=csrf)
    elif tab == "connectors148":
        content = render_connectors148(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "ecosystem149":
        content = render_ecosystem149(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "capture150":
        content = render_capture150(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "research":
        content = _research(ctx, selected, csrf, page=page, min_precision=min_precision, target_filter=target_filter)
    elif tab == "workflow137":
        content = render_workflow137(ctx, selected, csrf, esc=_esc)
    elif tab == "research_intelligence":
        content = render_research_strategy(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "intake":
        content = _intake(ctx, selected, csrf)
    elif tab == "capture_identity":
        content = render_capture_identity(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "photos":
        content = render_photo141(ctx, selected, csrf, esc=_esc)
    elif tab == "evidence":
        content = _objects(ctx, selected, "evidence")
    elif tab == "evidence138":
        content = render_evidence138(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "graph":
        content = _graph(ctx, selected)
    elif tab == "graph_lab":
        content = render_graph_hypothesis(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "timeline":
        content = _objects(ctx, selected, "timeline")
    elif tab == "contradictions":
        content = _objects(ctx, selected, "contradiction")
    elif tab == "assistant":
        content = _assistant(ctx, selected, csrf, actor)
    elif tab == "orchestrator":
        content = render_orchestrator(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "synthesis":
        content = render_synthesis(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "governance":
        content = render_governance(ctx, selected, csrf, actor=actor, esc=_esc, table=_table)
    elif tab == "review":
        content = _review(ctx, selected)
    elif tab == "security":
        content = render_security(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "reliability":
        content = render_reliability(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "operations":
        content = render_phase4_operations(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "release":
        content = render_phase3_release(ctx, selected, csrf, esc=_esc, table=_table) + render_release(ctx, selected, csrf, esc=_esc, table=_table)
    elif tab == "export":
        content = _export(ctx, selected)
    else:
        content = _audit(ctx, selected)
    flash = f'<div class="notice">{_esc(message)}</div>' if message else ""
    flash += f'<div class="notice error">{_esc(error)}</div>' if error else ""
    selector = _case_selector(cases, selected, tab) if case else ""
    flowbar = _flowbar(ctx, selected) if case and tab not in {"cockpit244","workflow245","monitor246","runtime247","production248","people244","evidence244","graph244","timeline244","research244","coai244","opsec244","reports244"} else ""
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(BUILD_NAME)}</title><style>{CSS}</style></head><body><div class="shell"><aside class="sidebar"><div class="brand"><div class="logo">EE</div><div><b>EagleEye</b><span>Phase 13 · Simplified AI Investigation Workspace</span></div></div><nav class="nav">{nav}</nav><div class="side-note">Lokal · fallgebunden · review-first<br>Build {_esc(BUILD)}</div></aside><main class="main"><header class="topbar"><div class="title"><h1>{_esc(TAB_LABELS.get(tab, "Workspace"))}</h1><p>{_esc(case["title"] if case else BUILD_NAME)} · Benutzer: {_esc(actor)}</p></div><div class="inline">{selector}<form method="post" action="/security/logout"><input type="hidden" name="csrf" value="{_esc(csrf)}"><button class="small ghost" type="submit">Abmelden</button></form></div></header>{flowbar}{flash}{content}<div class="footer">Anzeige gespeicherter Daten ≠ unabhängige Wahrheitsprüfung. Keine automatische Bestätigung von Identität, Anwesenheit, Kausalität oder Schuld.</div></main></div></body></html>'''


def create_workspace_app(*, base_dir: str | Path | None = None) -> FastAPI:
    root = Path(base_dir or Path.cwd()).resolve()
    local_token = _token(root)
    bootstrap_csrf = _csrf(local_token)
    from eagleeye_pro.core.app_context import AppContext

    ctx = AppContext(base_dir=root)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            try:
                ctx.close()
            except Exception:
                pass

    app = FastAPI(title=BUILD_NAME, version=BUILD, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.base_dir = str(root)
    app.state.local_token = local_token
    app.state.csrf_token = bootstrap_csrf
    app.state.context = ctx

    protection = ctx.investigator_protection_124
    governance = ctx.collaboration_governance_132
    auth146 = ctx.build146

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        ctx.reliability_quality_125.heartbeat()
        raw_host = (request.headers.get("host") or "").strip().lower()
        if raw_host.startswith("[") and "]" in raw_host:
            host_header = raw_host[1:raw_host.index("]")]
        elif raw_host.count(":") == 1:
            host_header = raw_host.rsplit(":", 1)[0]
        else:
            host_header = raw_host.strip("[]")
        client_host = (request.client.host if request.client else "").strip("[]").lower()
        if host_header not in ALLOWED_HOSTS or client_host not in ALLOWED_HOSTS | {"testclient"}:
            return JSONResponse({"detail": "Loopback access only"}, status_code=403)
        companion_paths = {"/api/capture-companion/submit", "/api/capture150/config", "/api/capture150/submit", "/api/firefox-companion/register", "/api/firefox-companion/orders", "/api/firefox-companion/ack"}
        companion_path = request.url.path in companion_paths
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            fetch_site = (request.headers.get("sec-fetch-site") or "").casefold()
            origin = (request.headers.get("origin") or "").strip()
            if companion_path:
                # The unsigned local Firefox companion has a moz-extension:// origin.
                # It receives no session cookie or CSRF exemption beyond this single
                # endpoint; authorization is a short-lived, one-time capture ticket.
                if fetch_site and fetch_site not in {"cross-site", "same-origin", "none"}:
                    return JSONResponse({"detail": "Invalid companion fetch metadata"}, status_code=403)
                if origin and origin.casefold() != "null":
                    origin_parts = urlsplit(origin)
                    if origin_parts.scheme.casefold() != "moz-extension" or not origin_parts.hostname:
                        return JSONResponse({"detail": "Invalid capture companion origin"}, status_code=403)
            else:
                if fetch_site and fetch_site not in {"same-origin", "none"}:
                    return JSONResponse({"detail": "Cross-site state change blocked"}, status_code=403)
                # Hardened Firefox profiles and local redirect flows may legitimately
                # emit an opaque Origin value ("null"). The request is still bound to
                # loopback above and every state-changing route validates EagleEye's
                # per-installation CSRF token. Non-opaque origins remain restricted to
                # local HTTP loopback hosts.
                if origin and origin.casefold() != "null":
                    origin_parts = urlsplit(origin)
                    origin_host = (origin_parts.hostname or "").casefold()
                    if origin_parts.scheme.casefold() != "http" or origin_host not in ALLOWED_HOSTS:
                        return JSONResponse({"detail": "Invalid request origin"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if companion_path:
            companion_origin = (request.headers.get("origin") or "").strip()
            if companion_origin and (companion_origin.casefold() == "null" or companion_origin.casefold().startswith("moz-extension://")):
                response.headers["Access-Control-Allow-Origin"] = companion_origin
                response.headers["Vary"] = "Origin"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-EagleEye-Capture-Ticket, X-EagleEye-Companion-Ticket, X-EagleEye-Companion-Token"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        else:
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(), payment=(), interest-cohort=(), browsing-topics=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
        return response

    def record_server_error(request: Request, exc: Exception) -> str:
        import traceback
        error_id = "srv1320_" + secrets.token_hex(6)
        log_dir = root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            log_dir.chmod(0o700)
        except OSError:
            pass
        log_path = log_dir / "server_errors_133_1.log"
        compatibility_log_path = log_dir / "server_errors_126_2.log"
        trace = traceback.format_exc(limit=40)
        trace = trace.replace(str(root), "<EAGLEEYE_ROOT>")
        trace = re.sub(r"(?i)(access[_-]?token|api[_-]?key|authorization|password|secret)(\s*[=:]\s*)[^\s,;]+", r"\1\2[REDACTED]", trace)
        trace = re.sub(r"(?i)(token=)[A-Za-z0-9._~+/-]{12,}", r"\1[REDACTED]", trace)
        entry = {
            "error_id": error_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": request.method,
            "path": request.url.path,
            "error_type": type(exc).__name__,
            "traceback": trace,
        }
        serialized = json.dumps(entry, ensure_ascii=False) + "\n"
        for target in (log_path, compatibility_log_path):
            with target.open("a", encoding="utf-8") as handle:
                handle.write(serialized)
            try:
                target.chmod(0o600)
            except OSError:
                pass
        return error_id

    @app.middleware("http")
    async def server_error_guard(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            error_id = record_server_error(request, exc)
            body = (
                '<!doctype html><html lang="de"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>EagleEye Fehler</title><style>' + CSS + '</style></head><body>'
                '<main class="main" style="max-width:760px;margin:8vh auto"><div class="panel">'
                '<h1>Der Arbeitsschritt konnte nicht abgeschlossen werden</h1>'
                '<div class="notice error">Interner Fehlercode: <b>' + _esc(error_id) + '</b></div>'
                '<p>EagleEye hat die technische Diagnose lokal unter <code>logs/server_errors_133_1.log</code> gespeichert. '
                'Es wurden keine Falldaten an einen externen Dienst übertragen.</p>'
                '<p><a class="button ghost" href="/">Zum Workspace zurückkehren</a></p>'
                '</div></main></body></html>'
            )
            return HTMLResponse(body, status_code=500, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    def client_fingerprint(request: Request) -> str:
        material = "|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            (request.client.host if request.client else ""),
        ))
        return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()

    AUTH_COOKIE = auth146.COOKIE_NAME
    CSRF_COOKIE = "ee_auth_csrf"

    def bootstrap_authenticated(request: Request) -> bool:
        supplied = request.query_params.get("token", "") or request.cookies.get("ee_bootstrap", "") or request.headers.get("x-eagleeye-token", "")
        return bool(supplied and secrets.compare_digest(supplied, local_token))

    def access_lock_enabled() -> bool:
        return not auth146.bootstrap_required()

    def auth_identity(request: Request, *, touch: bool = True) -> dict[str, Any] | None:
        current = getattr(request.state, "auth_identity", None)
        if current:
            return current
        identity = auth146.validate_session(
            request.cookies.get(AUTH_COOKIE, ""),
            client_fingerprint=client_fingerprint(request),
            touch=touch,
        )
        if identity:
            request.state.auth_identity = identity
        return identity

    def authenticated(request: Request) -> bool:
        return auth_identity(request) is not None

    def require_auth(request: Request) -> dict[str, Any]:
        identity = auth_identity(request)
        if not identity:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def request_csrf(request: Request) -> str:
        identity = require_auth(request)
        raw = request.cookies.get(CSRF_COOKIE, "")
        if not auth146.csrf_token_valid(session_token=request.cookies.get(AUTH_COOKIE, ""), submitted=raw):
            auth146.revoke_session(token=request.cookies.get(AUTH_COOKIE, ""), reason="csrf_cookie_invalid", actor=str(identity.get("username") or "system"))
            raise HTTPException(status_code=401, detail="Sitzungs-CSRF-Bindung ungültig")
        return raw

    def verify_csrf(form: dict[str, str], request: Request) -> None:
        supplied = str(form.get("csrf") or "")
        expected = request_csrf(request)
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=403, detail="CSRF-Prüfung fehlgeschlagen")

    def verify_bootstrap_csrf(form: dict[str, str]) -> None:
        if not secrets.compare_digest(str(form.get("csrf") or ""), bootstrap_csrf):
            raise HTTPException(status_code=403, detail="Bootstrap-CSRF-Prüfung fehlgeschlagen")

    def governance_identity(request: Request) -> dict[str, Any] | None:
        identity = auth_identity(request)
        if not identity:
            return None
        return {
            "username": identity["username"], "display_name": identity["display_name"],
            "role_key": identity["role_key"], "user_id": identity["user_id"],
            "global_role": identity["global_role"], "session_id": identity["session_id"],
        }

    def request_actor(request: Request) -> str:
        identity = getattr(request.state, "auth_identity", None) or auth_identity(request)
        if identity:
            return str(identity.get("username") or "")
        raise HTTPException(status_code=401, detail="Benutzersitzung fehlt oder ist abgelaufen")

    async def _secured_form(request: Request) -> tuple[dict[str, Any], dict[str, str]]:
        session = require_auth(request)
        form = await _form(request)
        verify_csrf(form, request)
        return session, form

    mount_build343_routes(app, ctx=ctx, require_auth=require_auth)

    def _post_result(request: Request, *, case_id: str, result: Any, tab: str = "build214") -> RedirectResponse:
        try:
            if isinstance(result, dict):
                keys = [k for k in ("status","decision","count","created","gate","risk_level","snapshot_id","feedback_id","training_example_ids") if k in result]
                summary = " · ".join(f"{k}: {result[k]}" for k in keys) or "Aktion erfolgreich gespeichert."
            else:
                summary = "Aktion erfolgreich gespeichert."
        except Exception:
            summary = "Aktion erfolgreich gespeichert."
        return RedirectResponse(_link(tab, case_id, message=summary), status_code=303)

    def _governance_permission(path: str, method: str) -> str:
        method = method.upper()
        if method == "GET":
            if path == "/" or path.startswith("/api/") or path.startswith("/workspace/detail/"):
                return "case.read"
            return ""
        if path == "/cases/create":
            return "case.create"
        if path == "/build307/autonomous-research":
            return "research.execute"
        if path == "/build307/security-selftest":
            return "security.review"
        if path == "/build307/dossier":
            return "report.write"
        if path.startswith("/governance/"):
            return ""
        if path == "/auth146/sessions/revoke":
            return "session.revoke"
        if path.startswith("/auth146/users") or path.startswith("/auth146/cases"):
            return "user.manage"
        if path.startswith("/auth146/"):
            return ""
        prefix_map = (
            (("/targets/", "/subjects/", "/research/", "/research-intelligence/", "/workflow137/", "/identity139/", "/assistant140/", "/quality141/", "/connectors148/run", "/connectors148/result", "/ecosystem149/", "/capture150/"), "research.execute"),
            (("/connectors148/quarantine/review",), "intake.review"),
            (("/security143/persona-review", "/security143/session-approve"), "persona.approve"),
            (("/security143/egress-review",), "egress.approve"),
            (("/security143/session-start",), "persona.session.start"),
            (("/security143/session-action",), "persona.session.use"),
            (("/security143/session-close",), "persona.session.close"),
            (("/security143/session-request",), "persona.use"),
            (("/security143/access-review",), "security.review"),
            (("/security143/persona",), "persona.create"),
            (("/security143/account",), "persona.manage"),
            (("/security143/egress",), "egress.manage"),
            (("/security143/session",), "persona.use"),
            (("/final144/", "/final145/"), "security.review"),
            (("/intake/", "/photos136/", "/api/photo136/", "/photos137/", "/api/photo137/", "/photos138/", "/api/photo138/", "/photos139/", "/api/photo139/", "/photos140/", "/photos141/"), "intake.write"),
            (("/evidence138/", "/evidence211/"), "evidence.review"),
            (("/build212/",), "identity.review"),
            (("/build213/",), "research.execute"),
            (("/build214/", "/build215/", "/build216/", "/build217/", "/build218/", "/build219/", "/build220/", "/build221/", "/build222/", "/build223/", "/build224/", "/build225/", "/build226/", "/build227/", "/build228/", "/build229/", "/build230/", "/build231/", "/build232/", "/build233/", "/build234/", "/build235/", "/build236/", "/build237/", "/build238/", "/build239/", "/build240/", "/build241/", "/build242/", "/build243/", "/build244/", "/build245/", "/build246/", "/build247/", "/build248/", "/build249/", "/build251/", "/build252/", "/build253/", "/build254/", "/build255/", "/build256/", "/build257/", "/build258/", "/build259/", "/build260/", "/build261/", "/build262/", "/build263/", "/build264/", "/build265/", "/build266/", "/build267/", "/build268/", "/build269/"), "research.execute"),
            (("/workspace/intake/decision",), "intake.review"),
            (("/capture-identity/ticket", "/capture-identity/manual"), "evidence.capture"),
            (("/capture-identity/hypothesis",), "identity.create"),
            (("/capture-identity/review", "/capture-identity/benchmark"), "identity.review"),
            (("/graph-lab/analyse", "/graph-lab/path", "/graph-lab/hypothesis", "/graph-lab/claim", "/graph-lab/evidence", "/graph-lab/red-team"), "hypothesis.write"),
            (("/graph-lab/review", "/graph-lab/request-review", "/graph-lab/review-red-team"), "hypothesis.review"),
            (("/reports142/create", "/reports142/redaction"), "report.write"),
            (("/reports142/request-review",), "report.request_review"),
            (("/reports142/review",), "report.review"),
            (("/reports142/release", "/reports142/verify"), "release.manage"),
            (("/synthesis/create", "/synthesis/verify"), "report.write"),
            (("/synthesis/request-review",), "report.request_review"),
            (("/synthesis/review",), "report.review"),
            (("/orchestrator/plans",), "ai.plan"),
            (("/orchestrator/approve", "/orchestrator/reject", "/orchestrator/execute", "/orchestrator/pause", "/orchestrator/resume", "/orchestrator/cancel"), "ai.execute"),
            (("/orchestrator/review-output",), "ai.review"),
            (("/assistant/local",), "ai.execute"),
            (("/assistant/authorize", "/assistant/search", "/assistant/retry", "/assistant/bridge", "/assistant/chatgpt-protected"), "research.execute"),
            (("/assistant/config",), "security.manage"),
            (("/security/",), "security.manage"),
            (("/reliability/",), "backup.manage"),
            (("/operations/",), "release.manage"),
            (("/release/",), "release.manage"),
        )
        for prefixes, permission in prefix_map:
            if any(path.startswith(prefix) for prefix in prefixes):
                return permission
        return "case.update" if method in {"POST", "PUT", "PATCH", "DELETE"} else ""

    @app.middleware("http")
    async def governance_guard(request: Request, call_next):
        path = request.url.path
        if request.method.upper() == "OPTIONS" or path in {"/health", "/security/start", "/security/login", "/security/logout", "/governance/login", "/governance/logout", "/security/companion-bootstrap", "/api/capture-companion/submit", "/api/capture150/config", "/api/capture150/submit", "/api/firefox-companion/register", "/api/firefox-companion/orders", "/api/firefox-companion/ack"}:
            return await call_next(request)
        if not authenticated(request):
            return await call_next(request)
        identity = governance_identity(request)
        if governance.settings().get("team_mode_enabled") and not identity:
            if request.method.upper() == "GET":
                response = RedirectResponse("/governance/login", status_code=303)
                if request.query_params.get("token") and not access_lock_enabled():
                    response.set_cookie("ee_session", local_token, httponly=True, samesite="strict", path="/")
                return response
            return JSONResponse({"detail": "Governance-Sitzung fehlt oder ist abgelaufen"}, status_code=401)
        identity = identity or {"username": governance.OWNER_USERNAME, "display_name": "Lokaler Administrator", "role_key": "administrator"}
        request.state.governance_identity = identity
        actor = str(identity.get("username") or governance.OWNER_USERNAME)
        case_id = request.query_params.get("case_id", "")
        form_data: dict[str, str] = {}
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            raw = await request.body()
            if len(raw) <= MAX_FORM_BYTES:
                parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
                form_data = {key: values[-1] if values else "" for key, values in parsed.items()}
                case_id = case_id or form_data.get("case_id", "")
        permission = _governance_permission(path, request.method)
        try:
            if permission:
                governance.authorize(username=actor, case_id=case_id, permission=permission)
            lock_map = {
                "/capture-identity/review": ("identity_hypothesis", "hypothesis_id"),
                "/graph-lab/claim": ("graph_hypothesis", "hypothesis_id"),
                "/graph-lab/evidence": ("graph_hypothesis", "hypothesis_id"),
                "/graph-lab/red-team": ("graph_hypothesis", "hypothesis_id"),
                "/graph-lab/request-review": ("graph_hypothesis", "hypothesis_id"),
                "/graph-lab/review": ("graph_hypothesis", "hypothesis_id"),
                "/synthesis/verify": ("report_draft", "report_id"),
                "/synthesis/request-review": ("report_draft", "report_id"),
                "/synthesis/review": ("report_draft", "report_id"),
                "/orchestrator/approve": ("orchestration_plan", "plan_id"),
                "/orchestrator/reject": ("orchestration_plan", "plan_id"),
                "/orchestrator/execute": ("orchestration_plan", "plan_id"),
                "/orchestrator/pause": ("orchestration_plan", "plan_id"),
                "/orchestrator/resume": ("orchestration_plan", "plan_id"),
                "/orchestrator/cancel": ("orchestration_plan", "plan_id"),
                "/orchestrator/review-output": ("orchestration_output", "output_id"),
                "/workspace/intake/decision": ("intake", "intake_id"),
            }
            if case_id and path in lock_map:
                object_type, field = lock_map[path]
                object_id = form_data.get(field, "")
                if object_id:
                    governance.assert_editable(case_id=case_id, object_type=object_type, object_id=object_id, actor=actor)
        except Exception as exc:
            return JSONResponse({"detail": str(exc)}, status_code=403)
        token = ctx.audit.push_actor(actor)
        try:
            return await call_next(request)
        finally:
            ctx.audit.pop_actor(token)

    STEP_UP_PATHS = {
        "/reports142/release": "report.release",
        "/final145/seal": "phase4.seal",
        "/security143/session-start": "persona.session.start",
        "/reliability/stage-restore": "backup.restore",
        "/security/secrets": "secret.manage",
        "/security/lockdown": "security.lockdown",
        "/auth146/users/create": "user.manage",
        "/auth146/users/update": "user.manage",
        "/auth146/cases/assign": "user.manage",
        "/auth146/cases/revoke": "user.manage",
        "/auth146/sessions/revoke": "session.revoke",
        "/connectors148/contract/accept": "connector.manage",
        "/connectors148/quarantine/set": "connector.manage",
        "/connectors148/secret/bind": "secret.manage",
    }
    AUTH_EXEMPT = {
        "/health", "/security/start", "/security/bootstrap", "/security/login", "/security/recover",
        "/security/companion-bootstrap", "/security/research-redirect",
        "/api/capture-companion/submit", "/api/capture150/config", "/api/capture150/submit", "/api/firefox-companion/register",
        "/api/firefox-companion/orders", "/api/firefox-companion/ack",
    }

    @app.middleware("http")
    async def identity_access_guard(request: Request, call_next):
        path = request.url.path
        if request.method.upper() == "OPTIONS" or path in AUTH_EXEMPT:
            return await call_next(request)
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            fetch_site = (request.headers.get("sec-fetch-site") or "").casefold()
            origin = (request.headers.get("origin") or "").strip()
            if fetch_site and fetch_site not in {"same-origin", "none"}:
                return JSONResponse({"detail": "Cross-site state change blocked"}, status_code=403)
            if origin and origin.casefold() != "null":
                parts = urlsplit(origin)
                if parts.scheme.casefold() != "http" or (parts.hostname or "").casefold() not in ALLOWED_HOSTS:
                    return JSONResponse({"detail": "Invalid request origin"}, status_code=403)
        if auth146.bootstrap_required():
            if request.method.upper() == "GET" and bootstrap_authenticated(request):
                response = RedirectResponse("/security/bootstrap", status_code=303)
                response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
                return response
            return JSONResponse({"detail": "EagleEye Bootstrap ist noch nicht abgeschlossen"}, status_code=423)
        identity = auth_identity(request)
        if not identity:
            if request.method.upper() == "GET":
                response = RedirectResponse("/security/login", status_code=303)
                response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
                return response
            return JSONResponse({"detail": "Anmeldung erforderlich oder Sitzung abgelaufen"}, status_code=401)
        request.state.auth_identity = identity
        password_change_allowed = path in {"/auth146/password/change", "/security/logout"} or (path == "/" and request.query_params.get("tab") == "auth146")
        if identity.get("must_change_password") and not password_change_allowed:
            if request.method.upper() == "GET":
                return RedirectResponse("/?tab=auth146&error=" + quote("Vor der weiteren Nutzung muss das Startpasswort geändert werden."), status_code=303)
            return JSONResponse({"detail": "Startpasswort muss geändert werden"}, status_code=403)
        case_id = request.query_params.get("case_id", "")
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            raw = await request.body()
            if len(raw) <= MAX_FORM_BYTES:
                parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
                form_data = {key: values[-1] if values else "" for key, values in parsed.items()}
                case_id = case_id or form_data.get("case_id", "")
        permission = _governance_permission(path, request.method)
        try:
            if permission:
                auth146.authorize(identity=identity, case_id=case_id, permission=permission, correlation_id=request.headers.get("x-correlation-id", ""))
            action_key = STEP_UP_PATHS.get(path)
            if action_key and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                auth146.require_step_up(session_id=identity["session_id"], action_key=action_key, case_id=case_id, consume=True)
        except Exception as exc:
            if request.method.upper() == "POST":
                return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)
            return JSONResponse({"detail": str(exc)}, status_code=403)
        return await call_next(request)

    def _set_auth_cookies(response: Response, issued: Any, request: Request) -> None:
        secure = request.url.scheme == "https"
        response.set_cookie(AUTH_COOKIE, issued.token, httponly=True, secure=secure, samesite="strict", path="/", max_age=issued.max_age)
        response.set_cookie(CSRF_COOKIE, issued.csrf_token, httponly=True, secure=secure, samesite="strict", path="/", max_age=issued.max_age)
        response.delete_cookie("ee_session", path="/")
        response.delete_cookie("ee_protected_session", path="/")

    def _clear_auth_cookies(response: Response) -> None:
        response.delete_cookie(AUTH_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        response.delete_cookie("ee_session", path="/")
        response.delete_cookie("ee_protected_session", path="/")

    def bootstrap_page(error: str = "") -> str:
        flash = f'<div class="notice error">{_esc(error)}</div>' if error else ""
        return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EagleEye Erstkonfiguration</title><style>{CSS}</style></head><body><main class="main" style="max-width:720px;margin:5vh auto"><div class="panel"><div class="brand"><div class="logo">EE</div><div><b>EagleEye</b><span>Build {BUILD} · Startup Recovery & Browser Workspace</span></div></div><h1>Erstes Administratorkonto erstellen</h1><div class="notice warn">Es gibt kein Standardkonto und kein Standardpasswort. Nach diesem Schritt sind Fälle, Bilder, Reports, APIs und Operations nur noch nach Anmeldung erreichbar.</div>{flash}<form method="post" action="/security/bootstrap"><input type="hidden" name="csrf" value="{_esc(bootstrap_csrf)}"><div class="field"><label>Benutzername</label><input name="username" pattern="[a-z0-9._-]{{3,32}}" required autofocus autocomplete="username"></div><div class="field"><label>Anzeigename</label><input name="display_name" required></div><div class="field"><label>Passwort, mindestens 15 Zeichen</label><input type="password" name="password" minlength="15" maxlength="128" required autocomplete="new-password"></div><div class="field"><label>Passwort wiederholen</label><input type="password" name="password_confirm" minlength="15" maxlength="128" required autocomplete="new-password"></div><p><button>Bootstrap abschließen</button></p></form></div></main></body></html>'''

    @app.get("/security/start")
    def security_start(request: Request):
        """Canonical local launcher landing endpoint (Build 334 hotfix)."""
        if auth146.bootstrap_required():
            if not bootstrap_authenticated(request):
                raise HTTPException(status_code=403, detail="Lokaler Startnachweis fehlt")
            response = RedirectResponse("/security/bootstrap", status_code=303)
            response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
            return response
        return RedirectResponse("/security/login", status_code=303)

    @app.get("/security/bootstrap", response_class=HTMLResponse)
    def security_bootstrap_get(request: Request, error: str = ""):
        if not auth146.bootstrap_required():
            return RedirectResponse("/security/login", status_code=303)
        if not bootstrap_authenticated(request):
            raise HTTPException(status_code=403, detail="Lokaler Startnachweis fehlt")
        response = HTMLResponse(bootstrap_page(error))
        response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
        return response

    @app.post("/security/bootstrap")
    async def security_bootstrap_post(request: Request):
        if not auth146.bootstrap_required() or not bootstrap_authenticated(request):
            raise HTTPException(status_code=403, detail="Lokaler Startnachweis fehlt")
        form = await _form(request); verify_bootstrap_csrf(form)
        if form.get("password", "") != form.get("password_confirm", ""):
            return RedirectResponse("/security/bootstrap?" + urlencode({"error": "Passwörter stimmen nicht überein."}), status_code=303)
        try:
            user = auth146.create_initial_admin(username=form.get("username", ""), display_name=form.get("display_name", ""), password=form.get("password", ""))
            issued = auth146.authenticate(username=user["username"], password=form.get("password", ""), client_fingerprint=client_fingerprint(request))
            if not issued:
                raise RuntimeError("Bootstrap-Anmeldung konnte nicht erstellt werden")
            response = RedirectResponse("/", status_code=303)
            _set_auth_cookies(response, issued, request)
            response.delete_cookie("ee_bootstrap", path="/")
            return response
        except Exception as exc:
            return RedirectResponse("/security/bootstrap?" + urlencode({"error": str(exc)}), status_code=303)

    def login_page(error: str = "") -> str:
        flash = f'<div class="notice error">{_esc(error)}</div>' if error else ""
        return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EagleEye Anmeldung</title><style>{CSS}</style></head><body><main class="main" style="max-width:620px;margin:8vh auto"><div class="panel"><div class="brand"><div class="logo">EE</div><div><b>EagleEye</b><span>Build {BUILD} · sichere lokale Anmeldung</span></div></div><h1>Anmelden</h1><p>Benutzername und Passwort werden lokal geprüft. Die Antwort verrät nicht, ob ein Konto existiert.</p>{flash}<form method="post" action="/security/login"><input type="hidden" name="csrf" value="{_esc(bootstrap_csrf)}"><div class="field"><label>Benutzername</label><input name="username" required autofocus autocomplete="username"></div><div class="field"><label>Passwort</label><input type="password" name="password" required autocomplete="current-password"></div><p><button>Anmelden</button></p></form><p><a class="button ghost" href="/security/recover">Konto mit Recovery-Code wiederherstellen</a></p></div></main></body></html>'''

    @app.get("/security/login", response_class=HTMLResponse)
    def security_login_get(request: Request, error: str = ""):
        if auth146.bootstrap_required():
            if bootstrap_authenticated(request):
                return RedirectResponse("/security/bootstrap", status_code=303)
            raise HTTPException(status_code=403, detail="Lokaler Startnachweis fehlt")
        if auth_identity(request, touch=False):
            return RedirectResponse("/", status_code=303)
        response = HTMLResponse(login_page(error))
        response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
        return response

    @app.post("/security/login")
    async def security_login_post(request: Request):
        if auth146.bootstrap_required():
            raise HTTPException(status_code=423, detail="Bootstrap nicht abgeschlossen")
        form = await _form(request); verify_bootstrap_csrf(form)
        issued = auth146.authenticate(username=form.get("username", ""), password=form.get("password", ""), client_fingerprint=client_fingerprint(request))
        if not issued:
            return RedirectResponse("/security/login?" + urlencode({"error": "Anmeldung nicht möglich."}), status_code=303)
        response = RedirectResponse("/", status_code=303)
        _set_auth_cookies(response, issued, request)
        response.delete_cookie("ee_bootstrap", path="/")
        return response

    @app.post("/security/logout")
    async def security_logout(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        auth146.revoke_session(token=request.cookies.get(AUTH_COOKIE, ""), reason="user_logout", actor=identity["username"])
        response = RedirectResponse("/security/login", status_code=303)
        _clear_auth_cookies(response)
        response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
        return response

    @app.get("/security/recover", response_class=HTMLResponse)
    def security_recover_get(request: Request, error: str = ""):
        flash = f'<div class="notice error">{_esc(error)}</div>' if error else ""
        return HTMLResponse(f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EagleEye Recovery</title><style>{CSS}</style></head><body><main class="main" style="max-width:620px;margin:8vh auto"><div class="panel"><h1>Konto wiederherstellen</h1>{flash}<form method="post" action="/security/recover"><input type="hidden" name="csrf" value="{_esc(bootstrap_csrf)}"><div class="field"><label>Benutzername</label><input name="username" required></div><div class="field"><label>Recovery-Code</label><input name="recovery_code" required autocomplete="one-time-code"></div><div class="field"><label>Neues Passwort</label><input type="password" name="new_password" minlength="15" maxlength="128" required autocomplete="new-password"></div><p><button>Wiederherstellen</button></p></form></div></main></body></html>''')

    @app.post("/security/recover")
    async def security_recover_post(request: Request):
        form = await _form(request); verify_bootstrap_csrf(form)
        try:
            ok = auth146.recover_account(username=form.get("username", ""), recovery_code=form.get("recovery_code", ""), new_password=form.get("new_password", ""), client_fingerprint=client_fingerprint(request))
        except Exception:
            ok = False
        if not ok:
            return RedirectResponse("/security/recover?" + urlencode({"error": "Wiederherstellung nicht möglich."}), status_code=303)
        return RedirectResponse("/security/login?" + urlencode({"error": "Passwort geändert. Bitte neu anmelden."}), status_code=303)

    @app.get("/governance/login")
    def governance_login_get(request: Request):
        # Build 146 unifies local identity and the historical governance actor.
        # A second passphrase login would create two diverging session boundaries.
        require_auth(request)
        return RedirectResponse("/?tab=auth146", status_code=303)

    @app.post("/governance/login")
    async def governance_login_post(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        return RedirectResponse("/?tab=auth146", status_code=303)

    @app.post("/governance/logout")
    async def governance_logout(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        auth146.revoke_session(token=request.cookies.get(AUTH_COOKIE, ""), reason="governance_logout_alias", actor=identity["username"])
        response = RedirectResponse("/security/login", status_code=303)
        _clear_auth_cookies(response)
        response.delete_cookie("ee_governance_session", path="/")
        return response

    @app.post("/auth146/users/create")
    async def auth146_create_user(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            user = auth146.create_user(
                username=form.get("username", ""), display_name=form.get("display_name", ""),
                global_role=form.get("global_role", "read_only"), password=form.get("password", ""),
                actor=identity["username"],
            )
            return RedirectResponse(_link("auth146", case_id, message=f"Benutzer {user['username']} wurde angelegt; Startpasswort muss geändert werden."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/cases/assign")
    async def auth146_assign_case(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.assign_case(
                case_id=case_id, username=form.get("username", ""), case_role=form.get("case_role", "read_only"),
                actor=identity["username"], notes=form.get("notes", ""),
            )
            return RedirectResponse(_link("auth146", case_id, message="Fallmitgliedschaft wurde gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/users/update")
    async def auth146_update_user(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            user = auth146.update_user(
                username=form.get("username", ""), actor=identity["username"],
                global_role=form.get("global_role", ""), active=form.get("active", "1") == "1",
                must_change_password=form.get("must_change_password", "0") == "1",
            )
            return RedirectResponse(_link("auth146", case_id, message=f"Benutzerstatus für {user['username']} wurde aktualisiert; bestehende Sitzungen wurden widerrufen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/cases/revoke")
    async def auth146_revoke_case(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.revoke_case_membership(
                case_id=case_id, username=form.get("username", ""), case_role=form.get("case_role", ""),
                actor=identity["username"], reason=form.get("reason", ""),
            )
            return RedirectResponse(_link("auth146", case_id, message="Fallzugriff wurde entzogen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/sessions/revoke")
    async def auth146_admin_revoke_session(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.revoke_session_by_id(session_id=form.get("session_id", ""), actor=identity["username"], reason=form.get("reason", "administrator_revoked"))
            return RedirectResponse(_link("auth146", case_id, message="Sitzung wurde widerrufen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/password/change")
    async def auth146_change_password(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.change_password(
                username=identity["username"], current_password=form.get("current_password", ""),
                new_password=form.get("new_password", ""), actor=identity["username"],
                current_session_id=identity["session_id"],
            )
            response = RedirectResponse("/security/login?" + urlencode({"error": "Passwort geändert. Bitte neu anmelden."}), status_code=303)
            _clear_auth_cookies(response)
            response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
            return response
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/recovery/generate", response_class=HTMLResponse)
    async def auth146_recovery_generate(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        codes = auth146.generate_recovery_codes(username=identity["username"], actor=identity["username"])
        code_html = "".join(f"<li><code>{_esc(code)}</code></li>" for code in codes)
        back_link = _esc(_link("auth146", form.get("case_id", "")))
        body = (
            '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Recovery-Codes</title><style>{CSS}</style></head><body><main class="main" style="max-width:760px;margin:5vh auto">'
            '<div class="panel"><h1>Recovery-Codes</h1><div class="notice warn">Diese Codes werden nur jetzt angezeigt. '
            'Speichere sie offline und getrennt von der EagleEye-Installation. Jeder Code kann genau einmal verwendet werden.</div>'
            f'<ol>{code_html}</ol><p><a class="button" href="{back_link}">Ich habe die Codes gesichert</a></p></div></main></body></html>'
        )
        return HTMLResponse(body, headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"})

    @app.post("/auth146/step-up")
    async def auth146_step_up(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            grant = auth146.issue_step_up(
                session_token=request.cookies.get(AUTH_COOKIE, ""), password=form.get("password", ""),
                action_key=form.get("action_key", ""), case_id=case_id, client_fingerprint=client_fingerprint(request),
            )
            return RedirectResponse(_link("auth146", case_id, message=f"Step-up-Freigabe bis Epoch {grant['expires_epoch']} erteilt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("auth146", case_id, error=str(exc)), status_code=303)

    @app.post("/auth146/sessions/revoke-others")
    async def auth146_revoke_others(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        count = auth146.revoke_user_sessions(
            user_id=identity["user_id"], reason="user_revoked_other_sessions", actor=identity["username"],
            except_session_id=identity["session_id"],
        )
        return RedirectResponse(_link("auth146", form.get("case_id", ""), message=f"{count} andere Sitzung(en) wurden widerrufen."), status_code=303)


    @app.post("/research147/plan/create")
    async def research147_plan_create(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="research_plan_147")
            source_keys = [key[len("source_"):] for key, value in form.items() if key.startswith("source_") and value == "1"]
            aliases = [line.strip() for line in form.get("aliases", "").splitlines() if line.strip()]
            result = ctx.build147.create_plan(
                case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""),
                purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), source_keys=source_keys,
                full_name=form.get("full_name", ""), username=form.get("username", ""), email=form.get("email", ""),
                organisation=form.get("organisation", ""), location=form.get("location", ""), aliases=aliases,
                disclosure_budget=int(form.get("disclosure_budget", "2") or 2),
                max_external_actions=int(form.get("max_external_actions", "12") or 12), actor=identity["username"],
            )
            return RedirectResponse(_link("research147", case_id, message=f"Rechercheplan {result['plan_id']} erstellt und lokal OPSEC-geprüft."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research147", case_id, error=str(exc)), status_code=303)

    @app.post("/research147/plan/approve")
    async def research147_plan_approve(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="research_plan_147", object_id=form.get("plan_id", ""))
            result = ctx.build147.approve_plan(case_id=case_id, plan_id=form.get("plan_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("research147", case_id, message=f"Plan freigegeben: {result['created_jobs']} Jobs, {result['deduplicated']} Dubletten vermieden."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research147", case_id, error=str(exc)), status_code=303)

    @app.post("/research147/job/execute")
    async def research147_job_execute(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="research_job_147", object_id=form.get("job_id", ""))
            result = ctx.build147.execute_job(
                case_id=case_id, job_id=form.get("job_id", ""), confirmation=form.get("confirmation", ""),
                actor=identity["username"], local_redirect_origin=f"http://127.0.0.1:{port}", mode=form.get("mode", "replay"),
            )
            return RedirectResponse(_link("research147", case_id, message=f"Recherchejob kontrolliert gestartet: {result.get('execution_mode', '')}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research147", case_id, error=str(exc)), status_code=303)

    @app.post("/research147/job/complete")
    async def research147_job_complete(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="research_job_147", object_id=form.get("job_id", ""))
            ctx.build147.complete_manual_job(case_id=case_id, job_id=form.get("job_id", ""), result_count=int(form.get("result_count", "0") or 0), actor=identity["username"])
            return RedirectResponse(_link("research147", case_id, message="Manuelle Sichtung wurde dokumentiert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research147", case_id, error=str(exc)), status_code=303)

    @app.post("/research147/candidate/add")
    async def research147_candidate_add(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="intake.write", object_type="social_profile_candidate_147")
            row = ctx.build147.add_social_candidate(
                case_id=case_id, source_key=form.get("source_key", ""), profile_url=form.get("profile_url", ""),
                target_id=form.get("target_id", ""), username=form.get("username", ""), display_name=form.get("display_name", ""),
                bio=form.get("bio", ""), location=form.get("location", ""), source_context=form.get("source_context", ""),
                confidence=float(str(form.get("confidence", "0.2")).replace(",", ".") or 0.2), actor=identity["username"],
            )
            return RedirectResponse(_link("research147", case_id, message=f"Social-Media-Kandidat {row['candidate_id']} gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research147", case_id, error=str(exc)), status_code=303)

    @app.post("/research147/candidate/review")
    async def research147_candidate_review(request: Request):
        identity = require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="intake.review", object_type="social_profile_candidate_147", object_id=form.get("candidate_id", ""))
            ctx.build147.review_candidate(case_id=case_id, candidate_id=form.get("candidate_id", ""), status=form.get("status", ""), reason=form.get("reason", ""), actor=identity["username"])
            return RedirectResponse(_link("research147", case_id, message="Kandidatenprüfung gespeichert; keine automatische Identitätsbestätigung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research147", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/contract/test")
    async def connectors148_contract_test(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.require_global(identity["username"], "connector.manage")
            result = ctx.build148.run_contract_tests(form.get("connector_id", ""), actor=identity["username"])
            return RedirectResponse(_link("connectors148", case_id, message=f"Connector-Vertrag getestet: {result['score']}/100, Status {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/contract/accept")
    async def connectors148_contract_accept(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.require_global(identity["username"], "connector.manage")
            row = ctx.build148.accept_contract(form.get("connector_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"], notes="Vertrag über Build-148-Governanceoberfläche akzeptiert.")
            return RedirectResponse(_link("connectors148", case_id, message=f"Connector-Vertrag akzeptiert: {row['label']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/quarantine/set")
    async def connectors148_quarantine_set(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.require_global(identity["username"], "connector.manage")
            row = ctx.build148.set_quarantine(form.get("connector_id", ""), quarantined=form.get("quarantined", "1") == "1", reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("connectors148", case_id, message=f"Connector-Status aktualisiert: {row['health_state']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/secret/bind")
    async def connectors148_secret_bind(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.require_global(identity["username"], "secret.manage")
            row = ctx.build148.bind_secret_reference(form.get("connector_id", ""), secret_name=form.get("secret_name", ""), vault_key=form.get("vault_key", ""), required=form.get("required", "") == "1", confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("connectors148", case_id, message=f"Secret-Referenz für {row['label']} gespeichert; kein Geheimniswert wurde in Falldaten übernommen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/run")
    async def connectors148_run(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build148.execute_connector(case_id=case_id, connector_id=form.get("connector_id", ""), input_data={"query": form.get("query", ""), "max_results": int(form.get("max_results", "25") or 25)}, purpose=form.get("purpose", ""), actor=identity["username"], confirmation=form.get("confirmation", ""), mode=form.get("mode", "dry_run"), local_redirect_origin=str(request.base_url).rstrip("/"))
            return RedirectResponse(_link("connectors148", case_id, message=f"Connector-Run {result['run_id']} abgeschlossen/gestartet: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/result")
    async def connectors148_result(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            row = ctx.build148.record_guided_result(case_id=case_id, run_id=form.get("run_id", ""), title=form.get("title", ""), url=form.get("url", ""), snippet=form.get("snippet", ""), actor=identity["username"])
            return RedirectResponse(_link("connectors148", case_id, message=f"Manueller Connector-Treffer {row['quarantine_id']} in Quarantäne gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/connectors148/quarantine/review")
    async def connectors148_quarantine_review(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            row = ctx.build148.review_quarantine(case_id=case_id, quarantine_id=form.get("quarantine_id", ""), status=form.get("status", ""), reason=form.get("reason", ""), actor=identity["username"])
            return RedirectResponse(_link("connectors148", case_id, message=f"Quarantäneprüfung gespeichert: {row['review_status']}; candidate-only bleibt aktiv."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("connectors148", case_id, error=str(exc)), status_code=303)

    @app.post("/ecosystem149/plan/create")
    async def ecosystem149_plan_create(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="source_plan_149")
            families = [value.strip() for value in form.get("families", "").split(",") if value.strip()]
            plan = ctx.build149.create_plan(
                case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""),
                purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), requested_families=families,
                disclosure_budget=int(form.get("disclosure_budget", "2") or 2),
                max_external_actions=int(form.get("max_external_actions", "10") or 10),
                allow_exact_email=form.get("allow_exact_email", "") == "1",
                allow_licensed_sources=form.get("allow_licensed_sources", "") == "1", actor=identity["username"],
            )
            return RedirectResponse(_link("ecosystem149", case_id, message=f"Lokaler Quellenplan {plan['plan_id']} mit {len(plan['selected_connectors'])} priorisierten Quellen erstellt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("ecosystem149", case_id, error=str(exc)), status_code=303)

    @app.post("/ecosystem149/plan/approve")
    async def ecosystem149_plan_approve(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="source_plan_149", object_id=form.get("plan_id", ""))
            plan = ctx.build149.approve_plan(case_id=case_id, plan_id=form.get("plan_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("ecosystem149", case_id, message=f"Quellenplan freigegeben; {len(plan['jobs'])} manuelle Jobs vorbereitet."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("ecosystem149", case_id, error=str(exc)), status_code=303)

    @app.post("/ecosystem149/job/execute")
    async def ecosystem149_job_execute(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="research.execute", object_type="source_job_149", object_id=form.get("job_id", ""))
            result = ctx.build149.execute_job(case_id=case_id, job_id=form.get("job_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"], mode=form.get("mode", "dry_run"), local_redirect_origin=str(request.base_url).rstrip("/"))
            return RedirectResponse(_link("ecosystem149", case_id, message=f"Quellenjob {result['job_id']} verarbeitet: {result.get('status', 'completed')}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("ecosystem149", case_id, error=str(exc)), status_code=303)

    @app.post("/ecosystem149/results/cluster")
    async def ecosystem149_results_cluster(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="intake.review", object_type="source_cluster_149")
            result = ctx.build149.cluster_case_results(case_id=case_id, confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("ecosystem149", case_id, message=f"{result['clusters']} lokale Quellencluster erzeugt; Ergebnisse bleiben candidate-only."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("ecosystem149", case_id, error=str(exc)), status_code=303)

    @app.post("/capture150/policy/create")
    async def capture150_policy_create(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="evidence.write", object_type="capture_policy_150")
            raw_hosts = re.split(r"[,;\n\r]+", form.get("allowed_hosts", ""))
            result = ctx.build150.create_policy(
                case_id=case_id, target_id=form.get("target_id", ""), label=form.get("label", ""),
                purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), mode=form.get("mode", "manual"),
                allowed_hosts=raw_hosts, include_html=form.get("include_html") == "1",
                include_visible_text=form.get("include_visible_text") == "1", include_screenshot=form.get("include_screenshot") == "1",
                include_resource_inventory=form.get("include_resources") == "1",
                min_interval_seconds=int(form.get("min_interval_seconds", "30") or 30),
                max_captures=int(form.get("max_captures", "100") or 100), actor=identity["username"],
            )
            return RedirectResponse(_link("capture150", case_id, message=f"Capture-Policy {result['policy_id']} als Entwurf gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture150", case_id, error=str(exc)), status_code=303)

    @app.post("/capture150/policy/approve")
    async def capture150_policy_approve(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="evidence.review", object_type="capture_policy_150", object_id=form.get("policy_id", ""))
            result = ctx.build150.approve_policy(case_id=case_id, policy_id=form.get("policy_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("capture150", case_id, message=f"Capture-Policy freigegeben: {result['policy_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture150", case_id, error=str(exc)), status_code=303)

    @app.post("/capture150/session/start")
    async def capture150_session_start(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="evidence.write", object_type="capture_session_150")
            result = ctx.build150.start_session(case_id=case_id, policy_id=form.get("policy_id", ""), duration_minutes=int(form.get("duration_minutes", "60") or 60), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("capture150", case_id, message=f"Capture-Session aktiv: {result['session_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture150", case_id, error=str(exc)), status_code=303)

    @app.post("/capture150/session/stop")
    async def capture150_session_stop(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="evidence.write", object_type="capture_session_150", object_id=form.get("session_id", ""))
            result = ctx.build150.stop_session(case_id=case_id, session_id=form.get("session_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("capture150", case_id, message=f"Capture-Session beendet: {result['session_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture150", case_id, error=str(exc)), status_code=303)

    @app.post("/capture150/record/verify")
    async def capture150_record_verify(request: Request):
        identity = require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            auth146.authorize(identity=identity, case_id=case_id, permission="evidence.review", object_type="browser_capture_150", object_id=form.get("record_id", ""))
            result = ctx.build150.verify_record(case_id=case_id, record_id=form.get("record_id", ""), confirmation=form.get("confirmation", ""), actor=identity["username"])
            return RedirectResponse(_link("capture150", case_id, message=f"Integritätsprüfung: {'bestanden' if result['valid'] else 'FEHLER'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture150", case_id, error=str(exc)), status_code=303)

    @app.options("/api/capture150/config")
    @app.options("/api/capture150/submit")
    def capture150_options():
        return Response(status_code=204)

    @app.get("/api/capture150/config")
    def capture150_config(request: Request, case_id: str):
        try:
            token = request.headers.get("x-eagleeye-companion-token", "")
            return JSONResponse(ctx.build150.companion_config(case_id=case_id, token=token))
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": "Capture-Konfiguration wurde abgewiesen"}, status_code=403)

    @app.post("/api/capture150/submit")
    async def capture150_submit(request: Request):
        raw = await request.body()
        if len(raw) > ctx.build150.MAX_PAYLOAD_BYTES:
            return JSONResponse({"ok": False, "detail": "Capture-Payload ist zu groß"}, status_code=413)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            original_payload = dict(payload)
            token = request.headers.get("x-eagleeye-companion-token", "")
            case_id_191 = str(payload.pop("case_id", ""))
            result = ctx.build150.submit_companion_capture(
                case_id=case_id_191, session_id=str(payload.pop("session_id", "")), token=token,
                trigger_mode=str(payload.pop("trigger_mode", "manual")), payload=payload,
                origin=request.headers.get("origin", ""),
            )
            bridge_result = None
            try:
                if ctx.db.one("SELECT source_id FROM capture_source_profiles_190 WHERE source_id='browser_direct_capture'") is None:
                    ctx.build190.seed_profiles(confirmation="CAPTURE SOURCES 190 ANLEGEN")
                bridge_result = ctx.build191.ingest_browser_bridge(
                    case_id=case_id_191, source_id="browser_direct_capture",
                    page_url=str(original_payload.get("url", "")), title=str(original_payload.get("title", "")),
                    visible_text=str(original_payload.get("visible_text", "")), dom_html=str(original_payload.get("html", "")),
                    resources=list(original_payload.get("resources", []) or []),
                    screenshot_base64=str(original_payload.get("screenshot_base64", "")),
                    headers={}, confirmation=f"BROWSER BRIDGE 191 {case_id_191} SPEICHERN",
                )
            except Exception:
                bridge_result = None
            return JSONResponse({"ok": True, "record_id": result["record_id"], "capture_id": result["capture_id_129"], "capture_id_191": (bridge_result or {}).get("capture_id", ""), "bridge_id_191": (bridge_result or {}).get("bridge_id", ""), "change_state": result["change_state"], "integrity_state": result["integrity_state"]})
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": "Capture konnte nicht sicher verarbeitet werden"}, status_code=400)

    @app.get("/assets/graph123.js")
    def graph_asset(request: Request):
        require_auth(request)
        path = Path(__file__).with_name("assets") / "graph123.js"
        return Response(path.read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/assets/graph130.js")
    def graph130_asset(request: Request):
        require_auth(request)
        path = Path(__file__).with_name("assets") / "graph130.js"
        return Response(path.read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/assets/photo136.js")
    def photo136_asset(request: Request):
        require_auth(request)
        path = Path(__file__).with_name("assets") / "photo136.js"
        return Response(path.read_text(encoding="utf-8"), media_type="application/javascript")

    @app.post("/api/capture191/warc")
    async def capture191_warc(request: Request):
        require_auth(request)
        payload = await request.json()
        try:
            result = ctx.build191.export_warc(
                case_id=str(payload.get("case_id", "")), capture_id=str(payload.get("capture_id", "")),
                created_by=request_actor(request), include_resources=bool(payload.get("include_resources", True)),
                confirmation=f"WARC 191 {str(payload.get('capture_id',''))} EXPORTIEREN",
            )
            return JSONResponse({"ok": True, **result})
        except Exception:
            return JSONResponse({"ok": False, "detail": "WARC-Export konnte nicht sicher erstellt werden"}, status_code=400)


    @app.post("/build228/example-add")
    async def build228_example_add(request: Request):
        require_auth(request); form = await request.form(); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build228.add_example(case_id=case_id, instruction=str(form.get("instruction", "")), response=str(form.get("response", "")), language=str(form.get("language", "de")), created_by=actor, confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Trainingsbeispiel {result['example_id']} angelegt; Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build228/example-review")
    async def build228_example_review(request: Request):
        require_auth(request); payload=await request.json(); eid=str(payload.get("example_id", "")); actor=request_actor(request)
        try:
            result=ctx.build228.review_example(example_id=eid, decision=str(payload.get("decision", "approved")), reviewer=actor, confirmation=f"TRAINING EXAMPLE 228 {eid} PRUEFEN")
            return JSONResponse({"ok": True, "example": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build228/dataset-create")
    async def build228_dataset_create(request: Request):
        require_auth(request); payload=await request.json(); case_id=str(payload.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build228.create_dataset(case_id=case_id, name=str(payload.get("name", "investigative-sft")), seed=int(payload.get("seed", 228)), created_by=actor, confirmation=f"TRAINING DATASET 228 {case_id} ERSTELLEN")
            return JSONResponse({"ok": True, "dataset": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build228/dataset-approve")
    async def build228_dataset_approve(request: Request):
        require_auth(request); payload=await request.json(); did=str(payload.get("dataset_id", "")); actor=request_actor(request)
        try:
            result=ctx.build228.approve_dataset(dataset_id=did, approver=actor, confirmation=f"TRAINING DATASET 228 {did} FREIGEBEN")
            return JSONResponse({"ok": True, "dataset": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build229/loop-create")
    async def build229_loop_create(request: Request):
        require_auth(request); form = await request.form(); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.create_loop(
                case_id=case_id, session_id=str(form.get("session_id", "")), objective=str(form.get("objective", "")),
                working_language=str(form.get("working_language", "de")), max_cycles=int(form.get("max_cycles", 4)),
                required_independent_origins=int(form.get("required_independent_origins", 2)), created_by=actor,
                confirmation=f"VERIFIED RESEARCH LOOP 229 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Verified Research Loop {result['loop_id']} angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build229/cycle-start")
    async def build229_cycle_start(request: Request):
        require_auth(request); form = await request.form(); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); loop_id=str(form.get("loop_id", "")); actor=request_actor(request)
        try:
            countries=[x.strip() for x in str(form.get("countries", "")).split(",") if x.strip()]
            result=ctx.build229.start_cycle(
                loop_id=loop_id, query_text=str(form.get("query_text", "")), target_type=str(form.get("target_type", "unknown")),
                target_value=str(form.get("target_value", "")), countries=countries, actor=actor,
                confirmation=f"VERIFIED RESEARCH CYCLE 229 {loop_id} STARTEN")
            return RedirectResponse(_link("build214", case_id, message=f"Research-Zyklus {result['cycle_id']} vorbereitet; keine Quelle wurde automatisch ausgeführt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build229/claim-add")
    async def build229_claim_add(request: Request):
        require_auth(request); payload=await request.json(); cycle_id=str(payload.get("cycle_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.add_claim(
                cycle_id=cycle_id, claim_text=str(payload.get("claim_text", "")), claim_kind=str(payload.get("claim_kind", "observation")),
                confidence=float(payload.get("confidence", 0)), supporting_refs=list(payload.get("supporting_refs") or []),
                contradicting_refs=list(payload.get("contradicting_refs") or []), retrieval_claim_id=str(payload.get("retrieval_claim_id", "")),
                actor=actor, confirmation=f"VERIFIED CLAIM 229 {cycle_id} ANLEGEN")
            return JSONResponse({"ok": True, "claim": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build229/claim-review")
    async def build229_claim_review(request: Request):
        require_auth(request); payload=await request.json(); claim_id=str(payload.get("verified_claim_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.review_claim(verified_claim_id=claim_id, decision=str(payload.get("decision", "unresolved")),
                rationale=str(payload.get("rationale", "")), reviewer=actor, confirmation=f"VERIFIED CLAIM 229 {claim_id} PRUEFEN")
            return JSONResponse({"ok": True, "claim": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build229/cycle-assess")
    async def build229_cycle_assess(request: Request):
        require_auth(request); payload=await request.json(); cycle_id=str(payload.get("cycle_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.assess_cycle(cycle_id=cycle_id, actor=actor, confirmation=f"VERIFIED RESEARCH CYCLE 229 {cycle_id} BEWERTEN")
            return JSONResponse({"ok": True, "assessment": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build229/gap-add")
    async def build229_gap_add(request: Request):
        require_auth(request); payload=await request.json(); loop_id=str(payload.get("loop_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.add_gap(loop_id=loop_id, question=str(payload.get("question", "")), target_type=str(payload.get("target_type", "unknown")),
                target_value=str(payload.get("target_value", "")), priority=int(payload.get("priority", 50)), actor=actor,
                confirmation=f"RESEARCH GAP 229 {loop_id} ANLEGEN")
            return JSONResponse({"ok": True, "gap": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build229/gap-resolve")
    async def build229_gap_resolve(request: Request):
        require_auth(request); payload=await request.json(); gap_id=str(payload.get("gap_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.resolve_gap(gap_id=gap_id, resolution_note=str(payload.get("resolution_note", "")), actor=actor,
                confirmation=f"RESEARCH GAP 229 {gap_id} SCHLIESSEN")
            return JSONResponse({"ok": True, "gap": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build229/training-export")
    async def build229_training_export(request: Request):
        require_auth(request); payload=await request.json(); claim_id=str(payload.get("verified_claim_id", "")); actor=request_actor(request)
        try:
            result=ctx.build229.export_verified_claim_training_candidate(verified_claim_id=claim_id, actor=actor,
                confirmation=f"VERIFIED CLAIM TRAINING 229 {claim_id} EXPORTIEREN")
            return JSONResponse({"ok": True, **result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/identity-create")
    async def build230_identity_create(request: Request):
        require_auth(request); form = await request.form(); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        aliases=[x.strip() for x in str(form.get("aliases", "")).split(",") if x.strip()]
        try:
            result=ctx.build230.create_identity_record(case_id=case_id, source_ref=str(form.get("source_ref", "")), record_ref=str(form.get("record_ref", "")), label=str(form.get("label", "")), language=str(form.get("language", "und")), aliases=aliases, anchors={}, statement_refs=[], source_reliability=.5, created_by=actor, confirmation=f"MULTILINGUAL IDENTITY 230 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Mehrsprachiger Identitätskandidat {result['multilingual_record_id']} angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build230/identity-compare")
    async def build230_identity_compare(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request)
        left=str(payload.get("left_record_id", "")); right=str(payload.get("right_record_id", ""))
        try:
            row=ctx.build230._identity(left); case_id=row["case_id"]
            result=ctx.build230.compare_identity_records(left_record_id=left, right_record_id=right, created_by=actor, confirmation=f"MULTILINGUAL IDENTITY COMPARE 230 {case_id} AUSFUEHREN")
            return JSONResponse({"ok": True, "pair": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/identity-review")
    async def build230_identity_review(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request); pair_id=str(payload.get("pair_id", ""))
        try:
            result=ctx.build230.review_identity_pair(pair_id=pair_id, decision=str(payload.get("decision", "uncertain")), rationale=str(payload.get("rationale", "")), reviewer=actor, confirmation=f"MULTILINGUAL IDENTITY REVIEW 230 {pair_id} SPEICHERN")
            return JSONResponse({"ok": True, "pair": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/rendering-create")
    async def build230_rendering_create(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request); sid=str(payload.get("statement_id", "")); case_id=str(payload.get("case_id", ""))
        try:
            result=ctx.build230.register_statement_rendering(case_id=case_id, statement_id=sid, target_language=str(payload.get("target_language", "de")), translated_text=str(payload.get("translated_text", "")), engine=str(payload.get("engine", "manual")), engine_version=str(payload.get("engine_version", "")), transliteration_text=str(payload.get("transliteration_text", "")), uncertainties=list(payload.get("uncertainties", []) or []), named_entities_preserved=bool(payload.get("named_entities_preserved", False)), created_by=actor, confirmation=f"STATEMENT RENDERING 230 {sid} ANLEGEN")
            return JSONResponse({"ok": True, "rendering": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/rendering-review")
    async def build230_rendering_review(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request); rid=str(payload.get("rendering_id", ""))
        try:
            result=ctx.build230.review_statement_rendering(rendering_id=rid, decision=str(payload.get("decision", "approved")), review_note=str(payload.get("review_note", "")), reviewer=actor, confirmation=f"STATEMENT RENDERING REVIEW 230 {rid} SPEICHERN")
            return JSONResponse({"ok": True, "rendering": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/fusion-create")
    async def build230_fusion_create(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request); case_id=str(payload.get("case_id", ""))
        try:
            result=ctx.build230.create_source_fusion(case_id=case_id, subject_ref=str(payload.get("subject_ref", "")), predicate=str(payload.get("predicate", "")), working_language=str(payload.get("working_language", "de")), canonical_value=payload.get("canonical_value", {}), evidence_roles=dict(payload.get("evidence_roles", {}) or {}), created_by=actor, confirmation=f"MULTILINGUAL SOURCE FUSION 230 {case_id} ANLEGEN")
            return JSONResponse({"ok": True, "fusion": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/fusion-review")
    async def build230_fusion_review(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request); fid=str(payload.get("fusion_id", ""))
        try:
            result=ctx.build230.review_source_fusion(fusion_id=fid, decision=str(payload.get("decision", "needs_more_evidence")), review_note=str(payload.get("review_note", "")), reviewer=actor, confirmation=f"MULTILINGUAL SOURCE FUSION REVIEW 230 {fid} SPEICHERN")
            return JSONResponse({"ok": True, "fusion": result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build230/fusion-handoff")
    async def build230_fusion_handoff(request: Request):
        require_auth(request); payload=await request.json(); actor=request_actor(request); fid=str(payload.get("fusion_id", ""))
        try:
            result=ctx.build230.handoff_to_verified_loop(fusion_id=fid, cycle_id=str(payload.get("cycle_id", "")), claim_text=str(payload.get("claim_text", "")), confidence=float(payload.get("confidence", .8)), actor=actor, confirmation=f"MULTILINGUAL FUSION 230 {fid} AN BUILD229 UEBERGEBEN")
            return JSONResponse({"ok": True, **result})
        except Exception as exc: return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)

    @app.post("/build231/outcome-submit")
    async def build231_outcome_submit(request: Request):
        require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); query_id=str(form.get("query_id", "")); actor=request_actor(request)
        refs=[x.strip() for x in str(form.get("evidence_refs", "")).split(",") if x.strip()]
        try:
            result=ctx.build231.submit_outcome(
                case_id=case_id, query_id=query_id, source_key=str(form.get("source_key", "")), outcome_kind=str(form.get("outcome_kind", "useful")),
                precision_signal=float(form.get("precision_signal", .5) or .5), counterevidence_signal=float(form.get("counterevidence_signal", 0) or 0),
                latency_ms=int(form.get("latency_ms", 0) or 0), error_signal=float(form.get("error_signal", 0) or 0),
                opsec_incident=bool(form.get("opsec_incident")), country=str(form.get("country", "")), evidence_refs=refs,
                rationale=str(form.get("rationale", "")), submitted_by=actor, confirmation=f"SOURCE OUTCOME 231 {query_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Source-Outcome {result['outcome_id']} reviewpflichtig gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build231/outcome-review")
    async def build231_outcome_review(request: Request):
        require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); outcome_id=str(form.get("outcome_id", "")); actor=request_actor(request)
        try:
            result=ctx.build231.review_outcome(outcome_id=outcome_id, decision=str(form.get("decision", "accepted")), review_note=str(form.get("review_note", "")), reviewer=actor, confirmation=f"SOURCE OUTCOME REVIEW 231 {outcome_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Outcome-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build231/policy-build")
    async def build231_policy_build(request: Request):
        require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build231.build_policy_snapshot(
                case_id=case_id, half_life_days=int(form.get("half_life_days", 120) or 120), min_sample=int(form.get("min_sample", 5) or 5),
                max_adjustment=float(form.get("max_adjustment", .10) or .10), max_domain_share=float(form.get("max_domain_share", .55) or .55),
                max_reviewer_share=float(form.get("max_reviewer_share", .60) or .60), exploration_rate=float(form.get("exploration_rate", .08) or .08),
                created_by=actor, confirmation=f"SOURCE POLICY 231 {case_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Source-Policy v{result['policy_version']} als Draft erzeugt; separates Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build231/policy-review")
    async def build231_policy_review(request: Request):
        require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); policy_id=str(form.get("policy_id", "")); actor=request_actor(request)
        try:
            result=ctx.build231.review_policy_snapshot(policy_id=policy_id, decision=str(form.get("decision", "approved")), rationale=str(form.get("rationale", "")), reviewer=actor, confirmation=f"SOURCE POLICY REVIEW 231 {policy_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Policy-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build231/exploration-propose")
    async def build231_exploration_propose(request: Request):
        require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); query_id=str(form.get("query_id", "")); actor=request_actor(request)
        try:
            result=ctx.build231.propose_exploration(query_id=query_id, created_by=actor, confirmation=f"SOURCE EXPLORATION 231 {query_id} VORSCHLAGEN")
            msg = f"Exploration {result['proposal_id']} nur als manuellen Versuch vorgeschlagen." if result.get("proposal_id") else str(result.get("reason") or "Kein Vorschlag")
            return RedirectResponse(_link("build214", case_id, message=msg), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build231/exploration-review")
    async def build231_exploration_review(request: Request):
        require_auth(request); form = await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); proposal_id=str(form.get("proposal_id", "")); actor=request_actor(request)
        try:
            result=ctx.build231.review_exploration(proposal_id=proposal_id, decision=str(form.get("decision", "deferred")), rationale=str(form.get("rationale", "")), reviewer=actor, confirmation=f"SOURCE EXPLORATION REVIEW 231 {proposal_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Exploration-Review {result['decision']} gespeichert; keine Quelle wurde automatisch aktiviert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build232/suite-seed")
    async def build232_suite_seed(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build232.seed_goldstandard_suite(case_id=case_id, created_by=actor, confirmation=f"PHASE8 GOLDSTANDARD 232 {case_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Goldstandard {result['suite_id']} mit {result['case_count']} Fällen eingefroren."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build232/trial-submit")
    async def build232_trial_submit(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); suite_id=str(form.get("suite_id", "")); actor=request_actor(request)
        try:
            results=json.loads(str(form.get("results_json", "{}"))); environment=json.loads(str(form.get("environment_json", "{}")))
            result=ctx.build232.submit_trial(suite_id=suite_id, system_label=str(form.get("system_label", "candidate")), build_label=str(form.get("build_label", "")), results=results, environment=environment, submitted_by=actor, confirmation=f"PHASE8 TRIAL 232 {suite_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualification-Trial {result['trial_id']} reviewpflichtig gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build232/trial-review")
    async def build232_trial_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); trial_id=str(form.get("trial_id", "")); actor=request_actor(request)
        try:
            result=ctx.build232.review_trial(trial_id=trial_id, decision=str(form.get("decision", "accepted")), note=str(form.get("note", "")), reviewer=actor, confirmation=f"PHASE8 TRIAL REVIEW 232 {trial_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Trial-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build232/scorecard-create")
    async def build232_scorecard_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); trial_id=str(form.get("trial_id", "")); actor=request_actor(request)
        try:
            result=ctx.build232.create_scorecard(trial_id=trial_id, created_by=actor, confirmation=f"PHASE8 SCORECARD 232 {trial_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Scorecard {result['scorecard_id']} berechnet."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build232/compare")
    async def build232_compare(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); baseline_id=str(form.get("baseline_scorecard_id", "")); candidate_id=str(form.get("candidate_scorecard_id", "")); actor=request_actor(request)
        try:
            result=ctx.build232.compare_scorecards(baseline_scorecard_id=baseline_id, candidate_scorecard_id=candidate_id, created_by=actor, confirmation=f"PHASE8 QUALIFICATION 232 {candidate_id} VERGLEICHEN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualification-Vergleich {result['comparison_id']}: {result['status']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build232/comparison-review")
    async def build232_comparison_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); comparison_id=str(form.get("comparison_id", "")); actor=request_actor(request)
        try:
            result=ctx.build232.review_comparison(comparison_id=comparison_id, decision=str(form.get("decision", "needs_revision")), rationale=str(form.get("rationale", "")), reviewer=actor, confirmation=f"PHASE8 QUALIFICATION REVIEW 232 {comparison_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Phase-8-Review {result['decision']} gespeichert; keine automatische Aktivierung."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)


    @app.post("/build233/campaign-create")
    async def build233_campaign_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); suite_id=str(form.get("suite_id", "")); actor=request_actor(request)
        try:
            result=ctx.build233.create_campaign(case_id=case_id, suite_id=suite_id, title=str(form.get("title", "")), created_by=actor, confirmation=f"PHASE8 CAMPAIGN 233 {case_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualification-Campaign {result['campaign_id']} angelegt; Blind-Arme erzeugt."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build233/manifest-freeze")
    async def build233_manifest_freeze(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); campaign_id=str(form.get("campaign_id", "")); actor=request_actor(request)
        try:
            environment=json.loads(str(form.get("environment_json", "{}")))
            result=ctx.build233.freeze_manifest(campaign_id=campaign_id, environment=environment, protocol_notes=str(form.get("protocol_notes", "")), created_by=actor, confirmation=f"PHASE8 MANIFEST 233 {campaign_id} EINFRIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"Execution Manifest {result['manifest_id']} eingefroren."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build233/arm-submit")
    async def build233_arm_submit(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); campaign_id=str(form.get("campaign_id", "")); actor=request_actor(request)
        try:
            results=json.loads(str(form.get("results_json", "{}")))
            result=ctx.build233.submit_arm(campaign_id=campaign_id, arm_code=str(form.get("arm_code", "")), results=results, submitted_by=actor, confirmation=f"PHASE8 ARM 233 {campaign_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Blind Arm als {result['arm_role']} gespeichert; Trial {result['trial_id']} reviewpflichtig."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build233/arm-review")
    async def build233_arm_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); trial_id=str(form.get("trial_id", "")); actor=request_actor(request)
        try:
            result=ctx.build233.review_arm(trial_id=trial_id, decision=str(form.get("decision", "accepted")), note=str(form.get("note", "")), reviewer=actor, confirmation=f"PHASE8 ARM REVIEW 233 {trial_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Arm-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build233/cycle-finalize")
    async def build233_cycle_finalize(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); campaign_id=str(form.get("campaign_id", "")); actor=request_actor(request)
        try:
            result=ctx.build233.finalize_cycle(campaign_id=campaign_id, created_by=actor, confirmation=f"PHASE8 CYCLE 233 {campaign_id} AUSWERTEN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualification-Zyklus {result['cycle_id']}: {result['status']} · {len(result['remediation_tickets'])} Remediation-Ticket(s)."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build233/cycle-review")
    async def build233_cycle_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); cycle_id=str(form.get("cycle_id", "")); actor=request_actor(request)
        try:
            result=ctx.build233.review_cycle(cycle_id=cycle_id, decision=str(form.get("decision", "needs_remediation")), rationale=str(form.get("rationale", "")), reviewer=actor, confirmation=f"PHASE8 CYCLE REVIEW 233 {cycle_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualification-Review {result['decision']} gespeichert; keine automatische Freigabe."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build233/ticket-action")
    async def build233_ticket_action(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); ticket_id=str(form.get("ticket_id", "")); actor=request_actor(request)
        try:
            result=ctx.build233.act_on_ticket(ticket_id=ticket_id, status=str(form.get("status", "accepted_for_234")), note=str(form.get("note", "")), actor=actor, confirmation=f"REMEDIATION 233 {ticket_id} STATUS SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Remediation {ticket_id}: {result['status']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build234/plan-create")
    async def build234_plan_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); ticket_id=str(form.get("ticket_id", "")); actor=request_actor(request)
        try:
            result=ctx.build234.create_plan(ticket_id=ticket_id, root_cause=str(form.get("root_cause", "")), change_summary=str(form.get("change_summary", "")), verification_strategy=str(form.get("verification_strategy", "")), created_by=actor, confirmation=f"REMEDIATION PLAN 234 {ticket_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Remediation-Plan {result['plan_id']} erstellt; unabhängiges Review erforderlich."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build234/plan-review")
    async def build234_plan_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); plan_id=str(form.get("plan_id", "")); actor=request_actor(request)
        try:
            result=ctx.build234.review_plan(plan_id=plan_id, decision=str(form.get("decision", "approved")), note=str(form.get("note", "")), reviewer=actor, confirmation=f"REMEDIATION PLAN REVIEW 234 {plan_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Plan-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build234/rerun-submit")
    async def build234_rerun_submit(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); plan_id=str(form.get("plan_id", "")); actor=request_actor(request)
        try:
            results=json.loads(str(form.get("results_json", "{}")))
            result=ctx.build234.submit_rerun(plan_id=plan_id, results=results, submitted_by=actor, confirmation=f"REMEDIATION RERUN 234 {plan_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Rerun {result['rerun_id']} gespeichert; Trial {result['trial_id']} reviewpflichtig."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build234/rerun-review")
    async def build234_rerun_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); rerun_id=str(form.get("rerun_id", "")); actor=request_actor(request)
        try:
            result=ctx.build234.review_rerun(rerun_id=rerun_id, decision=str(form.get("decision", "accepted")), note=str(form.get("note", "")), reviewer=actor, confirmation=f"REMEDIATION RERUN REVIEW 234 {rerun_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Rerun-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build234/verify")
    async def build234_verify(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); rerun_id=str(form.get("rerun_id", "")); actor=request_actor(request)
        try:
            result=ctx.build234.finalize_verification(rerun_id=rerun_id, created_by=actor, confirmation=f"REMEDIATION VERIFY 234 {rerun_id} AUSWERTEN")
            return RedirectResponse(_link("build214", case_id, message=f"Verification {result['verification_id']}: {result['status']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build234/verify-review")
    async def build234_verify_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); verification_id=str(form.get("verification_id", "")); actor=request_actor(request)
        try:
            result=ctx.build234.review_verification(verification_id=verification_id, decision=str(form.get("decision", "needs_revision")), rationale=str(form.get("rationale", "")), reviewer=actor, confirmation=f"REMEDIATION VERIFY REVIEW 234 {verification_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Remediation-Review {result['decision']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build235/import-core")
    async def build235_import_core(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build235.import_core_case(case_id=case_id, actor=actor, confirmation=f"KERNEL IMPORT 235 {case_id} STARTEN")
            count=sum(result["imported"].values())
            return RedirectResponse(_link("build214", case_id, message=f"Canonical Kernel: {count} historische Datensätze verlustfrei abgebildet."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build235/entity-create")
    async def build235_entity_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build235.create_entity(case_id=case_id, label=str(form.get("label", "")), entity_type=str(form.get("entity_type", "person")), confidence=float(form.get("confidence", .5) or .5), attributes={}, actor=actor, confirmation=f"KERNEL OBJECT 235 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Canonical Entity {result['object_id']} als Kandidat angelegt."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build235/claim-create")
    async def build235_claim_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build235.create_claim(case_id=case_id, claim_text=str(form.get("claim_text", "")), confidence=float(form.get("confidence", .5) or .5), about_object_id=str(form.get("about_object_id", "")), actor=actor, confirmation=f"KERNEL OBJECT 235 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Canonical Claim {result['object_id']} angelegt."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build235/object-create")
    async def build235_object_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            payload=json.loads(str(form.get("payload_json", "{}") or "{}"))
            result=ctx.build235.create_object(case_id=case_id, object_type=str(form.get("object_type", "finding")), subtype=str(form.get("subtype", "")), label=str(form.get("label", "")), state=str(form.get("state", "candidate")), confidence=float(form.get("confidence", .5) or .5), payload=payload, provenance={"origin":"build235_workspace"}, actor=actor, confirmation=f"KERNEL OBJECT 235 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Canonical Object {result['object_id']} angelegt."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build235/link-create")
    async def build235_link_create(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build235.create_link(case_id=case_id, source_object_id=str(form.get("source_object_id", "")), relation_type=str(form.get("relation_type", "related_to")), target_object_id=str(form.get("target_object_id", "")), confidence=float(form.get("confidence", .5) or .5), evidence_refs=[], actor=actor, confirmation=f"KERNEL LINK 235 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Canonical Link {result['link_id']} als Kandidat angelegt."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build235/link-review")
    async def build235_link_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); link_id=str(form.get("link_id", "")); actor=request_actor(request)
        try:
            result=ctx.build235.review_link(link_id=link_id, decision=str(form.get("decision", "needs_more_evidence")), rationale=str(form.get("rationale", "")), reviewer=actor, confirmation=f"KERNEL LINK REVIEW 235 {link_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Canonical Link Review: {result['decision']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build236/source-register")
    async def build236_source_register(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request); key=str(form.get("source_key", "")).strip()
        split=lambda name,default: [x.strip() for x in str(form.get(name,default)).split(",") if x.strip()]
        try:
            result=ctx.build236.register_source(source_key=key,title=str(form.get("title", "")),provider=str(form.get("provider", "manual")),source_type=str(form.get("source_type", "open_web")),route_class=str(form.get("route_class", "public_web")),adapter_family=str(form.get("adapter_family", "manual_236")),access_mode=str(form.get("access_mode", "manual_browser")),target_types=split("target_types","unknown"),outputs=split("outputs","evidence"),countries=split("countries","global"),languages=split("languages","mul"),cost_class=str(form.get("cost_class", "unknown")),network_capable=str(form.get("access_mode", "manual_browser")) not in {"local","local_import"},requires_auth=bool(form.get("requires_auth")),opsec_risk=str(form.get("opsec_risk", "elevated")),notes=str(form.get("notes", "")),created_by=actor,confirmation=f"SOURCE FABRIC 236 {key} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Source Fabric: {result['source_key']} als reviewpflichtige Revision registriert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build236/source-review")
    async def build236_source_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); revision_id=str(form.get("revision_id", "")); actor=request_actor(request)
        try:
            result=ctx.build236.review_revision(revision_id=revision_id,decision=str(form.get("decision", "approved")),rationale=str(form.get("rationale", "")),reviewer=actor,confirmation=f"SOURCE FABRIC REVIEW 236 {revision_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Source-Governance: {result['decision']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build236/health-observe")
    async def build236_health_observe(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); key=str(form.get("source_key", "")); actor=request_actor(request)
        try:
            result=ctx.build236.observe_health(source_key=key,health_state=str(form.get("health_state", "unknown")),latency_ms=int(form.get("latency_ms", 0) or 0),error_class=str(form.get("error_class", "")),note=str(form.get("note", "")),observed_by=actor,confirmation=f"SOURCE HEALTH 236 {key} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Source-Health {result['health_state']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build236/bind-source")
    async def build236_bind_source(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); key=str(form.get("source_key", "")); actor=request_actor(request)
        try:
            result=ctx.build236.bind_source_to_case(case_id=case_id,source_key=key,actor=actor,confirmation=f"SOURCE FABRIC BIND 236 {case_id} {key}")
            return RedirectResponse(_link("build214", case_id, message=f"Quelle {key} mit Canonical Source {result['canonical_source_object_id']} verbunden."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build236/training-stage")
    async def build236_training_stage(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build236.stage_training_from_reviewed_outcomes(case_id=case_id,limit=int(form.get("limit", 10) or 10),actor=actor,confirmation=f"SOURCE TRAINING 236 {case_id} VORBEREITEN")
            return RedirectResponse(_link("build214", case_id, message=f"KI-Training: {len(result['staged'])} reviewpflichtige Trainingskandidaten vorbereitet; keine automatische Modellaktivierung."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/profile-add")
    async def build237_profile_add(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        split=lambda name: [x.strip() for x in str(form.get(name,"")).split(",") if x.strip()]
        try:
            result=ctx.build237.add_profile_observation(case_id=case_id,platform=str(form.get("platform", "")),source_key=str(form.get("source_key", "local_case_evidence")),handle=str(form.get("handle", "")),display_name=str(form.get("display_name", "")),profile_url=str(form.get("profile_url", "")),bio=str(form.get("bio", "")),language=str(form.get("language", "und")),aliases=split("aliases"),location=str(form.get("location", "")),created_by=actor,confirmation=f"SOCIAL PROFILE 237 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-Profil {result['profile_id']} als reviewpflichtige Beobachtung gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/profile-review")
    async def build237_profile_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request); oid=str(form.get("observation_id", ""))
        try:
            result=ctx.build237.review_profile_observation(observation_id=oid,decision=str(form.get("decision", "accepted")),rationale=str(form.get("rationale", "")),reviewer=actor,confirmation=f"SOCIAL PROFILE REVIEW 237 {oid} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-Profil-Review: {result['decision']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/post-add")
    async def build237_post_add(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build237.add_public_post(case_id=case_id,profile_id=str(form.get("profile_id", "")),source_key=str(form.get("source_key", "local_case_evidence")),content_original=str(form.get("content_original", "")),canonical_url=str(form.get("canonical_url", "")),platform_post_id=str(form.get("platform_post_id", "")),language=str(form.get("language", "und")),published_at=str(form.get("published_at", "")),created_by=actor,confirmation=f"SOCIAL POST 237 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Öffentlicher Post {result['post_id']} gespeichert; Review erforderlich."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/post-review")
    async def build237_post_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request); pid=str(form.get("post_id", ""))
        try:
            result=ctx.build237.review_post(post_id=pid,decision=str(form.get("decision", "accepted")),rationale=str(form.get("rationale", "")),reviewer=actor,confirmation=f"SOCIAL POST REVIEW 237 {pid} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-Post-Review: {result['decision']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/identity-compare")
    async def build237_identity_compare(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build237.compare_profiles(left_profile_id=str(form.get("left_profile_id", "")),right_profile_id=str(form.get("right_profile_id", "")),created_by=actor,confirmation=f"SOCIAL IDENTITY 237 {case_id} VERGLEICHEN")
            return RedirectResponse(_link("build214", case_id, message=f"Cross-Platform-Kandidat {result['candidate_id']} mit Score {result['score']:.2f} erzeugt; kein automatischer Merge."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/identity-review")
    async def build237_identity_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request); cid=str(form.get("candidate_id", ""))
        try:
            result=ctx.build237.review_identity_candidate(candidate_id=cid,decision=str(form.get("decision", "uncertain")),rationale=str(form.get("rationale", "")),reviewer=actor,confirmation=f"SOCIAL IDENTITY REVIEW 237 {cid} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-Identity-Review: {result['decision']}; kein automatischer Merge."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/relationship-add")
    async def build237_relationship_add(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        refs=[x.strip() for x in str(form.get("evidence_refs", "")).split(",") if x.strip()]
        try:
            result=ctx.build237.add_relationship_candidate(case_id=case_id,actor_profile_id=str(form.get("actor_profile_id", "")),target_profile_id=str(form.get("target_profile_id", "")),target_label=str(form.get("target_label", "")),relation_type=str(form.get("relation_type", "mentions")),evidence_refs=refs,confidence=float(form.get("confidence", .5) or .5),created_by=actor,confirmation=f"SOCIAL RELATIONSHIP 237 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-Beziehungskandidat {result['relationship_id']} gespeichert."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/relationship-review")
    async def build237_relationship_review(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request); rid=str(form.get("relationship_id", ""))
        try:
            result=ctx.build237.review_relationship(relationship_id=rid,decision=str(form.get("decision", "needs_more_evidence")),rationale=str(form.get("rationale", "")),reviewer=actor,confirmation=f"SOCIAL RELATIONSHIP REVIEW 237 {rid} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-Beziehungsreview: {result['decision']}."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/training-stage")
    async def build237_training_stage(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build237.stage_training_from_reviewed_social(case_id=case_id,actor=actor,limit=int(form.get("limit", 30) or 30),confirmation=f"SOCIAL TRAINING 237 {case_id} VORBEREITEN")
            return RedirectResponse(_link("build214", case_id, message=f"Social-KI-Training: {len(result['staged'])} reviewpflichtige Trainingskandidaten vorbereitet."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build237/legacy-adopt")
    async def build237_legacy_adopt(request: Request):
        require_auth(request); form=await _form(request); verify_csrf(form, request)
        case_id=str(form.get("case_id", "")); actor=request_actor(request)
        try:
            result=ctx.build237.adopt_legacy_social(case_id=case_id,actor=actor,confirmation=f"SOCIAL LEGACY 237 {case_id} UEBERNEHMEN")
            return RedirectResponse(_link("build214", case_id, message=f"Legacy Social: {result['imported']} reviewte Profile übernommen, {result['skipped']} übersprungen."), status_code=303)
        except Exception as exc: return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)


    @app.post("/build238/hypothesis-add")
    async def build238_hypothesis_add(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""));
        refs=[x.strip() for x in str(form.get("evidence_refs","")).split(",") if x.strip()]; contra=[x.strip() for x in str(form.get("contradiction_refs","")).split(",") if x.strip()]
        return _post_result(request,case_id=case_id,result=ctx.build238.propose_relationship(case_id=case_id,source_object_id=str(form.get("source_object_id","")),relation_type=str(form.get("relation_type","related_to")),target_object_id=str(form.get("target_object_id","")),rationale=str(form.get("rationale","")),evidence_refs=refs,contradiction_refs=contra,confidence=float(form.get("confidence",.5) or .5),valid_from=str(form.get("valid_from","")),valid_to=str(form.get("valid_to","")),created_by=actor,confirmation=f"GRAPH HYPOTHESIS 238 {case_id} ANLEGEN"))

    @app.post("/build238/hypothesis-review")
    async def build238_hypothesis_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); hid=str(form.get("graph_hypothesis_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build238.review_relationship(graph_hypothesis_id=hid,decision=str(form.get("decision","needs_more_evidence")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"GRAPH HYPOTHESIS REVIEW 238 {hid} SPEICHERN"))

    @app.post("/build238/edge-annotate")
    async def build238_edge_annotate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); lid=str(form.get("link_id","")); refs=[x.strip() for x in str(form.get("evidence_refs","")).split(",") if x.strip()]
        return _post_result(request,case_id=case_id,result=ctx.build238.annotate_edge(link_id=lid,valid_from=str(form.get("valid_from","")),valid_to=str(form.get("valid_to","")),first_observed_at=str(form.get("first_observed_at","")),last_observed_at=str(form.get("last_observed_at","")),temporal_precision=str(form.get("temporal_precision","unknown")),evidence_refs=refs,provenance={"origin":"build238_workspace"},created_by=actor,confirmation=f"GRAPH EDGE 238 {lid} ANNOTIEREN"))

    @app.post("/build238/snapshot")
    async def build238_snapshot(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build238.create_snapshot(case_id=case_id,actor=actor,confirmation=f"GRAPH SNAPSHOT 238 {case_id} ERSTELLEN"))

    @app.post("/build238/training-stage")
    async def build238_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build238.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"GRAPH TRAINING 238 {case_id} VORBEREITEN"))

    @app.post("/build239/capture-text")
    async def build239_capture_text(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build239.capture_text(case_id=case_id,text=str(form.get("text","")),original_filename=str(form.get("original_filename","")),source_key=str(form.get("source_key","")),source_url=str(form.get("source_url","")),created_by=actor,confirmation=f"EVIDENCE VAULT 239 {case_id} CAPTURE"))

    @app.post("/build239/review")
    async def build239_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); vid=str(form.get("vault_item_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build239.review_item(vault_item_id=vid,decision=str(form.get("decision","needs_context")),evidence_quality=float(form.get("evidence_quality",.5) or .5),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"EVIDENCE REVIEW 239 {vid} SPEICHERN"))

    @app.post("/build239/kernel-bind")
    async def build239_kernel_bind(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); vid=str(form.get("vault_item_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build239.bind_to_kernel(vault_item_id=vid,title=str(form.get("title","Evidence")),statement=str(form.get("statement","")),confidence=float(form.get("confidence",.5) or .5),actor=actor,confirmation=f"EVIDENCE KERNEL 239 {vid} BINDEN"))

    @app.post("/build239/integrity")
    async def build239_integrity(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); vid=str(form.get("vault_item_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build239.verify_item(vault_item_id=vid,checked_by=actor))

    @app.post("/build239/snapshot")
    async def build239_snapshot(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build239.create_snapshot(case_id=case_id,actor=actor,confirmation=f"EVIDENCE SNAPSHOT 239 {case_id} ERSTELLEN"))

    @app.post("/build239/training-stage")
    async def build239_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build239.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"EVIDENCE TRAINING 239 {case_id} VORBEREITEN"))

    @app.post("/build240/snapshot")
    async def build240_snapshot(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build240.create_snapshot(case_id=case_id,actor=actor,confirmation=f"COAI SNAPSHOT 240 {case_id} ERSTELLEN"))

    @app.post("/build240/assess-turn")
    async def build240_assess_turn(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); turn_id=str(form.get("turn_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build240.assess_turn(turn_id=turn_id,actor=actor))

    @app.post("/build240/training-stage")
    async def build240_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build240.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"COAI TRAINING 240 {case_id} VORBEREITEN"))


    @app.post("/build241/cycle")
    async def build241_cycle(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        csv=lambda name:[x.strip() for x in str(form.get(name,"")).split(",") if x.strip()]
        gaps=[x.strip() for x in str(form.get("evidence_gaps","")).splitlines() if x.strip()]
        result=ctx.build241.create_cycle(case_id=case_id,question=str(form.get("question","")),primary_hypothesis=str(form.get("primary_hypothesis","")),counter_hypothesis=str(form.get("counter_hypothesis","")),primary_confidence=float(form.get("primary_confidence",.5) or .5),counter_confidence=float(form.get("counter_confidence",.5) or .5),supporting_refs=csv("supporting_refs"),counter_supporting_refs=csv("counter_supporting_refs"),contradicting_refs=csv("contradicting_refs"),evidence_gaps=gaps,actor=actor,confirmation=f"REASONING CYCLE 241 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result)

    @app.post("/build241/review")
    async def build241_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); cycle_id=str(form.get("cycle_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build241.review_cycle(cycle_id=cycle_id,decision=str(form.get("decision","revise")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"REASONING REVIEW 241 {cycle_id} SPEICHERN"))

    @app.post("/build241/step")
    async def build241_step(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); cycle_id=str(form.get("cycle_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build241.propose_next_step(cycle_id=cycle_id,label=str(form.get("label","")),evidence_gap=str(form.get("evidence_gap","")),expected_information_gain=float(form.get("expected_information_gain",.5) or .5),gap_reduction=float(form.get("gap_reduction",.5) or .5),opsec_risk=float(form.get("opsec_risk",.2) or .2),actor=actor,confirmation=f"REASONING STEP 241 {cycle_id} VORSCHLAGEN"))

    @app.post("/build241/correct")
    async def build241_correct(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); prior_cycle_id=str(form.get("prior_cycle_id", ""))
        csv=lambda name:[x.strip() for x in str(form.get(name,"")).split(",") if x.strip()]
        gaps=[x.strip() for x in str(form.get("evidence_gaps","")).splitlines() if x.strip()]
        result=ctx.build241.record_correction(prior_cycle_id=prior_cycle_id,question=str(form.get("question","")),corrected_hypothesis=str(form.get("corrected_hypothesis","")),corrected_counter_hypothesis=str(form.get("corrected_counter_hypothesis","")),primary_confidence=float(form.get("primary_confidence",.5) or .5),counter_confidence=float(form.get("counter_confidence",.5) or .5),supporting_refs=csv("supporting_refs"),counter_supporting_refs=csv("counter_supporting_refs"),contradicting_refs=csv("contradicting_refs"),evidence_gaps=gaps,trigger_evidence_refs=csv("trigger_evidence_refs"),rationale=str(form.get("rationale","")),actor=actor,confirmation=f"REASONING CORRECTION 241 {prior_cycle_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result)

    @app.post("/build241/assess-turn")
    async def build241_assess_turn(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); turn_id=str(form.get("turn_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build241.assess_turn(turn_id=turn_id,actor=actor))

    @app.post("/build241/training-stage")
    async def build241_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        return _post_result(request,case_id=case_id,result=ctx.build241.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"REASONING TRAINING 241 {case_id} VORBEREITEN"))

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "build": BUILD, "workspace": f"browser-{BUILD}", "offline_search": True, "autonomous_public_research": "explicit_confirmation_required", "machine_search_provider": "optional", "authentication": "required"}

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, tab: str = "cockpit244", case_id: str = "", flash: str = "", page: int = 1, min_precision: int = 0, target_id: str = ""):
        message, error = _take_flash(flash)
        if request.query_params.get("token"):
            if not bootstrap_authenticated(request):
                raise HTTPException(status_code=403, detail="Ungültiger lokaler Startnachweis")
            destination = "/security/bootstrap" if auth146.bootstrap_required() else "/security/login"
            response = RedirectResponse(destination, status_code=303)
            response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
            return response
        identity = require_auth(request)
        csrf_value = request_csrf(request)
        return HTMLResponse(_page(ctx, tab=tab, case_id=case_id, csrf=csrf_value, actor=str(identity["username"]), message=message, error=error, page=page, min_precision=min_precision, target_filter=target_id))

    @app.post("/evidence211/preserve-text")
    async def evidence211_preserve_text(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build211.preserve_text_evidence(
                case_id=case_id, title=form.get("title", ""), source_url=form.get("source_url", ""),
                text=form.get("text", ""), captured_by=actor, published_at=form.get("published_at", ""),
                legal_scope=form.get("legal_scope", "public_source_case_purpose"), metadata={},
                confirmation=f"EVIDENCE 211 {case_id} TEXT SPEICHERN",
            )
            return RedirectResponse(_link("evidence211", case_id, message=f"Beleg gesichert: {result['package']['package_id']} · Source-ID {result['source']['source_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/detect-tools")
    async def evidence211_detect_tools(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build211.detect_tools()
            available = sum(1 for row in result["tools"] if row["available"])
            return RedirectResponse(_link("evidence211", case_id, message=f"Lokale Prüfung abgeschlossen: {available} Werkzeuge/Komponenten verfügbar."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/enable-project")
    async def evidence211_enable_project(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); project_id = form.get("project_id", "")
        try:
            result = ctx.build211.enable_project(project_id=project_id, reviewer=actor, reason=form.get("reason", ""), confirmation=f"PROJECT 211 {project_id} FREIGEBEN")
            return RedirectResponse(_link("evidence211", case_id, message=f"Lokales Projekt freigegeben: {result['project_id']} ({result['detected_version'] or 'Version unbekannt'})."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/handoff")
    async def evidence211_handoff(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); project_id = form.get("project_id", "")
        try:
            result = ctx.build211.plan_external_capture(case_id=case_id, project_id=project_id, target_url=form.get("target_url", ""), purpose=form.get("purpose", ""), created_by=actor, confirmation=f"EXTERNAL CAPTURE 211 {case_id} PLANEN")
            return RedirectResponse(_link("evidence211", case_id, message=f"Manueller Capture-Handoff angelegt: {result['run_id']}. Keine automatische Außenverbindung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/import-capture")
    async def evidence211_import_capture(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); project_id = form.get("project_id", "")
        try:
            relative = Path(form.get("relative_path", "")).as_posix().lstrip("/")
            path = ctx.build211.import_root / project_id / relative
            common = dict(case_id=case_id, artifact_path=str(path), title=form.get("title", ""), source_url=form.get("source_url", ""), created_by=actor, collector_version=form.get("collector_version", "unknown") or "unknown", confirmation=f"EVIDENCE 211 {case_id} TOOL IMPORT")
            if project_id == "singlefile":
                result = ctx.build211.import_singlefile_capture(**common)
            elif project_id == "archivebox":
                result = ctx.build211.import_archivebox_capture(**common, media_type=form.get("media_type", "application/octet-stream"))
            else:
                raise ValueError("unsupported capture import project")
            return RedirectResponse(_link("evidence211", case_id, message=f"Externer Capture als Kandidatenbeleg importiert: {result['package']['package_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/exiftool-plan")
    async def evidence211_exiftool_plan(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build211.plan_tool_run(case_id=case_id, project_id="exiftool", package_id=form.get("package_id", ""), purpose=form.get("purpose", ""), options={}, created_by=actor, confirmation=f"TOOL RUN 211 {case_id} PLANEN")
            return RedirectResponse(_link("evidence211", case_id, message=f"Offline-ExifTool-Lauf geplant: {result['run_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/exiftool-run")
    async def evidence211_exiftool_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); run_id = form.get("run_id", "")
        try:
            result = ctx.build211.execute_exiftool(run_id=run_id, confirmation=f"TOOL RUN 211 {run_id} AUSFUEHREN")
            return RedirectResponse(_link("evidence211", case_id, message=f"ExifTool-Lauf abgeschlossen; abgeleitetes Beweisartefakt: {result['artifact_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/statement")
    async def evidence211_statement(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build211.create_statement(
                case_id=case_id, source_id=form.get("source_id", ""), entity_ref=form.get("entity_ref", ""),
                schema_name=form.get("schema_name", "Person"), predicate=form.get("predicate", ""),
                value=form.get("value", ""), original_value=form.get("original_value", ""),
                dataset_id=form.get("dataset_id", "case-local"), origin=form.get("origin", "manual_analyst_extraction"),
                statement_kind=form.get("statement_kind", "observation"), confidence=float(form.get("confidence", "0.5") or 0.5),
                created_by=actor, confirmation=f"STATEMENT 211 {case_id} ANLEGEN",
            )
            return RedirectResponse(_link("evidence211", case_id, message=f"Aussage als Kandidat angelegt: {result['statement']['statement_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/verify")
    async def evidence211_verify(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build211.verify_case(case_id=case_id)
            text = "bestanden" if result["ok"] else "FEHLER: " + ", ".join(result["errors"][:4])
            return RedirectResponse(_link("evidence211", case_id, message=f"Integritätsprüfung {text}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/approve-export")
    async def evidence211_approve_export(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); package_id = form.get("package_id", "")
        try:
            ctx.build211.approve_package_export(case_id=case_id, package_id=package_id, reviewer=actor, reason=form.get("reason", ""), confirmation=f"EVIDENCE EXPORT 211 {package_id} FREIGEBEN")
            return RedirectResponse(_link("evidence211", case_id, message=f"Package für redigierten Export freigegeben: {package_id}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence211/bundle")
    async def evidence211_bundle(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        package_ids = [x.strip() for x in form.get("package_ids", "").split(",") if x.strip()]
        try:
            result = ctx.build211.export_case_bundle(case_id=case_id, package_ids=package_ids, created_by=actor, confirmation=f"EVIDENCE BUNDLE 211 {case_id} ERSTELLEN")
            return RedirectResponse(_link("evidence211", case_id, message=f"Evidence-Bundle erstellt und geprüft: {result['bundle_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence211", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/source-validate")
    async def build212_source_validate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); source_id = form.get("source_id", "")
        checked = lambda key: form.get(key, "").lower() in {"true", "1", "on", "yes"}
        try:
            result = ctx.build212.validate_source(source_id=source_id, fixture_ok=checked("fixture_ok"), parser_ok=checked("parser_ok"), live_ok=checked("live_ok"), terms_reviewed=checked("terms_reviewed"), reviewer=actor, reason=form.get("reason", ""), confirmation=f"SOURCE 212 {source_id} VALIDIEREN")
            return RedirectResponse(_link("build212", case_id, message=f"Quelle {source_id}: {'aktiv' if result['active'] else 'weiter gesperrt'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/identity-record")
    async def build212_identity_record(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            fields = json.loads(form.get("fields_json", "{}"))
            refs = [x.strip() for x in form.get("provenance_refs", "").split(",") if x.strip()]
            result = ctx.build212.add_identity_record(case_id=case_id, source_ref=form.get("source_ref", ""), record_ref=form.get("record_ref", ""), fields=fields, provenance_refs=refs, source_reliability=float(form.get("source_reliability", ".5") or .5), created_by=actor, confirmation=f"IDENTITY RECORD 212 {case_id} ANLEGEN")
            return RedirectResponse(_link("build212", case_id, message=f"Identitätskandidat angelegt: {result['record_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/compare")
    async def build212_compare(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build212.compare_records(case_id=case_id, left_record_id=form.get("left_record_id", ""), right_record_id=form.get("right_record_id", ""), created_by=actor, confirmation=f"IDENTITY COMPARE 212 {case_id} AUSFUEHREN")
            return RedirectResponse(_link("build212", case_id, message=f"Vergleich {result['comparison_id']}: {result['probability']*100:.1f}% · nur Kandidat."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/review")
    async def build212_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); comparison_id = form.get("comparison_id", "")
        try:
            result = ctx.build212.review_comparison(comparison_id=comparison_id, reviewer=actor, reviewer_role=form.get("reviewer_role", "analyst"), decision=form.get("decision", "uncertain"), reason=form.get("reason", ""), confirmation=f"IDENTITY REVIEW 212 {comparison_id} SPEICHERN")
            return RedirectResponse(_link("build212", case_id, message=f"Unabhängiges Review gespeichert: {result['review_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/merge")
    async def build212_merge(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); comparison_id = form.get("comparison_id", "")
        try:
            result = ctx.build212.merge_records(comparison_id=comparison_id, label=form.get("label", ""), actor=actor, confirmation=f"IDENTITY MERGE 212 {comparison_id} AUSFUEHREN")
            return RedirectResponse(_link("build212", case_id, message=f"Reversible Identitätsgruppe erzeugt: {result['group_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/unmerge")
    async def build212_unmerge(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); group_id = form.get("group_id", ""); record_id = form.get("record_id", "")
        try:
            result = ctx.build212.unmerge_record(group_id=group_id, record_id=record_id, actor=actor, reason=form.get("reason", ""), confirmation=f"IDENTITY UNMERGE 212 {group_id} {record_id}")
            return RedirectResponse(_link("build212", case_id, message=f"Record reversibel aus Gruppe gelöst: {result['record_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/translate")
    async def build212_translate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build212.translate_case_text(case_id=case_id, source_id=form.get("source_id", ""), original_text=form.get("original_text", ""), original_language=form.get("original_language", ""), target_language=form.get("target_language", "de"), engine=form.get("engine", "manual"), translated_text=form.get("translated_text", ""), glossary={}, uncertainties=[x.strip() for x in form.get("uncertainties", "").split(",") if x.strip()], created_by=actor, confirmation=f"CASE TRANSLATION 212 {case_id} ANLEGEN")
            return RedirectResponse(_link("build212", case_id, message=f"Fallübersetzung angelegt: {result['translation_id']} · Interpretation, kein Fakt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/chat")
    async def build212_chat(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build212.prepare_chat_turn(case_id=case_id, question=form.get("question", ""), question_language=form.get("question_language", "de"), working_language=form.get("working_language", "de"), translation_id=form.get("translation_id", ""), created_by=actor, confirmation=f"CASE CHAT 212 {case_id} VORBEREITEN")
            return RedirectResponse(_link("build212", case_id, message=f"Chat-Ermittler-Turn vorbereitet: {result['turn_id']} · Agentenlauf {result['ai_run_id']} wartet auf Freigaben."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/chat-complete")
    async def build212_chat_complete(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); turn_id = form.get("turn_id", "")
        try:
            response = json.loads(form.get("response_json", "{}"))
            citations = [x.strip() for x in form.get("citations", "").split(",") if x.strip()]
            result = ctx.build212.complete_chat_turn(turn_id=turn_id, response=response, citations=citations, actor=actor, confirmation=f"CASE CHAT 212 {turn_id} SPEICHERN")
            return RedirectResponse(_link("build212", case_id, message=f"AI-Antwort review-pflichtig gespeichert: {result['turn_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/ai-feedback")
    async def build212_ai_feedback(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            dimensions = json.loads(form.get("dimensions_json", "{}"))
            result = ctx.build212.record_ai_feedback(case_id=case_id, item_type=form.get("item_type", "chat_turn"), item_id=form.get("item_id", ""), verdict=form.get("verdict", "needs_more_evidence"), dimensions=dimensions, reason=form.get("reason", ""), analyst=actor, confirmation=f"AI FEEDBACK 212 {case_id} SPEICHERN")
            return RedirectResponse(_link("build212", case_id, message=f"Ermittlerfeedback gespeichert: {result['feedback_id']} · keine automatische Modelländerung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/opsec-profile")
    async def build212_opsec_profile(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build212.create_opsec_profile(case_id=case_id, threat_level=form.get("threat_level", "elevated"), environment=form.get("environment", "existing_firefox_case_workspace"), reason=form.get("reason", ""), created_by=actor, confirmation=f"OPSEC PROFILE 212 {case_id} ANLEGEN")
            return RedirectResponse(_link("build212", case_id, message=f"OPSEC-Profil {result['threat_level']} angelegt: {result['profile_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/safety-lock")
    async def build212_safety_lock(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); enabled = form.get("enabled", "true").lower() == "true"
        try:
            result = ctx.build212.set_safety_lock(case_id=case_id, enabled=enabled, actor=actor, reason=form.get("reason", ""), confirmation=f"OPSEC LOCK 212 {case_id} {'AKTIVIEREN' if enabled else 'LOESEN'}")
            return RedirectResponse(_link("build212", case_id, message=f"Safety Lock {'aktiviert' if result['safety_lock'] else 'gelöst'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)

    @app.post("/build212/preflight")
    async def build212_preflight(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            requested = json.loads(form.get("requested_json", "{}"))
            result = ctx.build212.opsec_preflight(case_id=case_id, action_type=form.get("action_type", "source_research"), source_id=form.get("source_id", ""), requested=requested, created_by=actor, confirmation=f"OPSEC PREFLIGHT 212 {case_id} PRUEFEN")
            return RedirectResponse(_link("build212", case_id, message=f"OPSEC-Preflight: {result['decision']} · {len(result['risks'])} Risikoindikatoren."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build212", case_id, error=str(exc)), status_code=303)


    @app.post("/build213/import-definitions")
    async def build213_import_definitions(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); project_id = form.get("project_id", "")
        try:
            definitions = json.loads(form.get("definitions_json", "[]"))
            result = ctx.build213.import_definitions(project_id=project_id, dataset_version=form.get("dataset_version", ""), source_hash=form.get("source_hash", ""), definitions=definitions, reviewer=actor, notes=form.get("notes", ""), confirmation=f"SOCIAL DEFINITIONS 213 {project_id} IMPORTIEREN")
            return RedirectResponse(_link("build213", case_id, message=f"{result['definitions_imported']} Social-Definitionen kontrolliert importiert; keine Netzwerkausführung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/benchmark")
    async def build213_benchmark(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); project_id = form.get("project_id", "")
        try:
            fixtures = json.loads(form.get("fixtures_json", "[]"))
            result = ctx.build213.run_fixture_benchmark(project_id=project_id, import_id=form.get("import_id", ""), fixtures=fixtures, reviewer=actor, notes=form.get("notes", ""), confirmation=f"SOCIAL BENCHMARK 213 {project_id} AUSFUEHREN")
            return RedirectResponse(_link("build213", case_id, message=f"Offline-Benchmark {result['status']}: Precision {result['precision']:.2f}, Recall {result['recall']:.2f}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/project-approve")
    async def build213_project_approve(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id, actor = form.get("case_id", ""), request_actor(request)
        project_id = form.get("project_id", "")
        try:
            result = ctx.build213.approve_project(project_id=project_id, live_ok=form.get("live_ok") == "1", terms_reviewed=form.get("terms_reviewed") == "1", reviewer=actor, reason=form.get("reason", ""), confirmation=f"SOCIAL PROJECT 213 {project_id} FREIGEBEN")
            status = "aktiv" if result["active"] else "weiter gesperrt"
            return RedirectResponse(_link("build213", case_id, message=f"Social-Projekt {project_id}: {status}; keine automatische Ausführung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/plan")
    async def build213_plan(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            definition_ids = [x.strip() for x in re.split(r"[,;\n]", form.get("definition_ids", "")) if x.strip()]
            result = ctx.build213.create_username_plan(case_id=case_id, username=form.get("username", ""), question=form.get("question", ""), definition_ids=definition_ids, created_by=actor, confirmation=f"SOCIAL PLAN 213 {case_id} ANLEGEN")
            return RedirectResponse(_link("build213", case_id, message=f"Social-Rechercheplan vorbereitet: {len(result['task_ids'])} Tasks, {result['parallel_tabs']} Firefox-Tabs; kein automatisches Öffnen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/candidate")
    async def build213_candidate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build213.ingest_candidate(case_id=case_id, task_id=form.get("task_id", ""), existence_state=form.get("existence_state", "possible"), profile_url=form.get("profile_url", ""), display_name=form.get("display_name", ""), bio_original=form.get("bio_original", ""), content_language=form.get("content_language", "und"), extracted=json.loads(form.get("extracted_json", "{}")), evidence_refs=[x.strip() for x in re.split(r"[,;\n]", form.get("evidence_refs", "")) if x.strip()], collector_version=form.get("collector_version", "manual-browser"), observed_at=form.get("observed_at", ""), created_by=actor, limitations=[x.strip() for x in re.split(r"[,;\n]", form.get("limitations", "")) if x.strip()], confirmation=f"SOCIAL CANDIDATE 213 {case_id} SPEICHERN")
            return RedirectResponse(_link("build213", case_id, message=f"Social-Kandidat gespeichert: {result['candidate_id']} · Identität unbestätigt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/review")
    async def build213_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); candidate_id = form.get("candidate_id", "")
        try:
            result = ctx.build213.review_candidate(candidate_id=candidate_id, reviewer=actor, decision=form.get("decision", "uncertain"), identity_relation=form.get("identity_relation", "unknown"), reason=form.get("reason", ""), confirmation=f"SOCIAL REVIEW 213 {candidate_id} SPEICHERN")
            return RedirectResponse(_link("build213", case_id, message=f"Kandidatenreview gespeichert: {result['review_id']}; keine Identitätsbestätigung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/translate")
    async def build213_translate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build213.translate_candidate_content(case_id=case_id, candidate_id=form.get("candidate_id", ""), field_name=form.get("field_name", "bio_original"), target_language=form.get("target_language", "de"), engine=form.get("engine", "manual"), translated_text=form.get("translated_text", ""), created_by=actor, glossary={}, uncertainties=[x.strip() for x in re.split(r"[,;\n]", form.get("uncertainties", "")) if x.strip()], confirmation=f"SOCIAL TRANSLATION 213 {case_id} ANLEGEN")
            return RedirectResponse(_link("build213", case_id, message=f"Fallbezogene Social-Übersetzung gespeichert: {result['translation_id']} · Original bleibt erhalten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/chat")
    async def build213_chat(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build213.prepare_chat_turn(case_id=case_id, question=form.get("question", ""), question_language=form.get("question_language", "de"), working_language=form.get("working_language", "de"), created_by=actor, confirmation=f"SOCIAL CHAT 213 {case_id} VORBEREITEN")
            return RedirectResponse(_link("build213", case_id, message=f"Social-Chat-Turn vorbereitet: {result['turn_id']} · keine automatische Ausführung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/chat-complete")
    async def build213_chat_complete(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); turn_id = form.get("turn_id", "")
        try:
            result = ctx.build213.complete_chat_turn(turn_id=turn_id, response=json.loads(form.get("response_json", "{}")), citations=[x.strip() for x in re.split(r"[,;\n]", form.get("citations", "")) if x.strip()], actor=actor, confirmation=f"SOCIAL CHAT 213 {turn_id} SPEICHERN")
            return RedirectResponse(_link("build213", case_id, message=f"Reviewpflichtige Social-AI-Antwort gespeichert: {result['turn_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/ai-feedback")
    async def build213_ai_feedback(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build213.record_ai_feedback(case_id=case_id, item_type=form.get("item_type", "social_chat_turn"), item_id=form.get("item_id", ""), verdict=form.get("verdict", "needs_more_evidence"), dimensions=json.loads(form.get("dimensions_json", "{}")), reason=form.get("reason", ""), analyst=actor, confirmation=f"SOCIAL AI FEEDBACK 213 {case_id} SPEICHERN")
            return RedirectResponse(_link("build213", case_id, message=f"AI-Feedback gespeichert: {result['feedback_id']} · kein autonomes Modellupdate."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/opsec")
    async def build213_opsec(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); site_key = form.get("site_key", "")
        try:
            result = ctx.build213.create_platform_opsec(case_id=case_id, site_key=site_key, threat_level=form.get("threat_level", "elevated"), reason=form.get("reason", ""), created_by=actor, confirmation=f"SOCIAL OPSEC 213 {case_id} {site_key} ANLEGEN")
            return RedirectResponse(_link("build213", case_id, message=f"Plattform-OPSEC-Profil {result['threat_level']} angelegt: {result['profile_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build213/preflight")
    async def build213_preflight(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build213.preflight(case_id=case_id, task_id=form.get("task_id", ""), requested=json.loads(form.get("requested_json", "{}")), created_by=actor, confirmation=f"SOCIAL PREFLIGHT 213 {case_id} PRUEFEN")
            return RedirectResponse(_link("build213", case_id, message=f"Social-OPSEC-Preflight: {result['decision']} · {len(result['risks'])} Risiken."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build213", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/document-register")
    async def build214_document_register(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build214.register_document(case_id=case_id, evidence_ref=form.get("evidence_ref", ""), original_name=form.get("original_name", ""), media_type=form.get("media_type", "application/octet-stream"), size_bytes=int(form.get("size_bytes", "0") or 0), content_sha256=form.get("content_sha256", ""), language=form.get("language", "und"), source_kind=form.get("source_kind", "evidence_import"), active_content_state=form.get("active_content_state", "unknown"), created_by=actor, confirmation=f"DOCUMENT 214 {case_id} REGISTRIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"Dokument sicher registriert: {result['document_id']} · keine Ausführung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/extraction")
    async def build214_extraction(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); document_id = form.get("document_id", "")
        try:
            result = ctx.build214.record_extraction(case_id=case_id, document_id=document_id, extractor=form.get("extractor", "manual"), extractor_version=form.get("extractor_version", ""), text_original=form.get("text_original", ""), metadata=json.loads(form.get("metadata_json", "{}")), warnings=[x.strip() for x in re.split(r"[,;\n]", form.get("warnings", "")) if x.strip()], language=form.get("language", "und"), page_count=int(form.get("page_count", "0") or 0), created_by=actor, confirmation=f"DOCUMENT EXTRACTION 214 {document_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Extraktionssnapshot gespeichert: {result['extraction_id']} · reviewpflichtig."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/mentions")
    async def build214_mentions(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); extraction_id = form.get("extraction_id", "")
        try:
            result = ctx.build214.record_mentions(case_id=case_id, extraction_id=extraction_id, mentions=json.loads(form.get("mentions_json", "[]")), created_by=actor, confirmation=f"DOCUMENT MENTIONS 214 {extraction_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"{len(result['mentions'])} Mention-Kandidaten gespeichert; keine automatische Identitätszuordnung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/entity")
    async def build214_entity(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            refs = [x.strip() for x in re.split(r"[,;\n]", form.get("source_refs", "")) if x.strip()]
            result = ctx.build214.create_entity(case_id=case_id, entity_type=form.get("entity_type", "observation"), label=form.get("label", ""), properties=json.loads(form.get("properties_json", "{}")), source_refs=refs, language=form.get("language", "und"), confidence=float(form.get("confidence", ".5") or .5), created_by=actor, confirmation=f"ONTOLOGY ENTITY 214 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Ontologie-Entität angelegt: {result['entity_id']} · Kandidatenstatus."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/relation")
    async def build214_relation(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            refs = [x.strip() for x in re.split(r"[,;\n]", form.get("source_refs", "")) if x.strip()]
            result = ctx.build214.create_relation(case_id=case_id, source_entity_id=form.get("source_entity_id", ""), target_entity_id=form.get("target_entity_id", ""), relation_type=form.get("relation_type", "related_to"), valid_from=form.get("valid_from", ""), valid_to=form.get("valid_to", ""), observed_at=form.get("observed_at", ""), source_refs=refs, confidence=float(form.get("confidence", ".5") or .5), contradiction_status=form.get("contradiction_status", "none"), notes=form.get("notes", ""), created_by=actor, confirmation=f"ONTOLOGY RELATION 214 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Zeitliche Beziehung angelegt: {result['relation_id']} · Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/translate")
    async def build214_translate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); extraction_id = form.get("extraction_id", "")
        try:
            result = ctx.build214.translate_excerpt(case_id=case_id, extraction_id=extraction_id, original_text=form.get("original_text", ""), original_language=form.get("original_language", "und"), target_language=form.get("target_language", "de"), translated_text=form.get("translated_text", ""), engine=form.get("engine", "manual"), engine_version=form.get("engine_version", ""), glossary=json.loads(form.get("glossary_json", "{}")), uncertainties=[x.strip() for x in re.split(r"[,;\n]", form.get("uncertainties", "")) if x.strip()], created_by=actor, confirmation=f"DOCUMENT TRANSLATION 214 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Dokumentübersetzung gespeichert: {result['translation_id']} · Original erhalten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/chat")
    async def build214_chat(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build214.prepare_chat_turn(case_id=case_id, question=form.get("question", ""), question_language=form.get("question_language", "de"), working_language=form.get("working_language", "de"), focus=form.get("focus", "case_synthesis"), created_by=actor, confirmation=f"INVESTIGATION CHAT 214 {case_id} VORBEREITEN")
            return RedirectResponse(_link("build214", case_id, message=f"Konsolidierter Chat-Turn vorbereitet: {result['turn_id']} · keine automatische Ausführung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/chat-complete")
    async def build214_chat_complete(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); turn_id = form.get("turn_id", "")
        try:
            result = ctx.build214.complete_chat_turn(turn_id=turn_id, response=json.loads(form.get("response_json", "{}")), citations=[x.strip() for x in re.split(r"[,;\n]", form.get("citations", "")) if x.strip()], actor=actor, confirmation=f"INVESTIGATION CHAT 214 {turn_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Reviewpflichtige AI-Antwort gespeichert: {result['turn_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/ai-feedback")
    async def build214_ai_feedback(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build214.record_ai_feedback(case_id=case_id, item_type=form.get("item_type", "investigation_chat_turn"), item_id=form.get("item_id", ""), verdict=form.get("verdict", "needs_more_evidence"), dimensions=json.loads(form.get("dimensions_json", "{}")), reason=form.get("reason", ""), analyst=actor, confirmation=f"INVESTIGATION AI FEEDBACK 214 {case_id} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"AI-Feedback gespeichert: {result['feedback_id']} · kein autonomes Modellupdate."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/opsec")
    async def build214_opsec(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build214.create_document_opsec(case_id=case_id, threat_level=form.get("threat_level", "elevated"), document_class=form.get("document_class", "untrusted_public_document"), reason=form.get("reason", ""), created_by=actor, confirmation=f"DOCUMENT OPSEC 214 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Dokument-OPSEC-Profil {result['threat_level']} angelegt: {result['profile_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build214/preflight")
    async def build214_preflight(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build214.preflight_document(case_id=case_id, document_id=form.get("document_id", ""), requested=json.loads(form.get("requested_json", "{}")), created_by=actor, confirmation=f"DOCUMENT PREFLIGHT 214 {case_id} PRUEFEN")
            return RedirectResponse(_link("build214", case_id, message=f"Dokument-Preflight: {result['decision']} · {len(result['risks'])} Risiken."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)


    @app.post("/build215/models-refresh")
    async def build215_models_refresh(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build215.refresh_models(case_id=case_id, actor=actor, confirmation=f"OLLAMA MODELS 215 {case_id} AKTUALISIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"Ollama lokal geprüft: {len(result['models'])} Modell(e), ausgewählt: {result['selected_model']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build215/model-select")
    async def build215_model_select(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build215.select_model(case_id=case_id, model_name=form.get("model_name", ""), context_window=int(form.get("context_window", "8192") or 8192), temperature=float(form.get("temperature", ".15") or .15), actor=actor, confirmation=f"OLLAMA MODEL 215 {case_id} AUSWAEHLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Lokales Fallmodell aktiviert: {result['selected_model']} · Kontext {result['context_window']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build215/chat-run")
    async def build215_chat_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); turn_id = form.get("turn_id", "")
        try:
            result = ctx.build215.execute_chat_turn(turn_id=turn_id, actor=actor, confirmation=f"LOCAL AI CHAT 215 {turn_id} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Lokaler AI-Ermittler abgeschlossen: {result['ollama_run_id']} · Antwort bleibt reviewpflichtig."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build215/translate-run")
    async def build215_translate_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build215.translate_extraction(case_id=case_id, extraction_id=form.get("extraction_id", ""), original_text=form.get("original_text", ""), original_language=form.get("original_language", "und"), target_language=form.get("target_language", "de"), glossary=json.loads(form.get("glossary_json", "{}")), actor=actor, confirmation=f"LOCAL AI TRANSLATION 215 {case_id} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Lokale AI-Übersetzung gespeichert: {result['translation_id']} · Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/session-create")
    async def build216_session_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build216.create_session(case_id=case_id, title=form.get("title", ""), working_language=form.get("working_language", "de"), created_by=actor, confirmation=f"CHAT SESSION 216 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Ermittlungsdialog angelegt: {result['session_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/message-send")
    async def build216_message_send(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build216.send_message(session_id=session_id, message=form.get("message", ""), message_language=form.get("message_language", "de"), actor=actor, confirmation=f"CHAT 216 {session_id} SENDEN")
            return RedirectResponse(_link("build214", case_id, message=f"AI-Ermittler antwortete quellenbezogen: {result['assistant_message_id']} · Grounding {result['source_grounding_score']:.2f}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/source-index")
    async def build216_source_index(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build216.index_case_sources(case_id=case_id, actor=actor)
            return RedirectResponse(_link("build214", case_id, message=f"Fallquellen indexiert: {result['indexed_chunks']} Chunks."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/embedding-refresh")
    async def build216_embedding_refresh(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build216.refresh_embedding_models(case_id=case_id, actor=actor, confirmation=f"EMBEDDING MODELS 216 {case_id} AKTUALISIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"Lokale Embedding-Modelle erkannt: {len(result['models'])}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/embedding-select")
    async def build216_embedding_select(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build216.select_embedding_model(session_id=session_id, model_name=form.get("model_name", ""), actor=actor, confirmation=f"EMBEDDING MODEL 216 {session_id} AUSWAEHLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Embedding-Modell gewählt: {result['embedding_model']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/embed-sources")
    async def build216_embed_sources(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build216.embed_case_sources(session_id=session_id, actor=actor, confirmation=f"SOURCE EMBEDDINGS 216 {session_id} ERZEUGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Fallquellen lokal eingebettet: {result['embedded_chunks']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build216/training-from-chat")
    async def build216_training_from_chat(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build216.create_training_example_from_chat(assistant_message_id=form.get("assistant_message_id", ""), corrected_output=None, label=form.get("label", ""), rationale=form.get("rationale", ""), created_by=actor, confirmation=f"TRAINING EXAMPLE 216 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Trainingsentwurf angelegt: {result['example_id']} · unabhängiger Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build217/plan-create")
    async def build217_plan_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build217.create_plan(session_id=session_id, objective=form.get("objective", ""), question_language=form.get("question_language", "de"), actor=actor, confirmation=f"INVESTIGATION PLAN 217 {session_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Ermittlungsplan erstellt: {result['plan_id']} · {len(result['source_recommendations'])} Quellenrouten · Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build217/plan-review")
    async def build217_plan_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); plan_id = form.get("plan_id", "")
        try:
            decisions = json.loads(form.get("route_decisions_json", "{}") or "{}")
            result = ctx.build217.review_plan(plan_id=plan_id, plan_decision=form.get("plan_decision", "changes_requested"), route_decisions=decisions, reviewer=actor, rationale=form.get("rationale", ""), confirmation=f"INVESTIGATION PLAN REVIEW 217 {plan_id} ABSCHLIESSEN")
            return RedirectResponse(_link("build214", case_id, message=f"Planreview abgeschlossen: {result['status']} · {result['approved_routes']} Routen freigegeben · Trainingsentwurf {result['training_example_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build217/routes-materialize")
    async def build217_routes_materialize(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); plan_id = form.get("plan_id", "")
        try:
            result = ctx.build217.materialize_approved_routes(plan_id=plan_id, actor=actor, confirmation=f"SOURCE ROUTES 217 {plan_id} VORBEREITEN")
            return RedirectResponse(_link("build214", case_id, message=f"Freigegebene Quellenrouten vorbereitet: {len(result['requests'])}. Keine automatische Netzwerkausführung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)


    @app.post("/build218/tools-detect")
    async def build218_tools_detect(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build218.detect_local_tools(actor=actor, confirmation="DIGITAL SOURCE TOOLS 218 ERKENNEN")
            return RedirectResponse(_link("build214", case_id, message=f"Lokale Quellenwerkzeuge geprüft: {len(result['tools'])}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build218/run")
    async def build218_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            result = ctx.build218.run_adapter(case_id=case_id, adapter_key=adapter_key, target_type=form.get("target_type", "username"), target_value=form.get("target_value", ""), purpose=form.get("purpose", ""), actor=actor, confirmation=f"DIGITAL SOURCE 218 {case_id} {adapter_key} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Quellenlauf {result['run_id']}: {result['status']} · {result['result_count']} Kandidaten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build218/request-execute")
    async def build218_request_execute(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); request_id = form.get("request_id", "")
        try:
            keys = [x.strip() for x in form.get("adapter_keys", "").split(",") if x.strip()]
            result = ctx.build218.execute_request(request_id=request_id, adapter_keys=keys, actor=actor, confirmation=f"DIGITAL SOURCE REQUEST 218 {request_id} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Ausführungsauftrag {request_id}: {len(result['runs'])} Adapterläufe."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build218/result-review")
    async def build218_result_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); result_id = form.get("result_id", "")
        try:
            result = ctx.build218.review_result(result_id=result_id, decision=form.get("decision", "needs_more_evidence"), reason=form.get("reason", ""), reviewer=actor, confirmation=f"DIGITAL SOURCE RESULT 218 {result_id} PRUEFEN")
            return RedirectResponse(_link("build214", case_id, message=f"Kandidat geprüft; Trainingsentwurf {result['training_example_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)




    @app.post("/build225/index-refresh")
    async def build225_index_refresh(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build225.refresh_indexes(case_id=case_id, actor=actor)
            return RedirectResponse(_link("build214", case_id, message=f"Retrievalindex: {result['claims']} Claims, {result['lineage_nodes']} Herkunftsknoten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build225/claim-create")
    async def build225_claim_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build225.create_claim(case_id=case_id, subject_ref=form.get("subject_ref", ""), predicate=form.get("predicate", ""), canonical_text=form.get("canonical_text", ""), normalized_value={"text": form.get("canonical_text", "")}, language=form.get("language", "de"), claim_kind=form.get("claim_kind", "hypothesis"), confidence=float(form.get("confidence", "0.5") or 0.5), created_by=actor, confirmation=f"CLAIM 225 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Claim {result['claim_id']} als Kandidat angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build225/retrieve")
    async def build225_retrieve(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build225.retrieve(case_id=case_id, session_id=form.get("session_id", ""), query_text=form.get("query_text", ""), query_language=form.get("query_language", "de"), target_claim_id=form.get("target_claim_id", ""), limit=12)
            return RedirectResponse(_link("build214", case_id, message=f"Retrieval {result['retrieval_run_id']}: {result['selected_count']} Quellen, Gegenbeleg={result['counterevidence_included']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build225/review")
    async def build225_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); run_id = form.get("retrieval_run_id", "")
        split = lambda name: [x.strip() for x in form.get(name, "").split(",") if x.strip()]
        try:
            result = ctx.build225.review_retrieval(retrieval_run_id=run_id, decision=form.get("decision", "useful"), correct_refs=split("correct_refs"), missing_refs=split("missing_refs"), wrongly_ranked_refs=split("wrongly_ranked_refs"), rationale=form.get("rationale", ""), reviewer=actor, confirmation=f"RETRIEVAL REVIEW 225 {run_id} FREIGEBEN")
            return RedirectResponse(_link("build214", case_id, message=f"Retrievalreview gespeichert; Trainingsentwurf {result['training_example_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build226/rank")
    async def build226_rank(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            countries = [x.strip() for x in form.get("countries", "").split(",") if x.strip()]
            result = ctx.build226.rank_sources(case_id=case_id, session_id=form.get("session_id", ""), objective=form.get("objective", ""), target_type=form.get("target_type", "unknown"), target_value=form.get("target_value", ""), language=form.get("language", "und"), countries=countries, budget_class=form.get("budget_class", "standard"), max_sources=int(form.get("max_sources", "5") or 5), require_independence=True, actor=actor, confirmation=f"SOURCE INTELLIGENCE 226 {case_id} BERECHNEN")
            return RedirectResponse(_link("build214", case_id, message=f"Source Intelligence {result['query_id']}: {', '.join(result['selected_sources']) or 'keine freigegebene Quelle'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build226/review")
    async def build226_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); query_id = form.get("query_id", "")
        try:
            decisions = json.loads(form.get("source_decisions_json", "{}") or "{}")
            result = ctx.build226.review_ranking(query_id=query_id, decision=form.get("decision", "approved"), source_decisions=decisions, rationale=form.get("rationale", ""), reviewer=actor, confirmation=f"SOURCE INTELLIGENCE REVIEW 226 {query_id} ABSCHLIESSEN")
            return RedirectResponse(_link("build214", case_id, message=f"Source-Review gespeichert; Trainingsentwurf {result['training_example_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build227/configure")
    async def build227_configure(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build227.configure_state(session_id=session_id, investigation_goal=form.get("investigation_goal", ""), working_language=form.get("working_language", "de"), actor=actor, confirmation=f"CONVERSATIONAL INVESTIGATOR 227 {session_id} KONFIGURIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"Conversational Investigator für {result['session_id']} konfiguriert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build227/thread-create")
    async def build227_thread_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build227.create_thread(session_id=session_id, title=form.get("title", ""), objective=form.get("objective", ""), priority=int(form.get("priority", "50") or 50), actor=actor, confirmation=f"INVESTIGATION THREAD 227 {session_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Ermittlungsstrang {result['thread_id']} angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build281/mission")
    async def build281_mission(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build281.create_mission(case_id=case_id,objective=form.get("objective",""),mission_type=form.get("mission_type","hybrid_osint"),actor=request_actor(request))
            return RedirectResponse(_link("phase12_281",case_id,message=f"Phase-12-Mission {result['mission_id']} geplant; vor Autonomie ist OK erforderlich."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_281",case_id,error=str(exc)),status_code=303)

    @app.post("/build281/approve")
    async def build281_approve(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build281.approve_mission(mission_id=form.get("mission_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_281",case_id,message=f"Mission {result['mission_id']} freigegeben: bounded autonomy aktiv."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_281",case_id,error=str(exc)),status_code=303)

    @app.post("/build282/queue")
    async def build282_queue(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build282.queue_mission_cycle(mission_id=form.get("mission_id",""),requested_by=request_actor(request),execute_public_web=False)
            return RedirectResponse(_link("phase12_282",case_id,message=f"Job {result['job_id']} persistent eingereiht."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_282",case_id,error=str(exc)),status_code=303)

    @app.post("/build282/run-next")
    async def build282_run_next(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build282.run_next_job(worker_id="ai-worker-282")
            return RedirectResponse(_link("phase12_282",case_id,message=f"Queue-Ausführung: {result.get('status')} · {result.get('job_id','')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_282",case_id,error=str(exc)),status_code=303)

    @app.post("/build282/pause")
    async def build282_pause(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build282.pause_for_recovery(mission_id=form.get("mission_id",""),actor=request_actor(request),reason="lead investigator pause")
            return RedirectResponse(_link("phase12_282",case_id,message=f"Mission pausiert; Checkpoint {result['checkpoint']['checkpoint_id']}; neues OK erforderlich."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_282",case_id,error=str(exc)),status_code=303)

    @app.post("/build282/resume")
    async def build282_resume(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build282.resume_mission(mission_id=form.get("mission_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_282",case_id,message=f"Mission {result['mission_id']} mit neuem OK fortgesetzt."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_282",case_id,error=str(exc)),status_code=303)

    @app.post("/build282/recover")
    async def build282_recover(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build282.recover_stale_jobs(actor=request_actor(request))
            return RedirectResponse(_link("phase12_282",case_id,message=f"Recovery geprüft: {result['count']} stale Job(s) verarbeitet."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_282",case_id,error=str(exc)),status_code=303)

    @app.post("/build283/queue")
    async def build283_queue(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build283.queue_mission_cycle_once(mission_id=form.get("mission_id",""),requested_by=request_actor(request),execute_public_web=False)
            msg=(f"Job {result['job_id']} bereits vorhanden (idempotent)." if result.get('deduplicated') else f"Job {result['job_id']} idempotent eingereiht.")
            return RedirectResponse(_link("phase12_283",case_id,message=msg),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_283",case_id,error=str(exc)),status_code=303)

    @app.post("/build283/run-next")
    async def build283_run_next(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build283.run_next_job(worker_id="ai-worker-283")
            return RedirectResponse(_link("phase12_283",case_id,message=f"Sichere Queue-Ausführung: {result.get('status')} · {result.get('job_id','')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_283",case_id,error=str(exc)),status_code=303)

    @app.post("/build283/reconcile")
    async def build283_reconcile(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build283.reconcile_mission_state(mission_id=form.get("mission_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_283",case_id,message=f"Mission-Reconciliation: {result['status']} · {result['reconciliation_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_283",case_id,error=str(exc)),status_code=303)

    @app.post("/build283/resume-safe")
    async def build283_resume_safe(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build283.resume_mission_safe(mission_id=form.get("mission_id",""),confirmation=form.get("confirmation",""),resume_token=form.get("resume_token",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_283",case_id,message=f"Safe Resume autorisiert · Attestation {result['attestation']['attestation_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_283",case_id,error=str(exc)),status_code=303)

    @app.post("/build283/heartbeat")
    async def build283_heartbeat(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build283.heartbeat_worker(worker_id="ai-worker-283",worker_state="ready",actor=request_actor(request))
            return RedirectResponse(_link("phase12_283",case_id,message=f"Worker-Heartbeat: {result['worker_id']} · {result['worker_state']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_283",case_id,error=str(exc)),status_code=303)

    @app.post("/build284/preflight")
    async def build284_preflight(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build284.create_preflight_attestation(mission_id=form.get("mission_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_284",case_id,message=f"Preflight intakt · {result['attestation_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_284",case_id,error=str(exc)),status_code=303)

    @app.post("/build284/queue")
    async def build284_queue(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build284.queue_guarded_cycle(mission_id=form.get("mission_id",""),requested_by=request_actor(request))
            return RedirectResponse(_link("phase12_284",case_id,message=f"Guarded Job {result['job_id']} · Preflight {result['preflight']['attestation_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_284",case_id,error=str(exc)),status_code=303)

    @app.post("/build284/run-next")
    async def build284_run_next(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build284.run_next_guarded(worker_id="ai-worker-284")
            return RedirectResponse(_link("phase12_284",case_id,message=f"Guarded Run: {result.get('status')} · {result.get('job_id','')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_284",case_id,error=str(exc)),status_code=303)

    @app.post("/build284/replay")
    async def build284_replay(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            manifest=ctx.build284.create_replay_manifest(mission_id=form.get("mission_id",""),actor=request_actor(request))
            result=ctx.build284.execute_local_replay(replay_id=manifest['replay_id'],actor=request_actor(request))
            return RedirectResponse(_link("phase12_284",case_id,message=f"Local Replay deterministic={result['deterministic_match']} · {result['replay_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_284",case_id,error=str(exc)),status_code=303)

    @app.post("/build284/circuit-close")
    async def build284_circuit_close(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            result=ctx.build284.close_circuit(mission_id=form.get("mission_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_284",case_id,message=f"Mission Circuit: {result.get('state','closed')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_284",case_id,error=str(exc)),status_code=303)

    @app.post("/build285/mode")
    async def build285_mode(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build285.set_operator_mode(actor=request_actor(request),experience_mode=form.get("experience_mode","novice"))
            return RedirectResponse(_link("phase12_285",case_id,message=f"Ansicht: {result['experience_mode']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_285",case_id,error=str(exc)),status_code=303)

    @app.post("/build285/request")
    async def build285_request(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build285.plan_collection_request(mission_id=form.get("mission_id",""),source_locator=form.get("source_locator",""),collection_scope=form.get("collection_scope","darkweb_text"),requested_by=request_actor(request))
            return RedirectResponse(_link("phase12_285",case_id,message=f"Collection-Auftrag geplant: {result['request_id']} · wartet auf OK"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_285",case_id,error=str(exc)),status_code=303)

    @app.post("/build285/approve")
    async def build285_approve(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build285.approve_collection_request(request_id=form.get("request_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_285",case_id,message=f"Collection-Auftrag freigegeben: {result['request_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_285",case_id,error=str(exc)),status_code=303)

    @app.post("/build285/envelope")
    async def build285_envelope(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build285.create_transport_envelope(request_id=form.get("request_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_285",case_id,message=f"Transportvertrag erzeugt: {result['envelope_id']} · Live-Transport bleibt aus"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_285",case_id,error=str(exc)),status_code=303)

    @app.post("/build285/capture")
    async def build285_capture(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build285.stage_text_capture(request_id=form.get("request_id",""),observed_text=form.get("observed_text",""),content_type=form.get("content_type","text/plain"),actor=request_actor(request))
            return RedirectResponse(_link("phase12_285",case_id,message=f"Textbeleg aufgenommen: {result['result_id']} · Human Review erforderlich"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_285",case_id,error=str(exc)),status_code=303)


    @app.post("/build286/dispatch")
    async def build286_dispatch(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build286.dispatch_authorized_request(request_id=form.get("request_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_286",case_id,message=f"Gateway-Auftrag: {result['job_id']} · App-Netzwerk bleibt aus"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_286",case_id,error=str(exc)),status_code=303)

    @app.post("/build286/receipt")
    async def build286_receipt(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            receipt=ctx.build286.build_synthetic_receipt(job_id=form.get("job_id",""),observed_text=form.get("observed_text",""),content_type=form.get("content_type","text/plain"))
            result=ctx.build286.ingest_gateway_receipt(receipt=receipt,actor=request_actor(request))
            return RedirectResponse(_link("phase12_286",case_id,message=f"Gateway-Receipt aufgenommen: {result['receipt_id']} · Human Review erforderlich"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_286",case_id,error=str(exc)),status_code=303)


    @app.post("/build287/stage")
    async def build287_stage(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build287.stage_adapter_capture(job_id=form.get("job_id",""),observed_text=form.get("observed_text",""),content_type=form.get("content_type","text/plain"),actor=request_actor(request))
            return RedirectResponse(_link("phase12_287",case_id,message=f"Capture-Eingang bereit: {result['run_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_287",case_id,error=str(exc)),status_code=303)

    @app.post("/build287/process")
    async def build287_process(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build287.process_staged_capture(run_id=form.get("run_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_288",case_id,message=f"Capture verarbeitet: {result.get('state')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_287",case_id,error=str(exc)),status_code=303)

    @app.post("/build288/snapshot")
    async def build288_snapshot(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build288.create_snapshot(receipt_id=form.get("receipt_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_288",case_id,message=f"Snapshot: {result['snapshot_id']} · Review erforderlich"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_288",case_id,error=str(exc)),status_code=303)

    @app.post("/build288/replay")
    async def build288_replay(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build288.replay_snapshot(snapshot_id=form.get("snapshot_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_288",case_id,message=f"Offline-Replay deterministisch={result['deterministic']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_288",case_id,error=str(exc)),status_code=303)


    @app.post("/build289/assess")
    async def build289_assess(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build289.assess_case(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("phase12_289",case_id,message=f"AI-Strukturprüfung: {len(result['gaps'])} priorisierte Punkte"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_289",case_id,error=str(exc)),status_code=303)

    @app.post("/build289/propose-wave")
    async def build289_propose_wave(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build289.propose_research_wave(assessment_id=form.get("assessment_id",""),max_tasks=6,external_collection_budget=2,actor=request_actor(request))
            return RedirectResponse(_link("phase12_289",case_id,message=f"Recherchewelle vorgeschlagen: {result['wave_id']} · OK erforderlich"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_289",case_id,error=str(exc)),status_code=303)

    @app.post("/build289/approve-wave")
    async def build289_approve_wave(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build289.approve_research_wave(wave_id=form.get("wave_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_289",case_id,message=f"Recherchewelle freigegeben: {result['wave_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_289",case_id,error=str(exc)),status_code=303)

    @app.post("/build289/run-local")
    async def build289_run_local(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build289.run_approved_local_cycle(wave_id=form.get("wave_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_289",case_id,message=f"Lokaler AI-Zyklus: {result['local_tasks_processed']} lokal · {result['external_tasks_deferred']} extern zurückgestellt"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_289",case_id,error=str(exc)),status_code=303)

    @app.post("/build290/plan")
    async def build290_plan(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build290.create_discriminating_plan(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("phase12_290",case_id,message=f"Diskriminierender Evidenzplan: {len(result['discriminators'])} Fragen priorisiert"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_290",case_id,error=str(exc)),status_code=303)

    @app.post("/build290/approve")
    async def build290_approve(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build290.approve_plan(plan_id=form.get("plan_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_290",case_id,message=f"Evidenzplan freigegeben: {result['plan_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_290",case_id,error=str(exc)),status_code=303)

    @app.post("/build290/run-local")
    async def build290_run_local(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build290.run_approved_local_analysis(plan_id=form.get("plan_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_290",case_id,message=f"Lokale Vergleichsanalyse: {result['local_tasks_processed']} lokal · {result['external_tasks_deferred']} extern zurückgestellt"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_290",case_id,error=str(exc)),status_code=303)

    @app.post("/build291/round")
    async def build291_round(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build291.create_adaptive_round(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("phase12_291",case_id,message=f"Adaptive Runde {result['round_no']} erstellt: {len(result['adaptive_ranking'])} Fragen neu gewichtet"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_291",case_id,error=str(exc)),status_code=303)

    @app.post("/build291/approve")
    async def build291_approve(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build291.approve_round(round_id=form.get("round_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_291",case_id,message=f"Adaptive Runde freigegeben: {result['round_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_291",case_id,error=str(exc)),status_code=303)

    @app.post("/build291/run")
    async def build291_run(request: Request):
        form = await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build291.run_approved_adaptive_cycle(round_id=form.get("round_id",""),actor=request_actor(request))
            changed=result['result']['reprioritization']['changed_positions']
            return RedirectResponse(_link("phase12_291",case_id,message=f"Adaptiver AI-Zyklus: {result['local_tasks_processed']} lokal · {result['external_tasks_deferred']} extern zurückgestellt · {changed} Prioritäten geändert"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_291",case_id,error=str(exc)),status_code=303)


    @app.post("/build292/fusion")
    async def build292_fusion(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build292.create_fusion(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("phase12_292",case_id,message=f"Cross-Surface-Fusion erstellt: {len(result['surfaces'])} Oberflächen · Confidence {result['confidence_score']:.2f}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_292",case_id,error=str(exc)),status_code=303)

    @app.post("/build292/checkpoint/approve")
    async def build292_checkpoint_approve(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build292.approve_checkpoint(checkpoint_id=form.get("checkpoint_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_292",case_id,message=f"Checkpoint freigegeben: {result['checkpoint_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_292",case_id,error=str(exc)),status_code=303)

    @app.post("/build292/checkpoint/advance")
    async def build292_checkpoint_advance(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build292.advance_checkpoint(checkpoint_id=form.get("checkpoint_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase12_292",case_id,message=f"Checkpoint weitergeführt: Stufe {result.get('stage_no',3)} · {result.get('stage','investigator_decision')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_292",case_id,error=str(exc)),status_code=303)

    @app.post("/build293/enqueue")
    async def build293_enqueue(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build293.enqueue_work(case_id=case_id,mission_id=form.get("mission_id",""),work_kind=form.get("work_kind","observability_snapshot"),requested_by=request_actor(request))
            return RedirectResponse(_link("phase12_293",case_id,message=f"Operational-Job eingereiht: {result['op_job_id']} · {result['status']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_293",case_id,error=str(exc)),status_code=303)

    @app.post("/build293/run-next")
    async def build293_run_next(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build293.run_next_job(worker_id="ui-worker-293")
            return RedirectResponse(_link("phase12_293",case_id,message=f"Operational Worker: {result.get('status','idle')} · {result.get('op_job_id','kein Job')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_293",case_id,error=str(exc)),status_code=303)

    @app.post("/build293/recovery/approve")
    async def build293_recovery_approve(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build293.approve_recovery(job_id=form.get("op_job_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_293",case_id,message=f"Recovery freigegeben: {result['op_job_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_293",case_id,error=str(exc)),status_code=303)

    @app.post("/build294/run-next")
    async def build294_run_next(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build294.run_next_fair_job(worker_id="ui-worker-294")
            return RedirectResponse(_link("phase12_294",case_id,message=f"Fair Scheduler: {result.get('status','idle')} · {result.get('op_job_id','kein Job')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_294",case_id,error=str(exc)),status_code=303)

    @app.post("/build294/isolation/clear")
    async def build294_isolation_clear(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            result=ctx.build294.clear_isolation(case_id=case_id,confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_294",case_id,message=f"Fault-Isolation: {result['fault_state']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_294",case_id,error=str(exc)),status_code=303)

    @app.post("/build295/backup/create")
    async def build295_backup_create(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build295.create_backup(actor=request_actor(request))
            return RedirectResponse(_link("phase12_295",case_id,message=f"Backup verifiziert: {result['backup_id']} · SQLite {result['sqlite_quick_check']} · FK {result['foreign_key_violations']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_295",case_id,error=str(exc)),status_code=303)

    @app.post("/build295/anchor/create")
    async def build295_anchor_create(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build295.create_continuity_anchor(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("phase12_295",case_id,message=f"Continuity-Anchor erstellt: {result['anchor_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_295",case_id,error=str(exc)),status_code=303)

    @app.post("/build295/reconcile")
    async def build295_reconcile(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            row=ctx.db.one('SELECT anchor_id FROM phase12_continuity_anchors_295 WHERE scope=? AND case_id=? ORDER BY rowid DESC LIMIT 1',('case' if case_id else 'system',case_id))
            if not row: raise ValueError('Kein Continuity-Anchor vorhanden.')
            result=ctx.build295.reconcile_after_restart(anchor_id=row['anchor_id'],actor=request_actor(request))
            return RedirectResponse(_link("phase12_295",case_id,message=f"Restart-Reconciliation: {result['running_jobs_moved_to_recovery']} In-Flight-Jobs in Recovery · Continuity={result['continuity_ok']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_295",case_id,error=str(exc)),status_code=303)

    @app.post("/build295/restore/prepare")
    async def build295_restore_prepare(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build295.prepare_restore(backup_id=form.get("backup_id",""),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_295",case_id,message=f"Offline-Restore vorbereitet: {result['restore_plan_id']} · aktive DB unverändert"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_295",case_id,error=str(exc)),status_code=303)

    @app.post("/build296/drill/run")
    async def build296_drill_run(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build296.run_recovery_drill(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("phase12_296",case_id,message=f"Recovery-Drill {result['result']}: RTO {result['measured_rto_seconds']:.3f}s · RPO {result['rpo_seconds']}s"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_296",case_id,error=str(exc)),status_code=303)

    @app.post("/build296/rotation/plan")
    async def build296_rotation_plan(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build296.create_rotation_plan(retain_count=int(form.get("retain_count","3") or 3),confirmation=form.get("confirmation",""),approved_by=request_actor(request))
            return RedirectResponse(_link("phase12_296",case_id,message=f"Rotationsempfehlung: {len(result['retained'])} behalten · {len(result['retirement_candidates'])} Kandidaten · automatische Löschung AUS"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_296",case_id,error=str(exc)),status_code=303)

    @app.post("/build297/field-suite/run")
    async def build297_field_suite_run(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build297.run_field_suite(actor=request_actor(request))
            return RedirectResponse(_link("phase12_297",case_id,message=f"Field Qualification {result['result']}: {result['passed_count']}/{result['scenario_count']} Szenarien · interne Qualifikation, keine Produktionszertifizierung"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_297",case_id,error=str(exc)),status_code=303)




    @app.post("/build307/autonomous-research")
    async def build307_autonomous_research(request: Request):
        require_auth(request)
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id",""); actor=request_actor(request); target_id=form.get("target_id","")
        try:
            seeds=[x.strip() for x in str(form.get("seed_urls","")).splitlines() if x.strip()]
            auth=ctx.build307.authorize_autonomous_research(case_id=case_id,target_id=target_id,purpose=form.get("purpose",""),confirmation=form.get("confirmation",""),approved_by=actor,provider=form.get("provider","auto"),max_queries=int(form.get("max_queries","6") or 6),max_results_per_query=int(form.get("max_results","6") or 6),max_pages=int(form.get("max_pages","8") or 8),max_depth=int(form.get("max_depth","1") or 1),max_total_bytes=int(form.get("max_total_bytes","3000000") or 3000000),seed_urls=seeds)
            result=await asyncio.to_thread(ctx.build307.execute_autonomous_research,auth["run_id"],actor=actor)
            return RedirectResponse(_link("investigation302",case_id,message=f"Autonome AI-Recherche abgeschlossen: {result['query_count']} Queries · {result['search_result_count']} Suchtreffer · {result['fetched_count']} Seiten/Dokumente · {result['intake_count']} candidate Intakes · {result['blocked_count']} OPSEC-blockiert."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061",case_id,target_id=target_id,error=str(exc)),status_code=303)

    @app.post("/build307/security-selftest")
    async def build307_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build307.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build307/dossier")
    async def build307_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build307.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build307/dossier/download")
    async def build307_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build307.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build308/crawl")
    async def build308_crawl(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        try:
            seeds=[x.strip() for x in str(form.get("seed_urls","")).splitlines() if x.strip()]
            auth=ctx.build308.authorize_crawl(case_id=case_id,target_id=str(form.get("target_id","")),purpose=str(form.get("purpose","")),confirmation=str(form.get("confirmation","")),approved_by=actor,provider=str(form.get("provider","auto")),seed_urls=seeds,max_queries=int(form.get("max_queries","6") or 6),max_results_per_query=int(form.get("max_results","6") or 6),max_pages=int(form.get("max_pages","12") or 12),max_depth=int(form.get("max_depth","2") or 2),max_total_bytes=int(form.get("max_total_bytes","4000000") or 4000000),max_frontier=int(form.get("max_frontier","250") or 250))
            result=await asyncio.to_thread(ctx.build308.execute_crawl,auth["authorization_id"],actor=actor)
            return _post_result(request,case_id=case_id,result=result,tab="investigation302")
        except Exception as exc:
            return _post_result(request,case_id=case_id,result={"error":str(exc),"build":"308.0","fail_closed":True},tab="investigation302")

    @app.post("/build308/security-selftest")
    async def build308_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build308.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build308/dossier")
    async def build308_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build308.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build308/dossier/download")
    async def build308_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build308.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)


    @app.post("/build309/query-plan")
    async def build309_query_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        try:
            result=ctx.build311.generate_query_plan(case_id=case_id,target_id=str(form.get("target_id","")),purpose=str(form.get("purpose","")),max_queries=int(form.get("max_queries","24") or 24),actor=actor)
            return _post_result(request,case_id=case_id,result=result,tab="investigation302")
        except Exception as exc:
            return _post_result(request,case_id=case_id,result={"error":str(exc),"build":"309.0","fail_closed":True},tab="investigation302")

    @app.post("/build309/crawl")
    async def build309_crawl(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        try:
            seeds=[x.strip() for x in str(form.get("seed_urls","")).splitlines() if x.strip()]
            auth=ctx.build311.authorize_crawl(case_id=case_id,target_id=str(form.get("target_id","")),purpose=str(form.get("purpose","")),confirmation=str(form.get("confirmation","")),approved_by=actor,provider=str(form.get("provider","auto")),seed_urls=seeds,max_queries=int(form.get("max_queries","6") or 6),max_results_per_query=int(form.get("max_results","6") or 6),max_pages=int(form.get("max_pages","12") or 12),max_depth=int(form.get("max_depth","2") or 2),max_total_bytes=int(form.get("max_total_bytes","4000000") or 4000000),max_frontier=int(form.get("max_frontier","250") or 250))
            result=await asyncio.to_thread(ctx.build311.execute_crawl,auth["authorization_id"],actor=actor)
            result=dict(result); result["query_plan_id"]=auth.get("query_plan_id"); result["query_count_309"]=auth.get("query_count_309")
            return _post_result(request,case_id=case_id,result=result,tab="investigation302")
        except Exception as exc:
            return _post_result(request,case_id=case_id,result={"error":str(exc),"build":"309.0","fail_closed":True},tab="investigation302")

    @app.post("/build309/security-selftest")
    async def build309_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build311.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build309/dossier")
    async def build309_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build311.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")


    @app.post("/build310/security-selftest")
    async def build310_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build311.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.get("/build309/dossier/download")
    async def build309_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build309.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)





    @app.post("/build315/resolve")
    async def build315_resolve(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build315.create_resolution_run(case_id=case_id,target_id=str(form.get("target_id","")),hypothesis_type=str(form.get("hypothesis_type","identity")),hypothesis_text=str(form.get("hypothesis_text","")),actor=actor)
        built=ctx.build315.build_resolution_signals(result["resolution_id"])
        assessed=ctx.build315.assess_resolution(result["resolution_id"])
        return _post_result(request,case_id=case_id,result={**result,"signals":built,"assessment":assessed},tab="investigation302")

    @app.post("/build315/security-selftest")
    async def build315_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build315.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build315/dossier")
    async def build315_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build315.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build315/dossier/download")
    async def build315_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build315.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)





    @app.post("/build320/deep-qualification")
    async def build320_deep_qualification(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build320.run_phase13_deep_qualification(case_id=case_id,target_id=str(form.get("target_id","")),actor=actor)
        if result.get("result")=="pass": result["freeze"]=ctx.build320.freeze_phase13(qualification_id=result["qualification_id"],actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build320/security-selftest")
    async def build320_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build320.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build319/field-qualification")
    async def build319_field_qualification(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build319.run_extreme_field_qualification(case_id=case_id,target_id=str(form.get("target_id","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build319/security-selftest")
    async def build319_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build319.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")
    @app.post("/build318/unified-run")
    async def build318_unified_run(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build318.start_unified_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),authorization_phrase=str(form.get("authorization_phrase","")),max_actions=int(form.get("max_actions",5) or 5),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build318/security-selftest")
    async def build318_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build318.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")
    @app.post("/build317/query-plan")
    async def build317_query_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build317.create_query_plan(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build317/security-selftest")
    async def build317_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build317.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build316/fabric")
    async def build316_fabric(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        snap=ctx.build316.create_fabric_snapshot(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),actor=actor)
        built=ctx.build316.materialize_fabric(snap["snapshot_id"]); assessed=ctx.build316.assess_fabric(snap["snapshot_id"])
        return _post_result(request,case_id=case_id,result={"snapshot":snap,"materialized":built,"assessment":assessed},tab="investigation302")

    @app.post("/build316/security-selftest")
    async def build316_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build316.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build316/dossier")
    async def build316_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build316.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build316/dossier/download")
    async def build316_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build316.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build314/govlegal-plan")
    async def build314_govlegal_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        jurisdictions=[x.strip() for x in str(form.get("jurisdictions","")).split(",") if x.strip()]
        result=ctx.build314.create_govlegal_plan(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),jurisdictions=jurisdictions,actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build314/recon-lab")
    async def build314_recon_lab(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build314.create_recon_lab_simulation(case_id=case_id,target_id=str(form.get("target_id","")),scope=str(form.get("scope","")),confirmation=str(form.get("confirmation","")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build314/security-selftest")
    async def build314_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build314.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build314/dossier")
    async def build314_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build314.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build314/dossier/download")
    async def build314_dossier_download(request: Request):
        ctx.auth.require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build314.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build313/technical-plan")
    async def build313_technical_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        anchors=[x.strip() for x in str(form.get("anchors","")).split(",") if x.strip()]
        result=ctx.build313.create_technical_plan(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),anchors=anchors,actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation302")

    @app.post("/build313/security-selftest")
    async def build313_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build313.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build313/dossier")
    async def build313_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build313.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build313/dossier/download")
    async def build313_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build313.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)
    @app.post("/build312/record-plan")
    async def build312_record_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        try:
            countries=[x.strip() for x in str(form.get("countries","")).replace(";",",").split(",") if x.strip()]
            languages=[x.strip() for x in str(form.get("languages","de,en")).replace(";",",").split(",") if x.strip()]
            result=ctx.build312.create_record_plan(case_id=case_id,target_id=str(form.get("target_id","")),record_kind=str(form.get("record_kind","person")),objective=str(form.get("objective","")),countries=countries,languages=languages,actor=actor)
            return _post_result(request,case_id=case_id,result=result,tab="investigation302")
        except Exception as ex:
            return _post_result(request,case_id=case_id,result={"error":str(ex)},tab="investigation302")

    @app.post("/build312/security-selftest")
    async def build312_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build312.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build312/dossier")
    async def build312_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build312.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build312/dossier/download")
    async def build312_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build312.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build311/broker-plan")
    async def build311_broker_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        try:
            result=ctx.build311.create_broker_plan(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),actor=actor)
            return _post_result(request,case_id=case_id,result=result,tab="investigation302")
        except Exception as exc:
            return _post_result(request,case_id=case_id,result={"error":str(exc),"build":"311.0","fail_closed":True},tab="investigation302")

    @app.post("/build311/broker-run")
    async def build311_broker_run(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        try:
            result=await asyncio.to_thread(ctx.build311.execute_broker_route,plan_id=str(form.get("plan_id","")),connector_key=str(form.get("connector_key","")),purpose=str(form.get("purpose","")),approved_by=actor,confirmation=str(form.get("confirmation","")),mode=str(form.get("mode","live")),max_results=int(form.get("max_results","20") or 20))
            return _post_result(request,case_id=case_id,result=result,tab="investigation302")
        except Exception as exc:
            return _post_result(request,case_id=case_id,result={"error":str(exc),"build":"311.0","fail_closed":True},tab="investigation302")

    @app.post("/build311/security-selftest")
    async def build311_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build311.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build311/dossier")
    async def build311_dossier(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build311.compose_evidence_dossier(case_id=case_id,title=str(form.get("title","")),actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build311/dossier/download")
    async def build311_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id","")); dossier_id=str(request.query_params.get("dossier_id","")); p,d=ctx.build311.dossier_file(case_id,dossier_id); return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build306/workflow-ai-research")
    async def build306_workflow_ai_research(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        target_id = form.get("target_id", "")
        try:
            auth = ctx.ai_analyst_107.authorize_search(
                case_id=case_id, target_id=target_id, approved_by=actor,
                purpose=form.get("purpose", ""), provider="browser_queue",
                max_queries=int(form.get("max_queries", "8") or 8), max_results_per_query=10,
                confirmation=form.get("confirmation", ""),
            )
            result = ctx.ai_analyst_107.execute_authorized_search(auth["authorization_id"])
            job = ctx.scale_performance_123.create_job(
                case_id=case_id, target_id=target_id, job_type="ai_browser_queue",
                payload={"queries": result.get("queries") or [], "engines": list(ctx.scale_performance_123.DEFAULT_ENGINES)},
                actor=actor,
            )
            done = ctx.scale_performance_123.run_job(job["job_id"])
            queued = json.loads(done.get("result_json") or "{}")
            return RedirectResponse(_link("research3061", case_id, target_id=target_id, message=f"AI-Ermittler hat {len(result.get('queries') or [])} Queries geplant; {int(queued.get('tasks', 0))} Browser-Suchaufgaben angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061", case_id, target_id=target_id, error=str(exc)), status_code=303)

    @app.post("/build306/source-selection")
    async def build306_source_selection(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id", ""))
        result=ctx.build306.select_sources(case_id=case_id,objective=str(form.get("objective", "evidence-focused source triage")),limit=int(form.get("limit",8) or 8),actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="sources302")

    @app.post("/build306/security-selftest")
    async def build306_security_selftest(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id", ""))
        result=ctx.build306.run_security_agent_selftest(actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build306/dossier")
    async def build306_dossier(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id", ""))
        result=ctx.build306.compose_evidence_dossier(case_id=case_id,title=str(form.get("title", "")),actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build306/dossier/download")
    async def build306_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id", "")); dossier_id=str(request.query_params.get("dossier_id", ""))
        p,d=ctx.build306.dossier_file(case_id,dossier_id)
        return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build305/security-selftest")
    async def build305_security_selftest(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id", ""))
        result=ctx.build305.run_security_agent_selftest(actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build305/dossier")
    async def build305_dossier(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id", ""))
        result=ctx.build305.compose_evidence_dossier(case_id=case_id,title=str(form.get("title", "")),actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="reports302")

    @app.get("/build305/dossier/download")
    async def build305_dossier_download(request: Request):
        require_auth(request)
        case_id=str(request.query_params.get("case_id", "")); dossier_id=str(request.query_params.get("dossier_id", ""))
        p,d=ctx.build305.dossier_file(case_id,dossier_id)
        return FileResponse(str(p),media_type="text/markdown",filename=p.name)

    @app.post("/build304/analyze-source")
    async def build304_analyze_source(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build304.analyze_source_content(form.get("source_id",""),actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Content Intelligence: {r['claim_candidate_count']} Claim-Kandidaten · {r['indicator_count']} Indikatoren · Security {r['security_severity']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build304/queue-run")
    async def build304_queue_run(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build304.secure_run_next(form.get("queue_id",""),actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Secure Queue-Step {r['status']} · Security {r.get('security_risk_level','n/a')}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build304/security-review")
    async def build304_security_review(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build304.review_security_scan(form.get("scan_id",""),form.get("decision",""),form.get("confirmation",""),form.get("rationale",""),request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Security Review: {r['decision']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build304/security-selftest")
    async def build304_security_selftest(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build304.run_security_agent_selftest(actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"AI Security Agent Selftest {r['result']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build304/dossier")
    async def build304_dossier(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build304.compose_evidence_dossier(case_id=case_id,title=form.get("title",""),actor=request_actor(request))
            return RedirectResponse(_link("reports302",case_id,message=f"Evidence Dossier 304 Rev {r['revision_no']} · Gate {r['quality_gate']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("reports302",case_id,error=str(exc)),status_code=303)

    @app.get("/build304/dossier/download")
    async def build304_dossier_download(request: Request):
        require_auth(request)
        case_id=request.query_params.get("case_id",""); dossier_id=request.query_params.get("dossier_id","")
        try:
            p,d=ctx.build304.dossier_file(case_id,dossier_id)
            return FileResponse(path=p,media_type="text/markdown; charset=utf-8",filename=f"EagleEye_{case_id}_Evidence_Dossier_304_Rev{d['revision_no']}.md")
        except Exception as exc:raise HTTPException(status_code=404,detail=str(exc))

    @app.post("/build303/queue")
    async def build303_queue(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build303.create_research_queue(case_id=case_id,seed_url=form.get("seed_url",""),purpose=form.get("purpose","Bounded read-only onion research"),max_requests=int(form.get("max_requests","8") or 8),max_depth=int(form.get("max_depth","1") or 1),max_total_bytes=int(form.get("max_total_bytes","2097152") or 2097152),actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Onion Research Queue {r['queue_id']} angelegt · wartet auf OK"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build303/queue-approve")
    async def build303_queue_approve(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build303.approve_queue(form.get("queue_id",""),form.get("confirmation",""),request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Queue {r['queue_id']} freigegeben · bounded read-only"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build303/queue-run")
    async def build303_queue_run(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build303.run_next(form.get("queue_id",""),actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Queue-Step {r['status']} · {r['bytes_received']} Bytes · {r['links_staged']} Links staged"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build303/selftest")
    async def build303_selftest(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build303.run_queue_scope_selftest(actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Build303 Queue-Scope-Selftest {r['result']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build303/dossier")
    async def build303_dossier(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build303.compose_dossier(case_id=case_id,title=form.get("title",""),actor=request_actor(request))
            return RedirectResponse(_link("reports302",case_id,message=f"AI-Dossier Revision {r['revision_no']} erstellt · Review erforderlich"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("reports302",case_id,error=str(exc)),status_code=303)

    @app.post("/build303/dossier-review")
    async def build303_dossier_review(request: Request):
        form=await _read_form_limited(request); case_id=form.get("case_id","")
        try:
            r=ctx.build303.review_dossier(case_id=case_id,dossier_id=form.get("dossier_id",""),decision=form.get("decision",""),review_note=form.get("review_note",""),reviewer=request_actor(request))
            return RedirectResponse(_link("reports302",case_id,message=f"Dossier-Review gespeichert: {r['decision']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("reports302",case_id,error=str(exc)),status_code=303)

    @app.get("/build303/dossier/download")
    async def build303_dossier_download(request: Request):
        require_auth(request)
        case_id=request.query_params.get("case_id",""); dossier_id=request.query_params.get("dossier_id","")
        try:
            p,d=ctx.build303.dossier_file(case_id,dossier_id)
            return FileResponse(path=p,media_type="text/markdown; charset=utf-8",filename=f"EagleEye_{case_id}_Dossier_Rev{d['revision_no']}.md")
        except Exception as exc:raise HTTPException(status_code=404,detail=str(exc))

    @app.post("/build302/selftest")
    async def build302_selftest(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            r=ctx.build302.run_transport_hardening_selftest(actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Tor-Hardening-Selftest {r['result']} · Navigation 65→8"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build302/ai-assess")
    async def build302_ai_assess(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            r=ctx.build289.assess_case(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("investigation302",case_id,message=f"AI-Strukturprüfung: {len(r['gaps'])} priorisierte Evidenzlücken"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("investigation302",case_id,error=str(exc)),status_code=303)

    @app.post("/build302/ai-plan")
    async def build302_ai_plan(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            r=ctx.build290.create_discriminating_plan(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("investigation302",case_id,message=f"Evidenzstrategie aktualisiert: {len(r['discriminators'])} Fragen"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("investigation302",case_id,error=str(exc)),status_code=303)

    @app.post("/build302/ai-adapt")
    async def build302_ai_adapt(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            r=ctx.build291.create_adaptive_round(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("investigation302",case_id,message=f"Adaptive Runde {r['round_no']} erstellt · Human Gate bleibt aktiv"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("investigation302",case_id,error=str(exc)),status_code=303)

    @app.post("/build302/ai-fuse")
    async def build302_ai_fuse(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            r=ctx.build292.create_fusion(case_id=case_id,actor=request_actor(request))
            return RedirectResponse(_link("investigation302",case_id,message=f"Cross-Surface-Fusion: {len(r['surfaces'])} Oberflächen · Confidence {r['confidence_score']:.2f}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("investigation302",case_id,error=str(exc)),status_code=303)

    @app.post("/build302/fetch")
    async def build302_fetch(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id","")
        try:
            r=ctx.build302.hardened_fetch_mission(form.get("mission_id",""),actor=request_actor(request))
            return RedirectResponse(_link("sources302",case_id,message=f"Hardened Onion Read: HTTP {r['http_status']} · Source {r['source_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("sources302",case_id,error=str(exc)),status_code=303)

    @app.post("/build301/mission")
    async def build301_mission(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            r=ctx.build301.create_mission(case_id=case_id,onion_url=form.get("onion_url",""),purpose=form.get("purpose","Read-only OSINT research"),max_bytes=int(form.get("max_bytes","524288") or 524288),max_redirects=int(form.get("max_redirects","2") or 2),actor=request_actor(request))
            return RedirectResponse(_link("phase13_301",case_id,message=f"Tor-Mission {r['mission_id']} angelegt · wartet auf exaktes OK"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase13_301",case_id,error=str(exc)),status_code=303)

    @app.post("/build301/approve")
    async def build301_approve(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            r=ctx.build301.approve_mission(form.get("mission_id",""),form.get("confirmation",""),request_actor(request))
            return RedirectResponse(_link("phase13_301",case_id,message=f"Mission {r['mission_id']} read-only freigegeben"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase13_301",case_id,error=str(exc)),status_code=303)

    @app.post("/build301/fetch")
    async def build301_fetch(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            r=ctx.build301.fetch_mission(form.get("mission_id",""),actor=request_actor(request))
            return RedirectResponse(_link("phase13_301",case_id,message=f"Onion read-only erfasst · HTTP {r['http_status']} · {r['bytes_received']} Bytes · Source {r['source_id']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase13_301",case_id,error=str(exc)),status_code=303)

    @app.post("/build301/selftest")
    async def build301_selftest(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            r=ctx.build301.run_protocol_selftest(actor=request_actor(request))
            return RedirectResponse(_link("phase13_301",case_id,message=f"SOCKS5-Protokolltest {r['result']}"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase13_301",case_id,error=str(exc)),status_code=303)

    @app.post("/build300/final-rc/run")
    async def build300_final_rc_run(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build300.run_final_rc_suite(actor=request_actor(request))
            return RedirectResponse(_link("phase12_300",case_id,message=f"Phase-12 RC {result['result']}: {result['passed_count']}/{result['scenario_count']} Tiefentest-Szenarien · interne Qualifikation"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_300",case_id,error=str(exc)),status_code=303)

    @app.post("/build299/prerc/run")
    async def build299_prerc_run(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build299.run_prerc_suite(actor=request_actor(request))
            return RedirectResponse(_link("phase12_299",case_id,message=f"Pre-RC {result['result']}: {result['passed_count']}/{result['scenario_count']} Szenarien · interne Qualifikation"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_299",case_id,error=str(exc)),status_code=303)

    @app.post("/build298/field-pressure/run")
    async def build298_field_pressure_run(request: Request):
        form=await _form(request); verify_csrf(form, request); case_id=form.get("case_id","")
        try:
            result=ctx.build298.run_pressure_suite(actor=request_actor(request))
            return RedirectResponse(_link("phase12_298",case_id,message=f"Field Pressure {result['result']}: {result['passed_count']}/{result['scenario_count']} Szenarien · interne Qualifikation, keine Produktionszertifizierung"),status_code=303)
        except Exception as exc:return RedirectResponse(_link("phase12_298",case_id,error=str(exc)),status_code=303)

    @app.post("/build280/release")
    async def build280_release(request: Request):
        form=await request.form(); case_id=form.get("case_id","")
        try:
            _require_csrf(request,form)
            result=ctx.build280.create_release_candidate(actor=_actor(request))
            return RedirectResponse(_link("release280",case_id,message=f"Build-280 RC: {result['stage_pass_count']}/{result['stage_count']} Gates; Full Case {result['full_case_stages']}; Agents {result['agents']}; Status={result['status']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("release280",case_id,error=str(exc)),status_code=303)

    @app.post("/build279/qualify")
    async def build279_qualify(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build279.qualify_case(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("qualification279",case_id,message=f"Build-279-Qualifikation: {result['stage_pass_count']}/{result['stage_count']} Stages, {result['agent_pass_count']}/10 Agents, RC={result['release_candidate_readiness']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("qualification279",case_id,error=str(exc)),status_code=303)

    @app.post("/build279/simulate")
    async def build279_simulate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        actor=request_actor(request)
        try:
            result=ctx.build279.run_synthetic_full_case(actor=actor)
            return RedirectResponse(_link("qualification279",result['case_id'],message=f"Synthetische Full-Case-Simulation abgeschlossen: {result['stage_pass_count']}/{result['stage_count']} Stages, {result['agent_pass_count']}/10 Agents, RC={result['release_candidate_readiness']}."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("qualification279",form.get("case_id",""),error=str(exc)),status_code=303)

    @app.post("/build278/build")
    async def build278_build(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build278.build_product(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("product278",case_id,message=f"Intelligence Product {result['product_id']} Rev. {result['revision_no']} erstellt; Export-Audit {result['export_audit']['result']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("product278",case_id,error=str(exc)),status_code=303)

    @app.post("/build278/review")
    async def build278_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build278.review_product(case_id=case_id,product_id=form.get("product_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("product278",case_id,message=f"Product Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("product278",case_id,error=str(exc)),status_code=303)

    @app.post("/build277/run")
    async def build277_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build277.run_red_team(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("redteam277",case_id,message=f"Red-Team 2.0 abgeschlossen: {len(result['findings'])} Challenge(s), OPSEC {result['opsec_audit']['result']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("redteam277",case_id,error=str(exc)),status_code=303)

    @app.post("/build277/review")
    async def build277_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build277.review_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("redteam277",case_id,message=f"Red-Team Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("redteam277",case_id,error=str(exc)),status_code=303)

    @app.post("/build276/run")
    async def build276_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build276.run_orchestration(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("agents276",case_id,message=f"Co-Analyst Orchestrator {result['orchestration_id']} abgeschlossen; {result['agent_count']} Spezialagenten, OPSEC {result['opsec_audit']['result']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("agents276",case_id,error=str(exc)),status_code=303)

    @app.post("/build276/review")
    async def build276_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build276.review_supervisor_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("agents276",case_id,message=f"Supervisor Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("agents276",case_id,error=str(exc)),status_code=303)

    @app.post("/build275/analyze")
    async def build275_analyze(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build275.synthesize(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("reasoning275",case_id,message=f"Reasoning Brief {result['brief']['brief_id']} erstellt; Compartment Audit: {result['compartment_audit']['result']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("reasoning275",case_id,error=str(exc)),status_code=303)

    @app.post("/build275/review")
    async def build275_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build275.review_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("reasoning275",case_id,message=f"Reasoning Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("reasoning275",case_id,error=str(exc)),status_code=303)

    @app.post("/build274/analyze")
    async def build274_analyze(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build274.analyze_family(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("knowledge274",case_id,message=f"Cross-Case Brief {result['brief_id']} erstellt; {result['reused_from_other_cases_count']} öffentliche Objekte wurden bereits in anderen Fällen beobachtet. Privacy Guard: {result['privacy_guard']['result']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("knowledge274",case_id,error=str(exc)),status_code=303)

    @app.post("/build274/review")
    async def build274_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build274.review_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("knowledge274",case_id,message=f"Cross-Case Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("knowledge274",case_id,error=str(exc)),status_code=303)

    @app.post("/build273/profile")
    async def build273_profile(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            langs=[x.strip() for x in form.get("languages","").replace(";",",").split(",") if x.strip()]
            result=ctx.build273.create_profile(case_id=case_id,target_id=form.get("target_id",""),country_code=form.get("country_code",""),country_name=form.get("country_name",""),birth_place=form.get("birth_place",""),languages=langs,actor=actor)
            return RedirectResponse(_link("documents273",case_id,message=f"Personen-Dokumentprofil Rev. {result['revision_no']} gespeichert: {result['country_code']}."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("documents273",case_id,error=str(exc)),status_code=303)

    @app.post("/build273/person-search")
    async def build273_person_search(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build274.create_person_document_run(case_id=case_id,user_request=form.get("message","") or "Finde zur Person alle möglichen Dokumente",target_id=form.get("target_id",""),country_code=form.get("country_code",""),birth_place=form.get("birth_place",""),actor=actor)
            return RedirectResponse(_link("documents273",case_id,message=f"Personen-Dokumentlauf {result['run_id']} vorbereitet: {len(result['queries'])} öffentliche Queries, {len(result['manual_sources'])} kontrollierte manuelle Quellen. OK startet die begrenzte Recherche."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("documents273",case_id,error=str(exc)),status_code=303)

    @app.post("/build273/analyze")
    async def build273_analyze(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build273.analyze_family(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("documents273",case_id,message=f"Document Brief {result['brief_id']} Rev. {result['revision_no']}: {result['document_count']} Dokumente → {result['family_count']} Familien."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("documents273",case_id,error=str(exc)),status_code=303)

    @app.post("/build273/review")
    async def build273_review(request: Request):
        form=await _form(request); verify_csrf(form,request); case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build273.review_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("documents273",case_id,message=f"Document Brief Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:return RedirectResponse(_link("documents273",case_id,error=str(exc)),status_code=303)

    @app.post("/build272/analyze")
    async def build272_analyze(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build272.analyze_family(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("narrative272",case_id,message=f"Narrative Brief {result['brief_id']} Rev. {result['revision_no']} erstellt: {result['observation_count']} Observations → {result['narrative_cluster_count']} Narrative-Cluster."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("narrative272",case_id,error=str(exc)),status_code=303)

    @app.post("/build272/review")
    async def build272_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build272.review_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("narrative272",case_id,message=f"Narrative Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("narrative272",case_id,error=str(exc)),status_code=303)

    @app.post("/build271/analyze")
    async def build271_analyze(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build271.analyze_family(case_id=case_id,parent_run_id=form.get("parent_run_id",""),actor=actor)
            return RedirectResponse(_link("source271",case_id,message=f"Source Independence Brief {result['brief_id']} erstellt: {result['raw_source_count']} Raw Sources → {result['cluster_count']} Origin-Cluster."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("source271",case_id,error=str(exc)),status_code=303)

    @app.post("/build271/review")
    async def build271_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build271.review_brief(case_id=case_id,brief_id=form.get("brief_id",""),decision=form.get("decision","needs_more_evidence"),rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("source271",case_id,message=f"Source Independence Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("source271",case_id,error=str(exc)),status_code=303)

    @app.post("/build270/plan")
    async def build270_plan(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            parent_run_id=form.get("parent_run_id","")
            source=ctx.build271.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            narrative=ctx.build272.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            documents=ctx.build273.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            knowledge=ctx.build274.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            result=ctx.build270.build_collection_plan(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            aug=ctx.build271.augment_collection_plan(case_id=case_id,plan_id=result['plan_id'],brief_id=source['brief_id'])
            naug=ctx.build272.augment_collection_plan(case_id=case_id,plan_id=result['plan_id'],brief_id=narrative['brief_id'])
            daug=ctx.build273.augment_collection_plan(case_id=case_id,plan_id=result['plan_id'],brief_id=documents['brief_id'])
            kaug=ctx.build274.augment_collection_plan(case_id=case_id,plan_id=result['plan_id'],brief_id=knowledge['brief_id'])
            return RedirectResponse(_link("knowledge274",case_id,message=f"Source + Narrative + Document Corpus + Cross-Case Public Knowledge analysiert; Collection Plan {result['plan_id']} um {len(aug['added_task_ids'])+len(naug['added_task_ids'])+len(daug['added_task_ids'])+len(kaug['added_task_ids'])} Gap-Task(s) ergänzt."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("collection270",case_id,error=str(exc)),status_code=303)

    @app.post("/build270/wave")
    async def build270_wave(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            provider=os.environ.get("EAGLEEYE_COLLECTION_PROVIDER","browser_queue")
            mode=os.environ.get("EAGLEEYE_OPSEC_MODE","standard")
            result=ctx.build274.approve_and_execute_wave(case_id=case_id,plan_id=form.get("plan_id",""),confirmation=form.get("confirmation",""),
                approved_by=actor,provider=provider,opsec_mode=mode)
            return RedirectResponse(_link("knowledge274",case_id,message=f"Collection Wave {result['wave_no']} abgeschlossen; Source, Narrative, Document Corpus und Cross-Case Public Knowledge aktualisiert: {result['status']}. Weitere externe Welle nur mit neuem OK."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("collection270",case_id,error=str(exc)),status_code=303)

    @app.post("/build269/review")
    async def build269_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id=form.get("case_id",""); actor=request_actor(request)
        try:
            result=ctx.build269.review_ach(case_id=case_id,matrix_id=form.get("matrix_id",""),decision=form.get("decision","needs_more_evidence"),
                rationale=form.get("rationale",""),reviewer=actor)
            return RedirectResponse(_link("ach269",case_id,message=f"ACH Review {result['decision']} gespeichert."),status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("ach269",case_id,error=str(exc)),status_code=303)

    @app.post("/build227/turn-start")
    async def build227_turn_start(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            message=form.get("message", "")
            if str(message).strip().upper()=="OK":
                pending=ctx.db.one("SELECT r.run_id FROM ai_research_runs_263 r LEFT JOIN ai_execution_approvals_264 a ON a.run_id=r.run_id WHERE r.case_id=? AND a.run_id IS NULL ORDER BY r.created_at DESC,r.rowid DESC LIMIT 1",(case_id,))
                if pending:
                    result=ctx.build279.execute_initial_run(case_id=case_id,run_id=pending["run_id"],confirmation="OK",approved_by=actor,opsec_mode=os.environ.get("EAGLEEYE_OPSEC_MODE","standard"))
                    plan=ctx.build270.build_collection_plan(case_id=case_id,parent_run_id=pending["run_id"],actor=actor)
                    aug=ctx.build271.augment_collection_plan(case_id=case_id,plan_id=plan['plan_id'],brief_id=result['source_independence_271']['brief_id'])
                    naug=ctx.build272.augment_collection_plan(case_id=case_id,plan_id=plan['plan_id'],brief_id=result['narrative_diffusion_272']['brief_id'])
                    daug=ctx.build273.augment_collection_plan(case_id=case_id,plan_id=plan['plan_id'],brief_id=result['document_corpus_273']['brief_id'])
                    kaug=ctx.build274.augment_collection_plan(case_id=case_id,plan_id=plan['plan_id'],brief_id=result['cross_case_knowledge_274']['brief_id'])
                    return RedirectResponse(_link("qualification279", case_id, message=f"AI-Ermittler hat Analyse, Product Builder und die vollständige Build-279-Qualifikation ausgeführt; Collection Plan {plan['plan_id']} um {len(aug['added_task_ids'])+len(naug['added_task_ids'])+len(daug['added_task_ids'])+len(kaug['added_task_ids'])} Gap-Task(s) ergänzt. Ein weiteres OK startet genau eine begrenzte Collection Wave."), status_code=303)
                planrow=ctx.db.one("SELECT plan_id FROM collection_plans_270 WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,))
                if planrow and ctx.build270.plan(planrow["plan_id"])["pending_tasks"]:
                    provider=os.environ.get("EAGLEEYE_COLLECTION_PROVIDER","browser_queue")
                    mode=os.environ.get("EAGLEEYE_OPSEC_MODE","standard")
                    result=ctx.build279.approve_and_execute_wave(case_id=case_id,plan_id=planrow["plan_id"],confirmation="OK",approved_by=actor,provider=provider,opsec_mode=mode)
                    return RedirectResponse(_link("qualification279",case_id,message=f"Collection Wave {result['wave_no']} abgeschlossen; neue Daten wurden bis zur aktualisierten Full-Case-Qualifikation verarbeitet. Weitere externe Welle nur mit neuem OK."),status_code=303)
            if ctx.build273.is_person_document_command(message):
                result=ctx.build279.create_person_document_run(case_id=case_id,user_request=message,target_id=form.get("target_id",""),actor=actor)
                return RedirectResponse(_link("knowledge274",case_id,message=f"Country-Aware Personen-Dokumentrecherche {result['run_id']} vorbereitet ({result['country_code']}); {len(result['queries'])} öffentliche Queries + {len(result['manual_sources'])} manuelle/kontrollierte Quellen; Cross-Case Public-Reuse-Kontext wurde ergänzt. Antworte mit OK zur begrenzten Ausführung."),status_code=303)
            if ctx.build263.is_research_command(message):
                result=ctx.build263.create_research_run(case_id=case_id,user_request=message,target_id=form.get("target_id",""),auto_open=False,actor=actor)
                return RedirectResponse(_link("execution264", case_id, message=f"AI-Recherche {result['run_id']} vorbereitet. Antworte im AI-Ermittler mit OK oder nutze den OK-Button zur selbstständigen Abarbeitung."), status_code=303)
            result = ctx.build227.start_turn(session_id=session_id, message=message, message_language=form.get("message_language", "de"), actor=actor, confirmation=f"CONVERSATIONAL TURN 227 {session_id} STARTEN")
            return RedirectResponse(_link("build214", case_id, message=f"Turn {result['turn_id']} gestartet; Status kann über /build227/turn/{result['turn_id']} abgerufen werden."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build227/turn-stop")
    async def build227_turn_stop(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); turn_id = form.get("turn_id", "")
        try:
            result = ctx.build227.request_stop(turn_id=turn_id, actor=actor, confirmation=f"CONVERSATIONAL TURN 227 {turn_id} STOPPEN")
            return RedirectResponse(_link("build214", case_id, message=f"Stop für Turn {result['turn_id']} angefordert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build227/turn-retry")
    async def build227_turn_retry(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); turn_id = form.get("turn_id", "")
        try:
            result = ctx.build227.retry_turn(turn_id=turn_id, actor=actor, confirmation=f"CONVERSATIONAL TURN 227 {turn_id} WIEDERHOLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Retry {result['turn_id']} abgeschlossen: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.get("/build227/turn/{turn_id}")
    async def build227_turn_status(turn_id: str):
        try:
            return JSONResponse(ctx.build227.turn_status(turn_id=turn_id))
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)

    @app.post("/build224/profiles-refresh")
    async def build224_profiles_refresh(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build224.refresh_local_profiles(case_id=case_id, actor=actor, confirmation=f"AI MODEL PROFILES 224 {case_id} AKTUALISIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"{len(result['profiles'])} lokale Modellprofile erfasst."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build224/reference-suite")
    async def build224_reference_suite(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build224.seed_reference_suite(case_id=case_id, created_by=actor, confirmation=f"AI REFERENCE SUITE 224 {case_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Referenzsuite {result['suite_id']} mit {len(result['tasks'])} Aufgaben erstellt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build224/suite-run")
    async def build224_suite_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); suite_id = form.get("suite_id", "")
        try:
            profile_ids = [x.strip() for x in form.get("profile_ids", "").split(",") if x.strip()]
            result = ctx.build224.run_suite(suite_id=suite_id, profile_ids=profile_ids, actor=actor, confirmation=f"AI EVALUATION SUITE 224 {suite_id} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Modellvergleich abgeschlossen: {result['run_count']} Läufe."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build224/routing-recommend")
    async def build224_routing_recommend(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); suite_id = form.get("suite_id", "")
        try:
            result = ctx.build224.create_routing_recommendation(suite_id=suite_id, created_by=actor, confirmation=f"AI ROUTING RECOMMENDATION 224 {suite_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Reviewpflichtige Routing-Empfehlung {result['recommendation_id']} erzeugt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build223/config")
    async def build223_config(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build223.update_case_config(case_id=case_id, working_language=form.get("working_language", "de"), max_retrieval_chunks=int(form.get("max_retrieval_chunks", "12") or 12), max_source_actions=int(form.get("max_source_actions", "5") or 5), live_sources_enabled=form.get("live_sources_enabled", "") == "1", actor=actor, confirmation=f"KONSOLIDIERUNG 223 {case_id} KONFIGURIEREN")
            return RedirectResponse(_link("build214", case_id, message=f"Kanonische Konfiguration v{result['config_version']} gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build223/baseline")
    async def build223_baseline(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build223.create_baseline(case_id=case_id, created_by=actor, confirmation=f"PHASE8 BASELINE 223 {case_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Phase-8-Baseline {result['baseline_id']} erstellt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build223/chat")
    async def build223_chat(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build223.send_message(session_id=session_id, message=form.get("message", ""), message_language=form.get("message_language", "de"), actor=actor, confirmation=f"AI INVESTIGATOR 223 {session_id} SENDEN")
            return RedirectResponse(_link("build214", case_id, message=f"AI-Antwort gespeichert · Trace {result['trace_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build223/plan")
    async def build223_plan(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); session_id = form.get("session_id", "")
        try:
            result = ctx.build223.create_plan(session_id=session_id, objective=form.get("objective", ""), question_language=form.get("question_language", "de"), actor=actor, confirmation=f"INVESTIGATION PLAN 223 {session_id} ERSTELLEN")
            return RedirectResponse(_link("build214", case_id, message=f"Kanonischer Plan {result['plan_id']} · Trace {result['trace_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build223/source-run")
    async def build223_source_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            result = ctx.build223.run_source(case_id=case_id, adapter_key=adapter_key, target_type=form.get("target_type", ""), target_value=form.get("target_value", ""), purpose=form.get("purpose", ""), actor=actor, options={}, confirmation=f"SOURCE 223 {case_id} {adapter_key} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Quellenlauf {result.get('status')} · {result.get('result_count',0)} Ergebnisse · Trace {result['trace_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build223/loop-create")
    async def build223_loop_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build223.create_research_loop(case_id=case_id, session_id=form.get("session_id", ""), objective=form.get("objective", ""), working_language=form.get("working_language", "de"), max_cycles=int(form.get("max_cycles", "3") or 3), created_by=actor, confirmation=f"AI RESEARCH LOOP 223 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Research Loop {result['loop_id']} · Trace {result['trace_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build222/suite-create")
    async def build222_suite_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build222.create_suite(case_id=case_id, title=form.get("title", ""), description=form.get("description", ""), created_by=actor, qualification_profile={}, confirmation=f"PHASE7 SUITE 222 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualifikationssuite {result['suite_id']} angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build222/scenario-create")
    async def build222_scenario_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); suite_id = form.get("suite_id", "")
        try:
            def js(name, default):
                try: return json.loads(form.get(name, "") or json.dumps(default))
                except Exception: raise ValueError(f"{name} must be valid JSON")
            result = ctx.build222.add_scenario(suite_id=suite_id, scenario_key=form.get("scenario_key", ""), title=form.get("title", ""), category=form.get("category", "unique_identity"), language=form.get("language", "de"), difficulty=form.get("difficulty", "medium"), objective=form.get("objective", ""), expected_refs=js("expected_refs_json", []), forbidden_claims=js("forbidden_claims_json", []), expected_behaviors=js("expected_behaviors_json", ["source_grounded"]), expected_route_classes=js("expected_routes_json", []), expected_source_classes=js("expected_sources_json", []), minimum_cycles=int(form.get("minimum_cycles", "1") or 1), maximum_first_lead_seconds=int(form.get("maximum_first_lead_seconds", "300") or 300), created_by=actor, confirmation=f"PHASE7 SCENARIO 222 {suite_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"Qualifikationsszenario {result['scenario_id']} angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build222/scenario-evaluate")
    async def build222_scenario_evaluate(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); scenario_id = form.get("scenario_id", "")
        try:
            def js(name, default):
                try: return json.loads(form.get(name, "") or json.dumps(default))
                except Exception: raise ValueError(f"{name} must be valid JSON")
            result = ctx.build222.evaluate_loop(scenario_id=scenario_id, loop_id=form.get("loop_id", ""), observed_behaviors=js("observed_behaviors_json", []), adapter_labels=js("adapter_labels_json", []), translation_checks=js("translation_checks_json", []), contradiction_checks=js("contradiction_checks_json", []), dialog_continuity=float(form.get("dialog_continuity", "1.0") or 1.0), recovery_checks=js("recovery_checks_json", []), opsec_violations=js("opsec_violations_json", []), evaluator=actor, confirmation=f"PHASE7 SCENARIO 222 {scenario_id} AUSWERTEN")
            return RedirectResponse(_link("build214", case_id, message=f"Szenario-Score {result['overall_score']:.3f}; {'bestanden' if result['passed'] else 'nicht bestanden'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build222/environment-check")
    async def build222_environment_check(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); suite_id = form.get("suite_id", ""); check_key = form.get("check_key", "")
        try:
            try: details = json.loads(form.get("details_json", "{}") or "{}")
            except Exception: raise ValueError("details_json must be valid JSON")
            result = ctx.build222.record_environment_check(suite_id=suite_id, check_key=check_key, environment=form.get("environment", ""), status=form.get("status", "pending"), details=details, evidence_ref=form.get("evidence_ref", ""), checked_by=actor, confirmation=f"PHASE7 ENV CHECK 222 {suite_id} {check_key} SPEICHERN")
            return RedirectResponse(_link("build214", case_id, message=f"Umgebungsprüfung {result['check_id']} gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build222/suite-finalize")
    async def build222_suite_finalize(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); suite_id = form.get("suite_id", "")
        try:
            result = ctx.build222.finalize_suite(suite_id=suite_id, generated_by=actor, confirmation=f"PHASE7 QUALIFICATION 222 {suite_id} ABSCHLIESSEN")
            return RedirectResponse(_link("build214", case_id, message=f"Phase-7-Bericht {result['report_id']}: Entwicklung {result['development_status']}, operativ {result['operational_status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build221/loop-create")
    async def build221_loop_create(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request)
        try:
            result = ctx.build221.create_loop(case_id=case_id, session_id=form.get("session_id", ""), objective=form.get("objective", ""), working_language=form.get("working_language", "de"), max_cycles=int(form.get("max_cycles", "3") or 3), created_by=actor, confirmation=f"AI RESEARCH LOOP 221 {case_id} ANLEGEN")
            return RedirectResponse(_link("build214", case_id, message=f"AI Research Loop {result['loop_id']} angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build221/role-run")
    async def build221_role_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); loop_id = form.get("loop_id", "")
        try:
            loop = ctx.build221._loop(loop_id)
            result = ctx.build221.run_current_role(loop_id=loop_id, actor=actor, confirmation=f"AI ROLE 221 {loop_id} {loop['current_role']} AUSFUEHREN")
            return RedirectResponse(_link("build214", case_id, message=f"Rolle {result['role']} ausgeführt; Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build221/role-review")
    async def build221_role_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); run_id = form.get("run_id", "")
        try:
            result = ctx.build221.review_role_run(run_id=run_id, decision=form.get("decision", "approved"), reason=form.get("reason", ""), reviewer=actor, confirmation=f"AI ROLE REVIEW 221 {run_id} ABSCHLIESSEN")
            return RedirectResponse(_link("build214", case_id, message=f"Rollenreview {result['review_id']} gespeichert; Trainingsentwurf erzeugt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build221/action-review")
    async def build221_action_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); action_id = form.get("action_id", "")
        try:
            result = ctx.build221.review_action(action_id=action_id, decision=form.get("decision", "approved"), reason=form.get("reason", ""), reviewer=actor, confirmation=f"AI SOURCE ACTION 221 {action_id} PRUEFEN")
            return RedirectResponse(_link("build214", case_id, message=f"Quellenaktion {action_id}: {result['decision']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build221/actions-prepare")
    async def build221_actions_prepare(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); loop_id = form.get("loop_id", "")
        try:
            result = ctx.build221.prepare_approved_actions(loop_id=loop_id, actor=actor, confirmation=f"AI SOURCE ACTIONS 221 {loop_id} VORBEREITEN")
            return RedirectResponse(_link("build214", case_id, message=f"{len(result['prepared'])} Quellenaktionen vorbereitet; nichts automatisch ausgeführt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build220/run")
    async def build220_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            try:
                options = json.loads(form.get("options_json", "{}") or "{}")
            except Exception:
                raise ValueError("options_json must be valid JSON")
            result = ctx.build220.run_adapter(
                case_id=case_id, adapter_key=adapter_key, target_type=form.get("target_type", "url"),
                target_value=form.get("target_value", ""), purpose=form.get("purpose", ""), actor=actor,
                options=options, confirmation=f"SOURCE PACK 220 {case_id} {adapter_key} AUSFUEHREN",
            )
            return RedirectResponse(_link("build214", case_id, message=f"Build-220-Lauf {result.get('run_id','')}: {result['status']} · {result.get('result_count',0)} Ergebnisse."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build220/result-review")
    async def build220_result_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); result_id = form.get("result_id", "")
        try:
            result = ctx.build220.review_result(
                result_id=result_id, decision=form.get("decision", "needs_more_evidence"),
                reason=form.get("reason", ""), reviewer=actor, confirmation=f"SOURCE RESULT 220 {result_id} PRUEFEN",
            )
            return RedirectResponse(_link("build214", case_id, message=f"Build-220-Review {result['review_id']} gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build219/run")
    async def build219_run(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            result = ctx.build219.run_adapter(
                case_id=case_id, adapter_key=adapter_key, target_type=form.get("target_type", "username"),
                target_value=form.get("target_value", ""), purpose=form.get("purpose", ""), actor=actor,
                confirmation=f"RELIABLE SOURCE 219 {case_id} {adapter_key} AUSFUEHREN",
            )
            return RedirectResponse(_link("build214", case_id, message=f"Reliability-Lauf {result.get('run_id','')}: {result['status']} · {result.get('result_count',0)} Kandidaten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build219/contract-check")
    async def build219_contract_check(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            sample = json.loads(form.get("sample_json", "{}") or "{}")
            result = ctx.build219.check_contract(adapter_key=adapter_key, sample=sample, actor=actor, confirmation=f"SOURCE CONTRACT 219 {adapter_key} PRUEFEN")
            return RedirectResponse(_link("build214", case_id, message=f"Parservertrag {adapter_key}: {result['status']} · Drift {result['drift_severity']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build219/snapshot")
    async def build219_snapshot(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            result = ctx.build219.calculate_snapshot(adapter_key=adapter_key, actor=actor)
            return RedirectResponse(_link("build214", case_id, message=f"Reliability {adapter_key}: {result['overall_score']:.2f} · {result['state']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/build219/review")
    async def build219_review(request: Request):
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", ""); actor = request_actor(request); adapter_key = form.get("adapter_key", "")
        try:
            result = ctx.build219.review_adapter(
                case_id=case_id, adapter_key=adapter_key, decision=form.get("decision", "needs_more_observation"),
                reason=form.get("reason", ""), reviewer=actor,
                confirmation=f"SOURCE RELIABILITY REVIEW 219 {adapter_key} ABSCHLIESSEN",
            )
            return RedirectResponse(_link("build214", case_id, message=f"Quellenreview gespeichert; Trainingsentwurf {result['training_example_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("build214", case_id, error=str(exc)), status_code=303)

    @app.post("/cases/create")
    async def create_case(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        try:
            case = ctx.cases.create_case(form.get("title", ""), form.get("client", ""), form.get("purpose", ""), form.get("legal_basis", ""))
            governance.register_case(case_id=case["case_id"], actor=request_actor(request))
            auth146.assign_case(case_id=case["case_id"], username=request_actor(request), case_role="case_lead", actor=request_actor(request), notes="Fall durch Benutzer erstellt", bootstrap=True)
            return RedirectResponse(_link("intake3061", case["case_id"], message="Fall wurde angelegt. Nächster Schritt: Person oder Firma aufnehmen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("overview", "", error=str(exc)), status_code=303)

    @app.post("/subjects/create")
    async def create_subject(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigation_flow_1222.create_subject(
                case_id=case_id, name=form.get("name", ""), actor=request_actor(request), aliases=form.get("aliases", ""),
                emails=form.get("emails", ""), usernames=form.get("usernames", ""), locations=form.get("locations", ""),
                companies=form.get("companies", ""), domains=form.get("domains", ""), notes=form.get("notes", ""),
                objective=form.get("objective", ""), create_research_tasks=True, subject_type=form.get("subject_type", "person"),
            )
            target_id = str((result.get("target") or {}).get("target_id") or "")
            if target_id and form.get("subject_type", "person") == "person":
                ctx.build135.save_profile_form(case_id=case_id, target_id=target_id, form=form, actor=request_actor(request))
                ctx.build135.analyze_contradictions(case_id=case_id, target_id=target_id, actor=request_actor(request))
            count = int((result.get("research") or {}).get("tasks", 0))
            return RedirectResponse(_link("research3061", case_id, target_id=target_id, message=f"Ziel aufgenommen; {count} Rechercheaufgaben vorbereitet. Recherche kann jetzt direkt gestartet werden."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("intake3061", case_id, error=str(exc)), status_code=303)

    @app.post("/research/anchor")
    async def research_anchor(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.scale_performance_123.add_anchor(
                case_id=case_id, target_id=form.get("target_id", ""), anchor_type=form.get("anchor_type", ""),
                value=form.get("value", ""), reliability=float(form.get("reliability", "0.75") or 0.75), actor=request_actor(request),
            )
            return RedirectResponse(_link("research3061", case_id, target_id=form.get("target_id", ""), message="Geprüfter Rechercheanker gespeichert. Die nächste Recherchegeneration nutzt ihn."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061", case_id, error=str(exc)), status_code=303)

    @app.post("/research/adaptive")
    async def research_adaptive(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        engines = [label for field, label in (("engine_google","Google"),("engine_bing","Bing"),("engine_duckduckgo","DuckDuckGo"),("engine_brave","Brave"),("engine_startpage","Startpage")) if form.get(field)]
        try:
            job = ctx.scale_performance_123.create_job(case_id=case_id, target_id=form.get("target_id", ""), job_type="adaptive_research", payload={"engines": engines, "limit": int(form.get("limit", "80") or 80)}, actor=request_actor(request))
            done = ctx.scale_performance_123.run_job(job["job_id"])
            result = json.loads(done.get("result_json") or "{}")
            return RedirectResponse(_link("research3061", case_id, target_id=form.get("target_id", ""), message=f"Adaptive Recherche abgeschlossen: {int(result.get('tasks', 0))} neue Aufgaben, {int(result.get('duplicates', 0))} Duplikate vermieden."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061", case_id, error=str(exc)), status_code=303)

    @app.post("/research/generate")
    async def generate_research(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        engines = [label for field, label in (("engine_google","Google"),("engine_bing","Bing"),("engine_duckduckgo","DuckDuckGo"),("engine_brave","Brave"),("engine_startpage","Startpage")) if form.get(field)]
        try:
            result = ctx.investigation_flow_1222.create_research_package(case_id=case_id, target_id=form.get("target_id", ""), engines=engines, actor=request_actor(request))
            return RedirectResponse(_link("research3061", case_id, message=f"Recherchepaket erzeugt: {int(result.get('tasks', 0))} Aufgaben."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061", case_id, error=str(exc)), status_code=303)

    @app.post("/research/launch")
    @app.post("/research/open")
    async def research_launch(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            port = request.url.port or 80
            result = ctx.build136.launch_research_task(
                case_id=case_id, task_id=form.get("task_id", ""), actor=request_actor(request),
                local_redirect_origin=f"http://127.0.0.1:{port}",
            )
            return RedirectResponse(_link("research3061", case_id, message=f"Recherche als Tab geroutet: {result['destination_host']} · {result['dispatch_mode']} · bestehendes Firefox-Profil."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061", case_id, error=str(exc)), status_code=303)



    @app.post("/research/launch-parallel")
    async def research_launch_parallel(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            port = request.url.port or 80
            result = ctx.build136.launch_research_tasks_parallel(
                case_id=case_id, seed_task_id=form.get("task_id", ""), actor=request_actor(request),
                local_redirect_origin=f"http://127.0.0.1:{port}",
            )
            engines = ", ".join(str(x) for x in result.get("engines", []))
            return RedirectResponse(_link("research3061", case_id, message=f"{result.get('count', 0)} Suchmaschinen parallel im geschützten Firefox geöffnet: {engines}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research3061", case_id, error=str(exc)), status_code=303)

    @app.get("/security/research-redirect")
    def security_research_redirect(request: Request, ticket: str = ""):
        # This endpoint is intentionally authenticated by a short-lived, one-time
        # ticket instead of the workspace cookie: the isolated Firefox profile
        # must never inherit the analyst's workspace session. Loopback and host
        # checks remain enforced by the global middleware.
        try:
            destination = protection.consume_research_redirect(ticket)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        response = RedirectResponse(destination, status_code=303)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.post("/security/config")
    async def security_config(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            protection.configure(
                protection_mode=form.get("protection_mode", "hardened"),
                research_browser_mode=form.get("research_browser_mode", "isolated_firefox"),
                proxy_mode=form.get("proxy_mode", "none"), proxy_host=form.get("proxy_host", ""),
                proxy_port=int(form.get("proxy_port", "0") or 0), proxy_remote_dns=bool(form.get("proxy_remote_dns")),
                block_external_provider_network=bool(form.get("block_external_provider_network")),
                allow_default_browser_fallback=bool(form.get("allow_default_browser_fallback")),
                clear_profile_before_launch=bool(form.get("clear_profile_before_launch")),
                ephemeral_profile_per_launch=bool(form.get("ephemeral_profile_per_launch")),
                session_bind_client=bool(form.get("session_bind_client")),
                panic_purge_profiles=bool(form.get("panic_purge_profiles")),
                session_timeout_minutes=int(form.get("session_timeout_minutes", "20") or 20), actor=request_actor(request),
            )
            return RedirectResponse(_link("security", case_id, message="Investigator-Protection-Konfiguration gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/security/passphrase")
    async def security_passphrase(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            protection.set_access_passphrase(new_passphrase=form.get("new_passphrase", ""), current_passphrase=form.get("current_passphrase", ""), actor=request_actor(request))
            session_token, timeout = protection.issue_session(client_fingerprint(request))
            response = RedirectResponse(_link("security", case_id, message="Passphrasensperre ist aktiv. Beim nächsten Start muss der Arbeitsbereich entsperrt werden."), status_code=303)
            response.set_cookie("ee_protected_session", session_token, httponly=True, samesite="strict", path="/", max_age=timeout)
            response.delete_cookie("ee_session", path="/")
            return response
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/security/disable-lock")
    async def security_disable_lock(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            protection.disable_access_lock(current_passphrase=form.get("current_passphrase", ""), actor=request_actor(request))
            response = RedirectResponse(_link("security", case_id, message="Passphrasensperre deaktiviert."), status_code=303)
            response.set_cookie("ee_session", local_token, httponly=True, samesite="strict", path="/")
            response.delete_cookie("ee_protected_session", path="/")
            return response
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/security/secrets")
    async def security_secrets(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            updated = []
            for name in ("brave_api_key", "ollama_api_key"):
                if form.get(name, ""):
                    protection.save_provider_secret(name, form[name])
                    updated.append(name)
            return RedirectResponse(_link("security", case_id, message="Provider-Secrets verschlüsselt gespeichert: " + (", ".join(updated) if updated else "keine Änderung")), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/security/egress")
    async def security_egress(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            approval = protection.authorize_egress(case_id=case_id, provider=form.get("provider", ""), purpose=form.get("purpose", ""), approved_by=form.get("approved_by", ""), confirmation=form.get("confirmation", ""))
            return RedirectResponse(_link("security", case_id, message=f"Einmalige Netzfreigabe erstellt: {approval['provider']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/security/rotate-profile")
    async def security_rotate_profile(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            protection.rotate_case_compartment(case_id, actor=request_actor(request), purge_old=True)
            return RedirectResponse(_link("security", case_id, message="Fallbezogenes Firefox-Profil rotiert und alte Profilreste entfernt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/security/lockdown")
    async def security_lockdown(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        result = protection.emergency_lockdown(case_id=case_id, actor=request_actor(request))
        response = RedirectResponse("/security/login?" + urlencode({"error": f"Notfallsperre aktiv. {result['profiles_purged']} Profilverzeichnisse entfernt."}), status_code=303)
        response.delete_cookie("ee_protected_session", path="/")
        response.delete_cookie("ee_session", path="/")
        response.set_cookie("ee_bootstrap", local_token, httponly=True, samesite="strict", path="/", max_age=300)
        return response

    @app.post("/security/checkpoint")
    async def security_checkpoint(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            checkpoint = protection.create_evidence_checkpoint(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("security", case_id, message=f"Evidence-Checkpoint erzeugt: {checkpoint['checkpoint_sha256'][:16]}…"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security", case_id, error=str(exc)), status_code=303)

    @app.post("/reliability/check")
    async def reliability_check(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.reliability_quality_125.run_integrity_check(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("reliability", case_id, message=f"Integritätsprüfung: {result['status']} · Score {result['score']}/100 · {len(result['issues'])} Befunde"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reliability", case_id, error=str(exc)), status_code=303)

    @app.post("/reliability/recover")
    async def reliability_recover(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.reliability_quality_125.recover_stale_state(case_id=case_id, stale_seconds=60, actor=request_actor(request))
            return RedirectResponse(_link("reliability", case_id, message=f"Recovery: {result['operations']} Operationen, {result['jobs']} Jobs, {result['startup_sessions']} Startzustände."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reliability", case_id, error=str(exc)), status_code=303)

    @app.post("/reliability/backup")
    async def reliability_backup(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.reliability_quality_125.create_backup(actor=request_actor(request), case_id=case_id, include_evidence=bool(form.get("include_evidence")))
            return RedirectResponse(_link("reliability", case_id, message=f"Verschlüsseltes Backup erstellt und verifiziert: {result['backup_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reliability", case_id, error=str(exc)), status_code=303)

    @app.post("/reliability/verify-backup")
    async def reliability_verify_backup(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.reliability_quality_125.verify_backup(form.get("backup_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("reliability", case_id, message=f"Backup gültig: Schema {result['schema_version']} · {result['entry_count']} Dateien"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reliability", case_id, error=str(exc)), status_code=303)

    @app.post("/reliability/stage-restore")
    async def reliability_stage_restore(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.reliability_quality_125.stage_restore(form.get("backup_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("reliability", case_id, message=f"Geprüfte Restore-Stufe erzeugt: {result['stage_id']}. Anwendung vor einer Wiederherstellung schließen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reliability", case_id, error=str(exc)), status_code=303)

    @app.post("/intake/manual")
    async def manual_intake(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigation_flow_1222.include_manual_candidate(
                case_id=case_id, target_id=form.get("target_id", ""), title=form.get("title", ""),
                url=form.get("url", ""), text=form.get("text", ""), html_snapshot=form.get("html_snapshot", ""),
                source_label=form.get("source_label", ""), actor=request_actor(request),
            )
            suffix = " (Duplikat erkannt)" if result.get("duplicate") else ""
            return RedirectResponse(_link("intake", case_id, message=f"Fund in kontrollierten Intake übernommen{suffix}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("intake", case_id, error=str(exc)), status_code=303)

    @app.post("/api/photo136/capture")
    async def photo136_capture(request: Request):
        require_auth(request)
        raw = await request.body()
        if len(raw) > 17 * 1024 * 1024:
            return JSONResponse({"ok": False, "detail": "Foto-Payload überschreitet das zulässige Limit"}, status_code=413)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            supplied_csrf = request.headers.get("x-eagleeye-csrf", "") or str(payload.get("csrf") or "")
            expected_csrf = request_csrf(request)
            if not supplied_csrf or not secrets.compare_digest(supplied_csrf, expected_csrf):
                raise PermissionError("CSRF-Prüfung fehlgeschlagen")
            query_case_id = str(request.query_params.get("case_id") or "")
            payload_case_id = str(payload.get("case_id") or "")
            if not query_case_id:
                raise PermissionError("Fallbindung muss in der lokalen API-Adresse angegeben werden")
            if payload_case_id and payload_case_id != query_case_id:
                raise PermissionError("Fallbindung zwischen API-Adresse und Foto-Payload stimmt nicht überein")
            payload["case_id"] = query_case_id
            result = ctx.build136.capture_photo(payload=payload, actor=request_actor(request))
            return JSONResponse({"ok": True, "asset_id": result["asset_id"], "duplicate": bool(result.get("duplicate")), "source_kind": result["source_kind"], "sha256": result["sha256"]})
        except PermissionError as exc:
            return JSONResponse({"ok": False, "detail": str(exc)[:500]}, status_code=403)
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": str(exc)[:500]}, status_code=400)

    @app.get("/api/photo136/{asset_id}")
    def photo136_file(request: Request, asset_id: str, case_id: str):
        require_auth(request)
        try:
            row, path = ctx.build136.photo_path(case_id=case_id, asset_id=asset_id)
            return FileResponse(
                path,
                media_type=str(row.get("mime_type") or "application/octet-stream"),
                filename=str(row.get("original_filename") or path.name),
                content_disposition_type="inline",
                headers={"Cache-Control": "private, no-store", "X-EagleEye-SHA256": str(row.get("sha256") or "")},
            )
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/photos136/review")
    async def photo136_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build136.update_photo_review(
                case_id=case_id,
                asset_id=form.get("asset_id", ""),
                status=form.get("status", ""),
                notes=form.get("notes", ""),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("photos", case_id, message=f"Fotoreview gespeichert: {result['review_status']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/workflow137/create")
    async def workflow137_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build137.create_workflow(
                case_id=case_id, target_id=form.get("target_id", ""),
                objective_key=form.get("objective_key", "identity_confirmation"),
                objective_text=form.get("objective_text", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("workflow137", case_id, message=f"Ermittlungsworkflow erzeugt: {result['task_count']} nachvollziehbare Aufgaben."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("workflow137", case_id, error=str(exc)), status_code=303)

    @app.post("/workflow137/task")
    async def workflow137_task(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build137.update_workflow_task(
                case_id=case_id, workflow_task_id=form.get("workflow_task_id", ""),
                status=form.get("status", "planned"), outcome_note=form.get("outcome_note", ""),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("workflow137", case_id, message=f"Aufgabenstatus gespeichert: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("workflow137", case_id, error=str(exc)), status_code=303)

    @app.post("/workflow137/launch")
    async def workflow137_launch(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            port = request.url.port or 80
            result = ctx.build137.launch_workflow_task(
                case_id=case_id, workflow_task_id=form.get("workflow_task_id", ""),
                actor=request_actor(request), local_redirect_origin=f"http://127.0.0.1:{port}",
            )
            return RedirectResponse(_link("workflow137", case_id, message=f"Workflow-Aufgabe im geschützten Fallbrowser geöffnet: {result.get('dispatch_mode')}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("workflow137", case_id, error=str(exc)), status_code=303)

    @app.post("/photos137/analyze")
    async def photos137_analyze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build137.analyze_photo(case_id=case_id, asset_id=form.get("asset_id", ""), actor=request_actor(request))
            links = len(result.get("similarity_links") or [])
            return RedirectResponse(_link("photos", case_id, message=f"Lokale Bildanalyse abgeschlossen: {links} Ähnlichkeitskandidat(en), keine Identitätsaussage."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos137/copy")
    async def photos137_copy(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build137.create_research_copy(
                case_id=case_id, asset_id=form.get("asset_id", ""),
                max_dimension=int(form.get("max_dimension", "1600") or 1600),
                quality=int(form.get("quality", "88") or 88), crop={}, actor=request_actor(request),
            )
            suffix = " (bereits vorhanden)" if result.get("duplicate") else ""
            return RedirectResponse(_link("photos", case_id, message=f"Metadatenbereinigte Recherchekopie erzeugt{suffix}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.get("/api/photo137/copy/{copy_id}")
    def photo137_copy_file(request: Request, copy_id: str, case_id: str):
        require_auth(request)
        try:
            row, path = ctx.build137.copy_path(case_id=case_id, copy_id=copy_id)
            return FileResponse(path, media_type="image/jpeg", filename=str(row.get("filename") or path.name), content_disposition_type="attachment", headers={"Cache-Control": "private, no-store", "X-EagleEye-SHA256": str(row.get("sha256") or ""), "X-EagleEye-Metadata-Removed": "true"})
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/photos137/job-create")
    async def photos137_job_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build137.create_photo_research_job(
                case_id=case_id, copy_id=form.get("copy_id", ""), provider_key=form.get("provider_key", ""),
                purpose=form.get("purpose", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("photos", case_id, message=f"Fotorecherche vorbereitet: {result['provider_label']}; kein automatischer Upload."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos137/job-launch")
    async def photos137_job_launch(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            port = request.url.port or 80
            result = ctx.build137.launch_photo_research_job(
                case_id=case_id, job_id=form.get("job_id", ""), actor=request_actor(request),
                local_redirect_origin=f"http://127.0.0.1:{port}",
            )
            return RedirectResponse(_link("photos", case_id, message=f"Bildsuchanbieter im Fallbrowser geöffnet ({result['dispatch_mode']}). Recherchekopie muss weiterhin manuell hochgeladen werden."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos137/job-status")
    async def photos137_job_status(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build137.update_photo_job(
                case_id=case_id, job_id=form.get("job_id", ""), status=form.get("status", "prepared"),
                result_note=form.get("result_note", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("photos", case_id, message=f"Fotorecherche-Status gespeichert: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)


    @app.post("/evidence138/sync")
    async def evidence138_sync(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.sync_case_graph(case_id=case_id, actor=request_actor(request))
            total = sum(int(value) for value in result.get("created", {}).values())
            return RedirectResponse(_link("evidence138", case_id, message=f"Evidence Graph synchronisiert: {total} neue Nodes; keine automatische Identitätsaussage."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/analyze")
    async def evidence138_analyze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.run_integrity_analysis(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("evidence138", case_id, message=f"Belegketten geprüft: {result['warning_count']} offene Warnhinweise erzeugt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/node")
    async def evidence138_node(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.upsert_node(
                case_id=case_id, node_type=form.get("node_type", "other"), label=form.get("label", ""),
                normalized_value=form.get("normalized_value", ""), target_id=form.get("target_id", ""),
                review_state=form.get("review_state", "candidate"), attributes={}, actor=request_actor(request),
            )
            suffix = " (bestehender Node aktualisiert)" if result.get("duplicate") else ""
            return RedirectResponse(_link("evidence138", case_id, message=f"Evidence Node gespeichert{suffix}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/source")
    async def evidence138_source(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.register_source(
                case_id=case_id, title=form.get("title", ""), canonical_url=form.get("canonical_url", ""),
                source_type=form.get("source_type", "unknown"), independence_group=form.get("independence_group", ""),
                publisher=form.get("publisher", ""), reliability=float(form.get("reliability", "0.5") or 0.5),
                actor=request_actor(request),
            )
            suffix = " (bereits registriert)" if result.get("duplicate") else ""
            return RedirectResponse(_link("evidence138", case_id, message=f"Quelle registriert{suffix}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/assertion")
    async def evidence138_assertion(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.create_assertion(
                case_id=case_id, subject_node_id=form.get("subject_node_id", ""), predicate=form.get("predicate", ""),
                object_node_id=form.get("object_node_id", ""), assertion_text=form.get("assertion_text", ""),
                epistemic_state=form.get("epistemic_state", "lead"), confidence=float(form.get("confidence", "0.5") or 0.5),
                target_id=form.get("target_id", ""), valid_from=form.get("valid_from", ""), valid_to=form.get("valid_to", ""),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("evidence138", case_id, message=f"Evidence-Aussage angelegt: {result['epistemic_state']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/attach")
    async def evidence138_attach(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.attach_source(
                case_id=case_id, assertion_id=form.get("assertion_id", ""), source_id=form.get("source_id", ""),
                stance=form.get("stance", "supports"), weight=float(form.get("weight", "1") or 1),
                excerpt=form.get("excerpt", ""), rationale=form.get("rationale", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("evidence138", case_id, message=f"Quelle verknüpft: {result['source_count']} Quellen aus {result['independence_count']} Ursprungsgruppen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/review")
    async def evidence138_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.review_assertion(
                case_id=case_id, assertion_id=form.get("assertion_id", ""),
                epistemic_state=form.get("epistemic_state", "lead"), confidence=float(form.get("confidence", "0.5") or 0.5),
                review_note=form.get("review_note", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("evidence138", case_id, message=f"Aussage geprüft: {result['epistemic_state']} bei Konfidenz {result['confidence']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/evidence138/warning")
    async def evidence138_warning(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.update_warning(case_id=case_id, warning_id=form.get("warning_id", ""), status=form.get("status", "open"), actor=request_actor(request))
            return RedirectResponse(_link("evidence138", case_id, message=f"Warnungsstatus gespeichert: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("evidence138", case_id, error=str(exc)), status_code=303)

    @app.post("/photos138/variant")
    async def photos138_variant(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            params = {
                "left": int(form.get("left", "0") or 0), "top": int(form.get("top", "0") or 0),
                "right": int(form.get("right", "0") or 0), "bottom": int(form.get("bottom", "0") or 0),
            }
            result = ctx.build138.create_photo_variant(
                case_id=case_id, asset_id=form.get("asset_id", ""), variant_mode=form.get("variant_mode", "clean_full"),
                label=form.get("label", ""), parameters=params, max_dimension=int(form.get("max_dimension", "1600") or 1600),
                quality=int(form.get("quality", "88") or 88), actor=request_actor(request),
            )
            suffix = " (bereits vorhanden)" if result.get("duplicate") else ""
            return RedirectResponse(_link("photos", case_id, message=f"Fotorecherche-Variante erzeugt: {result['variant_mode']}{suffix}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.get("/api/photo138/variant/{variant_id}")
    def photo138_variant_file(request: Request, variant_id: str, case_id: str):
        require_auth(request)
        try:
            row, path = ctx.build138.variant_path(case_id=case_id, variant_id=variant_id)
            return FileResponse(path, media_type="image/jpeg", filename=str(row.get("filename") or path.name), content_disposition_type="attachment", headers={"Cache-Control": "private, no-store", "X-EagleEye-SHA256": str(row.get("sha256") or ""), "X-EagleEye-Metadata-Removed": "true", "X-EagleEye-Identity-Claim": "false"})
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/photos138/sweep")
    async def photos138_sweep(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ref = form.get("source_ref", "")
            source_type, source_id = ref.split(":", 1)
            providers = [key for key in ("google_lens", "bing_visual", "tineye", "yandex_images") if form.get(f"provider_{key}") == "1"]
            result = ctx.build138.create_photo_search_runs(
                case_id=case_id, source_type="variant" if source_type == "variant" else "copy137", source_id=source_id,
                provider_keys=providers, purpose=form.get("purpose", ""), confirmation=form.get("confirmation", ""),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("photos", case_id, message=f"Provider-Serie vorbereitet: {result['run_count']} manuelle Rechercheläufe, 0 automatische Uploads."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos138/run-launch")
    async def photos138_run_launch(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            port = request.url.port or 80
            result = ctx.build138.launch_photo_search_run(case_id=case_id, run_id=form.get("run_id", ""), actor=request_actor(request), local_redirect_origin=f"http://127.0.0.1:{port}")
            return RedirectResponse(_link("photos", case_id, message=f"Bildsuchanbieter im isolierten Fallbrowser geöffnet ({result['dispatch_mode']}); Upload bleibt manuell."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos138/run-status")
    async def photos138_run_status(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.update_photo_search_run(case_id=case_id, run_id=form.get("run_id", ""), status=form.get("status", "prepared"), result_note=form.get("result_note", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Fotorecherche-Lauf gespeichert: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos138/result")
    async def photos138_result(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            run_type, run_id = form.get("run_ref", "").split(":", 1)
            result = ctx.build138.record_photo_result(
                case_id=case_id, research_run_type=run_type, research_run_id=run_id,
                page_url=form.get("page_url", ""), image_url=form.get("image_url", ""), page_title=form.get("page_title", ""),
                result_kind=form.get("result_kind", "unknown"), local_result_asset_id=form.get("local_result_asset_id", ""),
                notes=form.get("notes", ""), actor=request_actor(request),
            )
            comparison = result.get("comparison") or {}
            suffix = f"; Dateivergleich: {comparison.get('image_relation_band')}" if comparison else ""
            return RedirectResponse(_link("photos", case_id, message=f"Fototreffer dokumentiert{suffix}. Keine Identitätsaussage."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos138/result-review")
    async def photos138_result_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.review_photo_result(case_id=case_id, result_id=form.get("result_id", ""), review_status=form.get("review_status", "candidate"), result_kind=form.get("result_kind", "unknown"), notes=form.get("notes", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Fototreffer geprüft: {result['review_status']} / {result['result_kind']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos138/clusters")
    async def photos138_clusters(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build138.build_photo_clusters(case_id=case_id, actor=request_actor(request), ahash_threshold=int(form.get("ahash_threshold", "8") or 8), dhash_threshold=int(form.get("dhash_threshold", "10") or 10))
            return RedirectResponse(_link("photos", case_id, message=f"Bildcluster neu berechnet: {result['cluster_count']} candidate-only Cluster, 0 Identitätsaussagen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/capture-identity/ticket")
    async def capture_identity_ticket(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.capture_identity_129.issue_capture_ticket(
                case_id=case_id, target_id=form.get("target_id", ""), purpose=form.get("purpose", ""),
                actor=request_actor(request), ttl_seconds=int(form.get("ttl_seconds", "600") or 600),
            )
            message = f"Einmaliges Companion-Ticket (bis {result['expires_at']}): {result['ticket']}"
            return RedirectResponse(_link("capture_identity", case_id, message=message), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture_identity", case_id, error=str(exc)), status_code=303)

    @app.post("/capture-identity/manual")
    async def capture_identity_manual(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ticket = ctx.capture_identity_129.issue_capture_ticket(
                case_id=case_id, target_id=form.get("target_id", ""), purpose="Manueller lokaler Capture-Fallback aus dem EagleEye Workspace.",
                actor=request_actor(request), ttl_seconds=120,
            )
            result = ctx.capture_identity_129.capture_from_companion(
                ticket=ticket["ticket"],
                payload={"url": form.get("url", ""), "title": form.get("title", ""), "visible_text": form.get("visible_text", ""), "html": form.get("html", "")},
                origin="local-workspace",
            )
            return RedirectResponse(_link("capture_identity", case_id, message=f"Capture candidate-only gesichert: {result['capture_id']} · {result['change_state']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture_identity", case_id, error=str(exc)), status_code=303)

    @app.post("/capture-identity/hypothesis")
    async def capture_identity_hypothesis(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.capture_identity_129.create_identity_hypothesis(
                case_id=case_id, left_entity_id=form.get("left_entity_id", ""),
                right_entity_id=form.get("right_entity_id", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("capture_identity", case_id, message=f"Identitätshypothese erzeugt: {result['recommendation']} · kein automatischer Merge."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture_identity", case_id, error=str(exc)), status_code=303)

    @app.post("/capture-identity/review")
    async def capture_identity_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            actor = request_actor(request)
            if governance.settings().get("team_mode_enabled") and governance.settings().get("require_four_eyes") and form.get("decision") == "same_person":
                result = governance.request_critical_action(
                    case_id=case_id, action_key="identity.confirm", object_id=form.get("hypothesis_id", ""),
                    payload={"reason": form.get("reason", "")}, reason=form.get("reason", ""), actor=actor,
                )
                return RedirectResponse(_link("governance", case_id, message=f"Vier-Augen-Freigabe angefordert: {result['request_id']}"), status_code=303)
            result = ctx.capture_identity_129.review_identity_hypothesis(
                case_id=case_id, hypothesis_id=form.get("hypothesis_id", ""), decision=form.get("decision", ""),
                reason=form.get("reason", ""), actor=actor,
            )
            return RedirectResponse(_link("capture_identity", case_id, message=f"Identity-Review gespeichert: {result['review_decision']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture_identity", case_id, error=str(exc)), status_code=303)

    @app.post("/capture-identity/benchmark")
    async def capture_identity_benchmark(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.capture_identity_129.run_identity_benchmark(actor=request_actor(request))
            return RedirectResponse(_link("capture_identity", case_id, message=f"Golden Identity Suite: Precision {result['precision']*100:.1f}% · False-Merge-Rate {result['false_merge_rate']*100:.1f}%"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("capture_identity", case_id, error=str(exc)), status_code=303)

    @app.get("/security/companion-bootstrap", response_class=HTMLResponse)
    def companion_bootstrap(ticket: str):
        try:
            item = ctx.build136.bootstrap_view(ticket)
            first_url = str(item.get("first_url") or "")
            body = f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta http-equiv="refresh" content="3;url={_esc(first_url)}"><title>EagleEye Firefox Companion</title><style>{CSS}</style></head><body><main class="main" style="max-width:720px;margin:8vh auto"><div class="panel"><div class="brand"><div class="logo">EE</div><div><b>EagleEye Build 140</b><span>Fallgebundener Firefox-Tab-Router</span></div></div><h1>Geschützte Firefox-Sitzung wird verbunden</h1><p>Das Companion registriert ausschließlich dieses isolierte Fallprofil. Anschließend wird der erste Recherche-Tab geöffnet.</p><div class="notice">Keine Falldatei und keine vollständige Personenakte wird an die Erweiterung übertragen.</div></div></main></body></html>'''
            return HTMLResponse(body, headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return HTMLResponse(f"<!doctype html><meta charset='utf-8'><h1>Companion-Bootstrap abgelaufen</h1><p>{_esc(exc)}</p>", status_code=404)

    @app.options("/api/firefox-companion/register")
    @app.options("/api/firefox-companion/orders")
    @app.options("/api/firefox-companion/ack")
    def firefox_companion_options():
        return Response(status_code=204)

    @app.post("/api/firefox-companion/register")
    async def firefox_companion_register(request: Request):
        try:
            ticket = request.headers.get("x-eagleeye-companion-ticket", "")
            if not ticket:
                raw = await request.body()
                if raw:
                    payload = json.loads(raw.decode("utf-8"))
                    ticket = str((payload or {}).get("ticket") or "")
            return JSONResponse(ctx.build136.register_companion(ticket))
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": str(exc)[:500]}, status_code=400)

    @app.get("/api/firefox-companion/orders")
    def firefox_companion_orders(request: Request, case_id: str, port: int = 0):
        try:
            token = request.headers.get("x-eagleeye-companion-token", "")
            return JSONResponse(ctx.build136.poll_orders(case_id=case_id, token=token, port=port))
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": str(exc)[:500]}, status_code=403)

    @app.post("/api/firefox-companion/ack")
    async def firefox_companion_ack(request: Request):
        try:
            raw = await request.body()
            if len(raw) > 64 * 1024:
                raise ValueError("Acknowledgement-Payload ist zu groß")
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            token = request.headers.get("x-eagleeye-companion-token", "")
            return JSONResponse(ctx.build136.acknowledge_order(
                case_id=str(payload.get("case_id") or ""), token=token,
                order_id=str(payload.get("order_id") or ""), status=str(payload.get("status") or ""),
                error_text=str(payload.get("error_text") or ""),
            ))
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": str(exc)[:500]}, status_code=400)

    @app.options("/api/capture-companion/submit")
    def capture_companion_options():
        return Response(status_code=204)

    @app.post("/api/capture-companion/submit")
    async def capture_companion_submit(request: Request):
        raw = await request.body()
        if len(raw) > 26 * 1024 * 1024:
            return JSONResponse({"ok": False, "detail": "Capture-Payload ist zu groß"}, status_code=413)
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            ticket = request.headers.get("x-eagleeye-capture-ticket", "") or str(payload.pop("ticket", ""))
            result = ctx.capture_identity_129.capture_from_companion(
                ticket=ticket, payload=payload, origin=request.headers.get("origin", ""),
            )
            return JSONResponse({"ok": True, "capture_id": result["capture_id"], "change_state": result["change_state"], "status": result["status"], "evidence_package_id": result["evidence_package_id"]})
        except Exception as exc:
            return JSONResponse({"ok": False, "detail": str(exc)[:500]}, status_code=400)

    @app.get("/api/capture129")
    def api_capture129(request: Request, case_id: str):
        require_auth(request)
        return ctx.capture_identity_129.dashboard(case_id)

    @app.post("/assistant/local")
    async def local_assistant(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigation_flow_1222.local_assist(case_id=case_id, prompt=form.get("prompt", ""), actor=request_actor(request))
            steps = result.get("next_steps") or []
            return RedirectResponse(_link("assistant", case_id, message="AI-Assistent: " + " | ".join(str(x) for x in steps[:3])), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant/config")
    async def assistant_config(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.ai_analyst_107.save_config(**{key: form.get(key, "") for key in ("ollama_url","ollama_model","search_provider","searxng_url","country","language")})
            return RedirectResponse(_link("assistant", case_id, message="Provider-Konfiguration gespeichert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant/authorize")
    async def assistant_authorize(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.ai_analyst_107.authorize_search(
                case_id=case_id, target_id=form.get("target_id", ""), approved_by=form.get("approved_by", ""),
                purpose=form.get("purpose", ""), provider=form.get("provider", ""),
                max_queries=int(form.get("max_queries", "6") or 6), max_results_per_query=int(form.get("max_results_per_query", "10") or 10),
                confirmation=form.get("confirmation", ""),
            )
            return RedirectResponse(_link("assistant", case_id, message="Einmalige AI-Websuche freigegeben."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant/search")
    async def assistant_search(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            authorization_id = form.get("authorization_id", "")
            auth_row = ctx.db.one("SELECT provider FROM ai_authorizations_107 WHERE authorization_id=? AND case_id=?", (authorization_id, case_id))
            if not auth_row:
                raise KeyError("AI-Freigabeticket gehört nicht zu diesem Fall")
            egress_approval = protection.reserve_provider_egress(case_id=case_id, provider=str(auth_row.get("provider") or "browser_queue"))
            try:
                result = ctx.ai_analyst_107.execute_authorized_search(authorization_id)
            except Exception:
                protection.release_provider_egress(egress_approval)
                raise
            protection.consume_provider_egress(egress_approval)
            if result.get("mode") == "browser_queue":
                run = ctx.db.one("SELECT target_id FROM ai_search_runs_107 WHERE run_id=? AND case_id=?", (result["run_id"], case_id))
                job = ctx.scale_performance_123.create_job(
                    case_id=case_id, target_id=run["target_id"], job_type="ai_browser_queue",
                    payload={"queries": result.get("queries") or [], "engines": list(ctx.scale_performance_123.DEFAULT_ENGINES)}, actor=request_actor(request),
                )
                done = ctx.scale_performance_123.run_job(job["job_id"])
                queued = json.loads(done.get("result_json") or "{}")
                return RedirectResponse(_link("research3061", case_id, target_id=run["target_id"], message=f"AI-Queryplan lokal erzeugt: {int(queued.get('tasks', 0))} Browser-Suchaufgaben. Kein Zusatzserver erforderlich."), status_code=303)
            bridge = ctx.investigation_flow_1222.bridge_ai_run(case_id=case_id, run_id=result["run_id"], actor=request_actor(request))
            return RedirectResponse(_link("intake", case_id, message=f"Externe AI-Suche abgeschlossen: {result.get('result_count', 0)} Treffer, {bridge.get('intake_count', 0)} Intake-Kandidaten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant/chatgpt-protected")
    async def assistant_chatgpt_protected(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            origin = f"http://127.0.0.1:{request.url.port or 80}"
            result = ctx.production_candidate_126.launch_chatgpt_protected(case_id=case_id, actor=request_actor(request), local_redirect_origin=origin)
            return RedirectResponse(_link("assistant", case_id, message=f"ChatGPT wurde ohne automatische Fallübertragung im geschützten Profil geöffnet ({result['browser_mode']})."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant", case_id, error=str(exc)), status_code=303)

    @app.post("/research-intelligence/create")
    async def research_intelligence_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.research_strategy_128.create_strategy(
                case_id=case_id, target_id=form.get("target_id", ""), actor=request_actor(request),
                query_limit=int(form.get("query_limit", "80") or 80),
            )
            return RedirectResponse(_link("research_intelligence", case_id, message=f"Research-Intelligence-Strategie erzeugt: {result['query_count']} Queries · {result['connector_count']} Connectoren · Coverage {result['coverage_score']}/100."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research_intelligence", case_id, error=str(exc)), status_code=303)

    @app.get("/api/research128")
    def api_research128(request: Request, case_id: str):
        require_auth(request)
        return ctx.research_strategy_128.dashboard(case_id)

    @app.post("/research-intelligence/connector-run")
    async def research_intelligence_connector_run(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.research_strategy_128.execute_connector(
                case_id=case_id, target_id=form.get("target_id", ""), connector_key=form.get("connector_key", ""),
                purpose=form.get("purpose", ""), approved_by=request_actor(request), confirmation=form.get("confirmation", ""),
                mode=form.get("mode", "live"), max_results=int(form.get("max_results", "20") or 20),
            )
            run = result["run"]
            return RedirectResponse(_link("research_intelligence", case_id, message=f"Connector-Lauf abgeschlossen: {run['provider_key']} · {run['result_count']} neue Kandidaten · {run['duplicate_count']} Duplikate."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("research_intelligence", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/analyse")
    async def graph_lab_analyse(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.graph_hypothesis_130.run_graph_analysis(
                case_id=case_id, actor=request_actor(request),
                node_types=[item.strip() for item in form.get("node_types", "").split(",") if item.strip()],
                date_from=form.get("date_from", ""), date_to=form.get("date_to", ""),
                location_query=form.get("location_query", ""), include_candidates=bool(form.get("include_candidates")),
            )
            return RedirectResponse(_link("graph_lab", case_id, message=f"Graphanalyse abgeschlossen: {result['node_count']} Knoten · {result['edge_count']} Kanten · {result['summary']['community_count']} Communities."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/path")
    async def graph_lab_path(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.graph_hypothesis_130.find_paths(
                case_id=case_id, source_node_id=form.get("source_node_id", ""), target_node_id=form.get("target_node_id", ""), actor=request_actor(request),
                max_depth=int(form.get("max_depth", "6") or 6), max_paths=int(form.get("max_paths", "5") or 5),
            )
            return RedirectResponse(_link("graph_lab", case_id, message=f"{result['path_count']} kürzeste fallgebundene Pfade gespeichert. Struktureller Pfad ≠ reale Beziehung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/hypothesis")
    async def graph_lab_hypothesis(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.graph_hypothesis_130.create_hypothesis(case_id=case_id, target_id=form.get("target_id", ""), title=form.get("title", ""), statement=form.get("statement", ""), rationale=form.get("rationale", ""), actor=request_actor(request), claim_type=form.get("claim_type", "other"))
            return RedirectResponse(_link("graph_lab", case_id, message=f"Candidate-only Hypothese erzeugt: {result['hypothesis_id']}. Keine automatische Promotion."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/claim")
    async def graph_lab_claim(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            claim_id = ctx.graph_hypothesis_130.add_claim(case_id=case_id, hypothesis_id=form.get("hypothesis_id", ""), claim_type=form.get("claim_type", "other"), statement=form.get("statement", ""), actor=request_actor(request))
            return RedirectResponse(_link("graph_lab", case_id, message=f"Claim ergänzt: {claim_id}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/evidence")
    async def graph_lab_evidence(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            object_type, object_id = (form.get("object_ref", "") + "|").split("|", 1)[:2]
            link_id = ctx.graph_hypothesis_130.link_evidence(case_id=case_id, hypothesis_id=form.get("hypothesis_id", ""), claim_id=form.get("claim_id", ""), object_type=object_type, object_id=object_id, stance=form.get("stance", "context"), weight=float(form.get("weight", "0.5") or 0.5), summary=form.get("summary", ""), actor=request_actor(request))
            return RedirectResponse(_link("graph_lab", case_id, message=f"Evidence mit Claim verknüpft: {link_id}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/red-team")
    async def graph_lab_red_team(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.graph_hypothesis_130.generate_red_team_review(case_id=case_id, hypothesis_id=form.get("hypothesis_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("graph_lab", case_id, message=f"Red-Team-Prüfung erzeugt: {result['red_team_id']} · suggestions_only · 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/review-red-team")
    async def graph_lab_review_red_team(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.graph_hypothesis_130.review_red_team(case_id=case_id, red_team_id=form.get("red_team_id", ""), decision=form.get("decision", ""), reason=form.get("reason", ""), actor=request_actor(request))
            return RedirectResponse(_link("graph_lab", case_id, message=f"Red-Team-Review gespeichert: {result['review_status']} · suggestions_only bleibt erhalten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/request-review")
    async def graph_lab_request_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.graph_hypothesis_130.request_hypothesis_review(case_id=case_id, hypothesis_id=form.get("hypothesis_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("graph_lab", case_id, message="Hypothese zur menschlichen Prüfung vorgemerkt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.post("/graph-lab/review")
    async def graph_lab_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            actor = request_actor(request)
            if governance.settings().get("team_mode_enabled") and governance.settings().get("require_four_eyes") and form.get("decision") == "supported_for_working_use":
                result = governance.request_critical_action(
                    case_id=case_id, action_key="hypothesis.accept", object_id=form.get("hypothesis_id", ""),
                    payload={"reason": form.get("reason", "")}, reason=form.get("reason", ""), actor=actor,
                )
                return RedirectResponse(_link("governance", case_id, message=f"Vier-Augen-Freigabe angefordert: {result['request_id']}"), status_code=303)
            result = ctx.graph_hypothesis_130.review_hypothesis(case_id=case_id, hypothesis_id=form.get("hypothesis_id", ""), decision=form.get("decision", ""), reason=form.get("reason", ""), actor=actor)
            return RedirectResponse(_link("graph_lab", case_id, message=f"Hypothesenreview gespeichert: {result['review_decision']} · candidate-only bleibt erhalten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("graph_lab", case_id, error=str(exc)), status_code=303)

    @app.get("/api/graph130")
    def api_graph130(request: Request, case_id: str):
        require_auth(request)
        payload = ctx.graph_hypothesis_130.graph_projection(case_id, limit_nodes=1500, limit_edges=4000)
        latest = ctx.db.one("SELECT run_id FROM graph_analysis_runs_130 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,))
        metric_map = {}
        if latest:
            metric_map = {row["node_id"]: row for row in ctx.db.all("SELECT * FROM graph_node_metrics_130 WHERE run_id=?", (latest["run_id"],))}
        for node in payload.get("nodes") or []:
            metric = metric_map.get(node["id"], {})
            node.update({"degree": metric.get("degree", 0), "degree_centrality": metric.get("degree_centrality", 0), "betweenness": metric.get("betweenness", 0), "component_id": metric.get("component_id", ""), "community_id": metric.get("community_id", "")})
        return payload

    @app.get("/api/graph130/source-independence")
    def api_graph130_source_independence(request: Request, case_id: str):
        require_auth(request)
        return ctx.graph_hypothesis_130.source_independence_graph(case_id)

    @app.get("/api/hypothesis130")
    def api_hypothesis130(request: Request, case_id: str, hypothesis_id: str):
        require_auth(request)
        return ctx.graph_hypothesis_130.claim_evidence_matrix(case_id, hypothesis_id)

    @app.post("/synthesis/create")
    async def synthesis_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigative_synthesis_131.create_synthesis(case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""), actor=request_actor(request))
            return RedirectResponse(_link("synthesis", case_id, message=f"Quellengebundene Synthese erzeugt: {result['report_id']} · {result['gap_count']} Gaps · {result['claim_count']} Claims · 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("synthesis", case_id, error=str(exc)), status_code=303)

    @app.post("/synthesis/verify")
    async def synthesis_verify(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigative_synthesis_131.verify_claims(case_id=case_id, report_id=form.get("report_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("synthesis", case_id, message=f"Claim-Prüfung: {result['source_bound']} quellengebunden · {result['contested']} umstritten · {result['unsubstantiated']} unbelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("synthesis", case_id, error=str(exc)), status_code=303)

    @app.post("/synthesis/request-review")
    async def synthesis_request_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigative_synthesis_131.request_review(case_id=case_id, report_id=form.get("report_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("synthesis", case_id, message=f"Bericht zum Review vorgemerkt · {result['unsubstantiated_claims']} unbelegte Claims bleiben sichtbar."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("synthesis", case_id, error=str(exc)), status_code=303)

    @app.post("/synthesis/review")
    async def synthesis_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            actor = request_actor(request)
            if governance.settings().get("team_mode_enabled") and governance.settings().get("require_four_eyes") and form.get("decision") == "accepted_for_working_use":
                result = governance.request_critical_action(
                    case_id=case_id, action_key="report.accept", object_id=form.get("report_id", ""),
                    payload={"reason": form.get("reason", "")}, reason=form.get("reason", ""), actor=actor,
                )
                return RedirectResponse(_link("governance", case_id, message=f"Vier-Augen-Freigabe angefordert: {result['request_id']}"), status_code=303)
            result = ctx.investigative_synthesis_131.review_report(case_id=case_id, report_id=form.get("report_id", ""), decision=form.get("decision", ""), reason=form.get("reason", ""), actor=actor)
            return RedirectResponse(_link("synthesis", case_id, message=f"Berichtsreview gespeichert: {result['review_decision']} · keine automatische Tatsachenpromotion oder Exportfreigabe."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("synthesis", case_id, error=str(exc)), status_code=303)

    @app.get("/api/report131")
    def api_report131(request: Request, case_id: str, report_id: str):
        require_auth(request)
        return ctx.investigative_synthesis_131.get_report(case_id, report_id)

    @app.post("/orchestrator/plans")
    async def orchestrator_create_plan(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.intelligence_orchestrator_127.create_plan(
                case_id=case_id,
                target_id=form.get("target_id") or None,
                objective=form.get("objective", ""),
                max_tasks=int(form.get("max_tasks", "7") or 7),
                max_runtime_seconds=int(form.get("max_runtime_seconds", "120") or 120),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("orchestrator", case_id, message=f"Planentwurf erzeugt: {result['plan_id']} · {result['task_count']} Tasks · Status {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/approve")
    async def orchestrator_approve(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.intelligence_orchestrator_127.approve_plan(
                case_id=case_id, plan_id=form.get("plan_id", ""), actor=request_actor(request),
                confirmation=form.get("confirmation", ""), reason=form.get("reason", ""),
            )
            return RedirectResponse(_link("orchestrator", case_id, message=f"Plan freigegeben: {result['plan_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/reject")
    async def orchestrator_reject(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.intelligence_orchestrator_127.reject_plan(case_id=case_id, plan_id=form.get("plan_id", ""), actor=request_actor(request), reason=form.get("reason", ""))
            return RedirectResponse(_link("orchestrator", case_id, message="Plan wurde verworfen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/execute")
    async def orchestrator_execute(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.intelligence_orchestrator_127.execute_plan(case_id=case_id, plan_id=form.get("plan_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("orchestrator", case_id, message=f"Orchestrator-Lauf abgeschlossen: {result['tasks_completed']} lokale Tasks, 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/pause")
    async def orchestrator_pause(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.intelligence_orchestrator_127.pause_plan(case_id=case_id, plan_id=form.get("plan_id", ""), actor=request_actor(request), reason=form.get("reason", ""))
            return RedirectResponse(_link("orchestrator", case_id, message="Plan wurde pausiert."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/resume")
    async def orchestrator_resume(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.intelligence_orchestrator_127.resume_plan(case_id=case_id, plan_id=form.get("plan_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("orchestrator", case_id, message="Plan wurde zur Ausführung fortgesetzt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/cancel")
    async def orchestrator_cancel(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.intelligence_orchestrator_127.cancel_plan(case_id=case_id, plan_id=form.get("plan_id", ""), actor=request_actor(request), reason=form.get("reason", ""))
            return RedirectResponse(_link("orchestrator", case_id, message="Plan wurde kontrolliert abgebrochen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.post("/orchestrator/review-output")
    async def orchestrator_review_output(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.intelligence_orchestrator_127.review_output(
                case_id=case_id, output_id=form.get("output_id", ""), decision=form.get("decision", ""),
                actor=request_actor(request), reason=form.get("reason", ""),
            )
            return RedirectResponse(_link("orchestrator", case_id, message=f"Output-Review gespeichert: {result['review_status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("orchestrator", case_id, error=str(exc)), status_code=303)

    @app.get("/api/orchestrator127")
    def api_orchestrator127(request: Request, case_id: str):
        require_auth(request)
        return ctx.intelligence_orchestrator_127.dashboard(case_id)

    @app.post("/operations/preflight")
    async def operations_preflight(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase4_operations_134.runtime_preflight(actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"Runtime Preflight: {result['status']} · Score {result['score']} · Blocker {result['blocker_count']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/contract")
    async def operations_contract(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase4_operations_134.run_contract_check(package_id=form.get("package_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"Connector Contract: {result['status']} · Blocker {result['blocker_count']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/signer")
    async def operations_signer(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase4_operations_134.add_trusted_signer(label=form.get("label", ""), public_key_b64=form.get("public_key_b64", ""), actor=request_actor(request), confirmation=form.get("confirmation", ""))
            return RedirectResponse(_link("operations", case_id, message=f"Trusted Signer gespeichert: {result['fingerprint_sha256']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/manifest")
    async def operations_manifest(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase4_operations_134.register_manifest(manifest_json=form.get("manifest_json", ""), signature_b64=form.get("signature_b64", ""), signer_fingerprint=form.get("signer_fingerprint", ""), actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"Connector-Manifest registriert: {result['trust_state']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/advice")
    async def operations_advice(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase4_operations_134.generate_connector_advice(case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""), actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"Lokale Connector-Empfehlung erstellt: {len(result['recommended_connectors'])} Vorschläge"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/build136-diagnostics")
    async def operations_build136_diagnostics(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build136.run_runtime_diagnostics(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"Build-136-Diagnose: {result['status']} · {result['score']}/100 · {result['blocker_count']} Blocker."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/build136-repair")
    async def operations_build136_repair(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build136.repair_browser_session(
                case_id=case_id,
                action=form.get("action", ""),
                confirmation=form.get("confirmation", ""),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("operations", case_id, message=f"Firefox-Recovery abgeschlossen: {result['action']} · {result['before']} → {result['after']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/build135-health")
    async def operations_build135_health(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build135.run_all_health(actor=request_actor(request), live_limit=20)
            counts = ", ".join(f"{key}: {value}" for key, value in sorted(result.get("counts", {}).items()))
            return RedirectResponse(_link("operations", case_id, message=f"Build-135 Health geprüft: {result['checked']} Zugänge · {counts}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/build135-route")
    async def operations_build135_route(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build135.route_sources(case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""), actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"AI Source Route 2.0: {len(result['recommendations'])} candidate-only Vorschläge · 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.post("/operations/build135-contradictions")
    async def operations_build135_contradictions(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build135.analyze_contradictions(case_id=case_id, target_id=form.get("target_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("operations", case_id, message=f"Profilanalyse abgeschlossen: {len(result.get('contradictions', []))} offene Widersprüche."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("operations", case_id, error=str(exc)), status_code=303)

    @app.get("/api/build342")
    def api_build342(request: Request):
        require_auth(request)
        return JSONResponse(ctx.build342.dashboard())

    @app.get("/api/build341")
    def api_build341(request: Request):
        require_auth(request)
        return JSONResponse(ctx.build341.dashboard())

    @app.get("/api/build135")
    def api_build135(request: Request, case_id: str = ""):
        require_auth(request)
        return JSONResponse(ctx.build135.dashboard(case_id))

    @app.get("/api/build136")
    def api_build136(request: Request, case_id: str = ""):
        require_auth(request)
        return JSONResponse(ctx.build136.dashboard(case_id))

    @app.get("/api/build138")
    def api_build138(request: Request, case_id: str = ""):
        require_auth(request)
        return JSONResponse(ctx.build138.dashboard(case_id))

    @app.get("/api/build137")
    def api_build137(request: Request, case_id: str = ""):
        require_auth(request)
        return JSONResponse(ctx.build137.dashboard(case_id))

    @app.get("/api/phase4operations134")
    def operations_api(request: Request, case_id: str = ""):
        require_auth(request)
        return JSONResponse(ctx.phase4_operations_134.dashboard(case_id))

    @app.post("/phase3-release/gate")
    async def phase3_release_gate(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase3_production_candidate_133.run_gate(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("release", case_id, message=f"Phase-3 Gate: {result['status']} · Score {result['score']}/100 · {result['blocker_count']} Blocker · {result['warning_count']} Hinweise"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/phase3-release/ai-opsec")
    async def phase3_ai_opsec(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase3_production_candidate_133.create_ai_opsec_assessment(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("release", case_id, message=f"Lokaler AI-/OPSEC-Brief erzeugt: {result['assessment_id']} · 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/phase3-release/field-validation")
    async def phase3_field_validation(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.phase3_production_candidate_133.record_field_validation(
                component_key=form.get("component_key", ""), platform_key=form.get("platform_key", ""),
                status=form.get("status", "not_run"), actor=request_actor(request), notes=form.get("notes", ""),
                evidence_fingerprint=form.get("evidence_fingerprint", ""),
            )
            return RedirectResponse(_link("release", case_id, message=f"Feldabnahme gespeichert: {result['component_key']} · {result['status']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/phase3-release/freeze")
    async def phase3_release_freeze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        if form.get("confirmation", "").strip() != "PHASE 3 EINFRIEREN":
            return RedirectResponse(_link("release", case_id, error="Bestätigung PHASE 3 EINFRIEREN fehlt."), status_code=303)
        try:
            result = ctx.phase3_production_candidate_133.prepare_freeze(case_id=case_id, actor=request_actor(request), notes=form.get("notes", ""))
            return RedirectResponse(_link("release", case_id, message=f"Phase-3-Freeze erzeugt: {result['freeze_id']} · Status {result['status']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/release/gate")
    async def release_gate(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.production_candidate_126.run_gate(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("release", case_id, message=f"Production Gate: {result['status']} · Score {result['score']}/100 · {result['blocker_count']} Blocker · {result['warning_count']} Hinweise"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/release/freeze")
    async def release_freeze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        if form.get("confirmation", "").strip() != "PHASE 2 EINFRIEREN":
            return RedirectResponse(_link("release", case_id, error="Bestätigung PHASE 2 EINFRIEREN fehlt."), status_code=303)
        try:
            result = ctx.production_candidate_126.prepare_freeze(case_id=case_id, actor=request_actor(request), notes=form.get("notes", ""))
            return RedirectResponse(_link("release", case_id, message=f"Phase-2-Freeze erzeugt: {result['freeze_id']} · Backup {result['backup_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/release/install-shortcut")
    async def release_install_shortcut(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        if form.get("confirmation", "").strip() != "VERKNÜPFUNG ERSTELLEN":
            return RedirectResponse(_link("release", case_id, error="Bestätigung VERKNÜPFUNG ERSTELLEN fehlt."), status_code=303)
        try:
            result = ctx.production_candidate_126.create_windows_shortcut(actor=request_actor(request), include_start_menu=bool(form.get("include_start_menu")))
            return RedirectResponse(_link("release", case_id, message=f"Windows-Verknüpfung eingerichtet: {result.get('desktop_path') or 'Desktop'}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("release", case_id, error=str(exc)), status_code=303)

    @app.post("/workspace/intake/decision")
    async def intake_decision(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.investigation_workspace_122.decide_intake(
                case_id=case_id, intake_id=form.get("intake_id", ""), decision=form.get("decision", ""),
                actor=request_actor(request), reason=form.get("reason", ""),
            )
            return RedirectResponse(_link("intake", case_id, message=f"Intake-Entscheidung gespeichert: {result['decision']}"), status_code=303)
        except WorkspaceConflictError as exc:
            return RedirectResponse(_link("intake", case_id, error=f"Konflikt: {exc}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("intake", case_id, error=str(exc)), status_code=303)

    @app.get("/workspace/detail/{object_type}/{object_id}", response_class=HTMLResponse)
    def detail(request: Request, object_type: str, object_id: str, case_id: str):
        require_auth(request)
        try:
            result = ctx.investigation_workspace_122.detail(case_id, object_type, object_id, actor=request_actor(request))
            record = json.dumps(result["record"], ensure_ascii=False, indent=2, default=str)
            limitations = "".join(f"<li>{_esc(x)}</li>" for x in result["explainability"]["limitations"])
            back_tab = {"intake":"intake","evidence":"evidence","entity":"entities","relation":"graph","timeline":"timeline","contradiction":"contradictions"}.get(object_type, "overview")
            body = f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Objektdetail · EagleEye</title><style>{CSS}</style></head><body><main class="main" style="max-width:1100px;margin:auto"><p><a class="button ghost" href="{_link(back_tab, case_id)}">← Zurück</a></p><div class="notice warn"><b>Explainability:</b> Anzeige gespeicherter Daten ≠ unabhängige Wahrheitsprüfung.<ul>{limitations}</ul></div><div class="panel"><h2>{_esc(object_type)} · {_esc(object_id)}</h2><pre>{_esc(record)}</pre></div></main></body></html>'''
            return HTMLResponse(body)
        except WorkspaceValidationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/graph123")
    def api_graph123(request: Request, case_id: str, q: str = "", limit_nodes: int = 600, limit_edges: int = 1200):
        require_auth(request)
        return ctx.scale_performance_123.graph_payload(case_id, query=q, limit_nodes=limit_nodes, limit_edges=limit_edges)

    @app.get("/api/workspace/snapshot")
    def api_snapshot(request: Request, case_id: str):
        require_auth(request)
        return ctx.investigation_workspace_122.case_snapshot(case_id)

    @app.get("/api/workspace/intake")
    def api_intake(request: Request, case_id: str, status: str = "new", limit: int = 100):
        require_auth(request)
        return ctx.investigation_workspace_122.intake(case_id, status=status, limit=limit)

    @app.post("/governance/password")
    async def governance_password(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.set_password(
                username=form.get("username", governance.OWNER_USERNAME),
                passphrase=form.get("passphrase", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Passphrase für {result['username']} gesetzt; vorhandene Sitzungen wurden widerrufen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/user/create")
    async def governance_user_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.create_user(
                username=form.get("username", ""), display_name=form.get("display_name", ""),
                role_key=form.get("role_key", "investigator"), passphrase=form.get("passphrase", ""),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Governance-Benutzer angelegt: {result['username']} · {result['role_key']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/user/status")
    async def governance_user_status(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.set_user_active(
                username=form.get("username", ""), active=form.get("active", "") == "1",
                actor=request_actor(request),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Benutzerstatus aktualisiert: {result['username']} · aktiv={bool(result['active'])}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/team-mode/enable")
    async def governance_team_enable(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            governance.enable_team_mode(actor=request_actor(request), confirmation=form.get("confirmation", ""))
            response = RedirectResponse("/governance/login", status_code=303)
            response.delete_cookie("ee_governance_session", path="/")
            return response
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/team-mode/disable")
    async def governance_team_disable(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            governance.disable_team_mode(actor=request_actor(request), confirmation=form.get("confirmation", ""))
            response = RedirectResponse(_link("governance", case_id, message="Teammodus deaktiviert; alle Governance-Sitzungen wurden widerrufen."), status_code=303)
            response.delete_cookie("ee_governance_session", path="/")
            return response
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/assignment/create")
    async def governance_assignment_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.assign_case(
                case_id=case_id, username=form.get("username", ""), role_key=form.get("role_key", "investigator"),
                actor=request_actor(request), notes=form.get("notes", ""),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Fallzuweisung gespeichert: {result['role_key']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/assignment/revoke")
    async def governance_assignment_revoke(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            governance.revoke_case_assignment(assignment_id=form.get("assignment_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("governance", case_id, message="Fallzuweisung widerrufen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/approval/decide")
    async def governance_approval_decide(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.decide_approval(
                request_id=form.get("request_id", ""), decision=form.get("decision", ""),
                reason=form.get("reason", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Vier-Augen-Entscheidung gespeichert: {result['status']} · Ausführung {result['execution_status']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/lock/acquire")
    async def governance_lock_acquire(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.acquire_lock(
                case_id=case_id, object_type=form.get("object_type", ""), object_id=form.get("object_id", ""),
                purpose=form.get("purpose", ""), ttl_minutes=int(form.get("ttl_minutes", "15") or 15),
                actor=request_actor(request),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Objekt gesperrt: {result['object_type']}:{result['object_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/lock/release")
    async def governance_lock_release(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            governance.release_lock(lock_id=form.get("lock_id", ""), actor=request_actor(request), force=bool(form.get("force")))
            return RedirectResponse(_link("governance", case_id, message="Objektsperre gelöst."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/comment")
    async def governance_comment(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.add_comment(
                case_id=case_id, object_type=form.get("object_type", "case"), object_id=form.get("object_id", case_id),
                text=form.get("text", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("governance", case_id, message=f"Kommentar gespeichert: {result['comment_id']}"), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/brief")
    async def governance_brief(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = governance.generate_reviewer_brief(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("governance", case_id, message=f"Lokaler Governance-Brief erzeugt: {len(result['recommendations'])} Empfehlungen · 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.post("/governance/session/revoke")
    async def governance_session_revoke(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            governance.revoke_session(session_id=form.get("session_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("governance", case_id, message="Governance-Sitzung widerrufen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("governance", case_id, error=str(exc)), status_code=303)

    @app.get("/api/governance132")
    def api_governance132(request: Request, case_id: str):
        require_auth(request)
        return governance.dashboard(case_id, actor=request_actor(request))


    @app.post("/identity139/candidate")
    async def identity139_candidate(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            attrs = {key: form.get(key, "") for key in ("name", "birth_date", "age", "occupation", "organization", "location", "username", "email", "domain") if form.get(key, "").strip()}
            result = ctx.build139.create_identity_candidate(
                case_id=case_id, target_id=form.get("target_id", ""), label=form.get("label", ""), attributes=attrs,
                source_refs=[v.strip() for v in form.get("source_refs", "").replace(";", ",").split(",") if v.strip()],
                actor=request_actor(request),
            )
            return RedirectResponse(_link("identity139", case_id, message=f"Identitätskandidat angelegt: {result['label']}; noch keine Identitätsentscheidung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("identity139", case_id, error=str(exc)), status_code=303)

    @app.post("/identity139/compare")
    async def identity139_compare(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build139.compare_identity_candidate(case_id=case_id, candidate_id=form.get("candidate_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("identity139", case_id, message=f"Nichtbiometrischer Vergleich: {result['result_band']} · Score {result['overall_score']}; Gesichtsmerkmale 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("identity139", case_id, error=str(exc)), status_code=303)

    @app.post("/identity139/decision")
    async def identity139_decision(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build139.decide_identity_candidate(
                case_id=case_id, candidate_id=form.get("candidate_id", ""), decision=form.get("decision", "requires_more_evidence"),
                rationale=form.get("rationale", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request),
            )
            return RedirectResponse(_link("identity139", case_id, message=f"Manuelle Identitätsbewertung gespeichert: {result['decision']}; keine automatische Fusion."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("identity139", case_id, error=str(exc)), status_code=303)

    @app.post("/identity139/brief")
    async def identity139_brief(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build139.generate_ai_brief(case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""), actor=request_actor(request))
            return RedirectResponse(_link("identity139", case_id, message=f"Lokaler Ermittlungsbrief erzeugt: {len(result['facts'])} Fakten, {len(result['hypotheses'])} Hypothesen, 0 externe AI-Aufrufe."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("identity139", case_id, error=str(exc)), status_code=303)

    @app.post("/identity139/opsec")
    async def identity139_opsec(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build139.assess_opsec(
                case_id=case_id, target_id=form.get("target_id", ""), action_type=form.get("action_type", "web_search"),
                purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""),
                data_classes=[v.strip() for v in form.get("data_classes", "").replace(";", ",").split(",") if v.strip()],
                actor=request_actor(request),
            )
            status = "blockiert" if result["blocked"] else "freigegeben"
            return RedirectResponse(_link("identity139", case_id, message=f"OPSEC-Prüfung: {result['risk_level']} · {status}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("identity139", case_id, error=str(exc)), status_code=303)

    @app.post("/photos139/detect")
    async def photos139_detect(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build139.detect_faces(case_id=case_id, asset_id=form.get("asset_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Lokale Gesichtsbereichsanalyse: {result['face_count']} Bereich(e), 0 Templates, 0 Identitätsvergleiche."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.get("/api/photo139/face/{detection_id}")
    def photo139_face_file(request: Request, detection_id: str, case_id: str):
        require_auth(request)
        try:
            row, path = ctx.build139.face_crop_path(case_id=case_id, detection_id=detection_id)
            return FileResponse(path, media_type="image/jpeg", filename=f"face-region-{detection_id}.jpg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'"})
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/photos139/face-runs")
    async def photos139_face_runs(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            providers = [key for key in ("google_lens", "bing_visual", "tineye", "yandex_images") if form.get(f"provider_{key}") == "1"]
            result = ctx.build139.create_face_research_runs(case_id=case_id, detection_id=form.get("detection_id", ""), provider_keys=providers, purpose=form.get("purpose", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Gesichtsausschnitt-Recherche vorbereitet: {result['run_count']} manuelle Läufe, 0 Uploads, 0 Identitätsaussagen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos139/face-launch")
    async def photos139_face_launch(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            port = request.url.port or 80
            result = ctx.build139.launch_face_research_run(case_id=case_id, run_id=form.get("run_id", ""), actor=request_actor(request), local_redirect_origin=f"http://127.0.0.1:{port}")
            return RedirectResponse(_link("photos", case_id, message=f"Bildsuchanbieter im isolierten Fallbrowser geöffnet ({result['dispatch_mode']}); Upload bleibt manuell."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos139/person-link")
    async def photos139_person_link(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            basis = [key for key in ("official_profile_context", "caption_names_person", "source_page_names_person", "exact_image_provenance", "timeline_compatible", "caption_names_other_person") if form.get(f"basis_{key}") == "1"]
            result = ctx.build139.assess_photo_person_link(case_id=case_id, target_id=form.get("target_id", ""), asset_id=form.get("asset_id", ""), basis=basis, actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Foto-Person-Hypothese bewertet: Support {result['support_score']}, Konflikt {result['conflict_score']}; Face Match 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)


    @app.post("/assistant140/analyze")
    async def assistant140_analyze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.generate_evidence_analysis(case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""), actor=request_actor(request))
            return RedirectResponse(_link("assistant140", case_id, message=f"Beleggebundene Analyse erzeugt: {len(result['claims'])} Aussagen, {len(result['recommendations'])} priorisierte Schritte, 0 externe AI-Aufrufe."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant140", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant140/claim-review")
    async def assistant140_claim_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.review_claim(case_id=case_id, claim_id=form.get("claim_id", ""), review_status=form.get("review_status", "unreviewed"), review_note=form.get("review_note", ""), actor=request_actor(request))
            return RedirectResponse(_link("assistant140", case_id, message=f"AI-Aussage manuell geprüft: {result['review_status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant140", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant140/plan")
    async def assistant140_plan(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.create_opsec_action_plan(case_id=case_id, analysis_id=form.get("analysis_id", ""), recommendation_ids=[form.get("recommendation_id", "")], purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), actor=request_actor(request))
            status = "blockiert" if result["blocked"] else "prüfbereit"
            return RedirectResponse(_link("assistant140", case_id, message=f"OPSEC-Aktionsplan: {result['risk_level']} · {status} · 0 externe Aktionen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant140", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant140/plan-review")
    async def assistant140_plan_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.approve_opsec_plan(case_id=case_id, plan_id=form.get("plan_id", ""), decision=form.get("decision", "approved"), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("assistant140", case_id, message=f"OPSEC-Plan manuell bewertet: {result['approval_status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant140", case_id, error=str(exc)), status_code=303)

    @app.post("/assistant140/disclosure")
    async def assistant140_disclosure(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.create_disclosure_package(case_id=case_id, analysis_id=form.get("analysis_id", ""), claim_ids=[form.get("claim_id", "")], destination_type=form.get("destination_type", "human_reviewer"), destination_label=form.get("destination_label", ""), purpose=form.get("purpose", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("assistant140", case_id, message=f"Minimiertes Offenlegungspaket erzeugt: {result['anchor_count']} Anker, keine Bilder/Biometrie, keine Übertragung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("assistant140", case_id, error=str(exc)), status_code=303)

    @app.post("/photos140/analyze")
    async def photos140_analyze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.analyze_image(case_id=case_id, asset_id=form.get("asset_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Lokale Bildanalyse: Qualität {result['quality_band']}, {len(result['anomaly_hints'])} technische Hinweise, 0 Manipulationsbehauptungen."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos140/compare")
    async def photos140_compare(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build140.compare_images(case_id=case_id, reference_asset_id=form.get("reference_asset_id", ""), compared_asset_id=form.get("compared_asset_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Bildvergleich: {result['relation_band']}; Identitätsaussage 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)


    @app.post("/reports142/create")
    async def reports142_create(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build142.create_report(case_id=case_id, target_id=form.get("target_id", ""), source_report131_id=form.get("source_report131_id", ""), report_type=form.get("report_type", "full_investigation"), title=form.get("title", ""), audience=form.get("audience", "internal"), redaction_profile=form.get("redaction_profile", "internal_full"), actor=request_actor(request))
            row = result["report"]
            return RedirectResponse(_link("reports142", case_id, message=f"Bericht erzeugt: {row['report142_id']} · Zitierabdeckung {round(float(row['citation_coverage'])*100)}%."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reports142", case_id, error=str(exc)), status_code=303)

    @app.post("/reports142/request-review")
    async def reports142_request_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            ctx.build142.request_review(case_id=case_id, report_id=form.get("report_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("reports142", case_id, message="Bericht zur Vier-Augen-Prüfung eingereicht."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reports142", case_id, error=str(exc)), status_code=303)

    @app.post("/reports142/review")
    async def reports142_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build142.review_report(case_id=case_id, report_id=form.get("report_id", ""), decision=form.get("decision", "approved"), reason=form.get("reason", ""), actor=request_actor(request))
            return RedirectResponse(_link("reports142", case_id, message=f"Review gespeichert: {result['report']['review_decision']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reports142", case_id, error=str(exc)), status_code=303)

    @app.post("/reports142/release")
    async def reports142_release(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build142.release_report(case_id=case_id, report_id=form.get("report_id", ""), release_label=form.get("release_label", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("reports142", case_id, message=f"Release {result['release']['release_no']} erzeugt: Manifest {result['release']['manifest_sha256'][:16]}..."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reports142", case_id, error=str(exc)), status_code=303)

    @app.post("/reports142/verify")
    async def reports142_verify(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build142.verify_release(case_id=case_id, release_id=form.get("release_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("reports142", case_id, message=f"Integritätsprüfung: {result['status']} · {result['checked_files']} Dateien."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("reports142", case_id, error=str(exc)), status_code=303)

    @app.get("/api/report142")
    def api_report142(request: Request, case_id: str, report_id: str):
        require_auth(request)
        return ctx.build142.get_report(case_id=case_id, report_id=report_id)

    @app.get("/reports142/download")
    def reports142_download(request: Request, case_id: str, release_id: str, file_role: str):
        require_auth(request)
        path, mime = ctx.build142.export_file(case_id=case_id, release_id=release_id, file_role=file_role)
        return FileResponse(path, media_type=mime, filename=path.name)

    @app.post("/security143/persona")
    async def security143_persona(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.create_persona(case_id=case_id, label=form.get("label", ""), persona_type=form.get("persona_type", "synthetic_alias"), purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), contact_alias=form.get("contact_alias", ""), risk_level=form.get("risk_level", "medium"), synthetic_identity_confirmed=form.get("synthetic_identity_confirmed") == "1", no_existing_person_impersonation=form.get("no_existing_person_impersonation") == "1", actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Research-Persona angelegt: {result['label']} · Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/persona-review")
    async def security143_persona_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.review_persona(case_id=case_id, persona_id=form.get("persona_id", ""), decision=form.get("decision", "approved"), reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Persona-Review: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/account")
    async def security143_account(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.add_persona_account(case_id=case_id, persona_id=form.get("persona_id", ""), platform=form.get("platform", ""), account_label=form.get("account_label", ""), username_alias=form.get("username_alias", ""), email_alias=form.get("email_alias", ""), account_origin=form.get("account_origin", "manual_existing"), terms_reviewed=form.get("terms_reviewed") == "1", credential_secret=form.get("credential_secret", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Alias-Account registriert: {result['platform']} · keine automatische Kontoerstellung."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/egress")
    async def security143_egress(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.create_egress_profile(case_id=case_id, label=form.get("label", ""), mode=form.get("mode", "socks5"), proxy_host=form.get("proxy_host", ""), proxy_port=int(form.get("proxy_port") or 0), remote_dns=form.get("remote_dns") == "1", requires_auth=form.get("requires_auth") == "1", credential_secret=form.get("credential_secret", ""), risk_note=form.get("risk_note", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Egress-Profil angelegt: {result['label']} · Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/egress-review")
    async def security143_egress_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.review_egress(case_id=case_id, egress_id=form.get("egress_id", ""), decision=form.get("decision", "approved"), reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Egress-Review: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/session")
    async def security143_session(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.plan_session(case_id=case_id, persona_id=form.get("persona_id", ""), account_id=form.get("account_id", ""), egress_id=form.get("egress_id", ""), purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), start_url=form.get("start_url", ""), require_origin_separation=form.get("require_origin_separation") == "1", max_actions=int(form.get("max_actions") or 20), duration_minutes=int(form.get("duration_minutes") or 60), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Research-Sitzung geplant: {result['session_id']} · Preflight erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/session-request")
    async def security143_session_request(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.request_session_approval(case_id=case_id, session_id=form.get("session_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"OPSEC-Preflight bestanden; Sitzung {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/session-approve")
    async def security143_session_approve(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.approve_session(case_id=case_id, session_id=form.get("session_id", ""), reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Research-Sitzung {result['status']} · Start bleibt manuell."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/session-start")
    async def security143_session_start(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.start_session(case_id=case_id, session_id=form.get("session_id", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Temporärer isolierter Sitzungsbrowser gestartet: {result['session']['egress_mode']} · keine Anonymitätsgarantie."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/session-action")
    async def security143_session_action(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.record_session_action(case_id=case_id, session_id=form.get("session_id", ""), action_type=form.get("action_type", "browse"), destination_url=form.get("destination_url", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Manueller Sitzungsschritt dokumentiert: {result['session']['consumed_actions']}/{result['session']['max_actions']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/session-close")
    async def security143_session_close(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.close_session(case_id=case_id, session_id=form.get("session_id", ""), reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Research-Sitzung geschlossen; temporäres Profil entfernt: {result['profile_removed']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.post("/security143/access-review")
    async def security143_access_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build143.attest_case_access(case_id=case_id, assignment_id=form.get("assignment_id", ""), decision=form.get("decision", "retain"), reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("security143", case_id, message=f"Fallzugriff geprüft: {result['decision']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("security143", case_id, error=str(exc)), status_code=303)

    @app.get("/api/security143")
    def api_security143(request: Request, case_id: str):
        require_auth(request)
        return ctx.build143.dashboard(case_id)


    @app.post("/final144/audit")
    async def final144_audit(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build144.run_full_audit(case_id=case_id, include_optional=form.get("include_optional") == "1", actor=request_actor(request))
            return RedirectResponse(_link("final144", case_id, message=f"RC-Audit: {result['status']} · Score {result['score']} · Blocker {result['blocker_count']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final144", case_id, error=str(exc)), status_code=303)

    @app.post("/final144/backup")
    async def final144_backup(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build144.create_verified_backup(case_id=case_id, confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("final144", case_id, message=f"Backup: {result['status']} · Restore {result['restore_status']} · {result['artifact_count']} Artefakte."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final144", case_id, error=str(exc)), status_code=303)

    @app.get("/api/final144")
    def api_final144(request: Request, case_id: str):
        require_auth(request)
        return ctx.build144.dashboard(case_id)


    @app.post("/final145/maintenance")
    async def final145_maintenance(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build145.run_maintenance(case_id=case_id, dry_run=form.get("apply") != "1", confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("final145", case_id, message=f"Wartung: {result['status']} · Derivate entfernt {result['estimated_savings']['expired_derivatives_removed']} · Aufgaben gelöscht 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final145", case_id, error=str(exc)), status_code=303)

    @app.post("/final145/health")
    async def final145_health(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build145.create_health_snapshot(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("final145", case_id, message=f"Phase-4-Gesundheit: {result['status']} · Score {result['score']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final145", case_id, error=str(exc)), status_code=303)

    @app.post("/final145/baseline")
    async def final145_baseline(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build145.create_baseline(case_id=case_id, baseline_label=form.get("baseline_label", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("final145", case_id, message=f"Baseline {result['baseline145_id']} erstellt · unabhängiges Review erforderlich."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final145", case_id, error=str(exc)), status_code=303)

    @app.post("/final145/review")
    async def final145_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build145.review_baseline(case_id=case_id, baseline_id=form.get("baseline_id", ""), decision=form.get("decision", "approved"), reason=form.get("reason", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("final145", case_id, message=f"Baseline-Review: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final145", case_id, error=str(exc)), status_code=303)

    @app.post("/final145/seal")
    async def final145_seal(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build145.seal_baseline(case_id=case_id, baseline_id=form.get("baseline_id", ""), confirmation=form.get("confirmation", ""), actor=request_actor(request))
            return RedirectResponse(_link("final145", case_id, message=f"Phase 4 versiegelt: {result['seal']['seal145_id']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final145", case_id, error=str(exc)), status_code=303)

    @app.post("/final145/verify")
    async def final145_verify(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build145.verify_seal(case_id=case_id, seal_id=form.get("seal_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("final145", case_id, message=f"Seal-Integrität: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("final145", case_id, error=str(exc)), status_code=303)

    @app.get("/api/final145")
    def api_final145(request: Request, case_id: str):
        require_auth(request)
        return ctx.build145.dashboard(case_id)


    @app.post("/quality141/case-scan")
    async def quality141_case_scan(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            findings = ctx.build141.analyze_case_source_risks(case_id=case_id, actor=request_actor(request))
            return RedirectResponse(_link("quality141", case_id, message=f"Quellenqualitaet aktualisiert: {len(findings)} offene Risiken."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("quality141", case_id, error=str(exc)), status_code=303)

    @app.post("/quality141/snapshot")
    async def quality141_snapshot(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            raw_status = form.get("http_status", "")
            status = int(raw_status) if raw_status.strip() else None
            result = ctx.build141.record_source_snapshot(case_id=case_id, source_id=form.get("source_id", ""), observed_url=form.get("observed_url", ""), observed_title=form.get("observed_title", ""), observed_text=form.get("observed_text", ""), http_status=status, actor=request_actor(request))
            return RedirectResponse(_link("quality141", case_id, message=f"Quellen-Snapshot gespeichert; Aenderungen: {', '.join(result['change_types']) or 'keine'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("quality141", case_id, error=str(exc)), status_code=303)

    @app.post("/quality141/change-review")
    async def quality141_change_review(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build141.review_source_change(case_id=case_id, change_id=form.get("change_id", ""), status=form.get("status", "acknowledged"), actor=request_actor(request))
            return RedirectResponse(_link("quality141", case_id, message=f"Quellenaenderung bewertet: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("quality141", case_id, error=str(exc)), status_code=303)

    @app.post("/quality141/analyze")
    async def quality141_analyze(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build141.generate_change_aware_analysis(case_id=case_id, target_id=form.get("target_id", ""), objective=form.get("objective", ""), actor=request_actor(request))
            return RedirectResponse(_link("quality141", case_id, message=f"Change-aware Analyse erstellt: Qualitaet {round(result['evidence_quality_score']*100)}%, externe AI 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("quality141", case_id, error=str(exc)), status_code=303)

    @app.post("/quality141/envelope")
    async def quality141_envelope(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            actions = [v.strip() for v in form.get("action_types", "").split(",") if v.strip()]
            classes = [v.strip() for v in form.get("data_classes", "").split(",") if v.strip()]
            result = ctx.build141.create_opsec_envelope(case_id=case_id, target_id=form.get("target_id", ""), purpose=form.get("purpose", ""), legal_basis=form.get("legal_basis", ""), destination_type=form.get("destination_type", "guided_browser"), destination_label=form.get("destination_label", ""), action_types=actions, data_classes=classes, max_identity_anchors=int(form.get("max_identity_anchors", "0") or 0), max_external_actions=int(form.get("max_external_actions", "0") or 0), ttl_minutes=int(form.get("ttl_minutes", "30") or 30), actor=request_actor(request))
            return RedirectResponse(_link("quality141", case_id, message=f"OPSEC-Fenster erstellt: {result['risk_level']}, {'blockiert' if result['blocked'] else 'Entwurf'}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("quality141", case_id, error=str(exc)), status_code=303)

    @app.post("/quality141/optimize")
    async def quality141_optimize(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build141.optimize_workflow(case_id=case_id, workflow_id=form.get("workflow_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("quality141", case_id, message=f"Workflow-Dry-Run: {len(result['recommendations'])} sichere Empfehlungen, Potenzial {result['estimated_minutes_saved']} Minuten."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("quality141", case_id, error=str(exc)), status_code=303)

    @app.post("/photos141/result-quality")
    async def photos141_result_quality(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build141.assess_photo_result(case_id=case_id, result_id=form.get("result_id", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Fototreffer bewertet: {result['quality_band']} ({round(result['overall_score']*100)}%), Identitaetsaussage 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)

    @app.post("/photos141/plan")
    async def photos141_plan(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "")
        try:
            result = ctx.build141.plan_photo_research(case_id=case_id, asset_id=form.get("asset_id", ""), purpose=form.get("purpose", ""), actor=request_actor(request))
            return RedirectResponse(_link("photos", case_id, message=f"Fotorechercheplan: {result['provider_diversity']} Anbieter, {result['redundant_steps_removed']} redundante Schritte entfernt, Auto-Uploads 0."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("photos", case_id, error=str(exc)), status_code=303)


    @app.get("/monitor210")
    async def monitor210_dashboard(request: Request, case_id: str = "default"):
        require_auth(request)
        return RedirectResponse(_link("monitor210", case_id), status_code=303)

    @app.post("/monitor210/schedule")
    async def monitor210_schedule(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "default")
        try:
            sources = [v.strip() for v in form.get("source_ids", "").split(",") if v.strip()]
            result = ctx.build210.create_schedule(
                case_id=case_id, name=form.get("name", ""), question=form.get("question", ""),
                source_ids=sources, interval_minutes=int(form.get("interval_minutes", "60") or 60),
                misfire_policy=form.get("misfire_policy", "coalesce"),
                confirmation=f"MONITOR SCHEDULE 210 {case_id} ANLEGEN",
            )
            return RedirectResponse(_link("monitor210", case_id, message=f"Monitoring-Schedule {result['schedule_id']} als Entwurf angelegt."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("monitor210", case_id, error=str(exc)), status_code=303)

    @app.post("/monitor210/schedule-action")
    async def monitor210_schedule_action(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "default"); schedule_id = form.get("schedule_id", ""); action = form.get("action", "")
        try:
            if action == "activate":
                result = ctx.build210.activate_schedule(schedule_id=schedule_id, approved_by=request_actor(request), confirmation=f"MONITOR SCHEDULE 210 {schedule_id} AKTIVIEREN")
            elif action == "pause":
                result = ctx.build210.pause_schedule(schedule_id=schedule_id, reason="analyst workspace", confirmation=f"MONITOR SCHEDULE 210 {schedule_id} PAUSIEREN")
            elif action == "run":
                result = ctx.build210.trigger_run(schedule_id=schedule_id, confirmation=f"MONITOR RUN 210 {schedule_id} STARTEN")
            else:
                raise ValueError("unknown action")
            return RedirectResponse(_link("monitor210", case_id, message=f"Monitoring-Aktion abgeschlossen: {result.get('status', action)}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("monitor210", case_id, error=str(exc)), status_code=303)

    @app.post("/monitor210/alert")
    async def monitor210_alert(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "default"); alert_id = form.get("alert_id", "")
        try:
            result = ctx.build210.acknowledge_alert(alert_id=alert_id, analyst=request_actor(request), decision=form.get("decision", ""), confirmation=f"ALERT 210 {alert_id} BEARBEITEN")
            return RedirectResponse(_link("monitor210", case_id, message=f"Alert-Entscheidung gespeichert: {result['status']}."), status_code=303)
        except Exception as exc:
            return RedirectResponse(_link("monitor210", case_id, error=str(exc)), status_code=303)

    @app.get("/agents208", response_class=HTMLResponse)
    async def agents208_dashboard(request: Request, case_id: str = "default"):
        require_auth(request)
        return HTMLResponse(ctx.build208.render_dashboard(case_id=case_id))


    @app.get("/agents209", response_class=HTMLResponse)
    async def agents209_dashboard(request: Request, case_id: str = "default"):
        require_auth(request)
        return HTMLResponse(ctx.build209.render_dashboard(case_id=case_id))

    @app.post("/agents209/run")
    async def agents209_run(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        case_id = form.get("case_id", "default")
        try:
            ctx.build209.create_collection_run(case_id=case_id, question=form.get("question", ""), source_ids=[], languages=["de","en"], max_tokens=100000, max_cost=10.0, confirmation=f"COLLECTION RUN 209 {case_id} ANLEGEN")
            return RedirectResponse(f"/agents209?case_id={case_id}", status_code=303)
        except Exception as exc:
            return RedirectResponse(f"/agents209?case_id={case_id}&error={str(exc)}", status_code=303)

    @app.post("/agents209/job")
    async def agents209_job(request: Request):
        require_auth(request)
        form = await _form(request); verify_csrf(form, request)
        job_id=form.get("job_id", ""); action=form.get("action", "")
        if action == "interrupt":
            ctx.db.execute("UPDATE collection_jobs_209 SET status='interrupted',updated_at=? WHERE job_id=?", (now_ts(), job_id))
        elif action == "resume":
            ctx.db.execute("UPDATE collection_jobs_209 SET status='queued',worker_id=NULL,updated_at=? WHERE job_id=?", (now_ts(), job_id))
        elif action == "approve":
            ctx.db.execute("UPDATE collection_jobs_209 SET status=CASE WHEN status='blocked' THEN 'queued' ELSE status END,updated_at=? WHERE job_id=?", (now_ts(), job_id))
        return RedirectResponse("/agents209", status_code=303)


    @app.middleware("http")
    async def build146_security_edge(request: Request, call_next):
        """Outermost loopback/origin/header boundary, including auth redirects."""
        raw_host = (request.headers.get("host") or "").strip().lower()
        if raw_host.startswith("[") and "]" in raw_host:
            host_header = raw_host[1:raw_host.index("]")]
        elif raw_host.count(":") == 1:
            host_header = raw_host.rsplit(":", 1)[0]
        else:
            host_header = raw_host.strip("[]")
        client_host = (request.client.host if request.client else "").strip("[]").lower()
        if host_header not in ALLOWED_HOSTS or client_host not in ALLOWED_HOSTS | {"testclient"}:
            response: Response = JSONResponse({"detail": "Loopback access only"}, status_code=403)
        else:
            companion_path = request.url.path in {
                "/api/capture-companion/submit", "/api/capture150/config", "/api/capture150/submit", "/api/firefox-companion/register",
                "/api/firefox-companion/orders", "/api/firefox-companion/ack",
            }
            blocked_response: Response | None = None
            if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                fetch_site = (request.headers.get("sec-fetch-site") or "").casefold()
                origin = (request.headers.get("origin") or "").strip()
                if companion_path:
                    if fetch_site and fetch_site not in {"cross-site", "same-origin", "none"}:
                        blocked_response = JSONResponse({"detail": "Invalid companion fetch metadata"}, status_code=403)
                    elif origin and origin.casefold() != "null":
                        parts = urlsplit(origin)
                        if parts.scheme.casefold() != "moz-extension" or not parts.hostname:
                            blocked_response = JSONResponse({"detail": "Invalid capture companion origin"}, status_code=403)
                else:
                    if fetch_site and fetch_site not in {"same-origin", "none"}:
                        blocked_response = JSONResponse({"detail": "Cross-site state change blocked"}, status_code=403)
                    elif origin and origin.casefold() != "null":
                        parts = urlsplit(origin)
                        if parts.scheme.casefold() != "http" or (parts.hostname or "").casefold() not in ALLOWED_HOSTS:
                            blocked_response = JSONResponse({"detail": "Invalid request origin"}, status_code=403)
            response = blocked_response or await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(), payment=(), browsing-topics=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
        return response



    @app.post("/build242/run-create")
    async def build242_run_create(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.create_run(case_id=case_id,objective=str(form.get("objective","")),priority=int(form.get("priority",50) or 50),max_tokens=int(form.get("max_tokens",20000) or 20000),max_cost=float(form.get("max_cost",0) or 0),actor=actor,confirmation=f"AGENT RUN 242 {case_id} ANLEGEN"))

    @app.post("/build242/task-review")
    async def build242_task_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); tid=str(form.get("task_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.approve_task(task_id=tid,decision=str(form.get("decision","approved")),rationale=str(form.get("rationale","Analyst review for controlled orchestration task.")),reviewer=actor,confirmation=f"AGENT TASK 242 {tid} PRUEFEN"))

    @app.post("/build242/task-start")
    async def build242_task_start(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); tid=str(form.get("task_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.start_task(task_id=tid,worker_id=actor,actor=actor,confirmation=f"AGENT TASK 242 {tid} STARTEN"))

    @app.post("/build242/run-resume")
    async def build242_run_resume(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); rid=str(form.get("run_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.resume_run(run_id=rid,actor=actor,confirmation=f"AGENT RUN 242 {rid} FORTSETZEN"))

    @app.post("/build242/opsec-scan")
    async def build242_opsec_scan(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.scan_case(case_id=case_id,actor=actor,auto_contain=True))

    @app.post("/build242/opsec-observe")
    async def build242_opsec_observe(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.record_observation(case_id=case_id,category=str(form.get("category","other")),severity=str(form.get("severity","medium")),confidence=float(form.get("confidence",.5) or .5),source_type="local_operator_signal",details={"note":str(form.get("details",""))},detector=actor,confirmation=f"OPSEC OBSERVATION 242 {case_id} SPEICHERN"))

    @app.post("/build242/opsec-review")
    async def build242_opsec_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); oid=str(form.get("observation_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.review_observation(observation_id=oid,decision=str(form.get("decision","needs_context")),reviewed_severity=str(form.get("reviewed_severity","medium")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"OPSEC REVIEW 242 {oid} SPEICHERN"))

    @app.post("/build242/opsec-train")
    async def build242_opsec_train(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.stage_training(case_id=case_id,actor=actor,confirmation=f"OPSEC TRAINING 242 {case_id} VORBEREITEN"))

    @app.post("/build242/opsec-calibrate")
    async def build242_opsec_calibrate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.calibrate_policy_candidate(case_id=case_id,actor=actor,confirmation=f"OPSEC CALIBRATION 242 {case_id} ERZEUGEN"))

    @app.post("/build242/opsec-policy-review")
    async def build242_opsec_policy_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); pid=str(form.get("policy_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.review_policy(policy_id=pid,decision=str(form.get("decision","rejected")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"OPSEC POLICY 242 {pid} PRUEFEN"))

    @app.post("/build242/opsec-policy-activate")
    async def build242_opsec_policy_activate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); pid=str(form.get("policy_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build242.activate_policy(policy_id=pid,actor=actor,confirmation=f"OPSEC POLICY 242 {pid} AKTIVIEREN"))


    @app.post("/build243/profile-create")
    async def build243_profile_create(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.propose_profile(case_id=case_id,rationale=str(form.get("rationale","Dedicated case OPSEC profile for controlled investigation workflow.")),actor=actor,confirmation=f"OPSEC PROFILE 243 {case_id} ANLEGEN"))

    @app.post("/build243/profile-review")
    async def build243_profile_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); pid=str(form.get("profile_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.review_profile(profile_id=pid,decision=str(form.get("decision","approved")),rationale=str(form.get("rationale","Independent review of case OPSEC profile controls.")),reviewer=actor,confirmation=f"OPSEC PROFILE 243 {pid} PRUEFEN"))

    @app.post("/build243/profile-activate")
    async def build243_profile_activate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); pid=str(form.get("profile_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.activate_profile(profile_id=pid,actor=actor,confirmation=f"OPSEC PROFILE 243 {pid} AKTIVIEREN"))

    @app.post("/build243/health-scan")
    async def build243_health_scan(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.assess(case_id=case_id,actor=actor,auto_contain=True))

    @app.post("/build243/health-review")
    async def build243_health_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); aid=str(form.get("assessment_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.review_health(assessment_id=aid,decision=str(form.get("decision","needs_context")),rationale=str(form.get("rationale","Independent review of measured OPSEC health assessment.")),reviewer=actor,confirmation=f"OPSEC HEALTH 243 {aid} PRUEFEN"))

    @app.post("/build243/egress-create")
    async def build243_egress_create(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.propose_egress_rule(case_id=case_id,destination_class=str(form.get("destination_class","source")),destination_ref=str(form.get("destination_ref","")),action=str(form.get("action","review")),purpose=str(form.get("purpose","Investigative source access review")),rationale=str(form.get("rationale","External step requires reviewed OPSEC purpose and destination policy.")),actor=actor,confirmation=f"OPSEC EGRESS 243 {case_id} ANLEGEN"))

    @app.post("/build243/egress-review")
    async def build243_egress_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); rid=str(form.get("rule_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.review_egress_rule(rule_id=rid,decision=str(form.get("decision","approved")),rationale=str(form.get("rationale","Independent review of egress policy candidate.")),reviewer=actor,confirmation=f"OPSEC EGRESS 243 {rid} PRUEFEN"))

    @app.post("/build243/secret-ref")
    async def build243_secret_ref(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.register_secret_ref(case_id=case_id,secret_ref=str(form.get("secret_ref","")),scope=str(form.get("scope","case_scoped")),storage_class=str(form.get("storage_class","external_vault")),exposure_status=str(form.get("exposure_status","unknown")),rotation_status=str(form.get("rotation_status","current")),note=str(form.get("note","")),actor=actor,confirmation=f"OPSEC SECRET 243 {case_id} REFERENZIEREN"))

    @app.post("/build243/training-stage")
    async def build243_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build243.stage_training(case_id=case_id,actor=actor,confirmation=f"OPSEC TRAINING 243 {case_id} VORBEREITEN"))

    @app.post("/build244/snapshot")
    async def build244_snapshot(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        return _post_result(request,case_id=case_id,result=ctx.build244.create_snapshot(case_id=case_id,actor=actor,confirmation=f"COCKPIT SNAPSHOT 244 {case_id} SPEICHERN"),tab="cockpit244")

    @app.post("/build244/feedback")
    async def build244_feedback(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build244.record_feedback(case_id=case_id,category=str(form.get("category","ui")),rating=int(form.get("rating",3) or 3),outcome=str(form.get("outcome","mixed")),note=str(form.get("note","")),related_ref=str(form.get("related_ref","")),actor=actor,confirmation=f"COCKPIT FEEDBACK 244 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="cockpit244")

    @app.post("/build244/feedback-review")
    async def build244_feedback_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); fid=str(form.get("feedback_id",""))
        result=ctx.build244.review_feedback(feedback_id=fid,decision=str(form.get("decision","accepted")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"COCKPIT FEEDBACK 244 {fid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="cockpit244")

    @app.post("/build244/training-stage")
    async def build244_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build244.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"COCKPIT TRAINING 244 {case_id} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="cockpit244")

    @app.post("/build245/create")
    async def build245_create(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build245.create_workflow(case_id=case_id,objective=str(form.get("objective","")),primary_question=str(form.get("primary_question","")),owner=str(form.get("owner",actor)),actor=actor,confirmation=f"WORKFLOW 245 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/checkpoint")
    async def build245_checkpoint(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); wid=str(form.get("workflow_id",""))
        refs=[x.strip() for x in str(form.get("related_refs","")).split(",") if x.strip()]
        result=ctx.build245.submit_checkpoint(workflow_id=wid,stage=str(form.get("stage","")),summary=str(form.get("summary","")),related_refs=refs,quality_score=float(form.get("quality_score",0.8) or 0.8),actor=actor,confirmation=f"WORKFLOW CHECKPOINT 245 {wid} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/checkpoint-review")
    async def build245_checkpoint_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); cid=str(form.get("checkpoint_id",""))
        result=ctx.build245.review_checkpoint(checkpoint_id=cid,decision=str(form.get("decision","accepted")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"WORKFLOW CHECKPOINT 245 {cid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/advance")
    async def build245_advance(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); wid=str(form.get("workflow_id",""))
        result=ctx.build245.advance(workflow_id=wid,actor=actor,rationale=str(form.get("rationale","Workflow gate reviewed.")),confirmation=f"WORKFLOW 245 {wid} ADVANCE")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/work-item")
    async def build245_work_item(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); wid=str(form.get("workflow_id",""))
        result=ctx.build245.propose_work_item(workflow_id=wid,title=str(form.get("title","")),description=str(form.get("description","")),priority=int(form.get("priority",60) or 60),owner_role=str(form.get("owner_role","analyst")),agent_role=str(form.get("agent_role","")),actor=actor,confirmation=f"WORKFLOW ITEM 245 {wid} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/item-status")
    async def build245_item_status(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); iid=str(form.get("item_id",""))
        result=ctx.build245.set_work_item_status(item_id=iid,status=str(form.get("status","approved")),note=str(form.get("note","Analyst status update.")),actor=actor,confirmation=f"WORKFLOW ITEM 245 {iid} STATUS")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/agent-support")
    async def build245_agent_support(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); iid=str(form.get("item_id",""))
        result=ctx.build245.request_agent_support(item_id=iid,actor=actor,confirmation=f"WORKFLOW AGENT 245 {iid} STARTEN")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build245/training-stage")
    async def build245_training_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build245.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"WORKFLOW TRAINING 245 {case_id} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="workflow245")

    @app.post("/build246/watchlist")
    async def build246_watchlist(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build246.create_watchlist(case_id=case_id,name=str(form.get("name","")),purpose=str(form.get("purpose","")),owner=str(form.get("owner",actor)),actor=actor,confirmation=f"WATCHLIST 246 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build246/target")
    async def build246_target(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); wid=str(form.get("watchlist_id",""))
        result=ctx.build246.add_target(watchlist_id=wid,target_type=str(form.get("target_type","person")),target_ref=str(form.get("target_ref","")),label=str(form.get("label","")),source_key=str(form.get("source_key","")),source_url=str(form.get("source_url","")),interval_minutes=int(form.get("interval_minutes",1440) or 1440),actor=actor,confirmation=f"WATCH TARGET 246 {wid} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build246/agent-check")
    async def build246_agent_check(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); tid=str(form.get("target_id",""))
        result=ctx.build246.request_agent_check(target_id=tid,actor=actor,confirmation=f"WATCH CHECK 246 {tid} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build246/observation")
    async def build246_observation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); tid=str(form.get("target_id",""))
        result=ctx.build246.record_observation(target_id=tid,summary=str(form.get("summary","")),source_ref=str(form.get("source_ref","")),observed_at=str(form.get("observed_at","")),metadata={},actor=actor,confirmation=f"WATCH OBSERVATION 246 {tid} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build246/change-review")
    async def build246_change_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); cid=str(form.get("change_id",""))
        result=ctx.build246.review_change(change_id=cid,decision=str(form.get("decision","accepted")),reviewed_significance=float(form.get("significance",.7) or .7),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"WATCH CHANGE 246 {cid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build246/evidence-stage")
    async def build246_evidence_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); cid=str(form.get("change_id",""))
        result=ctx.build246.stage_change_as_evidence(change_id=cid,actor=actor,confirmation=f"WATCH EVIDENCE 246 {cid} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build246/training")
    async def build246_training(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build246.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"WATCH TRAINING 246 {case_id} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="monitor246")

    @app.post("/build247/sync")
    async def build247_sync(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build247.sync_local_models(case_id=case_id,actor=actor,confirmation=f"AI MODELS 247 {case_id} SYNCHRONISIEREN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/model-review")
    async def build247_model_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); mid=str(form.get("model_id",""))
        result=ctx.build247.review_model(model_id=mid,decision=str(form.get("decision","approved")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"AI MODEL 247 {mid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/health")
    async def build247_health(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); mid=str(form.get("model_id",""))
        result=ctx.build247.record_health(model_id=mid,status=str(form.get("status","healthy")),latency_ms=float(form.get("latency_ms",0) or 0),error_rate=float(form.get("error_rate",0) or 0),tokens_per_second=float(form.get("tokens_per_second",0) or 0),detail={},actor=actor,confirmation=f"AI HEALTH 247 {mid} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/policy")
    async def build247_policy(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build247.propose_policy(case_id=case_id,task_type=str(form.get("task_type","investigation_dialogue")),language=str(form.get("language","de")),min_context=int(form.get("min_context",8192) or 8192),max_input_tokens=int(form.get("max_input_tokens",16000) or 16000),max_output_tokens=int(form.get("max_output_tokens",4096) or 4096),max_ram_mb=int(form.get("max_ram_mb",0) or 0),max_vram_mb=int(form.get("max_vram_mb",0) or 0),latency_class=str(form.get("latency_class","interactive")),rationale=str(form.get("rationale","Local-only production routing policy with reviewed budgets and OPSEC gates.")),actor=actor,confirmation=f"AI POLICY 247 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/policy-review")
    async def build247_policy_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); pid=str(form.get("policy_id",""))
        result=ctx.build247.review_policy(policy_id=pid,decision=str(form.get("decision","approved")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"AI POLICY 247 {pid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/policy-activate")
    async def build247_policy_activate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); pid=str(form.get("policy_id",""))
        result=ctx.build247.activate_policy(policy_id=pid,actor=actor,confirmation=f"AI POLICY 247 {pid} AKTIVIEREN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/route")
    async def build247_route(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build247.route(case_id=case_id,task_type=str(form.get("task_type","investigation_dialogue")),language=str(form.get("language","de")),requested_context=int(form.get("requested_context",8192) or 8192),input_tokens=int(form.get("input_tokens",4000) or 4000),output_tokens=int(form.get("output_tokens",1500) or 1500),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/route-review")
    async def build247_route_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); did=str(form.get("decision_id",""))
        result=ctx.build247.review_route(decision_id=did,decision=str(form.get("decision","good_route")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"AI ROUTE 247 {did} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/apply")
    async def build247_apply(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); did=str(form.get("decision_id",""))
        result=ctx.build247.apply_to_local_ai(decision_id=did,actor=actor,confirmation=f"AI ROUTE 247 {did} ANWENDEN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build247/training")
    async def build247_training(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build247.stage_training(case_id=case_id,actor=actor,limit=int(form.get("limit",50) or 50),confirmation=f"AI RUNTIME TRAINING 247 {case_id} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="runtime247")

    @app.post("/build248/probe")
    async def build248_probe(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build248.probe_ollama_mistral(case_id=case_id,actor=actor,confirmation=f"PRODUCTION OLLAMA 248 {case_id} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/register-mistral")
    async def build248_register_mistral(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build248.register_preferred_mistral(case_id=case_id,actor=actor,confirmation=f"MISTRAL 248 {case_id} REGISTRIEREN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/mistral-review")
    async def build248_mistral_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); mid=str(form.get("model_id",""))
        result=ctx.build248.review_preferred_mistral(model_id=mid,reviewer=actor,rationale=str(form.get("rationale","")),confirmation=f"MISTRAL REVIEW 248 {mid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/mistral-activate")
    async def build248_mistral_activate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); mid=str(form.get("model_id",""))
        result=ctx.build248.activate_preferred_mistral(case_id=case_id,model_id=mid,actor=actor,confirmation=f"MISTRAL 248 {mid} AKTIVIEREN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/preflight")
    async def build248_preflight(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build248.production_preflight(case_id=case_id,actor=actor,confirmation=f"PRODUCTION HARDENING 248 {case_id} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/review")
    async def build248_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); sid=str(form.get("snapshot_id",""))
        result=ctx.build248.review_preflight(snapshot_id=sid,decision=str(form.get("decision","approved")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"PRODUCTION REVIEW 248 {sid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/backup")
    async def build248_backup(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build248.create_verified_backup(case_id=case_id,actor=actor,confirmation=f"PRODUCTION BACKUP 248 {case_id} ERSTELLEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/restore-stage")
    async def build248_restore_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); bid=str(form.get("backup_id",""))
        result=ctx.build248.stage_restore(case_id=case_id,backup_id=bid,actor=actor,confirmation=f"PRODUCTION RESTORE 248 {bid} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build248/training")
    async def build248_training(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build248.stage_training(case_id=case_id,actor=actor,confirmation=f"PRODUCTION TRAINING 248 {case_id} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="production248")

    @app.post("/build249/campaign")
    async def build249_campaign(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build249.create_campaign(case_id=case_id,title=str(form.get("title","Build 249 Production Qualification")),profile=str(form.get("profile","standard")),approved_by=actor,confirmation=f"STRESS 249 {case_id} KAMPAGNE ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="stress249")

    @app.post("/build249/run")
    async def build249_run(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); cid=str(form.get("campaign_id",""))
        result=ctx.build249.run_campaign(campaign_id=cid,actor=actor,confirmation=f"STRESS 249 {cid} AUSFUEHREN")
        return _post_result(request,case_id=case_id,result=result,tab="stress249")

    @app.post("/build249/review")
    async def build249_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); rid=str(form.get("result_id",""))
        result=ctx.build249.review_result(result_id=rid,decision=str(form.get("decision","accepted")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"STRESS RESULT 249 {rid} PRUEFEN")
        return _post_result(request,case_id=case_id,result=result,tab="stress249")

    @app.post("/build249/gate")
    async def build249_gate(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id","")); cid=str(form.get("campaign_id",""))
        result=ctx.build249.release_gate(campaign_id=cid)
        return _post_result(request,case_id=case_id,result=result,tab="stress249")

    @app.post("/build249/blocker-resolve")
    async def build249_blocker_resolve(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); bid=str(form.get("blocker_id",""))
        result=ctx.build249.resolve_blocker(blocker_id=bid,note=str(form.get("note","")),actor=actor,confirmation=f"STRESS BLOCKER 249 {bid} SCHLIESSEN")
        return _post_result(request,case_id=case_id,result=result,tab="stress249")

    @app.post("/build249/training")
    async def build249_training(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build249.stage_training(case_id=case_id,actor=actor,confirmation=f"STRESS TRAINING 249 {case_id} VORBEREITEN")
        return _post_result(request,case_id=case_id,result=result,tab="stress249")


    @app.post("/build251/init")
    async def build251_init(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build251.initialize_case(case_id=case_id,objective=str(form.get("objective","")),jurisdictions=[x.strip() for x in str(form.get("jurisdictions","DE,EU")).split(',') if x.strip()],research_scope=str(form.get("research_scope","")),actor=actor,confirmation=f"INFLUENCE CASE 251 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="influence251")

    @app.post("/build251/entity")
    async def build251_entity(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        ids={"lei":str(form.get("lei",""))} if str(form.get("lei","")).strip() else {}
        result=ctx.build251.register_entity(case_id=case_id,entity_type=str(form.get("entity_type","")),display_name=str(form.get("display_name","")),jurisdiction=str(form.get("jurisdiction","")),official_domain=str(form.get("official_domain","")),identifiers=ids,former_names=[],parent_refs=[],notes=str(form.get("notes","")),actor=actor,confirmation=f"INFLUENCE ENTITY 251 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="influence251")

    @app.post("/build251/edge")
    async def build251_edge(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        refs=[x.strip() for x in str(form.get("evidence_refs","")).split(',') if x.strip()]
        result=ctx.build251.propose_relation(case_id=case_id,source_id=str(form.get("source_id","")),target_id=str(form.get("target_id","")),relation_type=str(form.get("relation_type","")),assertion_class=str(form.get("assertion_class","")),confidence=float(form.get("confidence","0.5") or .5),evidence_refs=refs,notes=str(form.get("notes","")),actor=actor,confirmation=f"INFLUENCE EDGE 251 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="influence251")

    @app.post("/build251/edge-review")
    async def build251_edge_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); edge_id=str(form.get("edge_id",""))
        result=ctx.build251.review_relation(edge_id=edge_id,decision=str(form.get("decision","accepted")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"INFLUENCE EDGE REVIEW 251 {edge_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="influence251")

    @app.post("/build251/claim-control")
    async def build251_claim_control(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build251.set_claim_control(case_id=case_id,kernel_claim_id=str(form.get("kernel_claim_id","")),legal_sensitivity=str(form.get("legal_sensitivity","normal")),assertion_class=str(form.get("assertion_class","documented_fact")),primary_evidence_required=str(form.get("primary_evidence_required",""))=="1",hearing_status=str(form.get("hearing_status","not_requested")),response_ref=str(form.get("response_ref","")),publication_status=str(form.get("publication_status","internal_unverified")),publication_note=str(form.get("publication_note","")),actor=actor,confirmation=f"INFLUENCE CLAIM CONTROL 251 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="influence251")

    @app.post("/build252/flow")
    async def build252_flow(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        refs=[x.strip() for x in str(form.get("evidence_refs","")).split(',') if x.strip()]
        result=ctx.build252.record_flow(case_id=case_id,payer_id=str(form.get("payer_id","")),payee_id=str(form.get("payee_id","")),instrument=str(form.get("instrument","grant")),assertion_class=str(form.get("assertion_class","documented_transaction")),amount_min=str(form.get("amount_min","")),amount_max=str(form.get("amount_max","")),currency=str(form.get("currency","EUR")),transaction_date=str(form.get("transaction_date","")),period_from=str(form.get("period_from","")),period_to=str(form.get("period_to","")),purpose=str(form.get("purpose","")),program_or_contract_ref=str(form.get("program_or_contract_ref","")),evidence_refs=refs,source_quality=str(form.get("source_quality","primary_official")),notes=str(form.get("notes","")),actor=actor,confirmation=f"FINANCIAL FLOW 252 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="finance252")

    @app.post("/build252/flow-review")
    async def build252_flow_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id","")); flow_id=str(form.get("flow_id",""))
        result=ctx.build252.review_flow(flow_id=flow_id,decision=str(form.get("decision","accepted")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"FINANCIAL FLOW REVIEW 252 {flow_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="finance252")

    @app.post("/build252/chain")
    async def build252_chain(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        refs=[x.strip() for x in str(form.get("evidence_refs","")).split(',') if x.strip()]
        result=ctx.build252.propose_chain_link(case_id=case_id,upstream_flow_id=str(form.get("upstream_flow_id","")),downstream_flow_id=str(form.get("downstream_flow_id","")),derivation_class=str(form.get("derivation_class","temporal_sequence_only")),evidence_refs=refs,rationale=str(form.get("rationale","")),actor=actor,confirmation=f"FINANCIAL CHAIN 252 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="finance252")


    @app.post("/build257/frame")
    async def build257_frame(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build257.create_frame_observation(case_id=case_id,span_id=str(form.get("span_id","")),frame_family=str(form.get("frame_family","abstain")),frame_label=str(form.get("frame_label","")),assertion_class=str(form.get("assertion_class","analytical_hypothesis")),analyst_summary=str(form.get("analyst_summary","")),actor=actor,confirmation=f"FRAME OBSERVATION 257 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build257/frame-review")
    async def build257_frame_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); observation_id=str(form.get("observation_id",""))
        result=ctx.build257.review_frame_observation(observation_id=observation_id,decision=str(form.get("decision","needs_more_evidence")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"FRAME REVIEW 257 {observation_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build257/step")
    async def build257_step(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build257.create_implementation_step(case_id=case_id,step_type=str(form.get("step_type","program")),span_id=str(form.get("span_id","")),label=str(form.get("label","")),assertion_class=str(form.get("assertion_class","documented_fact")),influence_entity_id=str(form.get("influence_entity_id","")),financial_flow_id=str(form.get("financial_flow_id","")),notes=str(form.get("notes","")),actor=actor,confirmation=f"IMPLEMENTATION STEP 257 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build257/link")
    async def build257_link(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        refs=[x.strip() for x in str(form.get("evidence_span_ids","" )).split(",") if x.strip()]
        result=ctx.build257.create_implementation_link(case_id=case_id,source_step_id=str(form.get("source_step_id","")),target_step_id=str(form.get("target_step_id","")),relation_type=str(form.get("relation_type","implements")),assertion_class=str(form.get("assertion_class","documented_fact")),evidence_span_ids=refs,rationale=str(form.get("rationale","")),actor=actor,confirmation=f"IMPLEMENTATION LINK 257 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build257/link-review")
    async def build257_link_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); link_id=str(form.get("link_id",""))
        result=ctx.build257.review_implementation_link(link_id=link_id,decision=str(form.get("decision","needs_more_evidence")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"IMPLEMENTATION LINK REVIEW 257 {link_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build257/training-candidate")
    async def build257_training_candidate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build257.stage_training_candidate_from_frame_review(review_id=str(form.get("review_id","")),actor=actor,confirmation=f"AI TRAINING CANDIDATE 257 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build257/ai-evaluation")
    async def build257_ai_evaluation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build257.record_ai_evaluation(case_id=case_id,benchmark_id=str(form.get("benchmark_id","")),predicted_frame_class=str(form.get("predicted_frame_class","abstain")),predicted_chain_role=str(form.get("predicted_chain_role","unknown")),predicted_decision=str(form.get("predicted_decision","abstain_insufficient_evidence")),model_or_ruleset=str(form.get("model_or_ruleset","manual-eval")),evaluated_by=actor,confirmation=f"AI BENCHMARK 257 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="framing257")

    @app.post("/build258/lineage")
    async def build258_lineage(request: Request):
        form=await request.form(); case_id=str(form.get("case_id","")); actor=_actor(request)
        result=ctx.build258.add_lineage(case_id=case_id,verified_claim_id=str(form.get("verified_claim_id","")),source_ref=str(form.get("source_ref","")),origin_key=str(form.get("origin_key","")),publisher=str(form.get("publisher","")),dependency_class=str(form.get("dependency_class","unknown")),parent_source_ref=str(form.get("parent_source_ref","")),stance=str(form.get("stance","neutral")),rationale=str(form.get("rationale","")),actor=actor,confirmation=f"CLAIM SOURCE 258 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="claims258")

    @app.post("/build258/counter")
    async def build258_counter(request: Request):
        form=await request.form(); case_id=str(form.get("case_id","")); actor=_actor(request)
        result=ctx.build258.add_counterevidence(case_id=case_id,verified_claim_id=str(form.get("verified_claim_id","")),span_id=str(form.get("span_id","")),stance=str(form.get("stance","contradicts")),strength=str(form.get("strength","moderate")),summary=str(form.get("summary","")),actor=actor,confirmation=f"COUNTEREVIDENCE 258 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="claims258")

    @app.post("/build258/review")
    async def build258_review(request: Request):
        form=await request.form(); case_id=str(form.get("case_id","")); actor=_actor(request); claim_id=str(form.get("verified_claim_id",""))
        result=ctx.build258.review_analysis(case_id=case_id,verified_claim_id=claim_id,decision=str(form.get("decision","needs_more_evidence")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"CLAIM INDEPENDENCE REVIEW 258 {claim_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="claims258")

    @app.post("/build259/packet")
    async def build259_packet(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build259.create_packet(case_id=case_id,verified_claim_id=str(form.get("verified_claim_id","")),title=str(form.get("title","")),body_text=str(form.get("body_text","")),assertion_class=str(form.get("assertion_class","documented_fact")),intended_audience=str(form.get("intended_audience","internal")),publication_channel=str(form.get("publication_channel","")),actor=actor,confirmation=f"PUBLICATION PACKET 259 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="publication259")

    @app.post("/build259/legal-review")
    async def build259_legal_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); packet_id=str(form.get("packet_id",""))
        result=ctx.build259.legal_editorial_review(case_id=case_id,packet_id=packet_id,decision=str(form.get("decision","hold")),risk_class=str(form.get("risk_class","moderate")),hearing_required=bool(form.get("hearing_required")),redaction_required=bool(form.get("redaction_required")),source_independence_checked=bool(form.get("source_independence_checked")),counterevidence_checked=bool(form.get("counterevidence_checked")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"LEGAL EDITORIAL REVIEW 259 {packet_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="publication259")

    @app.post("/build259/hearing")
    async def build259_hearing(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); packet_id=str(form.get("packet_id",""))
        result=ctx.build259.record_hearing(case_id=case_id,packet_id=packet_id,subject_label=str(form.get("subject_label","")),status=str(form.get("status","not_completed")),request_summary=str(form.get("request_summary","")),response_summary=str(form.get("response_summary","")),actor=actor,confirmation=f"HEARING RECORD 259 {packet_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="publication259")

    @app.post("/build259/redaction")
    async def build259_redaction(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); packet_id=str(form.get("packet_id",""))
        result=ctx.build259.add_redaction(case_id=case_id,packet_id=packet_id,target_text=str(form.get("target_text","")),replacement_text=str(form.get("replacement_text","[REDACTED]")),reason_class=str(form.get("reason_class","privacy")),actor=actor,confirmation=f"REDACTION PLAN 259 {packet_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="publication259")

    @app.post("/build259/redaction-review")
    async def build259_redaction_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); packet_id=str(form.get("packet_id",""))
        result=ctx.build259.review_redactions(case_id=case_id,packet_id=packet_id,decision=str(form.get("decision","revise")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"REDACTION REVIEW 259 {packet_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="publication259")

    @app.post("/build259/final-review")
    async def build259_final_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); packet_id=str(form.get("packet_id",""))
        result=ctx.build259.final_review(case_id=case_id,packet_id=packet_id,decision=str(form.get("decision","hold")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"PUBLICATION DECISION 259 {packet_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="publication259")

    @app.post("/build265/finalize-browser")
    async def build265_finalize_browser(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id",""))
        result=ctx.build266.finalize_browser_context(case_id=case_id,run_id=str(form.get("run_id","")))
        return _post_result(request,case_id=case_id,result=result,tab="temporal265")

    @app.post("/build264/execute")
    async def build264_execute(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build264.approve_and_execute(case_id=case_id,run_id=str(form.get("run_id","")),
            confirmation=str(form.get("confirmation","")),approved_by=actor,provider=str(form.get("provider","")),
            max_queries=int(form.get("max_queries","8") or 8),max_results_per_query=int(form.get("max_results_per_query","8") or 8))
        return _post_result(request,case_id=case_id,result=result,tab="execution264")

    @app.post("/build263/research-command")
    async def build263_research_command(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build263.create_research_run(case_id=case_id,user_request=str(form.get("message","")),target_id=str(form.get("target_id","")),
            auto_open=str(form.get("auto_open",""))=="1",actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="research263")

    @app.post("/build263/open-run")
    async def build263_open_run(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build263.open_run(case_id=case_id,run_id=str(form.get("run_id","")),max_tabs=8,actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="research263")

    @app.post("/build263/quality")
    async def build263_quality(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build263.create_quality_assessment(case_id=case_id,evidence_ref=str(form.get("evidence_ref","")),
            source_level=str(form.get("source_level","unknown")),originality=str(form.get("originality","unknown")),
            authenticity=str(form.get("authenticity","uncertain")),independence=str(form.get("independence","unknown")),
            corroboration=str(form.get("corroboration","unknown")),provenance_quality=str(form.get("provenance_quality","unknown")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="research263")

    @app.post("/build263/finding")
    async def build263_finding(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build263.add_finding(case_id=case_id,run_id=str(form.get("run_id","")),query_id=str(form.get("query_id","")),
            title=str(form.get("title","")),url=str(form.get("url","")),snippet=str(form.get("snippet","")),
            source_class=str(form.get("source_class","public_web")),evidence_ref=str(form.get("evidence_ref","")),
            stance=str(form.get("stance","context_only")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="research263")

    @app.post("/build262/from-case-state")
    async def build262_from_case_state(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build262.propose_from_case_state(case_id,actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="taskgraph262")

    @app.post("/build262/task")
    async def build262_task(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build262.create_task(case_id=case_id,task_type=str(form.get("task_type","")),title=str(form.get("title","")),question=str(form.get("question","")),priority=str(form.get("priority","normal")),source_classes=str(form.get("source_classes","case_evidence")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="taskgraph262")

    @app.post("/build262/dependency")
    async def build262_dependency(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build262.add_dependency(case_id=case_id,task_id=str(form.get("task_id","")),depends_on_task_id=str(form.get("depends_on_task_id","")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="taskgraph262")

    @app.post("/build262/state")
    async def build262_state(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build262.transition(case_id=case_id,task_id=str(form.get("task_id","")),state=str(form.get("state","")),rationale=str(form.get("rationale","")),result_summary=str(form.get("result_summary","")),evidence_refs=str(form.get("evidence_refs","")),reviewer=actor)
        return _post_result(request,case_id=case_id,result=result,tab="taskgraph262")

    @app.post("/build261/profile")
    async def build261_profile(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build261.upsert_profile(case_id=case_id,objective=str(form.get("objective","")),research_question=str(form.get("research_question","")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="caseintelligence261")

    @app.post("/build261/item")
    async def build261_item(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build261.add_item(case_id=case_id,item_type=str(form.get("item_type","")),title=str(form.get("title","")),statement=str(form.get("statement","")),evidence_ref=str(form.get("evidence_ref","")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="caseintelligence261")

    @app.post("/build260/run")
    async def build260_run(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build260.create_run(case_id=case_id,title=str(form.get("title","")),scope=str(form.get("scope","")),actor=actor,confirmation=f"PHASE10 QUALIFICATION 260 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="qualification260")

    @app.post("/build260/stage")
    async def build260_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); run_id=str(form.get("run_id",""))
        findings=[x.strip() for x in str(form.get("findings","")).splitlines() if x.strip()]
        result=ctx.build260.record_stage(case_id=case_id,run_id=run_id,stage_key=str(form.get("stage_key","")),status=str(form.get("status","pass")),severity=str(form.get("severity","info")),metrics={},findings=findings,evidence_ref=str(form.get("evidence_ref","")),actor=actor,confirmation=f"QUALIFICATION STAGE 260 {run_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="qualification260")

    @app.post("/build260/ai-evaluation")
    async def build260_ai_evaluation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build260.record_ai_evaluation(case_id=case_id,benchmark_id=str(form.get("benchmark_id","")),predicted_class=str(form.get("predicted_class","")),predicted_decision=str(form.get("predicted_decision","")),model_or_ruleset=str(form.get("model_or_ruleset","manual-eval")),evaluated_by=actor,confirmation=f"AI REDTEAM 260 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="qualification260")

    @app.post("/build260/final-review")
    async def build260_final_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); run_id=str(form.get("run_id",""))
        result=ctx.build260.final_review(case_id=case_id,run_id=run_id,decision=str(form.get("decision","blocked")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"PHASE10 RELEASE REVIEW 260 {run_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="qualification260")

    @app.post("/build256/stage")
    async def build256_stage(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        identifiers={}
        for part in str(form.get("identifiers","")).split(";"):
            if "=" in part:
                k,v=part.split("=",1); k=k.strip(); v=v.strip()
                if k and v: identifiers[k]=v
        result=ctx.build256.stage_entity(case_id=case_id,influence_entity_id=str(form.get("influence_entity_id","")),identifiers=identifiers,actor=actor,confirmation=f"ENTITY PROFILE 256 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="entities256")

    @app.post("/build256/generate")
    async def build256_generate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build256.generate_candidates(case_id=case_id,actor=actor,confirmation=f"ENTITY MATCH 256 {case_id} GENERIEREN")
        return _post_result(request,case_id=case_id,result=result,tab="entities256")

    @app.post("/build256/review")
    async def build256_review(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", "")); candidate_id=str(form.get("candidate_id",""))
        result=ctx.build256.review_candidate(candidate_id=candidate_id,decision=str(form.get("decision","needs_more_evidence")),canonical_entity_id=str(form.get("canonical_entity_id","")),rationale=str(form.get("rationale","")),reviewer=actor,confirmation=f"ENTITY MATCH REVIEW 256 {candidate_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="entities256")

    @app.post("/build256/training-candidate")
    async def build256_training_candidate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build256.stage_training_candidate_from_review(review_id=str(form.get("review_id","")),actor=actor,confirmation=f"AI TRAINING CANDIDATE 256 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="entities256")

    @app.post("/build256/ai-evaluation")
    async def build256_ai_evaluation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build256.record_ai_evaluation(case_id=case_id,benchmark_id=str(form.get("benchmark_id","")),predicted_left_transliteration=str(form.get("predicted_left_transliteration","")),predicted_right_transliteration=str(form.get("predicted_right_transliteration","")),predicted_resolution=str(form.get("predicted_resolution","abstain")),model_or_ruleset=str(form.get("model_or_ruleset","manual-eval")),evaluated_by=actor,confirmation=f"AI BENCHMARK 256 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="entities256")

    @app.post("/build255/process")
    async def build255_process(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build255.process_vault_pdf(case_id=case_id,vault_item_id=str(form.get("vault_item_id","")),actor=actor,confirmation=f"DOCUMENT PIPELINE 255 {case_id} EXTRACT",allow_ocr=str(form.get("allow_ocr",""))=="1")
        return _post_result(request,case_id=case_id,result=result,tab="documents255")

    @app.post("/build255/training-candidate")
    async def build255_training_candidate(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build255.stage_training_candidate_from_span(case_id=case_id,span_id=str(form.get("span_id","")),task_instruction=str(form.get("task_instruction","")),actor=actor,confirmation=f"AI TRAINING CANDIDATE 255 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="documents255")

    @app.post("/build255/ai-evaluation")
    async def build255_ai_evaluation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build255.record_ai_evaluation(case_id=case_id,benchmark_id=str(form.get("benchmark_id","")),predicted_page=int(form.get("predicted_page","0") or 0),predicted_block_type=str(form.get("predicted_block_type","")),predicted_text=str(form.get("predicted_text","")),predicted_table_row=int(form.get("predicted_table_row","-1") or -1),predicted_table_col=int(form.get("predicted_table_col","-1") or -1),predicted_provenance_class=str(form.get("predicted_provenance_class","")),model_or_ruleset=str(form.get("model_or_ruleset","manual-eval")),evaluated_by=actor,confirmation=f"AI BENCHMARK 255 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="documents255")

    @app.post("/build254/route")
    async def build254_route(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        identifiers=[x.strip() for x in str(form.get("identifiers","")).split(",") if x.strip()]
        result=ctx.build254.recommend_sources(case_id=case_id,research_question=str(form.get("research_question","")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),language_hint=str(form.get("language_hint","")),identifiers=identifiers,top_k=6)
        return _post_result(request,case_id=case_id,result=result,tab="sources254")

    @app.post("/build254/plan")
    async def build254_plan(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        terms=[x.strip() for x in str(form.get("query_terms","")).split(",") if x.strip()]
        identifiers=[x.strip() for x in str(form.get("identifiers","")).split(",") if x.strip()]
        artifacts=[x.strip() for x in str(form.get("expected_artifacts","")).split(",") if x.strip()]
        result=ctx.build254.create_lookup_plan(case_id=case_id,source_id=str(form.get("source_id","")),research_question=str(form.get("research_question","")),query_terms=terms,identifiers=identifiers,expected_artifacts=artifacts,purpose=str(form.get("purpose","")),actor=actor,confirmation=f"SOURCE PLAN 254 {case_id} ANLEGEN",query_language=str(form.get("query_language","")))
        return _post_result(request,case_id=case_id,result=result,tab="sources254")

    @app.post("/build254/observation")
    async def build254_observation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        refs=[x.strip() for x in str(form.get("evidence_refs","")).split(",") if x.strip()]
        fields={}
        for part in str(form.get("observed_fields","")).split(";"):
            if "=" in part:
                k,v=part.split("=",1); k=k.strip(); v=v.strip()
                if k: fields[k]=v
        result=ctx.build254.record_observation(case_id=case_id,source_id=str(form.get("source_id","")),plan_id=str(form.get("plan_id","")),external_record_ref=str(form.get("external_record_ref","")),document_date=str(form.get("document_date","")),observed_fields=fields,evidence_refs=refs,assertion_class=str(form.get("assertion_class","metadata_only")),notes=str(form.get("notes","")),actor=actor,confirmation=f"SOURCE OBSERVATION 254 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="sources254")

    @app.post("/build254/ai-evaluation")
    async def build254_ai_evaluation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build254.record_ai_evaluation(case_id=case_id,benchmark_id=str(form.get("benchmark_id","")),predicted_source_id=str(form.get("predicted_source_id","")),predicted_jurisdiction=str(form.get("predicted_jurisdiction","")),predicted_language=str(form.get("predicted_language","")),predicted_identifier_strategy=str(form.get("predicted_identifier_strategy","")),predicted_assertion_ceiling=str(form.get("predicted_assertion_ceiling","")),predicted_access_class=str(form.get("predicted_access_class","")),model_or_ruleset=str(form.get("model_or_ruleset","manual-eval")),evaluated_by=actor,confirmation=f"AI BENCHMARK 254 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="sources254")

    @app.post("/build254/preflight")
    async def build254_preflight(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id", ""))
        result=ctx.build254.source_preflight(case_id=case_id,source_id=str(form.get("source_id","")),actor=actor,record=True)
        return _post_result(request,case_id=case_id,result=result,tab="sources254")

    @app.post("/build253/recommend")
    async def build253_recommend(request: Request):
        session, form = await _secured_form(request); case_id=str(form.get("case_id",""))
        result=ctx.build253.recommend_sources(case_id=case_id,research_question=str(form.get("research_question","")),top_k=5)
        return _post_result(request,case_id=case_id,result=result,tab="sources253")

    @app.post("/build253/plan")
    async def build253_plan(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        terms=[x.strip() for x in str(form.get("query_terms","")).split(',') if x.strip()]
        artifacts=[x.strip() for x in str(form.get("expected_artifacts","")).split(',') if x.strip()]
        result=ctx.build253.create_lookup_plan(case_id=case_id,source_id=str(form.get("source_id","")),research_question=str(form.get("research_question","")),query_terms=terms,expected_artifacts=artifacts,purpose=str(form.get("purpose","")),actor=actor,confirmation=f"SOURCE PLAN 253 {case_id} ANLEGEN")
        return _post_result(request,case_id=case_id,result=result,tab="sources253")

    @app.post("/build253/observation")
    async def build253_observation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        refs=[x.strip() for x in str(form.get("evidence_refs","")).split(',') if x.strip()]
        fields={}
        for part in str(form.get("observed_fields","")).replace("\n",";").split(';'):
            if '=' in part:
                key,value=part.split('=',1); key=key.strip(); value=value.strip()
                if key: fields[key]=value
        result=ctx.build253.record_observation(case_id=case_id,source_id=str(form.get("source_id","")),plan_id=str(form.get("plan_id","")),external_record_ref=str(form.get("external_record_ref","")),document_date=str(form.get("document_date","")),observed_fields=fields,evidence_refs=refs,assertion_class=str(form.get("assertion_class","metadata_only")),notes=str(form.get("notes","")),actor=actor,confirmation=f"SOURCE OBSERVATION 253 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="sources253")

    @app.post("/build253/ai-evaluation")
    async def build253_ai_evaluation(request: Request):
        session, form = await _secured_form(request); actor=session["username"]; case_id=str(form.get("case_id",""))
        result=ctx.build253.record_ai_evaluation(case_id=case_id,benchmark_id=str(form.get("benchmark_id","")),predicted_source_id=str(form.get("predicted_source_id","")),predicted_assertion_ceiling=str(form.get("predicted_assertion_ceiling","")),predicted_access_class=str(form.get("predicted_access_class","")),model_or_ruleset=str(form.get("model_or_ruleset","manual-eval")),evaluated_by=actor,confirmation=f"AI BENCHMARK 253 {case_id} SPEICHERN")
        return _post_result(request,case_id=case_id,result=result,tab="sources253")

    @app.post("/build321/storage-profile")
    async def build321_storage_profile(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build321.create_storage_profile(case_id=case_id,profile_name=str(form.get("profile_name","Portable Investigation")),mode=str(form.get("mode","portable")),actor=actor)
        result["assessment"]=ctx.build321.assess_storage_profile(result["profile_id"]); return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build321/data-access-plan")
    async def build321_data_access_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build321.plan_data_access_strategy(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Resolve the highest-value evidence gaps")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation")

    @app.post("/build321/security-selftest")
    async def build321_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build321.run_security_agent_selftest(actor=request_actor(request)); return _post_result(request,case_id=case_id,result=result,tab="operations302")


    @app.post("/build322/evidence-plan")
    async def build322_evidence_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build322.plan_evidence_processing(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Extract maximum evidential value from verified local originals")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation")

    @app.post("/build322/case-manifest")
    async def build322_case_manifest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build322.create_case_manifest(case_id=case_id,actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="evidence")

    @app.post("/build322/ledger-checkpoint")
    async def build322_ledger_checkpoint(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); verify=ctx.build322.verify_ledger(); checkpoint=ctx.build322.checkpoint_ledger(actor=request_actor(request)) if verify.get("result")=="pass" else None
        return _post_result(request,case_id=case_id,result={"verification":verify,"checkpoint":checkpoint},tab="evidence")

    @app.post("/build322/security-selftest")
    async def build322_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build322.run_security_agent_selftest(actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="operations302")


    @app.post("/build324/graph-plan")
    async def build324_graph_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build324.plan_graph_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Resolve the highest-value relationship conflict")),actor=request_actor(request))
        return RedirectResponse(url=f"/?case_id={case_id}&view=analysis",status_code=303)

    @app.post("/build324/security-selftest")
    async def build324_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build324.run_graph_selftest(actor=request_actor(request)); ctx.build324.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(url=f"/?case_id={case_id}&view=operations",status_code=303)
    @app.post("/build323/search")
    async def build323_search(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build323.search_case(case_id=case_id,target_id=str(form.get("target_id","")),query=str(form.get("query","")),limit=10,actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation")

    @app.post("/build323/index-plan")
    async def build323_index_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); actor=request_actor(request)
        result=ctx.build323.plan_index_assisted_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Resolve the highest-value evidence gap")),actor=actor)
        return _post_result(request,case_id=case_id,result=result,tab="investigation")

    @app.post("/build323/security-selftest")
    async def build323_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build323.run_security_agent_selftest(actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="operations302")



    @app.post("/build326/bulk-plan")
    async def build326_bulk_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build326.plan_bulk_ingestion(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Identify the highest-value reviewed bulk or delta dataset for the current evidence gap")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),record_family=str(form.get("record_family","")),actor=request_actor(request))
        return RedirectResponse(url=_case_redirect(case_id,"investigation",notice=f"Build 326 Bulk-Plan: {len(result.get('bulk_source_candidates',[]))} Bulk-Quellen"),status_code=303)

    @app.post("/build326/security-selftest")
    async def build326_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build326.run_bulk_ingestion_selftest(actor=request_actor(request)); result=ctx.build326.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(url=_case_redirect(case_id,"operations",notice=f"Build 326 Security v23: {result.get('result')}") ,status_code=303)

    @app.post("/build327/corporate-plan")
    async def build327_corporate_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build327.plan_corporate_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Resolve corporate identity, ownership/control and counterevidence using independent primary sources")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),actor=request_actor(request))
        return RedirectResponse(url=_case_redirect(case_id,"investigation",notice=f"Build 327 Corporate Plan: {result.get('plan_id','')}") ,status_code=303)

    @app.post("/build327/security-selftest")
    async def build327_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build327.run_corporate_pack_selftest(actor=request_actor(request)); result=ctx.build327.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(url=_case_redirect(case_id,"operations",notice=f"Build 327 Security v24: {result.get('result')}") ,status_code=303)
    @app.post("/build325/source-plan")
    async def build325_source_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build325.plan_ai_source_strategy(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Identify authoritative and independent sources for the highest-value evidence gap")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),record_family=str(form.get("record_family","")),actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="investigation")

    @app.post("/build325/security-selftest")
    async def build325_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build325.run_source_registry_selftest(actor=request_actor(request)); result=ctx.build325.run_security_agent_selftest(actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="operations302")

    @app.post("/build325/dcat-export")
    async def build325_dcat_export(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build325.export_dcat_catalog(actor=request_actor(request))
        return _post_result(request,case_id=case_id,result=result,tab="sources")


    @app.post("/build329/public-funding-plan")
    async def build329_public_funding_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build329.plan_public_funding_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Review procurement awards, grants, subawards, recipients and counterevidence")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),actor=request_actor(request))
        return RedirectResponse(_link("investigation",case_id,message=f"Public-Funding-Plan {result['plan_id']} erzeugt"),status_code=303)

    @app.post("/build329/security-selftest")
    async def build329_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build329.run_procurement_grants_selftest(actor=request_actor(request)); result=ctx.build329.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v26: {result['result']}"),status_code=303)
    @app.post("/build328/financial-plan")
    async def build328_financial_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build328.plan_financial_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Review financial filings, ownership indicators, documented flows and counterevidence")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),actor=request_actor(request))
        return RedirectResponse(url=_case_redirect(case_id,"analysis",notice=f"Build 328 Financial Plan: {result.get('plan_id','')}") ,status_code=303)

    @app.post("/build328/security-selftest")
    async def build328_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build328.run_financial_pack_selftest(actor=request_actor(request)); result=ctx.build328.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(url=_case_redirect(case_id,"operations",notice=f"Build 328 Security v25: {result.get('result')}") ,status_code=303)


    @app.post("/build330/government-legal-plan")
    async def build330_government_legal_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build330.plan_government_legal_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Review court, regulatory, sanctions, exclusion and official legal records with finality and counterevidence")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),actor=request_actor(request))
        return RedirectResponse(_link("analysis",case_id,message=f"Government/Legal-Plan {result['plan_id']} erzeugt"),status_code=303)

    @app.post("/build330/security-selftest")
    async def build330_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build330.run_government_legal_selftest(actor=request_actor(request)); result=ctx.build330.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v27: {result['result']}"),status_code=303)

    @app.post("/build331/historical-web-plan")
    async def build331_historical_web_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build331.plan_historical_web_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Compare historical website states, disappeared pages, prior corporate representations and counterevidence")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),actor=request_actor(request))
        return RedirectResponse(_link("analysis",case_id,message=f"Historical-Web-Plan {result['plan_id']} erzeugt"),status_code=303)

    @app.post("/build331/security-selftest")
    async def build331_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build331.run_historical_web_selftest(actor=request_actor(request)); result=ctx.build331.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v28: {result['result']}"),status_code=303)

    @app.post("/build332/document-plan")
    async def build332_document_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build332.plan_document_investigation(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Review structured documents, tables, roles, amounts, page provenance and counterevidence")),actor=request_actor(request))
        return RedirectResponse(_link("analysis",case_id,message=f"Document-Plan {result['plan_id']} erzeugt"),status_code=303)

    @app.post("/build332/security-selftest")
    async def build332_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build332.run_document_intelligence_selftest(actor=request_actor(request)); result=ctx.build332.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v29: {result['result']}"),status_code=303)

    @app.post("/build333/multilingual-plan")
    async def build333_multilingual_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build333.plan_multilingual_source_discovery(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","Find authoritative local-language sources and counterevidence")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),actor=request_actor(request))
        return RedirectResponse(_link("analysis",case_id,message=f"Multilingual-Plan {result['plan_id']} erzeugt"),status_code=303)

    @app.post("/build333/security-selftest")
    async def build333_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build333.run_multilingual_discovery_selftest(actor=request_actor(request)); result=ctx.build333.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v30: {result['result']}"),status_code=303)

    @app.post("/build334/security-selftest")
    async def build334_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build334.run_entity_resolution_v2_selftest(actor=request_actor(request)); result=ctx.build334.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v31: {result['result']}"),status_code=303)

    @app.post("/build335/temporal-plan")
    async def build335_temporal_plan(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build335.plan_temporal_investigation(case_id=case_id,target_id=str(form.get("target_id","")),entity_key=str(form.get("entity_key","")),as_of_time=str(form.get("as_of_time","")),objective=str(form.get("objective","Reconstruct entity and relationship state through time, review conflicts and counterevidence")),actor=request_actor(request))
        return RedirectResponse(_link("analysis",case_id,message=f"Temporal-Plan {result['plan_id']} erzeugt"),status_code=303)

    @app.post("/build335/security-selftest")
    async def build335_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build335.run_temporal_intelligence_selftest(actor=request_actor(request)); result=ctx.build335.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v32: {result['result']}"),status_code=303)

    @app.post("/build336/security-selftest")
    async def build336_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build336.run_calibration_lab_selftest(actor=request_actor(request)); result=ctx.build336.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"Build 336 calibration/security: {result.get('result')}"),status_code=303)

    @app.post("/build337/supervisor-run")
    async def build337_supervisor_run(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id",""))
        result=ctx.build337.create_supervisor_run(case_id=case_id,target_id=str(form.get("target_id","")),objective=str(form.get("objective","")),jurisdiction_hint=str(form.get("jurisdiction_hint","")),authorization_phrase=str(form.get("authorization_phrase","")),max_cycles=int(form.get("max_cycles") or 3),max_actions=int(form.get("max_actions") or 10),actor=request_actor(request))
        return RedirectResponse(_link("investigation",case_id,message=f"Supervisor Run {result['run_id']} angelegt"),status_code=303)

    @app.post("/build337/supervisor-cycle")
    async def build337_supervisor_cycle(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build337.run_supervisor_cycle(str(form.get("run_id","")),actor=request_actor(request))
        return RedirectResponse(_link("investigation",case_id,message=f"Supervisor Zyklus {result.get('cycle_no','-')}: {result.get('status')}"),status_code=303)

    @app.post("/build337/security-selftest")
    async def build337_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build337.run_supervisor_selftest(actor=request_actor(request)); result=ctx.build337.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v34: {result.get('result')}"),status_code=303)

    @app.post("/build338/dossier-create")
    async def build338_dossier_create(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id",""))
        result=ctx.build340.create_dossier_vnext(case_id=case_id,supervisor_run_id=str(form.get("supervisor_run_id","")),title=str(form.get("title","")),parent_dossier_id=str(form.get("parent_dossier_id","")),notes=str(form.get("notes","")),actor=request_actor(request))
        return RedirectResponse(_link("reports",case_id,message=f"Dossier vNext {result['dossier_id']} angelegt"),status_code=303)

    @app.post("/build338/claim-add")
    async def build338_claim_add(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id",""))
        def _list(name):
            raw=str(form.get(name,"") or "").strip()
            if not raw:return []
            try:
                val=json.loads(raw)
            except Exception as exc:
                raise HTTPException(status_code=400,detail=f"Ungültiges JSON in {name}: {exc}")
            if not isinstance(val,list):raise HTTPException(status_code=400,detail=f"{name} muss eine JSON-Liste sein")
            return val
        result=ctx.build340.add_dossier_claim(dossier_id=str(form.get("dossier_id","")),claim_type=str(form.get("claim_type","assessment")),claim_text=str(form.get("claim_text","")),materiality=str(form.get("materiality","medium")),source_refs=_list("source_refs_json"),counter_refs=_list("counter_refs_json"),assumptions=_list("assumptions_json"),uncertainty_notes=str(form.get("uncertainty_notes","")),temporal_scope=str(form.get("temporal_scope","unspecified")),identity_status=str(form.get("identity_status","candidate_or_not_applicable")),legal_status=str(form.get("legal_status","not_applicable")),actor=request_actor(request))
        return RedirectResponse(_link("reports",case_id,message=f"Claim {result['claim_id']} append-only gespeichert"),status_code=303)

    @app.post("/build338/red-team")
    async def build338_red_team(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build340.run_red_team_review(dossier_id=str(form.get("dossier_id","")),actor=request_actor(request))
        return RedirectResponse(_link("reports",case_id,message=f"Red-Team {result['verdict']}: critical={result['critical']} major={result['major']}"),status_code=303)

    @app.post("/build338/human-review")
    async def build338_human_review(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build340.human_review_dossier(dossier_id=str(form.get("dossier_id","")),disposition=str(form.get("disposition","needs_rework")),notes=str(form.get("notes","")),reviewer=request_actor(request))
        return RedirectResponse(_link("reports",case_id,message=f"Human Review: {result['disposition']}"),status_code=303)

    @app.post("/build338/release")
    async def build338_release(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); result=ctx.build340.release_dossier_vnext(dossier_id=str(form.get("dossier_id","")),authorization_phrase=str(form.get("authorization_phrase","")),actor=request_actor(request))
        return RedirectResponse(_link("reports",case_id,message=f"Dossier Release {result['release_id']} · SHA256 {result['content_sha256'][:12]}…"),status_code=303)

    @app.post("/build338/security-selftest")
    async def build338_security_selftest(request: Request):
        session, form=await _secured_form(request); case_id=str(form.get("case_id","")); ctx.build340.run_dossier_selftest(actor=request_actor(request)); result=ctx.build340.run_security_agent_selftest(actor=request_actor(request))
        return RedirectResponse(_link("operations",case_id,message=f"AI Security v35: {result.get('result')}"),status_code=303)
    return app

