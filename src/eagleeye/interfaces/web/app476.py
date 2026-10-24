"""Build 476: real case-first operational navigation."""
from .app475 import create_workspace_app475
from .app449 import _drop
from .operations476 import attach_workbench

def create_workspace_app476(*,base_dir=None,workspace_build="476.0"):
    app = create_workspace_app475(base_dir=base_dir,workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye Operativer Ermittlungsarbeitsplatz " + workspace_build
    attach_workbench(app,workspace_build)
    _drop(app,"/health",{"GET"})
    @app.get("/health")
    def health():
        return {"ok":True,"build":workspace_build,
                "operational_workspace":True,"production_release_ready":False,
                "next_checkpoint":"480.0"}
    return app

create_app = create_workspace_app476
