"""Build 485: read-only first-case pilot acceptance, never self-authorizes customer use."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse

from .operations476 import case_access,page
from .research483 import listed

def pilot_counts(ctx,identity,case_id):
    sources=ctx.document_intelligence_458.documents(identity=identity,case_id=case_id)
    assets=ctx.build354.image_assets(case_id=case_id,limit=500)
    leads=listed(ctx,case_id)
    chain=ctx.evidence_claims_dossier_447
    integrity=chain.verify_integrity()
    evidence=chain.case_evidence(case_id)
    claims=chain.case_claims(case_id)
    dossiers=chain.case_dossiers(case_id)
    exports=chain.exports(case_id)
    return {
        "documents":len(sources),"images":len(assets),"search_leads":len(leads),
        "evidence":len(evidence),"accepted_evidence":sum(x["review_state"]=="accepted" for x in evidence),
        "claims":len(claims),"accepted_claims":sum(x["state"]=="accepted_for_dossier" for x in claims),
        "dossiers":len(dossiers),"formal_exports":len(exports),
        "integrity_ok":bool(integrity.get("valid")),
    }

def attach_pilot485(app,build):
    ctx=app.state.context
    @app.get("/workbench/pilot485",response_class=HTMLResponse)
    def case_pilot(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        stats=pilot_counts(ctx,user,case_id)
        rows=[
            ("1. Fallanlage und Zweck","Vorhanden","/workflow461"),
            ("2. Dork-/Websuche",str(stats["search_leads"])+" manuelle Suchhinweise","/workbench/leads483"),
            ("3. Originaldokumente",str(stats["documents"])+" Dokumente","/documents458"),
            ("4. Bildakte und Ähnlichkeit",str(stats["images"])+" Bildoriginale","/workbench/media484"),
            ("5. Kanonische Evidence",str(stats["accepted_evidence"])+"/"+str(stats["evidence"])+" akzeptiert","/workbench/closure"),
            ("6. Claims/Gegenbelege",str(stats["accepted_claims"])+"/"+str(stats["claims"])+" für Dossier akzeptiert","/?view=claims"),
            ("7. Interaktiver Netzwerkgraph","Verfügbar; Belegkanten getrennt prüfen","/graph464"),
            ("8. Dossier und Revisionen",str(stats["dossiers"])+" Revisionen","/?view=dossier"),
            ("9. Freigegebener Export",str(stats["formal_exports"])+" Exportdatensätze","/?view=operations"),
            ("10. Quellenintegrität","Bestanden" if stats["integrity_ok"] else "Fehlgeschlagen","/workbench/closure"),
        ]
        table="<table><thead><tr><th>Arbeitsschritt</th><th>Iststand</th><th>Aktion</th></tr></thead><tbody>"
        for title,status,path in rows:
            href=path+("&" if "?" in path else "?")+urlencode({"case_id":case_id})
            table+=("<tr><th>"+escape(title)+"</th><td>"+escape(status)+"</td>"
                    '<td><a href="'+escape(href,quote=True)+'">Öffnen</a></td></tr>')
        table+="</tbody></table>"
        body=('<p>Normaler Ermittlungsfall: <strong>'+escape(str(case.get("title") or ""))+
              '</strong>. Diese Anzeige liest den tatsächlichen lokalen Fallbestand. '
              'Sie simuliert keine Recherche und erteilt keine Kundenfreigabe.</p>'
              '<p class="warn"><strong>Freigabe: NEIN – lokaler Entwicklungs- und Praxistest.</strong> '
              'Für einen freigegebenen Auftrag sind getrennte technische, rechtliche, '
              'DSGVO- und Sicherheitsprüfungen sowie unabhängige Review-Akzeptanz erforderlich. '
              'Ein Zählerstand ist kein Beweis, dass der Auftrag vollständig recherchiert ist.</p>'+table+
              '<p>Für den Test: öffentlichen Auftrag anlegen → Dork-Suche durchführen → '
              'Treffer im Browser prüfen → Dokument/Bild sichern → Originalhash und '
              'Evidence prüfen → Claims/Gegenbelege erfassen → Graph untersuchen → '
              'Arbeitsbericht exportieren → Daten wiederherstellen.</p>')
        return HTMLResponse(page("Pilotprüfung 485 – vollständiger Ermittlungsfall",case_id,body,build),
                            headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"})
