"""Build 492 workspace: evidence-grade web capture, document structure/OCR,
source independence, stronger entity candidates and network analysis."""
from .app489 import create_workspace_app489
from .intel492 import attach_intel492
from .ux492 import attach_error_pages
from .docview492 import attach_document_view
from .buero import attach_buero
from .darknet import attach_darknet
from .ted import attach_ted


def create_workspace_app492(*, base_dir=None, workspace_build="492.0"):
    app = create_workspace_app489(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = f"EagleEye – Build {workspace_build}"
    attach_intel492(app, workspace_build, base_dir)
    attach_error_pages(app, workspace_build)
    attach_document_view(app, workspace_build)
    attach_buero(app, workspace_build)  # office: clients, mandates, screening, time, expenses
    attach_ted(app, workspace_build)  # EU public procurement notices
    attach_darknet(app, workspace_build)  # Tor: source register, search, capture as evidence

    # Keep the inherited same-origin Referrer-Policy: it already withholds case URLs from
    # other sites, while no-referrer would make Chromium send "Origin: null" on these
    # pages' POST forms and the CSRF/origin guard would (correctly) reject them.
    return app


create_app = create_workspace_app492
