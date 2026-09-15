from __future__ import annotations
from typing import Any, Callable


def render_auth146(ctx: Any, case_id: str, csrf: str, *, actor: str, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    service = ctx.build146
    status = service.dashboard()
    users = status.get("users_detail") or []
    sessions = status.get("active_sessions_detail") or []
    events = status.get("recent_events") or []
    memberships = service.list_case_memberships(case_id) if case_id else service.list_case_memberships()
    me = service.public_user(actor)
    is_admin = me.get("global_role") == "system_administrator"
    can_revoke_sessions = me.get("global_role") in {"system_administrator", "security_administrator"}
    roles = ["system_administrator", "security_administrator", "connector_administrator", "auditor", "investigator", "reviewer", "read_only"]
    role_options = "".join(f'<option value="{esc(role)}">{esc(role.replace("_", " ").title())}</option>' for role in roles)
    user_options = "".join(f'<option value="{esc(row["username"])}">{esc(row["display_name"])} · {esc(row["username"])}</option>' for row in users)
    session_options = "".join(f'<option value="{esc(row["session_id"])}">{esc(row["username"])} · {esc(row["session_id"])}</option>' for row in sessions)
    cards = f'''<div class="metrics">
      <div class="metric"><div class="label">Benutzer</div><div class="value">{int(status.get("users") or 0)}</div></div>
      <div class="metric"><div class="label">Aktive Sitzungen</div><div class="value">{int(status.get("active_sessions") or 0)}</div></div>
      <div class="metric"><div class="label">Passwortalgorithmus</div><div class="value" style="font-size:18px">Argon2id</div></div>
      <div class="metric"><div class="label">WebAuthn</div><div class="value" style="font-size:18px">{"bereit" if status.get("webauthn_available") else "optional nicht installiert"}</div></div>
    </div>'''
    admin = ""
    if is_admin:
        admin = f'''<div class="two-col"><div class="panel"><h2>Benutzer anlegen</h2>
        <form method="post" action="/auth146/users/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
        <div class="field"><label>Benutzername</label><input name="username" pattern="[a-z0-9._-]{{3,32}}" required autocomplete="off"></div>
        <div class="field"><label>Anzeigename</label><input name="display_name" required></div>
        <div class="field"><label>Globale Rolle</label><select name="global_role">{role_options}</select></div>
        <div class="field"><label>Temporäres Startpasswort, mindestens 15 Zeichen</label><input type="password" name="password" minlength="15" maxlength="128" required autocomplete="new-password"></div>
        <p><button>Benutzer kontrolliert anlegen</button></p></form></div>
        <div class="panel"><h2>Fallmitgliedschaft</h2>
        <form method="post" action="/auth146/cases/assign"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
        <div class="field"><label>Benutzer</label><select name="username">{user_options}</select></div>
        <div class="field"><label>Fallrolle</label><select name="case_role"><option>case_lead</option><option>investigator</option><option>analyst</option><option>reviewer</option><option>report_author</option><option>read_only</option></select></div>
        <div class="field"><label>Notiz</label><input name="notes" placeholder="Zweck der Zuweisung"></div>
        <p><button>Fallzugriff vergeben</button></p></form></div></div>
        <div class="two-col"><div class="panel"><h2>Benutzerstatus ändern</h2><p>Rollenänderung oder Deaktivierung widerruft sämtliche Sitzungen. Das letzte aktive Administratorkonto ist geschützt.</p>
        <form method="post" action="/auth146/users/update"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
        <div class="field"><label>Benutzer</label><select name="username">{user_options}</select></div><div class="field"><label>Globale Rolle</label><select name="global_role">{role_options}</select></div>
        <div class="form-grid"><div class="field"><label>Aktiv</label><select name="active"><option value="1">ja</option><option value="0">nein</option></select></div><div class="field"><label>Passwortwechsel erzwingen</label><select name="must_change_password"><option value="0">nein</option><option value="1">ja</option></select></div></div>
        <p><button>Benutzerstatus nach Step-up ändern</button></p></form></div>
        <div class="panel"><h2>Fallzugriff entziehen</h2><form method="post" action="/auth146/cases/revoke"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
        <div class="field"><label>Benutzer</label><select name="username">{user_options}</select></div><div class="field"><label>Fallrolle</label><select name="case_role"><option>case_lead</option><option>investigator</option><option>analyst</option><option>reviewer</option><option>report_author</option><option>read_only</option></select></div><div class="field"><label>Entzugsgrund</label><input name="reason" minlength="8" required></div><p><button>Fallzugriff nach Step-up entziehen</button></p></form></div></div>'''
    return f'''<div class="notice">Build 147 führt die sichere Benutzer-, Sitzungs- und Berechtigungsschicht fort und schützt zusätzlich Social- und Datenbankrecherche zentral. Rechte werden auf jeder Anfrage und zusätzlich in der bestehenden Governance geprüft.</div>
    <div class="panel"><h2>Identity &amp; Access Foundation</h2>{cards}<p class="footer">Passwortparameter: {esc(status.get("password_parameters"))} · Policy {esc(service.POLICY_VERSION)} · anonyme Fallzugriffe: nein</p></div>
    <div class="two-col"><div class="panel"><h2>Eigenes Passwort ändern</h2>
    <form method="post" action="/auth146/password/change"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
    <div class="field"><label>Aktuelles Passwort</label><input type="password" name="current_password" required autocomplete="current-password"></div>
    <div class="field"><label>Neues Passwort</label><input type="password" name="new_password" minlength="15" maxlength="128" required autocomplete="new-password"></div>
    <p><button>Passwort ändern und Sitzungen widerrufen</button></p></form></div>
    <div class="panel"><h2>Recovery und Sitzungen</h2><p>Neue Codes widerrufen alle bislang unbenutzten Recovery-Codes. Die Codes werden nur einmal angezeigt.</p>
    <form class="inline" method="post" action="/auth146/recovery/generate"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><button>Recovery-Codes erzeugen</button></form>
    <form class="inline" method="post" action="/auth146/sessions/revoke-others"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><button class="ghost">Andere Sitzungen abmelden</button></form></div></div>
    <div class="panel"><h2>Step-up für kritische Aktionen</h2><p>Eine zeitlich begrenzte erneute Passwortprüfung ist unter anderem für Berichtfreigabe, Backup-Restore, Secret-Verwaltung, Lockdown und Research-Persona-Start erforderlich.</p>
    <form method="post" action="/auth146/step-up"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
    <div class="form-grid"><div class="field"><label>Aktion</label><select name="action_key"><option value="report.release">Bericht veröffentlichen</option><option value="phase4.seal">Phase-4-Seal</option><option value="persona.session.start">Research-Persona starten</option><option value="backup.restore">Backup wiederherstellen</option><option value="secret.manage">Secret Vault verwalten</option><option value="security.lockdown">Security Lockdown</option><option value="user.manage">Benutzer-/Fallzugriffsverwaltung</option><option value="session.revoke">Sitzung administrativ widerrufen</option></select></div><div class="field"><label>Passwort erneut eingeben</label><input type="password" name="password" required autocomplete="current-password"></div></div><p><button>Step-up-Freigabe für 15 Minuten erteilen</button></p></form></div>
    {admin}
    {f'<div class="panel"><h2>Sitzung administrativ widerrufen</h2><form method="post" action="/auth146/sessions/revoke"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Sitzung</label><select name="session_id">{session_options}</select></div><div class="field"><label>Grund</label><input name="reason" value="Administratorprüfung" minlength="8" required></div><p><button>Sitzung nach Step-up widerrufen</button></p></form></div>' if can_revoke_sessions and sessions else ''}
    <div class="panel"><h2>Benutzer</h2>{table(users, [("username","Benutzername"),("display_name","Anzeigename"),("global_role","Globale Rolle"),("active","Aktiv"),("must_change_password","Passwortwechsel"),("last_login_at","Letzte Anmeldung")])}</div>
    <div class="panel"><h2>Fallmitgliedschaften</h2>{table(memberships, [("case_id","Fall"),("username","Benutzer"),("case_role","Fallrolle"),("active","Aktiv"),("granted_by","Vergeben durch"),("revoked_by","Entzogen durch")])}</div>
    <div class="panel"><h2>Aktive Sitzungen</h2>{table(sessions, [("session_id","Sitzung"),("username","Benutzer"),("assurance_level","Assurance"),("created_epoch","Beginn"),("idle_expires_epoch","Inaktivitätsende"),("absolute_expires_epoch","Gesamtende")])}</div>
    <div class="panel"><h2>Letzte Sicherheitsereignisse</h2>{table(events, [("created_at","Zeit"),("event_type","Ereignis"),("severity","Stufe"),("case_id","Fall")])}</div>'''
