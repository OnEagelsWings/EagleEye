from __future__ import annotations
from typing import Any, Callable


def render_handover168(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    service = ctx.service_registry.get('build168')
    state = service.dashboard(case_id)
    rows = [[p['title'], p['status'], p['validation_status'], p['created_at'], p['manifest_sha256'][:16] + '…'] for p in state['packages']]
    package_table = table(['Akte', 'Status', 'Validierung', 'Erstellt', 'Manifest-Hash'], rows) if rows else '<div class="notice">Noch keine Übergabeakte erstellt.</div>'
    requirements = ''.join(f'<li>{esc(item)}</li>' for item in state['requirements'])
    limitations = ''.join(f'<li>{esc(item)}</li>' for item in state['limitations'])
    return f'''<div class="notice warn"><b>Behördenakte Build 168:</b> OSINT-Hinweise sind keine gerichtlichen Feststellungen. Export, Integrität, Chain of Custody und Zwei-Personen-Freigabe werden getrennt geprüft.</div><div class="metrics"><div class="metric"><div class="label">Registrierte Evidenzobjekte</div><div class="value">{state['evidence_count']}</div></div><div class="metric"><div class="label">Akten</div><div class="value">{len(state['packages'])}</div></div></div><div class="two-col"><div class="panel"><h2>Übergabestatus</h2>{package_table}</div><div class="panel"><h2>Pflichtprüfungen</h2><ul>{requirements}</ul><h3>Methodische Grenzen</h3><ul>{limitations}</ul></div></div><div class="panel"><h2>Übergabekette</h2><div class="flowbar"><span class="flowstep ready"><b>1. Inventar</b>SHA-256 & Provenienz</span><span class="flowstep"><b>2. Custody</b>hashverkettete Ereignisse</span><span class="flowstep"><b>3. Export</b>JSON, HTML, CSV</span><span class="flowstep"><b>4. Validierung</b>Datei- und Kettenprüfung</span><span class="flowstep"><b>5. Freigabe</b>Analyst + Supervisor</span><span class="flowstep"><b>6. Übergabe</b>Empfangsnachweis</span></div></div>'''
