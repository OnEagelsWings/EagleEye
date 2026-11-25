"""Build 485 first operator walkthrough in a real Chromium browser."""
from eagleeye.interfaces.web.app485 import create_workspace_app485
from test_build475_onboarding_browser import run_onboarding

def test_installed_operator_navigation_without_devtools(tmp_path):
    run_onboarding(create_workspace_app485,tmp_path,
                   inventory=True,expert=True,findings=True,
                   report=True,dorks_images=True)
