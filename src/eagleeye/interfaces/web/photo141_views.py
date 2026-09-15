from __future__ import annotations
from typing import Any, Callable
from .photo140_views import render_photo140


def render_photo141(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str]) -> str:
    data = ctx.build141.dashboard(case_id)
    assets = [r for r in ctx.build136.photo_dashboard(case_id).get("photos", []) if r.get("source_kind") == "local_file"]
    results = ctx.build138.photo_dashboard(case_id).get("results", [])
    asset_options = ''.join(f'<option value="{esc(r["asset_id"])}">{esc(r.get("title") or r.get("original_filename") or r["asset_id"])}</option>' for r in assets)
    result_options = ''.join(f'<option value="{esc(r["result_id"])}">{esc(r.get("page_title") or r.get("page_url") or r["result_id"])}</option>' for r in results)
    qrows = ''.join(f'<tr><td>{esc(r["page_title"])}</td><td>{esc(round(float(r["overall_score"])*100))}%</td><td>{esc(r["quality_band"])}</td><td>{"ja" if r["earliest_known_candidate"] else "nein"}</td><td>candidate-only</td></tr>' for r in data["photo_quality"]) or '<tr><td colspan="5">Noch keine Fototreffer-Qualitätsbewertung.</td></tr>'
    plans = ''.join(f'<tr><td>{esc(r["created_at"])}</td><td>{esc(r["purpose"])}</td><td>{esc(r["provider_diversity"])}</td><td>{esc(r["redundant_steps_removed"])}</td><td>{esc(r["estimated_minutes"])}</td><td>0 / 0</td></tr>' for r in data["photo_plans"]) or '<tr><td colspan="6">Noch kein Build-141-Fotorechercheplan.</td></tr>'
    header = f'''
<div class="notice"><b>Build 141 · Photo Research Quality & Efficient Search:</b> Treffer werden nach Quellenautorität, Provenienz, zeitlicher Priorität, technischer Bildrelation und Kontextqualität bewertet. Pläne vermeiden redundante Anbieterläufe, priorisieren Ursprungssuche und behalten jeden Upload manuell.</div>
<div class="metrics"><div class="metric"><div class="label">Bewertete Fototreffer</div><div class="value">{esc(len(data['photo_quality']))}</div></div><div class="metric"><div class="label">Recherchepläne</div><div class="value">{esc(len(data['photo_plans']))}</div></div><div class="metric"><div class="label">Automatische Uploads</div><div class="value">0</div></div><div class="metric"><div class="label">Identitätsaussagen</div><div class="value">0</div></div></div>
<div class="two-col"><div class="panel"><h2>Fototreffer qualifizieren</h2><form method="post" action="/photos141/result-quality"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Dokumentierter Treffer</label><select name="result_id" required>{result_options}</select></div><button>Quelle, Provenienz, Alter und Bildrelation bewerten</button></form></div>
<div class="panel"><h2>Effizienten Fotorechercheplan erzeugen</h2><form method="post" action="/photos141/plan"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Ausgangsbild</label><select name="asset_id" required>{asset_options}</select></div><div class="field"><label>Zweck</label><input name="purpose" value="Ursprung, früheste Fundstelle und unabhängige Kontextquelle ermitteln" required></div><button>Anbieterdiversität und Variantenfolge planen</button></form></div></div>
<div class="panel"><h2>Qualität dokumentierter Fototreffer</h2><div class="table-wrap"><table><thead><tr><th>Treffer</th><th>Score</th><th>Band</th><th>Frühester Kandidat</th><th>Status</th></tr></thead><tbody>{qrows}</tbody></table></div></div>
<div class="panel"><h2>Fotorecherchepläne</h2><div class="table-wrap"><table><thead><tr><th>Zeit</th><th>Zweck</th><th>Anbieter</th><th>Dubletten entfernt</th><th>Minuten</th><th>Auto-Upload / Identität</th></tr></thead><tbody>{plans}</tbody></table></div></div><hr>
'''
    return header + render_photo140(ctx, case_id, csrf, esc=esc)
