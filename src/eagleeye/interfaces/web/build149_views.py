from __future__ import annotations

from typing import Any, Callable

FAMILY_LABELS = {
    "official_registry": "Amtliche Register",
    "company_intelligence": "Unternehmen",
    "identity_authority": "Norm- und Identitätsdaten",
    "scholarly_identity": "Wissenschaftliche Identitäten",
    "publications_archive": "Publikationen und Archive",
    "legal_public_records": "Recht und öffentliche Dokumente",
    "social_community": "Social Media und Communities",
    "web_news_archive": "Web, Presse und Archive",
    "domain_infrastructure": "Domains und Infrastruktur",
    "media_visual": "Medien und Bildquellen",
    "sanctions_watchlist": "Sanktions- und Fahndungslisten",
    "licensed_enrichment": "Lizenzierte Anreicherung",
}


def render_ecosystem149(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    dash = ctx.build149.dashboard(case_id)
    sources = dash.get("sources") or []
    plans = dash.get("plans") or []
    jobs = dash.get("jobs") or []
    clusters = dash.get("clusters") or []

    family_cards: list[str] = []
    for family, label in FAMILY_LABELS.items():
        rows = [row for row in sources if row.get("source_family") == family]
        if not rows:
            continue
        items = []
        for row in sorted(rows, key=lambda item: (-int(item.get("priority") or 0), str(item.get("label") or ""))):
            health = str(row.get("health_state") or "unknown")
            badge = "ok" if health == "operational" else "candidate"
            items.append(
                f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('label'))}</h3>'''
                f'''<span class="badge {badge}">{esc(health)}</span> <span class="badge">{esc(row.get('access_tier'))}</span>'''
                f'''</div></div><p>{esc(row.get('category'))} · Autorität {int(row.get('authority_score') or 0)}/100 · Unabhängigkeit {int(row.get('independence_score') or 0)}/100</p>'''
                f'''<p class="footer">Risiko {esc(row.get('risk_level'))} · Eingaben: {esc(', '.join(row.get('input_types') or []))} · {esc(row.get('jurisdiction'))}</p></div>'''
            )
        family_cards.append(f'<details {"open" if family in {"official_registry","identity_authority","scholarly_identity"} else ""}><summary><b>{esc(label)}</b> · {len(rows)} Quellen</summary>{"".join(items)}</details>')

    family_options = ''.join(f'<option value="{esc(key)}">{esc(label)}</option>' for key, label in FAMILY_LABELS.items())
    plan_cards: list[str] = []
    for plan in plans:
        opsec = plan.get("opsec_assessment") or {}
        selected = plan.get("selected_connectors") or []
        findings = opsec.get("findings") or []
        selected_rows = ''.join(
            f'<li><b>{esc(item.get("label"))}</b> · {esc(item.get("source_family"))} · Wert {esc(item.get("expected_value"))} · Anker {esc(", ".join(item.get("anchor_types") or []))}</li>'
            for item in selected
        )
        finding_rows = ''.join(f'<li>{esc(item.get("severity"))}: {esc(item.get("message"))}</li>' for item in findings)
        approve = ''
        if plan.get("status") in {"draft", "review_required"}:
            approve = f'''<form method="post" action="/ecosystem149/plan/approve"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(plan.get('plan_id'))}"><input name="confirmation" placeholder="QUELLENPLAN 149 FREIGEBEN" required><button>Plan freigeben</button></form>'''
        plan_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(plan.get('objective'))}</h3><span class="badge">{esc(plan.get('status'))}</span> <span class="badge {'candidate' if opsec.get('blocked') else 'ok'}">OPSEC {'blockiert' if opsec.get('blocked') else 'prüfbar'}</span></div></div><p>{esc(plan.get('purpose'))}</p><p><b>Lokale AI-Auswahl:</b> {len(selected)} Quellen · Familien {esc(', '.join((plan.get('ai_brief') or {}).get('family_coverage', {}).keys()))}</p><details><summary>Ausgewählte Quellen</summary><ol>{selected_rows or '<li>Keine geeignete Quelle.</li>'}</ol></details><details><summary>OPSEC-Befunde</summary><ul>{finding_rows or '<li>Keine Blocker festgestellt.</li>'}</ul></details>{approve}</div>''')

    job_cards: list[str] = []
    for job in jobs:
        controls = ''
        if job.get("status") == "planned":
            controls = f'''<form method="post" action="/ecosystem149/job/execute"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="job_id" value="{esc(job.get('job_id'))}"><select name="mode"><option value="dry_run">Dry Run</option><option value="live">Live / manuell geführt</option></select><input name="confirmation" placeholder="QUELLENJOB 149 AUSFÜHREN" required><button>Job kontrolliert ausführen</button></form>'''
        job_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(job.get('source_key'))}</h3><span class="badge">{esc(job.get('status'))}</span> <span class="badge">{esc(job.get('risk_level'))}</span></div></div><p>{esc(job.get('query_text'))}</p><p class="footer">Familie {esc(job.get('source_family'))} · Erwartungswert {esc(job.get('expected_value'))} · Treffer {int(job.get('result_count') or 0)}</p>{controls}</div>''')

    cluster_cards = ''.join(
        f'''<div class="intake-card"><h3>{esc(row.get('representative_title'))}</h3><p>{int(row.get('member_count') or 0)} ähnliche Treffer · {int(row.get('independent_host_count') or 0)} Hosts · {int(row.get('independent_family_count') or 0)} Quellenfamilien</p><span class="badge candidate">{esc(row.get('assessment'))}</span></div>'''
        for row in clusters
    )

    health = dash.get("health") or {}
    return f'''
<div class="notice"><b>Quellenökosystem 149:</b> Die lokale AI priorisiert amtliche, institutionelle und unabhängige Quellen vor Social Media. Jede Außenhandlung bleibt manuell, budgetiert und fallgebunden. Treffer bleiben candidate-only.</div>
<div class="metrics"><div class="metric"><div class="label">Quellen gesamt</div><div class="value">{int(dash.get('total_sources') or 0)}</div></div><div class="metric"><div class="label">Neu in 149</div><div class="value">{int(dash.get('new_sources_149') or 0)}</div></div><div class="metric"><div class="label">Native/API</div><div class="value">{int(dash.get('native_or_api_sources') or 0)}</div></div><div class="metric"><div class="label">Automatische Außenaktionen</div><div class="value">0</div></div></div>
<div class="panel"><h2>1. Quellenportfolio prüfen</h2><p>Quellen werden nach Familie, Autorität, Unabhängigkeit, Aktualität, Risiko und Zugriffsart getrennt. Vertrag und Health werden weiterhin im Connector-Bereich verwaltet.</p>{''.join(family_cards)}</div>
<div class="two-col"><div class="panel"><h2>2. Lokalen AI- und OPSEC-Plan erstellen</h2><form method="post" action="/ecosystem149/plan/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson-ID, optional</label><input name="target_id"></div><div class="field"><label>Ermittlungsziel</label><input name="objective" minlength="8" required placeholder="Berufliche und digitale Identität belastbar prüfen"></div><div class="field"><label>Zweck</label><textarea name="purpose" minlength="10" required></textarea></div><div class="field"><label>Rechtsgrundlage</label><input name="legal_basis" minlength="8" required></div><div class="field"><label>Bevorzugte Quellenfamilien, Mehrfachauswahl</label><select name="families"><option value="">Automatisch aus Ermittlungsziel</option>{family_options}</select></div><div class="form-grid"><div class="field"><label>Offenlegungsbudget je Suche</label><input type="number" name="disclosure_budget" min="1" max="3" value="2"></div><div class="field"><label>Maximale Außenaktionen</label><input type="number" name="max_external_actions" min="1" max="20" value="10"></div></div><label class="inline"><input type="checkbox" name="allow_licensed_sources" value="1"> Lizenzierte Quellen einplanen</label><label class="inline"><input type="checkbox" name="allow_exact_email" value="1"> Exakte E-Mail ausschließlich für explizit freigegebene Spezialquelle zulassen</label><button>Plan lokal erzeugen</button></form></div>
<div class="panel"><h2>3. Schutzprinzipien</h2><ul><li>Maximal drei Identitätsanker je Suchvariante.</li><li>Sanktions- und Fahndungslisten nur bei passendem Ermittlungsziel.</li><li>Namensähnlichkeit ist kein Identitäts-, Schuld- oder Verurteilungsnachweis.</li><li>Lizenzierte Quellen benötigen Vertrag, Secret-Lease und gegebenenfalls Persona.</li><li>Keine externe AI, keine automatische Anmeldung, keine automatische Evidence-Schreibung.</li></ul><p>Connectorzustände: {esc(', '.join(f'{key}: {value}' for key, value in sorted(health.items())))}</p></div></div>
<div class="panel"><h2>4. Quellenpläne prüfen und freigeben</h2>{''.join(plan_cards) if plan_cards else '<div class="empty">Noch kein Quellenplan für diesen Fall.</div>'}</div>
<div class="panel"><h2>5. Kontrollierte Jobs</h2>{''.join(job_cards) if job_cards else '<div class="empty">Jobs entstehen erst nach manueller Planfreigabe.</div>'}</div>
<div class="panel"><h2>6. Quellendubletten und Unabhängigkeit</h2><form method="post" action="/ecosystem149/results/cluster"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input name="confirmation" placeholder="QUELLENERGEBNISSE 149 CLUSTERN" required><button>Candidate-Ergebnisse lokal clustern</button></form>{cluster_cards or '<div class="empty">Noch keine Dublettencluster.</div>'}</div>
'''
