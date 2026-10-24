from eagleeye.interfaces.web.app479 import create_workspace_app479
from test_build475_onboarding_browser import run_onboarding
def test_current_report_and_preserved_expert_tools_in_real_browser(tmp_path):
    run_onboarding(create_workspace_app479,tmp_path,inventory=True,findings=True,report=True,expert=True)
