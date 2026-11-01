"""Build 485: non-deceptive case-level operator acceptance board.

This is NOT a certification of customer readiness. It reads existing case
records and verified provenance, never writes Claims, reviews or exports.
"""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse
from .operations476 import case_access, page
from .closure_workflow478 import case_closure_counts
from .research483 import listed

STEPS=(
 ("01 · Recherchefrage", "/workflow461",
  "Auftrag, Zweck, Rechtsgrundlage und Suchgrenzen dokumentieren."),
 ("02 · Dorks und Suchhinweise", "/workbench/dorks482",
  "Recherchelinks manuell prüfen und gefundene URLs als ungeprüfte Hinweise übernehmen."),
 ("03 · Quellen und Originale", "/documents458",
  "Rechtmäßig erhaltene Originaldateien samt Inhalt und Hash prüfen."),
 ("04 · Bildakte", "/workbench/images482",
  "Originalbilder, EXIF, lokale Ähnlichkeit und Quarantänestatus betrachten."),
 ("05 · Bildbeziehungen", "/workbench/media484",
  "Bildvergleich ist ein Kandidatenhinweis, keine bestätigte Personenrelation."),
 ("06 · Original-Evidence", "/workbench/closure",
  "Nur überprüfte Herkunftsvorgänge werden über die vorhandene Evidence-Kette bewertet."),
 ("07 · Entitäten und Graph", "/graph464",
  "Alle Graphkanten auf Originalfundstellen und Reviewstatus zurückführen."),
 ("08 · Quellenkritische Prüfung", "/review465",
  "Gegenbelege, Unklarheiten und abweichende Hypothesen dokumentieren."),
 ("09 · Analystenbericht", "/workbench/report",
  "Quellenbezogenen Arbeitsbericht exportieren; keine formale Zweitfreigabe behaupten."),
 ("10 · Dossier- und Auditprüfung", "/workbench/expert",
  "Vier-Augen-Gates für formale Dossierausgaben bleiben zwingend."),
)

def case_pilot_snapshot(ctx, identity, case_id):
    counts=case_closure_counts(ctx,identity,case_id)
    leads=listed(ctx,case_id)
    assets=ctx.build354.image_assets(case_id=case_id,limit=250)
    verified_images=[x for x in assets if x.get("review_status") == "accepted"]
    # No inferred customer authorization: this information must be documented
    # separately, including legal basis, security and independent review.
    return {**counts,
            "search_leads":len(leads),
            "images":len(assets),
            "reviewed_images":len(verified_images),
            "image_candidates":len(ctx.build354.similarity_links(case_id=case_id)[:300])}

def attach_pilot485(app,build):
    ctx=app.state.context

    @app.get("/workbench/pilot485",response_class=HTMLResponse)
    def pilot_workspace(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        snapshot=case_pilot_snapshot(ctx,user,case_id)
        stats=[
            ("Ungeprüfte Suchhinweise",snapshot["search_leads"],"Keine Originalquellen"),
            ("Originaldokumente",snapshot["documents"],"Nicht automatisch Evidence"),
            ("Bildobjekte",snapshot["images"],"Metadaten können unvollständig sein"),
            ("Bildvergleichskandidaten",snapshot["image_candidates"],"Keine Identität bestätigt"),
            ("Kanonische Evidence",snapshot["evidence"],"Prüfstatus ist separat"),
            ("Akzeptierte Evidence",snapshot["reviewed_evidence"],"Menschliche Prüfung"),
            ("Für Dossier akzeptierte Claims",snapshot["accepted_claims"],"Keine automatische Annahme"),
            ("Dossier-Revisionen",snapshot["dossiers"],"Freigabe separat"),
            ("Freigegebene Dossier-Revisionen",snapshot["approved_dossiers"],"Nur formal geprüfter Export"),
            ("Dossier-Exportdatensätze",snapshot["exports"],"Nicht automatisch kundenfähig"),
        ]
        cards="".join(
          '<section class="card"><h3>'+escape(title)+'</h3>'
          '<p><strong>'+str(value)+'</strong></p><p>'+escape(note)+'</p></section>'
          for title,value,note in stats
        )
        stages="".join(
          '<section class="card"><h3>'+escape(title)+'</h3>'
          '<p>'+escape(note)+'</p><a href="'+
          escape(path+"?"+urlencode({"case_id":case_id}),quote=True)+
          '">Arbeitsschritt öffnen →</a></section>'
          for title,path,note in STEPS
        )
        available={getattr(r,"path","") for r in app.router.routes}
        missing=[path for _title,path,_note in STEPS if path not in available]
        # A route existing is NOT an actual end-to-end or live-network proof.
        status=("Fehlende Arbeitswege: "+", ".join(missing)) if missing else (
          "Alle zehn Bedienrouten sind registriert. Das ist noch keine Live-Abnahme.")
        body=(
          '<p>Aktiver Fall: <strong>'+escape(str(case.get("title") or ""))+
          '</strong>. Diese Übersicht zählt ausschließlich bereits gespeicherte '
          'Fallobjekte, keine erfundenen Rechercheergebnisse.</p>'
          '<p class="warn"><strong>Freigabe für Kunden-/Behördenaufträge: NO-GO, '
          'bis eine unabhängige technische, rechtliche und fachliche Abnahme '
          'des konkreten Auftrags vorliegt.</strong> Ein vorhandener Dateihash '
          'ist kein Wahrheitsbeweis. Die reine Existenz einer Werkzeugroute '
          'belegt keinen erfolgreichen Live-Abruf.</p>'
          '<p><strong>Bedienstatus:</strong> '+escape(status)+'</p>'
          '<h2>Beleg- und Recherchebestand dieses Falls</h2><div class="grid">'+cards+'</div>'
          '<h2>Dein nächster Arbeitsschritt</h2><div class="grid">'+stages+'</div>'
          '<p class="warn">Für eine tatsächlich freizugebende Pilotversion zusätzlich '
          'prüfen: Windows-Neuinstallation, Wiederherstellung eines vorherigen '
          'Fallbestands, Beleg-/Bild-/Graphzuordnung, Gegenbelege, unabhängige '
          'Dossierfreigabe, Nutzungsrechte der Quellen und Datenschutz.</p>'
        )
        return HTMLResponse(page("Erster Kundenpilot – belegbarer Fallfortschritt",case_id,body,build),
            headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff",
                     "Referrer-Policy":"same-origin"})
