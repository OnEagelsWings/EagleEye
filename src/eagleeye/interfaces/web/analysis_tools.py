"""Case-scoped link to the local analysis runner and reviewed report import."""
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from .operations476 import case_access, page

SCRIPT = """
const form=document.querySelector('#analysis-import'), feedback=document.querySelector('#analysis-status');
const source=form.elements.report, preview=document.querySelector('#analysis-preview'), submit=form.querySelector('button');
let selected;
source.onchange=async()=>{
 selected=null;submit.disabled=true;preview.textContent='';feedback.textContent='';
 try{
  const file=source.files[0];if(!file)return;
  if(file.size>512000)throw Error('Befunddatei zu groß.');
  const text=await file.text(), report=JSON.parse(text);
  if(report.format!=='eagleeye-analysis/1'||report.caseId!==form.dataset.case||typeof report.body!=='string'||report.body.length>45000||!['ocr','video','search','metadata','alias','timeline','pcap','zap','leaks','yara','inventory','lynis'].includes(report.tool))throw Error('Befundformat oder Fallkennung passt nicht.');
  selected={text,tool:report.tool};preview.textContent=report.body;submit.disabled=false;
 }catch(err){feedback.textContent=String(err)}
};
form.onsubmit=async e=>{
 e.preventDefault();if(!selected)return;submit.disabled=true;
 try{
  const body=new FormData();body.set('file',new Blob([selected.text],{type:'text/plain'}),'Analysebefund.txt');body.set('title','Lokaler Analysebefund · '+selected.tool);
  const r=await fetch('/api/build458/cases/'+encodeURIComponent(form.dataset.case)+'/documents',{method:'POST',body});
  if(!r.ok)throw Error('Import fehlgeschlagen ('+r.status+').');
  feedback.textContent='Im Quellenbestand dieses Falls gespeichert.';selected=null;form.reset();
 }catch(err){feedback.textContent=String(err);submit.disabled=false}
};
"""

def attach_analysis_tools(app, build):
    @app.get("/assets/eagleeye-analysis.js")
    def script():
        return Response(SCRIPT, media_type="application/javascript")

    @app.get("/workbench/analysis-tools", response_class=HTMLResponse)
    def analysis_tools(request: Request, case_id: str):
        case_access(app, request, case_id)
        local = "http://127.0.0.1:48137/#" + urlencode({"caseId":case_id})
        body = (
            '<section class="card"><h2>Auf dem Analysegerät ausführen</h2>'
            '<p>Mit tools/analysis/EagleEye-Analyse.cmd (Windows) oder python3 bridge.py '
            '(Kali, im Ordner tools/analysis) den lokalen Dienst starten.</p>'
            '<p>ExifTool, Recoll, OCRmyPDF, FFmpeg, Sherlock und The Sleuth Kit sowie TShark, ZAP-Passivprüfung, Gitleaks, YARA, Nmap-Berichtsvergleich und Lynis stehen je nach Installation zur Auswahl.</p>'
            f'<a target="_blank" rel="noopener" href="{escape(local,quote=True)}">Analyse für diesen Fall öffnen</a></section>'
            f'<form class="card" id="analysis-import" data-case="{escape(case_id,quote=True)}">'
            '<h2>Befund in den Quellenbestand übernehmen</h2><label>Lokale befund.json'
            '<input name="report" type="file" accept=".json,application/json"></label>'
            '<pre id="analysis-preview" style="white-space:pre-wrap;max-height:25rem;overflow:auto"></pre>'
            '<button disabled>Gezeigten Befund als Quelldokument speichern</button>'
            '<p role="status" id="analysis-status"></p></form>'
            '<a target="_blank" rel="noopener" href="https://eagleeye-investigation.m-sprenger222.chatgpt.site/?view=tools">'
            'Analysewerkzeuge in Sites öffnen</a>'
            '<script src="/assets/eagleeye-analysis.js" defer></script>')
        return HTMLResponse(page("Analysewerkzeuge", case_id, body, build),headers={"Cache-Control":"no-store"})
