"""Real Chromium UI acceptance for first run, expert panel and working report."""
from eagleeye.interfaces.web.app481 import create_workspace_app481
from test_build475_onboarding_browser import run_onboarding

def test_build481_real_browser_case_document_source_graph_and_report(tmp_path):
    run_onboarding(create_workspace_app481, tmp_path,
                   inventory=True, expert=True, findings=True, report=True)
