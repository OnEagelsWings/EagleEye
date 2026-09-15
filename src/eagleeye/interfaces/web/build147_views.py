from __future__ import annotations

from typing import Any, Callable


def render_research147(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    svc = ctx.build147
    dashboard = svc.dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    target_options = '<option value="">Ohne Zielbindung</option>' + ''.join(
        f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets
    )
    social = svc.list_sources("social")
    databases = svc.list_sources("database")

    def source_checks(rows: list[dict[str, Any]], defaults: set[str]) -> str:
        cards = []
        for row in rows:
            checked = " checked" if row["source_key"] in defaults else ""
            persona = ' · Persona empfohlen' if row.get("persona_recommended") else ''
            native = 'native API' if row.get("native_execution") else 'geführter Browser'
            cards.append(
                f'<label class="action-card" style="cursor:pointer"><div class="inline">'
                f'<input style="width:auto" type="checkbox" name="source_{esc(row["source_key"])}" value="1"{checked}>'
                f'<b>{esc(row["label"])}</b></div><p>{esc(row["category"])} · {esc(native)} · Risiko {esc(row["risk_level"])}{esc(persona)}</p>'
                f'<span class="badge">{esc(row["auth_requirement"])}</span></label>'
            )
        return '<div class="actions">' + ''.join(cards) + '</div>'

    active_persona = dashboard.get("active_persona_session") or {}
    persona_note = (
        f'<div class="notice">Aktive Research-Persona-Sitzung: <b>{esc(active_persona.get("session_id"))}</b> · '
        f'Aktionsbudget {int(active_persona.get("consumed_actions") or 0)}/{int(active_persona.get("max_actions") or 0)}</div>'
        if active_persona else
        '<div class="notice warn">Keine aktive Research-Persona-Sitzung. Accountpflichtige und risikoreiche Plattformen werden blockiert oder nur nach vorgelagerter OPSEC-Sitzung geöffnet.</div>'
    )

    plan_rows = dashboard.get("plans") or []
    plans_html = []
    for row in plan_rows:
        action = ''
        if row.get("status") == "draft":
            action = f'''<form method="post" action="/research147/plan/approve"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(row["plan_id"])}"><input name="confirmation" placeholder="RECHERCHEPLAN 147 FREIGEBEN" required><button>Plan prüfen und freigeben</button></form>'''
        plans_html.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("objective"))}</h3><span class="badge">{esc(row.get("status"))}</span> <span class="badge">Risiko {esc(row.get("risk_level"))}</span></div></div><p>Erstellt von {esc(row.get("created_by"))} · {esc(row.get("created_at"))}</p>{action}</div>''')

    jobs_html = []
    for row in dashboard.get("jobs") or []:
        status = str(row.get("status") or "")
        execute = ''
        if status in {"queued", "leased", "failed_retryable"}:
            execute = f'''<form method="post" action="/research147/job/execute"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="job_id" value="{esc(row["job_id"])}"><input name="confirmation" placeholder="RECHERCHEJOB 147 AUSFÜHREN" required><select name="mode"><option value="replay">Replay/Test</option><option value="live">Live, offizielle öffentliche API</option></select><button>Kontrolliert ausführen</button></form>'''
        elif status == "opened_manual_review":
            execute = f'''<form method="post" action="/research147/job/complete"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="job_id" value="{esc(row["job_id"])}"><input type="number" min="0" max="500" name="result_count" value="0"><button>Manuelle Sichtung abschließen</button></form>'''
        jobs_html.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("label"))}</h3><span class="badge">{esc(status)}</span> <span class="badge candidate">candidate-only</span></div></div><p><b>Query:</b> {esc(row.get("query_text"))}</p><p class="footer">{esc(row.get("execution_mode"))} · Priorität {int(row.get("priority") or 0)} · Versuche {int(row.get("attempt_count") or 0)} · Treffer {int(row.get("result_count") or 0)}</p>{execute}</div>''')

    source_options = ''.join(f'<option value="{esc(row["source_key"])}">{esc(row["label"])}</option>' for row in social)
    candidate_rows = dashboard.get("candidates") or []
    candidates_html = []
    for row in candidate_rows:
        candidates_html.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("display_name") or row.get("username") or row.get("profile_url"))}</h3><span class="badge candidate">candidate-only</span> <span class="badge">{esc(row.get("review_status"))}</span></div><a class="button ghost small" href="{esc(row.get("canonical_url"))}" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">Offizielle Profilseite</a></div><p>{esc(row.get("bio"))}</p><p class="footer">{esc(row.get("label"))} · Konfidenz {float(row.get("confidence") or 0):.2f}</p><form method="post" action="/research147/candidate/review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="candidate_id" value="{esc(row["candidate_id"])}"><select name="status"><option value="needs_more_evidence">Weitere Belege</option><option value="plausible">Plausibel</option><option value="supported_context_only">Nur kontextuell gestützt</option><option value="rejected">Verwerfen</option></select><input name="reason" minlength="8" required placeholder="Prüfbegründung"><button>Prüfung speichern</button></form></div>''')

    return f'''
