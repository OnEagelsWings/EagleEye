from eagleeye.interfaces.web.app477 import create_workspace_app477
from test_build475_onboarding_browser import run_onboarding

def test_current_inventory_in_real_browser(tmp_path):
    run_onboarding(create_workspace_app477,tmp_path,inventory=True)
