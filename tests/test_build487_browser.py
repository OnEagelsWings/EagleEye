"""Build 487: Chromium onboarding preserves the complete case workflow and source navigation."""
from eagleeye.interfaces.web.app487 import create_workspace_app487
from test_build475_onboarding_browser import run_onboarding

def test_build487_first_run_and_case_workflow(tmp_path):
    run_onboarding(create_workspace_app487, tmp_path,
                   inventory=True, expert=True, findings=True,
                   report=True, dorks_images=True)
