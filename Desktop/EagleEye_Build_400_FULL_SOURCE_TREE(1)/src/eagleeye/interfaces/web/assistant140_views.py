from __future__ import annotations

from typing import Any, Callable


def render_assistant140(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str]) -> str:
    data = ctx.build140.assistant_dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    target_options = '<option value="">Gesamten Fall analysieren</option>' + ''.join(
        f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets
    )
    analysis_options = ''.join(
        f'<option value="{esc(row["analysis_id"])}">{esc(row["created_at"])} · {esc(row["objective"])}</option>'
        for row in data["analyses"]
    )
    claim_cards: list[str] = []
    for row in data["claims"]:
        source_ids = ctx.db.one("SELECT source_ids_json,evidence_assertion_ids_json FROM ai_claims_140 WHERE claim_id=?", (row["claim_id"],)) or {}
        claim_cards.append(f'''
<article class="intake-card"><div class="intake-head"><div><h3>{esc(row['claim_type'])}</h3><p>{esc(row['statement'])}</p></div><span class="badge candidate">{esc(row['review_status'])}</span></div>
<p><b>Konfidenz:</b> {esc(round(float(row['confidence']), 2))} · <b>Belegabdeckung:</b> {esc(round(float(row['citation_coverage']) * 100))}% · automatische Identitätsaussage: <b>nein</b></p>
<form method="post" action="/assistant140/claim-review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="claim_id" value="{esc(row['claim_id'])}"><div class="form-grid"><div class="field"><label>Prüfstatus</label><select name="review_status"><option value="accepted">Akzeptiert</option><option value="needs_evidence">Mehr Belege</option><option value="rejected">Verworfen</option><option value="unreviewed">Ungeprüft</option></select></div><div class="field"><label>Prüfnotiz</label><input name="review_note" value="{esc(row.get('review_note') or '')}"></div></div><button class="small ghost">Aussage prüfen</button></form>
<form method="post" action="/assistant140/disclosure"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="analysis_id" value="{esc(row['analysis_id'])}"><input type="hidden" name="claim_id" value="{esc(row['claim_id'])}"><div class="form-grid"><div class="field"><label>Zieltyp</label><select name="destination_type"><option value="external_ai">Genehmigte externe AI</option><option value="human_reviewer">Menschlicher Prüfer</option><option value="search_provider">Suchanbieter</option></select></div><div class="field"><label>Zielbezeichnung</label><input name="destination_label" required></div></div><div class="field"><label>Zweck</label><input name="purpose" required></div><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="DATENPAKET MANUELL FREIGEBEN" required></div><button class="small">Minimiertes Paket erzeugen</button></form></article>''')
    rec_cards: list[str] = []
    for row in data["recommendations"]:
        rec_cards.append(f'''
<article class="intake-card"><div class="intake-head"><div><h3>{esc(row['title'])}</h3><p>{esc(row['rationale'])}</p></div><span class="badge">Priorität {esc(round(float(row['priority_score']), 2))}</span></div>
<p>Erkenntniswert {esc(row['expected_information_gain'])} · OPSEC-Risiko {esc(row['opsec_risk'])} · Aufwand {esc(row['effort'])} · manuelle Freigabe: ja</p>
<form method="post" action="/assistant140/plan"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="analysis_id" value="{esc(row['analysis_id'])}"><input type="hidden" name="recommendation_id" value="{esc(row['recommendation_id'])}"><div class="form-grid"><div class="field"><label>Zweck</label><input name="purpose" value="{esc(row['title'])}" required></div><div class="field"><label>Rechtsgrundlage</label><input name="legal_basis" value="berechtigtes Interesse" required></div></div><button class="small">OPSEC-Aktionsplan erstellen</button></form></article>''')
    plan_rows: list[str] = []
    for row in data["plans"]:
        approve = '' if row["blocked"] or row["approval_status"] != "draft" else f'''<form method="post" action="/assistant140/plan-review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="plan_id" value="{esc(row['plan_id'])}"><input type="hidden" name="decision" value="approved"><input name="confirmation" placeholder="OPSEC-PLAN MANUELL FREIGEBEN" required><button class="small">Freigeben</button></form>'''
        plan_rows.append(f"<tr><td>{esc(row['created_at'])}</td><td>{esc(row['risk_level'])}</td><td>{'blockiert' if row['blocked'] else esc(row['approval_status'])}</td><td>{esc(row['purpose'])}</td><td>{approve}</td></tr>")
    analysis_rows = ''.join(
        f"<tr><td>{esc(row['created_at'])}</td><td>{esc(row['objective'])}</td><td>{esc(round(float(row['evidence_coverage']) * 100))}%</td><td>{esc(row['uncertainty_band'])}</td><td>0</td></tr>"
        for row in data["analyses"]
    ) or '<tr><td colspan="5">Noch keine Build-140-Analyse.</td></tr>'
    packages = ''.join(
        f"<tr><td>{esc(row['created_at'])}</td><td>{esc(row['destination_type'])}</td><td>{esc(row['anchor_count'])}</td><td>{esc(row['package_sha256'][:16])}…</td><td>nein</td></tr>"
        for row in data["packages"]
    ) or '<tr><td colspan="5">Noch kein Offenlegungspaket.</td></tr>'
    return f'''
<div class="notice"><b>Build 140 · Evidence-Grounded AI Analyst:</b> Jede Aussage wird als Fakt, Wahrscheinlichkeit, Hypothese, Widerspruch oder offene Frage klassifiziert und mit Evidence- und Quellenreferenzen verknüpft. Belegtexte gelten grundsätzlich als untrusted input und werden auf Prompt-Injection-Muster geprüft.</div>
<div class="metrics"><div class="metric"><div class="label">Analysen</div><div class="value">{esc(data['analysis_count'])}</div></div><div class="metric"><div class="label">AI-Aussagen</div><div class="value">{esc(data['claim_count'])}</div></div><div class="metric"><div class="label">Offene Prüfungen</div><div class="value">{esc(data['open_claim_count'])}</div></div><div class="metric"><div class="label">Externe AI / autonome Aktionen</div><div class="value">0 / 0</div></div></div>
<div class="two-col"><div class="panel"><h2>Beleggebundene Analyse erzeugen</h2><form method="post" action="/assistant140/analyze"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Ermittlungsziel</label><textarea name="objective" rows="4" required></textarea></div><button>Analyse, Gegenhypothesen und nächste Schritte erzeugen</button></form></div>
<div class="panel"><h2>Sicherheitsvertrag 140</h2><ul><li>Keine externen Modellaufrufe oder autonomen Webaktionen</li><li>Keine vollständige Fallakte in Offenlegungspaketen</li><li>Maximal drei minimierte Identitätsanker</li><li>Keine Bilder, Gesichtsausschnitte oder biometrischen Daten</li><li>Jede kritische Aktion benötigt manuelle Freigabe</li></ul></div></div>
<div class="panel"><h2>Letzte Analysen</h2><div class="table-wrap"><table><thead><tr><th>Zeit</th><th>Ziel</th><th>Belegabdeckung</th><th>Unsicherheit</th><th>Extern</th></tr></thead><tbody>{analysis_rows}</tbody></table></div></div>
<div class="panel"><h2>Zitierbare Aussagen</h2>{''.join(claim_cards) if claim_cards else '<div class="empty">Noch keine Aussagen.</div>'}</div>
<div class="panel"><h2>Priorisierte nächste Schritte</h2>{''.join(rec_cards) if rec_cards else '<div class="empty">Noch keine Empfehlungen.</div>'}</div>
<div class="two-col"><div class="panel"><h2>OPSEC-Aktionspläne</h2><div class="table-wrap"><table><thead><tr><th>Zeit</th><th>Risiko</th><th>Status</th><th>Zweck</th><th>Freigabe</th></tr></thead><tbody>{''.join(plan_rows) if plan_rows else '<tr><td colspan="5">Noch keine Pläne.</td></tr>'}</tbody></table></div></div><div class="panel"><h2>Minimierte Offenlegungspakete</h2><div class="table-wrap"><table><thead><tr><th>Zeit</th><th>Zieltyp</th><th>Anker</th><th>Hash</th><th>Übertragen</th></tr></thead><tbody>{packages}</tbody></table></div></div></div>
'''
