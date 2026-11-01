"""Build 482: restoration of preexisting Dork and Image Intelligence workbenches."""
from .app481 import create_workspace_app481
from .recovery482 import attach_recovery482

def create_workspace_app482(*, base_dir=None):
    app = create_workspace_app481(base_dir=base_dir, workspace_build="482.0")
    app.version = "482.0"
    app.title = "EagleEye – Einsatzarbeitsplatz mit Dork-Recherche und Bildakte 482"
    attach_recovery482(app, "482.0")
    return app

create_app = create_workspace_app482
