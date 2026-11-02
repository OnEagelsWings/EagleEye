"""Build 486: Chromium onboarding must keep the full real-case workflow."""
from eagleeye.interfaces.web.app486 import create_workspace_app486
from test_build475_onboarding_browser import run_onboarding


def test_build486_first_run_and_case_workflow(tmp_path):
    run_onboarding(create_workspace_app486, tmp_path,
                   inventory=True, expert=True, findings=True,
                   report=True, dorks_images=True)
