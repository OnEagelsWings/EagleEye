"""Build 485 real-world pilot runs the established no-mock checkpoint with current app.

This only replaces the app factory. The existing real public DNS/RDAP/Crossref
fetches, original source hashes, approvals and physical restore remain intact.
"""
import public_pilot482 as pilot
from eagleeye.interfaces.web.app485 import create_workspace_app485

pilot.create_workspace_app482=create_workspace_app485

if __name__=="__main__":
    raise SystemExit(pilot.main())
