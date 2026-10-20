"""Build 467: provenance corrections with existing case-scoped interface."""
from .app466 import create_workspace_app466 as _base
from .app449 import _drop

def create_workspace_app467(*,base_dir=None,workspace_build='467.0'):
    app=_base(base_dir=base_dir,workspace_build=workspace_build)
    app.title="EagleEye Build "+workspace_build+" – Investigation Workspace"
    app.version=workspace_build
    _drop(app,"/health",{"GET"})
    @app.get("/health")
    def health467():
        ctx=app.state.context
        integrity=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":workspace_build,"status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,"next_checkpoint":"470.0"}
    return app

create_app=create_workspace_app467
