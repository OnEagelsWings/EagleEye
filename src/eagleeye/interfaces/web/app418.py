from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app417 import create_workspace_app417
def create_workspace_app418(*,base_dir=None):
 app=create_workspace_app417(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build418; app.title='EagleEye Build 418.0'; app.version='418.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None); app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  h=dict(old() if callable(old) else {'ok':True}); s=ctx.build418.matrix_status(); h.update({'build':'418.0','phase':18,'phase18_builds_completed':18,'evidence_hypothesis_reasoning_matrix':True,'matrix_gate_pass':s['matrix_gate_pass'],'production_release_ready':False}); return h
 @app.get('/api/build418/matrix/status')
 def status418(request:Request): auth(request); return ctx.build418.matrix_status()
 @app.post('/api/build418/hypotheses/{hypothesis_id}/evidence')
 async def link418(hypothesis_id:str,request:Request):
  try:
   b=await request.json(); return ctx.build418.link_evidence(hypothesis_id=hypothesis_id,evidence_ref=b.get('evidence_ref'),relation=b.get('relation'),rationale=b.get('rationale',''),confidence=b.get('confidence'),identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.get('/api/build418/multi-agent/sessions/{session_id}/matrix')
 def matrix418(session_id:str,request:Request):
  try:return ctx.build418.reasoning_matrix(session_id=session_id,identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app418
