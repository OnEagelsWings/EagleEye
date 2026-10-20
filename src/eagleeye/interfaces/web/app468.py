"""Build 468: transparent synthetic retrieval baseline, not product search performance."""
from __future__ import annotations
import hashlib
from html import escape
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .app467 import create_workspace_app467
from .app448 import COOKIE
from .app449 import _drop
from eagleeye.application.benchmark468 import benchmark

def create_workspace_app468(*,base_dir=None):
    app=create_workspace_app467(base_dir=base_dir,workspace_build='468.0')
    app.version="468.0"\n    app.title="EagleEye Build 468 – Reproducible Benchmark"
    ctx=app.state.context
    _drop(app,"/health",{"GET"})
    @app.get("/health")
    def health468():
        valid=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":"468.0","status":"ok" if valid else "hold",
                "integrity_valid":valid,"production_release_ready":False,"next_checkpoint":"470.0"}

    @app.get("/benchmark468",response_class=HTMLResponse)
    def benchmark_page(request:Request):
        fingerprint=hashlib.sha256("|".join((
            request.headers.get("user-agent",""),
            request.headers.get("accept-language",""),
            request.client.host if request.client else "")).encode()).hexdigest()
        ident=ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE,""),client_fingerprint=fingerprint,touch=True)
        if not ident:
            return RedirectResponse("/security/login",status_code=303)
        result=benchmark()
        metrics=result["metrics"]
        lines="".join("<tr><th>"+escape(k)+"</th><td>"+format(v,".3f")+"</td></tr>"
                    for k,v in metrics.items())
        limitations="".join("<li>"+escape(text)+"</li>" for text in result["limitations"])
        return HTMLResponse('<!doctype html><html lang="de"><head><meta charset="utf-8">'
             '<title>EagleEye 468 · Messprotokoll</title><style>body{font:1rem system-ui;'
             'max-width:900px;margin:2rem auto;padding:1rem;background:#17243a;color:white}'
             'th,td{border:1px solid #90a4b9;padding:.6rem}a{color:#82e2d3}</style></head><body><main>'
             '<h1>Build 468 – reproduzierbarer Benchmark</h1>'
             '<p><strong>Synthetische SQLite-FTS5-Baseline, KEIN Leistungsnachweis der EagleEye-Produktsuche.</strong></p>'
             '<p>Dokumente: '+str(result["document_count"])+' · Abfragen: '+str(result["query_count"])+'</p>'
             '<p>Goldset SHA-256: '+escape(result["fixture_sha256"])+'</p>'
             '<table><tbody>'+lines+'</tbody></table>'
             '<p>Entity Resolution F1: N/A</p><p>OSINT-Live-Recherche-Güte: N/A</p>'
             '<p>P95 der isolierten FTS-Baseline: '+format(result["latency_ms"]["p95"],".3f")+' ms</p>'
             '<h2>Methodische Grenzen</h2><ul>'+limitations+'</ul>'
             '<p>Für gemessene reale Suchqualität benötigen wir fallbezogene Query-API und beschriftetes Goldset.</p>'
             '</main></body></html>',headers={"Cache-Control":"no-store"})
    return app

create_app=create_workspace_app468
