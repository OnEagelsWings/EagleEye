from __future__ import annotations
import html

def e(v): return html.escape(str(v or ""))

def render_research_center(ctx, case_id: str, csrf: str, token: str) -> str:
    targets = ctx.targets.list_targets(case_id)
    tasks = ctx.search_workbench.list_tasks(case_id)
    packages = ctx.search_workbench.list_packages(case_id)
    target_opts = "".join(f'<option value="{e(t.get("target_id"))}">{e(t.get("name"))}</option>' for t in targets)
    checks = "".join(f'<label class="check"><input type="checkbox" name="engines" value="{e(x)}" checked> {e(x)}</label>' for x in ["Google","Bing","DuckDuckGo","Brave"])
    rows=[]
    for t in tasks[:500]:
        rows.append(
            '<tr>'
            f'<td>{e(t.get("package_name"))}</td><td>{e(t.get("category"))}</td><td>{e(t.get("query"))}</td>'
            f'<td>{e(t.get("engine"))}</td><td>{e(t.get("status"))}</td>'
            f'<td><a class="buttonlink" target="_blank" rel="noreferrer" href="{e(t.get("url"))}">Suchen</a></td>'
            f'<td><form class="inline" method="post" action="/research/open?token={e(token)}">'
            f'<input type="hidden" name="csrf" value="{e(csrf)}"><input type="hidden" name="task_id" value="{e(t.get("task_id"))}"><button>Als geöffnet markieren</button></form></td></tr>'
        )
    prows="".join(f'<tr><td>{e(p.get("name"))}</td><td>{e(p.get("objective"))}</td><td>{e(p.get("task_count"))}</td><td>{e(p.get("status"))}</td></tr>' for p in packages)
    if not target_opts:
        target_opts='<option value="">Zuerst eine Person anlegen</option>'
    return f'''<h2>Recherchezentrum</h2>
<p>Hier beginnt die eigentliche Personensuche. EagleEye erzeugt aus den Suchankern nachvollziehbare Suchaufgaben und öffnet normale öffentliche Suchoberflächen.</p>
<div class="callout"><b>Arbeitsfolge:</b> Suchpaket erzeugen → Suchlink öffnen → Treffer prüfen → relevante URL oder Text über Intake sichern → bei Bedarf Capture oder Crawl.</div>
<h3>1. Suchpakete erzeugen</h3>
<form method="post" action="/research/generate?token={e(token)}"><input type="hidden" name="csrf" value="{e(csrf)}"><input type="hidden" name="case_id" value="{e(case_id)}">
<label>Zielperson<select name="target_id" required>{target_opts}</select></label><div class="checks">{checks}</div><button>Rechercheaufgaben erzeugen</button></form>
<p class="muted">Allgemeine Suchmaschinen werden nicht per HTML-Scraping ausgelesen. Die Links funktionieren ohne API-Schlüssel. Eine integrierte Ergebnisliste wird über offizielle APIs oder eine eigene SearXNG-Instanz angebunden.</p>
<h3>2. Suchpakete</h3><table><tr><th>Paket</th><th>Ziel</th><th>Aufgaben</th><th>Status</th></tr>{prows or '<tr><td colspan="4">Noch keine Suchpakete.</td></tr>'}</table>
<h3>3. Suchaufgaben und Links</h3><table><tr><th>Paket</th><th>Kategorie</th><th>Suchanfrage</th><th>Suchmaschine</th><th>Status</th><th>Link</th><th>Queue</th></tr>{''.join(rows) or '<tr><td colspan="7">Noch keine Rechercheaufgaben.</td></tr>'}</table>
<h3>4. Spezialisierte Quellen</h3><div class="providergrid"><div class="provider"><b>GitHub / GitLab</b><p>Öffentliche Profile und Repositories.</p></div><div class="provider"><b>Wayback</b><p>Historische Versionen gefundener URLs.</p></div><div class="provider"><b>RDAP / DNS</b><p>Technischer Domainkontext.</p></div><div class="provider"><b>SearXNG / Brave API</b><p>Optionen für strukturierte automatische Treffer.</p></div></div>'''
