"""Build 489 workspace: consolidate existing review and source provenance views."""
from .app488 import create_workspace_app488
from .checkpoint489 import attach_checkpoint489


def create_workspace_app489(*, base_dir=None, workspace_build="489.0"):
    app = create_workspace_app488(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye – Prüfcheckpoint 489"
    attach_checkpoint489(app, workspace_build)

    # The inherited security middleware applies a same-origin default after
    # endpoint headers have been created. This read-only evidence checkpoint
    # deliberately needs the stricter no-referrer policy, including when a
    # case title or source identifier is included in a navigation URL.
    @app.middleware("http")
    async def checkpoint_referrer_policy(request, call_next):
        response = await call_next(request)
        if request.url.path == "/workbench/checkpoint489":
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return app


create_app = create_workspace_app489
