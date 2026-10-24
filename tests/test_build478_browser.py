from eagleeye.interfaces.web.app478 import create_workspace_app478
from test_build475_onboarding_browser import run_onboarding

def test_current_source_findings_in_real_browser(tmp_path):
    run_onboarding(create_workspace_app478,tmp_path,inventory=True,findings=True)
