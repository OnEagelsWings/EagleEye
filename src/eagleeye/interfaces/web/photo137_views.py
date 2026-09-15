from __future__ import annotations

from typing import Any, Callable

from .photo136_views import render_photo136


def render_photo137(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str]) -> str:
    base = render_photo136(ctx, case_id, csrf, esc=esc)
    photos = ctx.build136.list_photos(case_id=case_id, limit=200)
    research = ctx.build137.photo_dashboard(case_id)
    analysis_cards: list[str] = []
    for photo in photos:
        if photo["source_kind"] != "local_file":
            continue
        analysis = ctx.build137.photo_analysis(case_id=case_id, asset_id=photo["asset_id"])
        metadata = analysis.get("metadata") or {}
        fp = analysis.get("fingerprint") or {}
        links = analysis.get("similarity_links") or []
        if metadata:
            summary = metadata.get("safe_summary") or {}
            analysis_text = f'''<div class="footer">Format: {esc(metadata.get("image_format"))} · Modus: {esc(metadata.get("color_mode"))} · Frames: {esc(metadata.get("frame_count"))}<br>EXIF: {"ja" if metadata.get("exif_present") else "nein"} · GPS-Hinweis: {"vorhanden – nicht offengelegt" if metadata.get("gps_present") else "nein"} · ICC: {"ja" if metadata.get("icc_present") else "nein"}<br>aHash: <code>{esc(fp.get("ahash64"))}</code> · dHash: <code>{esc(fp.get("dhash64"))}</code><br>Sichere Metadaten: {esc(summary)} · ähnliche Kandidaten: {esc(len(links))}</div>'''
        else:
            analysis_text = '<div class="notice warn">Noch keine lokale Metadaten- und Ähnlichkeitsanalyse.</div>'
        analysis_cards.append(f'''<article class="photo-card"><img class="photo-thumb" src="{esc(photo["view_url"])}" alt="Lokales candidate-only Foto" loading="lazy"><div class="photo-body"><h3>{esc(photo.get("title") or photo.get("original_filename"))}</h3>{analysis_text}<div class="inline"><form method="post" action="/photos137/analyze"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="asset_id" value="{esc(photo["asset_id"])}"><button class="small ghost">Lokal analysieren</button></form><form method="post" action="/photos137/copy"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="asset_id" value="{esc(photo["asset_id"])}"><input type="number" name="max_dimension" min="256" max="3000" value="1600" title="Maximale Kantenlänge"><input type="number" name="quality" min="60" max="95" value="88" title="JPEG-Qualität"><button class="small">Bereinigte Recherchekopie</button></form></div></div></article>''')

    copy_options = "".join(f'<option value="{esc(row["copy_id"])}">{esc(row["filename"])} · {esc(row["width_px"])}×{esc(row["height_px"])}</option>' for row in research["copies"]) or '<option value="">Zuerst Recherchekopie erzeugen</option>'
    job_rows: list[str] = []
    for job in research["jobs"]:
        statuses = "".join(f'<option value="{esc(status)}"{" selected" if status == job["status"] else ""}>{esc(status)}</option>' for status in ("prepared", "provider_opened", "uploaded_manually", "results_review", "completed", "cancelled"))
        job_rows.append(f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(job["provider_label"])}</h3><p>{esc(job["purpose"])}</p></div><span class="badge candidate">{esc(job["status"])}</span></div><p class="footer">Übertragen wird ausschließlich die bereinigte Kopie: {esc(job["disclosure"].get("filename") or job["copy_id"])} · automatische Uploads: 0</p><div class="inline"><a class="button ghost small" href="{esc(job["copy_download_url"])}">Recherchekopie bereitstellen</a><form method="post" action="/photos137/job-launch"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="job_id" value="{esc(job["job_id"])}"><button class="small">Anbieter im Fallbrowser öffnen</button></form><form method="post" action="/photos137/job-status"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="job_id" value="{esc(job["job_id"])}"><select name="status">{statuses}</select><input name="result_note" value="{esc(job.get("result_note") or "")}" placeholder="Trefferlage und nächste Prüfung"><button class="small ghost">Status speichern</button></form></div></div>''')

    return base + f'''
<div class="notice"><b>Fotorecherche · Build 137:</b> Vor jeder externen Reverse-Image-Suche analysiert EagleEye das Bild lokal und erzeugt eine getrennte, metadatenbereinigte Recherchekopie. Perceptual hashes beschreiben Bildähnlichkeit, niemals Personengleichheit.</div>
<div class="metrics"><div class="metric"><div class="label">Lokal analysiert</div><div class="value">{esc(research["analyzed_count"])}</div></div><div class="metric"><div class="label">Bereinigte Kopien</div><div class="value">{esc(research["copy_count"])}</div></div><div class="metric"><div class="label">Fotorecherche-Jobs</div><div class="value">{esc(research["job_count"])}</div></div><div class="metric"><div class="label">Automatische Uploads</div><div class="value">0</div></div></div>
<div class="panel"><h2>Lokale Bildanalyse und Recherchekopien</h2><div class="photo-grid">{"".join(analysis_cards) if analysis_cards else '<div class="empty">Keine lokal gesicherten Bilder verfügbar.</div>'}</div></div>
<div class="two-col"><div class="panel"><h2>Reverse-Image-Research vorbereiten</h2><form method="post" action="/photos137/job-create"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Bereinigte Recherchekopie</label><select name="copy_id" required>{copy_options}</select></div><div class="field"><label>Anbieter</label><select name="provider_key"><option value="google_lens">Google Lens</option><option value="bing_visual">Bing Visual Search</option><option value="tineye">TinEye</option><option value="yandex_images">Yandex Images</option></select></div><div class="field"><label>Dokumentierter Zweck</label><textarea name="purpose" rows="3" required placeholder="Welche Bildvariante, Quelle oder Veröffentlichung soll gefunden werden?"></textarea></div><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="FOTORECHERCHE FREIGEBEN" required></div><p><button>Research Job vorbereiten</button></p></form></div><div class="panel"><h2>Transparenter manueller Handoff</h2><ol><li>Recherchekopie lokal bereitstellen.</li><li>Anbieter im isolierten Fallbrowser öffnen.</li><li>Genau diese Kopie sichtbar über den offiziellen Uploaddialog auswählen.</li><li>Treffer per Drag-and-drop oder Quellenreferenz zurück in die Fotoakte übernehmen.</li></ol><p class="footer">EagleEye führt keinen Hintergrund-Upload, keine Mehrfachverteilung und keine Gesichtserkennung aus.</p></div></div>
<div class="panel"><h2>Fotorecherche-Jobs</h2>{"".join(job_rows) if job_rows else '<div class="empty">Noch keine Fotorecherche vorbereitet.</div>'}</div>
'''
