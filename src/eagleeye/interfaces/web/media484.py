"""Build 484: case-scoped visual comparison of original image evidence leads.

Reuses the Build-354 stored similarity links; never asserts a shared person,
location or identity and never mixes links between unrelated cases.
"""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from .operations476 import case_access,page

def _case_link(path, case_id):
    return escape(path+"?"+urlencode({"case_id":case_id}),quote=True)

def _status(row):
    metadata=row.get("metadata") or {}
    return str(row.get("review_status") or metadata.get("security_state") or "unreviewed")

def _photo(row,case_id):
    if _status(row) in ("quarantined","rejected"):
        return "<span>Bild nicht freigegeben (Quarantäne/abgelehnt)</span>"
    return ('<img alt="Fallbezogener Bildbeleg, Identität ungeprüft" loading="lazy" '
            'style="max-width:200px;max-height:155px;object-fit:contain" src="'+
            _case_link("/workbench/image482/"+str(row["media_id"]),case_id)+'">')

def attach_media484(app,build):
    ctx=app.state.context

    @app.get("/workbench/media484",response_class=HTMLResponse)
    def media_analysis(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        del user
        assets=ctx.build354.image_assets(case_id=case_id,limit=250)
        indexed={str(r["media_id"]):r for r in assets}
        links=ctx.build354.similarity_links(case_id=case_id)[:300]
        cards=[]
        for link in links:
            left=indexed.get(str(link["from_id"]))
            right=indexed.get(str(link["to_id"]))
            if not left or not right:
                raise HTTPException(409,"Bildbeziehung ohne fallbezogene Originalbilder.")
            provenance=link.get("provenance") or {}
            if provenance.get("identity_confirmed") is True or provenance.get("requires_human_review") is not True:
                raise HTTPException(409,"Ungültiger automatischer Bildbezug.")
            comparison=provenance.get("comparison") or {}
            relation=str(link.get("relation") or "unverified_similarity")
            metric=[]
            if "exact_sha256" in comparison:
                metric.append("Identische Originalbytes: "+("Ja" if comparison["exact_sha256"] else "Nein"))
            if "dhash_hamming" in comparison:
                metric.append("Visuelle dHash-Distanz: "+escape(str(comparison["dhash_hamming"])))
            if "local_embedding_cosine" in comparison:
                metric.append("Lokaler Bildvergleichswert: "+escape(str(comparison["local_embedding_cosine"])))
            pair='<div class="grid">'+''.join(
                '<div><p>'+escape(str(row["media_id"]))+'</p>'+_photo(row,case_id)+
                '<p>SHA-256: '+escape(str(row.get("sha256") or "nicht angezeigt"))+'</p></div>'
                for row in (left,right)
            )+'</div>'
            cards.append(
                '<section class="card"><h2>Ungeprüfte Bildähnlichkeit – '+escape(relation)+'</h2>'+
                pair+'<p>'+(" · ".join(metric) or "Lokale Analyse vorhanden")+'</p>'
                '<p><strong>Nur ein Bildvergleich.</strong> Keine Aussage über identische '
                'Personen, Organisationen, Orte oder gemeinsame Aufnahmequelle.</p></section>'
            )
        body=(
            '<p>Aktiver Fall: <strong>'+escape(str(case.get("title") or ""))+
            '</strong> · '+str(len(assets))+' Bildoriginale · '+str(len(links))+
            ' ungeprüfte Kandidatenverbindungen.</p>'
            '<p class="warn">Die Analyse nutzt die bereits vorhandene Build-354-'
            'Bildähnlichkeit. Metadaten, identische Pixel oder Hashes sind allein '
            'kein Beweis für eine Person, einen Ort oder einen Sachverhalt. '
            'Nicht bestätigte Vergleiche niemals automatisch als Graph-Fakten übernehmen.</p>'
            '<p><a href="'+_case_link("/workbench/images482",case_id)+
            '">Bildakte und Metadaten ansehen</a> · <a href="'+
            _case_link("/graph464",case_id)+
            '">Belegte Entitäten und Beziehungen im interaktiven Graph prüfen</a></p>'
            '<h2>Bildvergleiche mit Originalfundstellen</h2>'+
            ("".join(cards) or
             '<p>Noch keine Bildähnlichkeitskandidaten. Zwei Bilder können in der Bildakte '
             'getrennt importiert und lokal verglichen werden.</p>')
        )
        return HTMLResponse(page("Bildvergleich und Verbindungsprüfung",case_id,body,build),
                            headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
