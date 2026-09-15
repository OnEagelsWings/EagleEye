from __future__ import annotations
from typing import Any, Callable

def render_investigation167(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any],str], table: Callable[...,str]) -> str:
    svc=ctx.service_registry.get('build167')
    row=ctx.db.one('SELECT workflow_id FROM crime_threat_cases_167 WHERE case_id=?',(case_id,))
    crime=None; missing=None
    if row:
        crime=svc.situation(row['workflow_id'])
    mrow=ctx.db.one('SELECT workflow_id FROM missing_person_cases_166 WHERE case_id=?',(case_id,))
    if mrow:
        missing=ctx.service_registry.get('build166').situation(mrow['workflow_id'])
    manifest=svc.ui_manifest()
    cards=[]
    for section in manifest['sections']:
        cards.append(f'<a class="action-card" href="/?tab={esc(section["tab"])}&case_id={esc(case_id)}"><b>{esc(section["label"])}</b><br><span class="muted">{esc(" · ".join(section["contains"][:4]))}</span></a>')
    crime_html='<div class="notice">Für diesen Fall ist noch kein Straftaten-/Gefahrenhinweis-Workflow angelegt.</div>'
    if crime:
        c=crime['counts']
        crime_html=f'''<div class="metrics"><div class="metric"><div class="label">Beobachtungen</div><div class="value">{c['observations']}</div></div><div class="metric"><div class="label">Hypothesen</div><div class="value">{c['hypotheses']}</div></div><div class="metric"><div class="label">Schlüsselentitäten</div><div class="value">{c['entities']}</div></div><div class="metric"><div class="label">Offene Leads</div><div class="value">{c['open_leads']}</div></div></div><p><b>Informationslücken:</b> {esc(', '.join(crime['intelligence_gaps']) or 'keine automatisch erkannten')}</p>'''
    missing_html='<div class="notice">Kein Vermisstenfall-Workflow in diesem Fall.</div>'
    if missing:
        c=missing['counts']; missing_html=f'''<div class="metrics"><div class="metric"><div class="label">Sichtungen</div><div class="value">{c['sightings']}</div></div><div class="metric"><div class="label">Kontakte</div><div class="value">{c['contacts']}</div></div><div class="metric"><div class="label">Orte</div><div class="value">{c['locations']}</div></div><div class="metric"><div class="label">Offene Leads</div><div class="value">{c['open_leads']}</div></div></div>'''
    return f'''<div class="notice warn"><b>Ermittlungszentrale Build 167:</b> Hinweise, Hypothesen, Personen, Indikatoren und Leads bleiben getrennt. Zentralität, Nähe oder Erwähnung sind weder Schuld- noch Gefahrennachweis.</div><div class="panel"><h2>Konsolidierter Arbeitsbereich</h2><div class="actions">{''.join(cards)}</div></div><div class="two-col"><div class="panel"><h2>Straftaten & Gefahrenhinweise</h2>{crime_html}</div><div class="panel"><h2>Vermisstenfall</h2>{missing_html}</div></div><div class="panel"><h2>Arbeitslogik</h2><div class="flowbar"><span class="flowstep ready"><b>1. Quellen</b>öffentlich und freigegeben</span><span class="flowstep"><b>2. Beobachtungen</b>quellengebunden</span><span class="flowstep"><b>3. Hypothesen</b>mit Gegenbelegen</span><span class="flowstep"><b>4. Analyse</b>Identität, Graph, Zeit</span><span class="flowstep"><b>5. Übergabe</b>reviewpflichtige Akte</span></div></div>'''
