from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlsplit


def render_photo136(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str]) -> str:
    data = ctx.build136.photo_dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    options = '<option value="">Ohne feste Personenzuordnung</option>' + "".join(
        f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets
    )
    cards: list[str] = []
    for row in data["photos"]:
        target = next((item.get("name", "") for item in targets if item.get("target_id") == row.get("target_id")), "Ohne Zielbindung")
        if row["source_kind"] == "local_file":
            visual = f'<img class="photo-thumb" src="{esc(row["view_url"])}" alt="Gesichertes candidate-only Personenfoto" loading="lazy">'
        else:
            host = urlsplit(str(row.get("source_url") or "")).hostname or "externe Quelle"
            visual = f'<div class="photo-reference"><b>Remote Referenz</b><span>{esc(host)}</span><small>Aus OPSEC-Gründen nicht automatisch heruntergeladen.</small></div>'
        current_status = str(row.get("review_status") or "unreviewed")
        status_options = "".join(
            f'<option value="{esc(value)}"{" selected" if value == current_status else ""}>{esc(value)}</option>'
            for value in ("unreviewed", "candidate", "supported", "duplicate", "rejected")
        )
        cards.append(f'''<article class="photo-card">{visual}<div class="photo-body"><h3>{esc(row.get("title") or "Personenfoto")}</h3><div class="inline"><span class="badge candidate">candidate_only</span><span class="badge">{esc(row.get("review_status"))}</span></div><p>{esc(row.get("notes") or "Keine Notiz")}</p><div class="footer">{esc(target)} · {esc(row.get("mime_type") or row.get("source_kind"))} · {esc(row.get("byte_size"))} Bytes · {esc(row.get("width_px") or 0)}×{esc(row.get("height_px") or 0)} px<br>SHA-256: <code>{esc(row.get("sha256"))}</code><br>Erfasst: {esc(row.get("created_at"))}</div><form method="post" action="/photos136/review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="asset_id" value="{esc(row["asset_id"])}"><div class="field"><label>Reviewstatus</label><select name="status">{status_options}</select></div><div class="field"><label>Notiz</label><input name="notes" value="{esc(row.get("notes") or "")}"></div><p><button class="small ghost">Bewertung speichern</button></p></form></div></article>''')
    return f'''
<div class="notice"><b>Fotoakte Build 136:</b> Ziehe lokale Bilddateien in die Akte oder füge Bilder aus der Zwischenablage ein. Wird beim Ziehen aus einer Webseite nur eine URL geliefert, speichert EagleEye ausschließlich eine candidate-only Referenz und lädt das Bild nicht autonom herunter.</div>
<div class="metrics"><div class="metric"><div class="label">Fotoeinträge</div><div class="value">{esc(data["count"])}</div></div><div class="metric"><div class="label">Lokal gesichert</div><div class="value">{esc(data["local_files"])}</div></div><div class="metric"><div class="label">Remote Referenzen</div><div class="value">{esc(data["remote_references"])}</div></div><div class="metric"><div class="label">Ungeprüft</div><div class="value">{esc(data["unreviewed"])}</div></div></div>
<div class="two-col"><div class="panel"><h2>Drag-and-drop / Zwischenablage</h2><div id="photo136-drop" class="photo-drop" data-endpoint="/api/photo136/capture?case_id={esc(case_id)}" data-csrf="{esc(csrf)}" data-case-id="{esc(case_id)}"><b>Bilder hier ablegen</b><span>JPEG, PNG, WebP oder GIF · maximal 12 MB je Datei</span><span>Alternativ klicken oder Strg+V verwenden</span><input id="photo136-file" type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden></div><div id="photo136-status" class="notice" hidden></div></div>
<div class="panel"><h2>Zuordnung und Quellenkontext</h2><div class="field"><label>Zielperson optional</label><select id="photo136-target">{options}</select></div><div class="field"><label>Titel</label><input id="photo136-title" value="Personenfoto"></div><div class="field"><label>Quellseite optional</label><input id="photo136-page" placeholder="https://..."></div><div class="field"><label>Direkte Bild-URL optional</label><input id="photo136-source" placeholder="https://..."></div><div class="field"><label>Notiz</label><textarea id="photo136-notes" rows="4" placeholder="Fundkontext, sichtbare Merkmale, offene Zuordnungsfrage"></textarea></div><p class="footer">Originalbytes werden unverändert gespeichert und mit SHA-256 gesichert. Die Aufnahme bestätigt weder Identität noch Aufnahmezeit, Ort oder Echtheit.</p></div></div>
<div class="panel"><h2>Fotogalerie der Fallakte</h2><div class="photo-grid">{"".join(cards) if cards else '<div class="empty">Noch keine Fotos oder Bildreferenzen in dieser Fallakte.</div>'}</div></div>
<script src="/assets/photo136.js"></script>
'''
