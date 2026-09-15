from __future__ import annotations

from typing import Any, Callable


def render_research_strategy(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    svc = ctx.research_strategy_128
    dash = svc.dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    options = "".join(f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets)
    strategies = dash.get("strategies") or []
    latest = None
    if strategies:
        latest = svc.get_strategy(case_id, strategies[0]["strategy_id"])
    connector_rows = dash.get("connectors") or []
    strategy_table = table(strategies, [("created_at", "Zeit"), ("target_id", "Ziel"), ("status", "Status"), ("query_count", "Queries"), ("connector_count", "Connectoren"), ("source_count", "Quellen"), ("coverage_score", "Coverage")])
    connector_table = table(connector_rows, [("label", "Connector"), ("connector_type", "Typ"), ("provider_key", "Provider"), ("execution_mode", "Modus"), ("network_policy", "Netzwerk"), ("enabled", "Aktiv")])
    connector_options = "".join(f'<option value="{esc(row["connector_key"])}">{esc(row["label"])} · {esc(row["provider_key"])}</option>' for row in connector_rows if row.get("enabled"))
    source_table = table(dash.get("source_roles") or [], [("source_role", "Quellenrolle"), ("n", "Anzahl")])
    cluster_table = table(dash.get("clusters") or [], [("cluster_kind", "Cluster"), ("n", "Clusterzahl"), ("members", "Mitglieder")])
    detail = '<div class="notice">Noch keine Research-Intelligence-Strategie für diesen Fall erzeugt.</div>'
    if latest:
        coverage = latest.get("coverage") or {}
        ai = (latest.get("ai_brief") or {}).get("content") or {}
        gaps = "".join(f"<li>{esc(item)}</li>" for item in coverage.get("open_gaps", [])) or "<li>Keine offenen Lücken berechnet.</li>"
        next_steps = "".join(f"<li>{esc(item)}</li>" for item in ai.get("recommended_next_steps", [])) or "<li>Menschliches Review fortsetzen.</li>"
        node_counts: dict[str, int] = {}
        for node in latest.get("nodes") or []:
            node_counts[node.get("node_type", "unknown")] = node_counts.get(node.get("node_type", "unknown"), 0) + 1
        detail = f'''<div class="two-col"><div class="panel"><h2>Aktuelle Coverage</h2><div class="metrics"><div class="metric"><b>{int(coverage.get("coverage_score") or 0)}</b>Coverage</div><div class="metric"><b>{int(coverage.get("independent_hosts") or 0)}</b>unabhängige Hosts</div><div class="metric"><b>{int(coverage.get("source_clusters") or 0)}</b>Quellencluster</div><div class="metric"><b>{int(coverage.get("duplicate_penalty") or 0)}</b>Duplikatabzug</div></div><h3>Offene Lücken</h3><ul>{gaps}</ul></div><div class="panel"><h2>AI-Ermittlungsbrief</h2><p><b>Status:</b> suggestions_only · menschliches Review erforderlich</p><ul>{next_steps}</ul><p class="footer">Keine autonome Recherche, keine Identitätsbestätigung und keine automatische Evidence-Promotion.</p></div></div><div class="panel"><h2>Query-Graph</h2><p>{esc(node_counts)} · {len(latest.get("edges") or [])} Kanten · Digest {esc(str(latest.get("graph_digest") or "")[:20])}…</p><p class="footer">Der Graph erklärt Anker → Query → Connector → Quelle. Er bewertet nicht automatisch die Wahrheit einer Quelle.</p></div>'''
    return f'''<div class="notice warn"><b>Build 128 Research Intelligence:</b> Query-Graph, Quellenprovenienz, Kopier-/Abhängigkeitscluster und Coverage. Externe Connectoren bleiben bis zur menschlichen Providerfreigabe gesperrt.</div>
<div class="panel"><h2>Strategie erzeugen</h2><form method="post" action="/research-intelligence/create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="form-grid"><div class="field"><label>Person/Entität</label><select name="target_id" required>{options}</select></div><div class="field"><label>Maximale Queryzahl</label><input type="number" min="10" max="160" name="query_limit" value="80"></div></div><p><button>Query-Graph und Source Intelligence erstellen</button></p></form></div>
{detail}
<div class="two-col"><div class="panel"><h2>Strategieläufe</h2>{strategy_table}</div><div class="panel"><h2>Quellenbestand</h2>{source_table}<h3>Abhängigkeitscluster</h3>{cluster_table}</div></div>
<div class="panel"><h2>Connector SDK – 10 öffentliche Connectoren</h2><div class="notice warn">Live-Läufe benötigen vorher unter <b>Sicherheit</b> eine einmalige Freigabe für den konkreten Provider. EagleEye sendet nur einen minimierten, überprüften Anker und protokolliert im Sicherheits-Audit ausschließlich dessen SHA-256-Fingerprint.</div><form method="post" action="/research-intelligence/connector-run"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="form-grid"><div class="field"><label>Person/Entität</label><select name="target_id" required>{options}</select></div><div class="field"><label>Connector</label><select name="connector_key" required>{connector_options}</select></div><div class="field"><label>Modus</label><select name="mode"><option value="live">live – einmalige Netzfreigabe erforderlich</option><option value="replay">replay – vorhandene Fixture</option></select></div><div class="field"><label>Maximale Treffer</label><input type="number" min="1" max="50" name="max_results" value="20"></div></div><div class="field"><label>Dokumentierter Zweck</label><textarea name="purpose" rows="3" required></textarea></div><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="CONNECTOR RUN APPROVED" required></div><p><button>Connector kontrolliert ausführen</button></p></form>{connector_table}</div>'''
