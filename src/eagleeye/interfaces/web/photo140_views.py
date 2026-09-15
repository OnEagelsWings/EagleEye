from __future__ import annotations

from typing import Any, Callable

from .photo139_views import render_photo139


def render_photo140(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str]) -> str:
    data = ctx.build140.image_dashboard(case_id)
    base = ctx.build136.photo_dashboard(case_id)
    local = [row for row in base.get("photos", []) if row.get("source_kind") == "local_file"]
    options = '<option value="">Lokales Bild auswählen</option>' + ''.join(
        f'<option value="{esc(row["asset_id"])}">{esc(row.get("title") or row["asset_id"])}</option>' for row in local
    )
    cards: list[str] = []
    for row in data["analyses"]:
        hints = ''.join(f'<li>{esc(item)}</li>' for item in row.get("anomaly_hints", [])) or '<li>Keine auffälligen technischen Indikatoren.</li>'
        recs = ''.join(f'<li>{esc(item)}</li>' for item in row.get("research_recommendations", []))
        cards.append(f'''
<article class="intake-card"><div class="intake-head"><div><h3>{esc(row['asset_id'])}</h3><p>{esc(row['content_profile'])}</p></div><span class="badge">Qualität {esc(row['quality_band'])}</span></div>
<div class="metrics"><div class="metric"><div class="label">Schärfe</div><div class="value">{esc(round(float(row['sharpness']), 2))}</div></div><div class="metric"><div class="label">Entropy</div><div class="value">{esc(round(float(row['entropy']), 2))}</div></div><div class="metric"><div class="label">ELA-Hotspots</div><div class="value">{esc(round(float(row['ela_hotspot_ratio']), 3))}</div></div><div class="metric"><div class="label">Screenshot-Indikator</div><div class="value">{esc(round(float(row['screenshot_likelihood']), 2))}</div></div></div>
<p><b>Technische Hinweise, keine Manipulationsbehauptung:</b></p><ul>{hints}</ul><p><b>Rechercheempfehlungen:</b></p><ul>{recs}</ul><p class="footer">Gesichtsregionen: {esc(row['face_region_count'])} · biometrische Analyse: nein · Manipulationsaussage: nein</p></article>''')
    comparisons = ''.join(
        f"<tr><td>{esc(row['reference_asset_id'])}</td><td>{esc(row['compared_asset_id'])}</td><td>{esc(row['relation_band'])}</td><td>{esc(row['ahash_distance'])}/{esc(row['dhash_distance'])}</td><td>nein</td></tr>"
        for row in data["comparisons"]
    ) or '<tr><td colspan="5">Noch keine Bildvergleiche.</td></tr>'
    header = f'''
<div class="notice"><b>Build 140 · Local Image Intelligence:</b> Qualitäts-, Entropie-, Kanten-, Metadaten-, Rekodierungs- und Variantenindikatoren unterstützen die Fotorecherche. Sie beweisen weder Bildmanipulation noch Personenidentität.</div>
<div class="metrics"><div class="metric"><div class="label">Bildanalysen</div><div class="value">{esc(data['analysis_count'])}</div></div><div class="metric"><div class="label">Bildvergleiche</div><div class="value">{esc(data['comparison_count'])}</div></div><div class="metric"><div class="label">Manipulationsbehauptungen</div><div class="value">0</div></div><div class="metric"><div class="label">Biometrische Analysen</div><div class="value">0</div></div></div>
<div class="two-col"><div class="panel"><h2>Lokale technische Bildanalyse</h2><form method="post" action="/photos140/analyze"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Bild</label><select name="asset_id" required>{options}</select></div><button>Bild lokal analysieren</button></form></div>
<div class="panel"><h2>Zwei Bilder technisch vergleichen</h2><form method="post" action="/photos140/compare"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Referenz</label><select name="reference_asset_id" required>{options}</select></div><div class="field"><label>Vergleichsbild</label><select name="compared_asset_id" required>{options}</select></div><button>Hashes, Struktur und Variantenindikatoren vergleichen</button></form></div></div>
<div class="panel"><h2>Technische Bildanalysen</h2>{''.join(cards) if cards else '<div class="empty">Noch keine Build-140-Bildanalyse.</div>'}</div>
<div class="panel"><h2>Lokale Bildvariantenvergleiche</h2><div class="table-wrap"><table><thead><tr><th>Referenz</th><th>Vergleich</th><th>Relation</th><th>aHash/dHash</th><th>Identitätsaussage</th></tr></thead><tbody>{comparisons}</tbody></table></div></div><hr>
'''
    return header + render_photo139(ctx, case_id, csrf, esc=esc)
