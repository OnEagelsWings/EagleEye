from __future__ import annotations

from typing import Any, Callable


def render_capture150(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    dash = ctx.build150.dashboard(case_id)
    policies = dash.get("policies") or []
    sessions = dash.get("sessions") or []
    records = dash.get("records") or []
    diffs = dash.get("diffs") or []
    chain = dash.get("chain") or {}

    policy_cards: list[str] = []
    for row in policies:
        approve = ""
        if row.get("status") == "draft":
            approve = f'''<form method="post" action="/capture150/policy/approve"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="policy_id" value="{esc(row.get('policy_id'))}"><input name="confirmation" placeholder="CAPTURE-POLICY 150 FREIGEBEN" required><button>Policy freigeben</button></form>'''
        start = ""
        if row.get("status") == "approved":
            start = f'''<form method="post" action="/capture150/session/start"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="policy_id" value="{esc(row.get('policy_id'))}"><input type="number" name="duration_minutes" min="10" max="240" value="60"><input name="confirmation" placeholder="CAPTURE-SESSION 150 STARTEN" required><button>Session starten</button></form>'''
        policy_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('label'))}</h3><span class="badge">{esc(row.get('status'))}</span> <span class="badge {'candidate' if row.get('mode') == 'approved_hosts' else 'ok'}">{esc(row.get('mode'))}</span></div></div><p>{esc(row.get('purpose'))}</p><p><b>Hosts:</b> {esc(', '.join(row.get('allowed_hosts') or [])) or 'manuelle Aufnahme'}</p><p class="footer">Intervall {int(row.get('min_interval_seconds') or 0)} s · Budget {int(row.get('max_captures') or 0)} · Retention {int(row.get('retention_days') or 0)} Tage</p>{approve}{start}</div>''')

    session_cards: list[str] = []
    for row in sessions:
        stop = ""
        if row.get("status") == "active":
            stop = f'''<form method="post" action="/capture150/session/stop"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="session_id" value="{esc(row.get('session_id'))}"><input name="confirmation" placeholder="CAPTURE-SESSION 150 BEENDEN" required><button>Session sicher beenden</button></form>'''
        session_cards.append(f'''<div class="intake-card"><h3>{esc(row.get('session_id'))}</h3><span class="badge {'ok' if row.get('status') == 'active' else ''}">{esc(row.get('status'))}</span><p>{int(row.get('captured_count') or 0)} / {int(row.get('max_captures') or 0)} Captures · Ablauf {esc(row.get('expires_at'))}</p>{stop}</div>''')

    record_cards: list[str] = []
    for row in records:
        verify = f'''<form method="post" action="/capture150/record/verify"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="record_id" value="{esc(row.get('record_id'))}"><input name="confirmation" placeholder="CAPTURE 150 INTEGRITÄT PRÜFEN" required><button>Integrität prüfen</button></form>'''
        record_cards.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get('title'))}</h3><span class="badge">{esc(row.get('trigger_mode'))}</span> <span class="badge {'ok' if row.get('integrity_state') == 'verified' else 'candidate'}">{esc(row.get('integrity_state'))}</span></div></div><p>{esc(row.get('canonical_url'))}</p><p class="footer">{esc(row.get('change_state'))} · WACZ {esc(str(row.get('package_sha256') or '')[:16])}… · candidate-only</p>{verify}</div>''')

    diff_cards = ''.join(f'''<div class="intake-card"><h3>Änderung {esc(row.get('diff_id'))}</h3><p>Text {int(row.get('text_changed') or 0)} · HTML {int(row.get('html_changed') or 0)} · Screenshot {int(row.get('screenshot_changed') or 0)} · Ressourcen +{int(row.get('resources_added') or 0)}/-{int(row.get('resources_removed') or 0)}</p><span class="badge candidate">{esc(row.get('review_status'))}</span></div>''' for row in diffs)

    return f'''
<div class="notice"><b>Browser Evidence Capture 150:</b> Manuelle oder ausdrücklich freigegebene hostgebundene Captures aus dem isolierten Fallbrowser. HTML, sichtbarer Text, Viewport-Screenshot, Metadaten und Ressourceninventar werden gehasht und als candidate-only archiviert. Kein privater Browser, keine automatische Faktenpromotion.</div>
<div class="metrics"><div class="metric"><div class="label">Policies</div><div class="value">{len(policies)}</div></div><div class="metric"><div class="label">Captures</div><div class="value">{len(records)}</div></div><div class="metric"><div class="label">Eventkette</div><div class="value">{'OK' if chain.get('valid') else 'FEHLER'}</div></div><div class="metric"><div class="label">Vollständiger Netzwerk-WARC</div><div class="value">Nein</div></div></div>
<div class="two-col"><div class="panel"><h2>1. Capture-Policy anlegen</h2><form method="post" action="/capture150/policy/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Zielperson-ID, optional</label><input name="target_id"></div><div class="field"><label>Bezeichnung</label><input name="label" minlength="3" required></div><div class="field"><label>Zweck</label><textarea name="purpose" minlength="10" required></textarea></div><div class="field"><label>Rechtsgrundlage</label><input name="legal_basis" minlength="8" required></div><div class="field"><label>Modus</label><select name="mode"><option value="manual">Nur manuelle Aufnahme</option><option value="approved_hosts">Automatisch auf exakt freigegebenen Hosts</option></select></div><div class="field"><label>Erlaubte Hosts, komma- oder zeilengetrennt</label><textarea name="allowed_hosts" placeholder="example.org&#10;www.example.org"></textarea></div><div class="form-grid"><div class="field"><label>Mindestintervall Sekunden</label><input type="number" name="min_interval_seconds" min="10" max="86400" value="30"></div><div class="field"><label>Capture-Budget</label><input type="number" name="max_captures" min="1" max="5000" value="100"></div></div><label class="inline"><input type="checkbox" name="include_html" value="1" checked> HTML</label><label class="inline"><input type="checkbox" name="include_visible_text" value="1" checked> sichtbarer Text</label><label class="inline"><input type="checkbox" name="include_screenshot" value="1" checked> Viewport-Screenshot</label><label class="inline"><input type="checkbox" name="include_resources" value="1" checked> Ressourceninventar</label><button>Policy als Entwurf speichern</button></form></div>
<div class="panel"><h2>2. Sicherheitsgrenzen</h2><ul><li>Automatik nur mit exakter Host-Allowlist und unabhängiger Freigabe.</li><li>Nur öffentliche HTTPS-Seiten; lokale/private Adressen und Secret-URLs werden blockiert.</li><li>Kein automatischer Login, kein Formularausfüllen, kein Download fremder Dateien.</li><li>WACZ-Paket enthält Companion-Snapshot und WARC-Ressourcenrecords, aber keinen vollständigen Netzwerkverkehr.</li><li>System-Proxyvariablen werden nicht implizit übernommen.</li></ul></div></div>
<div class="panel"><h2>3. Policies prüfen und Sessions starten</h2>{''.join(policy_cards) if policy_cards else '<div class="empty">Noch keine Capture-Policy.</div>'}</div>
<div class="panel"><h2>4. Aktive und frühere Sessions</h2>{''.join(session_cards) if session_cards else '<div class="empty">Noch keine Capture-Session.</div>'}</div>
<div class="panel"><h2>5. Capture-Records</h2>{''.join(record_cards) if record_cards else '<div class="empty">Noch keine Build-150-Captures.</div>'}</div>
<div class="panel"><h2>6. Änderungsverläufe</h2>{diff_cards or '<div class="empty">Noch keine Vergleichsaufnahme.</div>'}</div>
'''
