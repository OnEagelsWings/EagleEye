"""Build 482: verify the existing Dork, image and graph systems using a real browser."""
from eagleeye.interfaces.web.app482 import create_workspace_app482
from test_build475_onboarding_browser import run_onboarding

def test_build482_first_run_to_dork_image_graph_and_real_working_report(tmp_path):
    run_onboarding(create_workspace_app482, tmp_path,
                   inventory=True, expert=True, findings=True,
                   report=True, dorks_images=True)
