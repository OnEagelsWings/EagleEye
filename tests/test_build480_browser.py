from eagleeye.interfaces.web.app480 import create_workspace_app480
from test_build475_onboarding_browser import run_onboarding
def test_real_chromium_complete_current_workflow(tmp_path):
    run_onboarding(create_workspace_app480,tmp_path,inventory=True,findings=True,report=True,expert=True)
