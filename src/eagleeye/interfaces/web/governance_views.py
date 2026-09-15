from __future__ import annotations

import json
from typing import Any


def render_governance(ctx: Any, case_id: str, csrf: str, *, actor: str, esc, table) -> str:
    svc = ctx.collaboration_governance_132
    data = svc.dashboard(case_id, actor=actor)
    current = data["current_user"]
    settings = data["settings"]
    metrics = data["metrics"]
    roles = data["roles"]
    is_admin = current.get("role_key") == "administrator"

    metric_html = "".join(
        f'<div class="metric"><div class="label">{esc(label)}</div><div class="value">{int(value)}</div></div>'
        for label, value in (
            ("Aktive Nutzer", metrics["active_users"]),
            ("Fallzuweisungen", metrics["active_assignments"]),
            ("Freigaben offen", metrics["pending_approvals"]),
            ("Objektsperren", metrics["active_locks"]),
            ("Kommentare", metrics["recent_comments"]),
            ("Sitzungen", metrics["active_sessions"]),
        )
    )
    role_options = "".join(
        f'<option value="{esc(row["role_key"])}">{esc(row["label"])}</option>' for row in roles
    )
    user_options = "".join(
        f'<option value="{esc(row["username"])}">{esc(row["display_name"])} · {esc(row["role_key"])}</option>'
        for row in data["users"] if row.get("active")
    )

    approval_cards: list[str] = []
    for row in data["approvals"]:
        actions = ""
        if row.get("status") == "pending" and row.get("requested_by", "").casefold() != actor.casefold():
            actions = f'''<form method="post" action="/governance/approval/decide" class="decision">
<input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="request_id" value="{esc(row['request_id'])}">
<select name="decision"><option value="approved">Freigeben und ausführen</option><option value="needs_changes">Änderungen verlangen</option><option value="rejected">Ablehnen</option></select>
<input name="reason" minlength="12" required placeholder="Substanzielle unabhängige Reviewbegründung"><button>Entscheiden</button></form>'''
        approval_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('action_key'))}</h3><span class="badge candidate">{esc(row.get('status'))}</span></div><span class="badge">{esc(row.get('required_permission'))}</span></div>
<p>Objekt: <code>{esc(row.get('object_type'))}:{esc(row.get('object_id'))}</code> · Antrag: {esc(row.get('requested_by'))}</p>
<p>Payload-Fingerprint: <code>{esc(str(row.get('payload_sha256') or '')[:20])}…</code> · Ausführung: {esc(row.get('execution_status'))}</p>{actions}</div>''')

    lock_cards = "".join(
        f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('object_type'))}:{esc(row.get('object_id'))}</h3><span class="badge">{esc(row.get('owner_username'))}</span></div><span class="badge candidate">aktiv</span></div><p>{esc(row.get('purpose'))}</p>
<form method="post" action="/governance/lock/release"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="lock_id" value="{esc(row.get('lock_id'))}"><button class="ghost small">Sperre lösen</button></form></div>'''
        for row in data["locks"]
    ) or '<div class="empty">Keine aktive Objektsperre.</div>'

    brief_cards: list[str] = []
    for row in data["briefs"]:
        try:
            content = json.loads(row.get("content_json") or "{}")
        except Exception:
            content = {}
        recs = content.get("recommendations") or []
        brief_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>Governance Reviewer Brief</h3><span class="badge candidate">{esc(row.get('trust_state'))}</span></div><span class="badge">{esc(row.get('review_status'))}</span></div>
<p>{esc(' · '.join(str(item.get('action') or '') for item in recs[:5]) or 'Keine priorisierte Governance-Lücke.')}</p>
<div class="footer">Modell: {esc(row.get('model_key'))} {esc(row.get('model_version'))} · externe Aktionen: {int(row.get('external_actions') or 0)}</div></div>''')

    user_cards = "".join(
        f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("display_name"))}</h3><span class="badge">{esc(row.get("username"))}</span></div><span class="badge {"ok" if row.get("active") else "candidate"}">{esc(row.get("role_key"))} · {"aktiv" if row.get("active") else "deaktiviert"}</span></div>
<form method="post" action="/governance/user/status"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="username" value="{esc(row.get("username"))}"><input type="hidden" name="active" value="{0 if row.get("active") else 1}"><button class="ghost small">{"Deaktivieren" if row.get("active") else "Aktivieren"}</button></form></div>'''
        for row in data["users"] if row.get("username") != svc.OWNER_USERNAME
    ) or '<div class="empty">Keine zusätzlichen Governance-Benutzer.</div>'
    session_cards = "".join(
        f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("display_name"))}</h3><span class="badge">{esc(row.get("username"))} · {esc(row.get("role_key"))}</span></div><span class="badge candidate">aktiv</span></div><p>Erstellt: {esc(row.get("created_at"))} · Ablauf: {esc(row.get("expires_epoch"))}</p>
