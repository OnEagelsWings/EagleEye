from __future__ import annotations

from typing import Any, Callable


def render_connectors148(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    svc = ctx.build148
    dash = svc.dashboard(case_id)
    connectors = dash.get("connectors") or []
    runs = dash.get("runs") or []
    quarantine = dash.get("quarantine") or []

    type_order = ["LOOKUP", "IMPORT", "ENRICHMENT", "MONITOR", "GUIDED_BROWSER", "CAPTURE", "EXPORT", "STREAM"]
    type_labels = {
        "LOOKUP": "Lookup", "IMPORT": "Import", "ENRICHMENT": "Enrichment", "MONITOR": "Monitoring",
        "GUIDED_BROWSER": "Geführter Browser", "CAPTURE": "Capture", "EXPORT": "Export", "STREAM": "Stream",
    }

    cards: list[str] = []
    for ctype in type_order:
        rows = [row for row in connectors if row.get("connector_type") == ctype]
        if not rows:
            continue
        items: list[str] = []
        for row in rows:
            state = str(row.get("health_state") or "unknown")
            state_class = "ok" if state == "operational" else "candidate"
            contract = str(row.get("contract_state") or "unaccepted")
            controls = f'''
<div class="inline">
<form method="post" action="/connectors148/contract/test"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="connector_id" value="{esc(row['connector_id'])}"><button class="ghost small">Vertrag testen</button></form>
<form method="post" action="/connectors148/contract/accept"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="connector_id" value="{esc(row['connector_id'])}"><input name="confirmation" placeholder="CONNECTOR-VERTRAG 148 AKZEPTIEREN" required><button class="small">Akzeptieren</button></form>
</div>'''
            items.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('label'))}</h3><span class="badge">{esc(ctype)}</span> <span class="badge {state_class}">{esc(state)}</span> <span class="badge">Vertrag {esc(contract)}</span></div></div><p>{esc(row.get('publisher'))} · Version {esc(row.get('connector_version'))} · Backend {esc(row.get('execution_backend'))}</p><p class="footer">Hosts: {esc(', '.join(row.get('allowed_hosts') or []) or 'keine externe Verbindung')} · Signatur: {esc(row.get('signature_status'))}</p>{controls}</div>''')
        cards.append(f'<details {"open" if ctype in {"LOOKUP","GUIDED_BROWSER"} else ""}><summary><b>{esc(type_labels[ctype])}</b> · {len(rows)} Connectoren</summary>{"".join(items)}</details>')

    operational = [row for row in connectors if row.get("health_state") == "operational" and row.get("connector_type") in {"LOOKUP", "GUIDED_BROWSER", "ENRICHMENT", "MONITOR"}]
    connector_options = ''.join(f'<option value="{esc(row["connector_id"])}">{esc(row["label"])} · {esc(row["connector_type"])}</option>' for row in operational)

    run_cards: list[str] = []
    for row in runs:
        run_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('label'))}</h3><span class="badge">{esc(row.get('status'))}</span></div></div><p>{esc(row.get('purpose'))}</p><p class="footer">{esc(row.get('execution_mode'))} · Treffer {int(row.get('result_count') or 0)} · Quarantäne {int(row.get('quarantine_count') or 0)} · {esc(row.get('created_at'))}</p></div>''')

    quarantine_cards: list[str] = []
    for row in quarantine:
        quarantine_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('title'))}</h3><span class="badge candidate">candidate-only</span> <span class="badge">{esc(row.get('review_status'))}</span></div></div><p>{esc(row.get('snippet'))}</p><p class="footer">{esc(row.get('label'))} · {esc(row.get('source_host'))}</p><form method="post" action="/connectors148/quarantine/review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="quarantine_id" value="{esc(row['quarantine_id'])}"><select name="status"><option value="ready_for_review">Zur fachlichen Prüfung</option><option value="accepted_candidate">Als Kandidat übernehmen</option><option value="rejected">Verwerfen</option></select><input name="reason" minlength="8" required placeholder="Prüfbegründung"><button>Prüfung speichern</button></form></div>''')

    secret_connectors = [row for row in connectors if row.get("secret_names")]
    secret_options = ''.join(f'<option value="{esc(row["connector_id"])}">{esc(row["label"])} · {esc(", ".join(row.get("secret_names") or []))}</option>' for row in secret_connectors)

    health = dash.get("health") or {}
    return f'''
<div class="notice"><b>Connector SDK 2.0:</b> Jeder Zugriff folgt Manifest → Vertragstest → manuelle Akzeptanz → kontrollierter Run → Quarantäne → fachliche Prüfung. Connectoren schreiben niemals direkt in Evidence Graph, Identitätsentscheidungen oder Berichte.</div>
<div class="metrics"><div class="metric"><div class="label">Connectoren</div><div class="value">{int(dash.get('total_connectors') or 0)}</div></div><div class="metric"><div class="label">Operativ</div><div class="value">{int(health.get('operational') or 0)}</div></div><div class="metric"><div class="label">Verträge akzeptiert</div><div class="value">{int(dash.get('accepted_contracts') or 0)}</div></div><div class="metric"><div class="label">Direkte Evidence-Schreibwege</div><div class="value">0</div></div></div>
<div class="panel"><h2>1. Connector-Katalog</h2><p>Die acht Connectorarten sind getrennt. Externe Hosts sind exakt allowlist-basiert, Vertragsänderungen sperren den Connector fail-closed.</p>{''.join(cards)}</div>
<div class="two-col"><div class="panel"><h2>2. Vertragstests und Governance</h2><p>Vor der ersten Ausführung müssen Manifest, Schemas, Host-Allowlist, Adapterbindung, Codefingerprint und candidate-only-Ausgabe vollständig bestehen.</p><div class="notice warn">Connector- und Secretverwaltung erfordern die globale Rolle Connectoradministrator oder Systemadministrator.</div><form method="post" action="/connectors148/secret/bind"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Connector mit deklariertem Secret</label><select name="connector_id">{secret_options}</select></div><div class="field"><label>Manifest-Secret-Name</label><input name="secret_name" placeholder="provider_api_key"></div><div class="field"><label>Vault-Key, kein Geheimniswert</label><input name="vault_key" placeholder="vault.provider.api_key"></div><label class="inline"><input type="checkbox" name="required" value="1"> Für Livebetrieb erforderlich</label><input name="confirmation" placeholder="CONNECTOR-SECRET 148 ZUORDNEN" required><button>Secret-Referenz zuordnen</button></form></div>
<div class="panel"><h2>3. Kontrollierte Ausführung</h2><form method="post" action="/connectors148/run"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Operativer Connector</label><select name="connector_id" required>{connector_options}</select></div><div class="field"><label>Öffentliche Suchanfrage</label><input name="query" required></div><div class="field"><label>Ermittlungszweck</label><input name="purpose" minlength="10" required></div><div class="form-grid"><div class="field"><label>Modus</label><select name="mode"><option value="dry_run">Dry Run</option><option value="replay">Replay/Test</option><option value="live">Live, freigegebene Schnittstelle</option></select></div><div class="field"><label>Max. Ergebnisse</label><input type="number" name="max_results" min="1" max="100" value="25"></div></div><input name="confirmation" placeholder="CONNECTOR-RUN 148 FREIGEBEN" required><button>Run kontrolliert starten</button></form></div></div>
<div class="panel"><h2>Ausführungsverlauf</h2>{''.join(run_cards) if run_cards else '<div class="empty">Noch keine Connector-Runs in diesem Fall.</div>'}</div>
<div class="panel"><h2>4. Quarantäne und manuelle Prüfung</h2><div class="notice warn">Alle Connector-Ergebnisse bleiben candidate-only. Eine Annahme macht aus dem Treffer noch keine bestätigte Tatsache oder Identität.</div>{''.join(quarantine_cards) if quarantine_cards else '<div class="empty">Noch keine Connector-Ergebnisse in der Quarantäne.</div>'}</div>
'''