<div class="notice"><b>Logischer Ablauf:</b> 1. Ziel und minimale Anker festlegen · 2. Quellen auswählen · 3. OPSEC-Prüfung und manuelle Freigabe · 4. Jobs einzeln ausführen · 5. Kandidaten prüfen und in Evidence überführen.</div>
{persona_note}
<div class="metrics"><div class="metric"><div class="label">Social-Quellen</div><div class="value">{int((dashboard.get("sources") or {}).get("social",0))}</div></div><div class="metric"><div class="label">Datenbanken</div><div class="value">{int((dashboard.get("sources") or {}).get("database",0))}</div></div><div class="metric"><div class="label">Native Quellen</div><div class="value">{int(dashboard.get("native_sources") or 0)}</div></div><div class="metric"><div class="label">Automatische Logins</div><div class="value">0</div></div></div>
<div class="panel"><h2>1. Rechercheplan anlegen</h2><p>Die lokale AI-Assistenz erzeugt maximal drei Anker pro Query, priorisiert belastbare Datenbanken vor Social-Media-Kandidaten und führt keine externe AI-Abfrage aus.</p><form method="post" action="/research147/plan/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="form-grid"><div class="field"><label>Zielperson</label><select name="target_id">{target_options}</select></div><div class="field"><label>Ermittlungsziel</label><input name="objective" required placeholder="Öffentliche digitale Profile und berufliche Identität prüfen"></div><div class="field"><label>Zweck</label><input name="purpose" minlength="10" required></div><div class="field"><label>Rechtsgrundlage</label><input name="legal_basis" required></div><div class="field"><label>Name optional</label><input name="full_name"></div><div class="field"><label>Benutzername optional</label><input name="username"></div><div class="field"><label>E-Mail optional, nur falls erforderlich</label><input name="email"></div><div class="field"><label>Organisation</label><input name="organisation"></div><div class="field"><label>Ort</label><input name="location"></div><div class="field"><label>Weitere Aliase, zeilenweise</label><textarea name="aliases" rows="3"></textarea></div><div class="field"><label>Offenlegungsbudget je Query</label><select name="disclosure_budget"><option value="1">1 Anker – streng</option><option value="2" selected>2 Anker – ausgewogen</option><option value="3">3 Anker – maximal</option></select></div><div class="field"><label>Maximale externe Schritte</label><input type="number" name="max_external_actions" min="1" max="30" value="12"></div></div>
<details open><summary><b>2. Social-Media-Quellen</b></summary>{source_checks(social,{"bluesky_profiles","mastodon_profiles","github","youtube"})}</details>
<details><summary><b>2. Datenbanken und Register</b></summary>{source_checks(databases,{"gleif","openalex","crossref","wikidata","handelsregister"})}</details><p><button>Plan lokal erzeugen und OPSEC prüfen</button></p></form></div>
<div class="panel"><h2>3. Recherchepläne</h2>{''.join(plans_html) if plans_html else '<div class="empty">Noch kein Build-147-Rechercheplan.</div>'}</div>
<div class="panel"><h2>4. Kontrollierte Job-Warteschlange</h2><div class="notice warn">Live-API-Läufe verwenden ausschließlich bereits zugelassene öffentliche Provider. Accountpflichtige Plattformen werden nicht automatisiert angemeldet oder gescrapt.</div>{''.join(jobs_html) if jobs_html else '<div class="empty">Nach Planfreigabe erscheinen hier deduplizierte Jobs.</div>'}</div>
<div class="two-col"><div class="panel"><h2>5. Social-Profilkandidat dokumentieren</h2><form method="post" action="/research147/candidate/add"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Plattform</label><select name="source_key">{source_options}</select></div><div class="field"><label>Offizielle Profil-URL</label><input name="profile_url" required placeholder="https://..."></div><div class="form-grid"><div class="field"><label>Benutzername</label><input name="username"></div><div class="field"><label>Anzeigename</label><input name="display_name"></div><div class="field"><label>Ort</label><input name="location"></div><div class="field"><label>Vorläufige Konfidenz 0–0,95</label><input name="confidence" value="0.2"></div></div><div class="field"><label>Bio/öffentliche Beschreibung</label><textarea name="bio" rows="3"></textarea></div><div class="field"><label>Quellenkontext</label><textarea name="source_context" rows="3"></textarea></div><p><button>Als Kandidat speichern</button></p></form></div><div class="panel"><h2>AI- und OPSEC-Grenzen</h2><ul><li>Keine externe AI und keine autonome Außenaktion.</li><li>Keine automatische Kontoerstellung oder Anmeldung.</li><li>Keine Anti-Bot- oder CAPTCHA-Umgehung.</li><li>Keine automatische Identitätsbestätigung.</li><li>Query-Budget: maximal drei Identitätsanker.</li><li>Accountpflichtige Quellen verlangen aktive Persona-/Egress-Sitzung.</li></ul></div></div>
<div class="panel"><h2>Dokumentierte Social-Media-Kandidaten</h2>{''.join(candidates_html) if candidates_html else '<div class="empty">Noch keine Profile dokumentiert.</div>'}</div>
'''
