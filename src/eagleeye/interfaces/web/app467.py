"""Build 467: provenance corrections with existing case-scoped interface."""
from .app466 import create_workspace_app466 as _base
from .app449 import _drop

def create_workspace_app467(*,base_dir=None):
    app=_base(base_dir=base_dir)
    app.title="EagleEye Build 467 – Provenance Review Corrections"
    app.version="467.0"
    _drop(app,"/health",{"GET"})
    @app.get("/health")
    def health467():
        ctx=app.state.context
        integrity=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":"467.0","status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,"next_checkpoint":"470.0"}
    return app

create_app=create_workspace_app467