<form method="post" action="/governance/session/revoke"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="session_id" value="{esc(row.get("session_id"))}"><button class="danger small">Sitzung widerrufen</button></form></div>'''
        for row in data["sessions"]
    ) or '<div class="empty">Keine aktive Governance-Sitzung.</div>'
    assignment_cards = "".join(
        f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("display_name"))}</h3><span class="badge">{esc(row.get("username"))}</span></div><span class="badge {"ok" if row.get("active") else "candidate"}">{esc(row.get("role_key"))}</span></div><p>{esc(row.get("notes"))}</p>
{f'<form method="post" action="/governance/assignment/revoke"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="assignment_id" value="{esc(row.get("assignment_id"))}"><button class="ghost small">Zuweisung widerrufen</button></form>' if row.get("active") and is_admin else ""}</div>'''
        for row in data["assignments"]
    ) or '<div class="empty">Keine Fallzuweisung.</div>'

    admin_panel = ""
    if is_admin:
        team_action = (
            f'''<form method="post" action="/governance/team-mode/disable"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="TEAMMODUS DEAKTIVIEREN" required></div><button class="danger">Teammodus deaktivieren</button></form>'''
            if settings.get("team_mode_enabled") else
            f'''<form method="post" action="/governance/team-mode/enable"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="TEAMMODUS AKTIVIEREN" required></div><button>Teammodus aktivieren</button></form>'''
        )
        admin_panel = f'''
<div class="two-col"><div class="panel"><h2>Benutzer anlegen</h2><form method="post" action="/governance/user/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
<div class="form-grid"><div class="field"><label>Benutzername</label><input name="username" required pattern="[A-Za-z0-9._-]+"></div><div class="field"><label>Anzeigename</label><input name="display_name" required></div></div>
<div class="field"><label>Globale Rolle</label><select name="role_key">{role_options}</select></div><div class="field"><label>Passphrase · mindestens 12 Zeichen</label><input type="password" name="passphrase" minlength="12" required autocomplete="new-password"></div><button>Benutzer anlegen</button></form></div>
<div class="panel"><h2>Eigentümer-Passphrase & Teammodus</h2><form method="post" action="/governance/password"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="username" value="local-analyst"><div class="field"><label>Neue local-analyst-Passphrase</label><input type="password" name="passphrase" minlength="12" required autocomplete="new-password"></div><button class="ghost">Passphrase setzen/rotieren</button></form><hr>{team_action}<p class="footer">Teammodus ergänzt eine zweite Login-Schicht. Der Webserver bleibt absichtlich loopback-only; Remote-Serverbetrieb ist in Build 132 blockiert.</p></div></div>
<div class="two-col"><div class="panel"><h2>Fall zuweisen</h2><form method="post" action="/governance/assignment/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Benutzer</label><select name="username">{user_options}</select></div><div class="field"><label>Fallrolle</label><select name="role_key">{role_options}</select></div><div class="field"><label>Notiz</label><input name="notes"></div><button>Zuweisen</button></form></div>
<div class="panel"><h2>Aktive Sitzungen</h2>{session_cards}</div></div><div class="panel"><h2>Benutzerstatus</h2>{user_cards}</div>'''

    return f'''
<div class="notice warn"><b>Build 132 · Collaboration & Governance:</b> Rollen, Fallisolation, Sitzungswiderruf, Objekt-Locking und Vier-Augen-Freigaben ergänzen den bestehenden lokalen Schutz. Keine automatische Freigabe, Rollenänderung, Sitzungsteilung oder externe AI-Aktion.</div>
<div class="panel"><div class="inline"><span class="badge ok">Aktiver Benutzer: {esc(current.get('display_name'))}</span><span class="badge">{esc(current.get('role_key'))}</span><span class="badge candidate">Teammodus: {'aktiv' if settings.get('team_mode_enabled') else 'Einzelplatz-kompatibel'}</span><span class="badge">Server: loopback-only</span>{f'<form method="post" action="/governance/logout"><input type="hidden" name="csrf" value="{esc(csrf)}"><button class="ghost small">Team-Sitzung abmelden</button></form>' if settings.get('team_mode_enabled') else ''}</div></div>
<div class="metrics">{metric_html}</div>{admin_panel}
<div class="two-col"><div class="panel"><h2>Fallzuweisungen</h2>{assignment_cards}</div>
<div class="panel"><h2>Reviewer-AI</h2><form method="post" action="/governance/brief"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><button>Lokalen Governance-Brief erzeugen</button></form><p class="footer">Prüft Freigabekonflikte, Reviewer-Abdeckung, Locks und veraltete Berichte. 0 externe Aktionen.</p>{''.join(brief_cards) or '<div class="empty">Noch kein Reviewer-Brief.</div>'}</div></div>
<div class="panel"><h2>Vier-Augen-Freigaben</h2>{''.join(approval_cards) or '<div class="empty">Keine Freigabeanfrage.</div>'}</div>
<div class="two-col"><div class="panel"><h2>Objekt sperren</h2><form method="post" action="/governance/lock/acquire"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="form-grid"><div class="field"><label>Objekttyp</label><input name="object_type" placeholder="report_draft" required></div><div class="field"><label>Objekt-ID</label><input name="object_id" required></div></div><div class="form-grid"><div class="field"><label>Zweck</label><input name="purpose" minlength="8" required></div><div class="field"><label>TTL Minuten</label><input type="number" name="ttl_minutes" min="2" max="120" value="15"></div></div><button>Sperre anlegen</button></form>{lock_cards}</div>
<div class="panel"><h2>Fallkommentar</h2><form method="post" action="/governance/comment"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="form-grid"><div class="field"><label>Objekttyp</label><input name="object_type" value="case"></div><div class="field"><label>Objekt-ID</label><input name="object_id" value="{esc(case_id)}"></div></div><div class="field"><label>Kommentar</label><textarea name="text" rows="4" required></textarea></div><button>Kommentar speichern</button></form><p class="footer">Kommentartext bleibt ausschließlich in der kontrollierten Tabelle; Audit enthält nur den SHA-256-Fingerprint.</p>{table(data['comments'], [('created_at','Zeit'),('author_username','Autor'),('object_type','Objekt'),('object_id','ID'),('comment_text','Kommentar')])}</div></div>
'''
