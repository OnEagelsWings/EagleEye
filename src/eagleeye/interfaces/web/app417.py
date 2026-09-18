from __future__ import annotations
from fastapi import HTTPException, Request
from .app416 import create_workspace_app416
def create_workspace_app417(*,base_dir=None,db_path=None):
 app=create_workspace_app416(base_dir=base_dir,db_path=db_path); ctx=app.state.context; auth=app.state.auth_context
 app.title='EagleEye Build 417.0'
 for r in app.routes:
  if getattr(r,'path',None)=='/health':
   old=r.endpoint
   def health(old=old):
    h=dict(old()); s=ctx.build417.hypothesis_status(); h.update({'build':'417.0','phase':18,'phase18_builds_completed':17,'hypothesis_counterevidence_coordination':True,'hypothesis_gate_pass':s['hypothesis_gate_pass'],'production_release_ready':False}); return h
   r.endpoint=health
 @app.get('/api/build417/hypotheses/status')
 def status417(request:Request): auth(request); return ctx.build417.hypothesis_status()
 @app.post('/api/build417/multi-agent/sessions/{session_id}/hypotheses')
 async def create417(session_id:str,request:Request):
  try:
   body=await request.json(); return ctx.build417.create_hypothesis(session_id=session_id,statement=body.get('statement',''),alternative_to=body.get('alternative_to',''),identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.post('/api/build417/hypotheses/{hypothesis_id}/items')
 async def item417(hypothesis_id:str,request:Request):
  try:
   body=await request.json(); return ctx.build417.add_hypothesis_item(hypothesis_id=hypothesis_id,item_type=body.get('item_type',''),reference=body.get('reference',''),note=body.get('note',''),identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.get('/api/build417/hypotheses/{hypothesis_id}')
 def review417(hypothesis_id:str,request:Request):
  try:return ctx.build417.review_hypothesis(hypothesis_id=hypothesis_id,identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.post('/api/build417/hypotheses/{hypothesis_id}/state')
 async def state417(hypothesis_id:str,request:Request):
  try:
   body=await request.json(); return ctx.build417.set_hypothesis_state(hypothesis_id=hypothesis_id,state=body.get('state',''),identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app417
