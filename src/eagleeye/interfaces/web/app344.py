from __future__ import annotations
import html,secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI,Form,HTTPException,Request
from fastapi.responses import HTMLResponse,JSONResponse,RedirectResponse
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.version import BUILD,BUILD_NAME
COOKIE='eagleeye344_session';CSRF_COOKIE='eagleeye344_csrf';ALLOWED={'127.0.0.1','localhost','::1','testclient','testserver'}
def _esc(v:Any):return html.escape(str(v if v is not None else ''))
def _token_file(root):
 p=root/'data/security_344/local_session_token';p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  p.write_text(secrets.token_urlsafe(32),encoding='utf-8')
  try:p.chmod(0o600)
  except OSError:pass
 return p
def create_workspace_app344(*,base_dir=None):
 root=Path(base_dir or Path.cwd()).resolve();launch_token=_token_file(root).read_text().strip();session_value=secrets.token_urlsafe(32);csrf_value=secrets.token_urlsafe(24);ctx=AppContext(base_dir=root)
 @asynccontextmanager
 async def lifespan(_app):
  try:yield
  finally:ctx.close()
 app=FastAPI(title=BUILD_NAME,version=BUILD,docs_url=None,redoc_url=None,lifespan=lifespan);app.state.context=ctx;app.state.base_dir=str(root)
 @app.middleware('http')
 async def local_only(request,call_next):
  raw=(request.headers.get('host') or '').split(':',1)[0].strip('[]').lower();client=(request.client.host if request.client else '').strip('[]').lower()
  if raw not in ALLOWED or client not in ALLOWED:return JSONResponse({'detail':'Loopback access only'},status_code=403)
  r=await call_next(request);r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY';r.headers['Referrer-Policy']='no-referrer';r.headers['Cache-Control']='no-store';r.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'";return r
 def authed(req):return secrets.compare_digest(req.cookies.get(COOKIE,''),session_value)
 def require_auth(req):
  if not authed(req):raise HTTPException(status_code=401,detail='Local session required')
 def require_csrf(req,submitted):
  require_auth(req);cookie=req.cookies.get(CSRF_COOKIE,'')
  if not cookie or not secrets.compare_digest(cookie,csrf_value) or not secrets.compare_digest(str(submitted or ''),csrf_value):raise HTTPException(status_code=403,detail='CSRF check failed')
 def shell(body,title='EagleEye'):
  css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1100px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}input,textarea{width:100%;box-sizing:border-box;padding:9px;margin:5px 0 10px;border:1px solid #cbd5e1;border-radius:8px}button{padding:9px 14px;border:0;border-radius:8px;background:#1f2937;color:white}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem}code{background:#eef2f7;padding:2px 5px;border-radius:4px}"
  return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_esc(title)}</title><style>{css}</style></head><body><main>{body}</main></body></html>")
 @app.get('/health')
 def health():
  m=ctx.build344.schema_metrics();return {'ok':True,'build':BUILD,'schema_baseline':m['within_gate'],'tables':m['table'],'indexes':m['index']}
 @app.get('/security/start')
 def security_start(token:str=''):
  if not token or not secrets.compare_digest(token,launch_token):raise HTTPException(status_code=403,detail='Invalid local launch token')
  r=RedirectResponse('/',status_code=303);r.set_cookie(COOKIE,session_value,httponly=True,samesite='strict',secure=False,max_age=8*60*60);r.set_cookie(CSRF_COOKIE,csrf_value,httponly=False,samesite='strict',secure=False,max_age=8*60*60);return r
 @app.get('/security/login')
 def security_login():return shell("<div class='card'><h1>EagleEye Build 344</h1><p>Der lokale Workspace wird nur über den geschützten Launcher geöffnet.</p></div>",'EagleEye Login')
 @app.get('/api/build344')
 def api_build344(request:Request):require_auth(request);return ctx.build344.dashboard()
 @app.get('/')
 def home(request:Request):
  if not authed(request):return RedirectResponse('/security/login',status_code=303)
  m=ctx.build344.schema_metrics();cases=ctx.cases.list_cases();gate=ctx.build344.qualified_gate();rows=''.join(f"<tr><td><a href='/cases/{_esc(c['case_id'])}'>{_esc(c['title'])}</a></td><td>{_esc(c['status'])}</td><td>{_esc(c['jurisdiction'])}</td><td>{_esc(c['created_at'])}</td></tr>" for c in cases) or "<tr><td colspan='4' class='muted'>Noch keine Fälle.</td></tr>";body=f"<div class='card'><h1>EagleEye · Phase 15 · Build 344</h1><p>Evidence-first, local-first Schema Baseline v1. Legacy-Build-Schemata werden nicht automatisch geladen.</p></div><div class='grid'><div class='card'><div class='metric'>{m['table']}</div><div>Tabellen</div></div><div class='card'><div class='metric'>{m['index']}</div><div>Indizes</div></div><div class='card'><div class='metric'>{m['trigger']}</div><div>Trigger</div></div><div class='card'><div class='metric'>{m['logical_bytes']//1024} KiB</div><div>DB-Größe</div></div></div><div class='card'><b>Build Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'noch nicht belegt'} · <b>Production:</b> nicht freigegeben · <a href='/api/build344'>JSON-Status</a></div><div class='card'><h2>Fälle</h2><table><tbody>{rows}</tbody></table></div><div class='card'><h2>Neuen Fall anlegen</h2><form method='post' action='/cases'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><label>Titel</label><input name='title' required><label>Auftraggeber</label><input name='client'><label>Zweck</label><textarea name='purpose' required></textarea><label>Rechtsgrundlage</label><input name='legal_basis' required><button>Anlegen</button></form></div>";return shell(body)
 @app.post('/cases')
 def create_case(request:Request,title:str=Form(...),client:str=Form(''),purpose:str=Form(...),legal_basis:str=Form(...),csrf:str=Form(...)):
  require_csrf(request,csrf);row=ctx.cases.create_case(title,client,purpose,legal_basis);return RedirectResponse(f"/cases/{row['case_id']}",status_code=303)
 @app.get('/cases/{case_id}')
 def case_detail(case_id:str,request:Request):
  require_auth(request)
  try:case=ctx.cases.get_case(case_id)
  except KeyError:raise HTTPException(status_code=404,detail='Case not found')
  counts={'targets':ctx.db.one('SELECT COUNT(*) c FROM targets WHERE case_id=?',(case_id,))['c'],'evidence':ctx.db.one('SELECT COUNT(*) c FROM evidence_items WHERE case_id=?',(case_id,))['c'],'reviews':ctx.db.one('SELECT COUNT(*) c FROM review_items WHERE case_id=?',(case_id,))['c'],'tasks':ctx.db.one('SELECT COUNT(*) c FROM phase15_agent_tasks WHERE case_id=?',(case_id,))['c'],'search_runs':ctx.db.one('SELECT COUNT(*) c FROM phase15_search_runs WHERE case_id=?',(case_id,))['c']};body=f"<p><a href='/'>← Übersicht</a></p><div class='card'><h1>{_esc(case['title'])}</h1><p>{_esc(case['purpose'])}</p></div><div class='grid'>"+''.join(f"<div class='card'><div class='metric'>{v}</div><div>{_esc(k)}</div></div>" for k,v in counts.items())+'</div>'+ctx.build344.render_workspace_panel(case_id=case_id,csrf=csrf_value,section='cockpit');return shell(body,case['title'])
 return app
