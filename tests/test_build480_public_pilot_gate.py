"""The live acceptance gate must fail honestly without a fake fallback."""
import json,sys
from unittest.mock import patch
from tools.public_pilot480 import main
def test_all_unavailable_sources_fail_and_keep_diagnostic_artifact(tmp_path):
    output=tmp_path/'public-pilot.json'
    with patch.object(sys,'argv',['public_pilot480','--output',str(output)]),patch('tools.public_pilot480.actual_capture',side_effect=OSError('provider unavailable')) as capture:
        assert main()==1
    proof=json.loads(output.read_text())
    assert capture.call_count==3 and proof['result']=='FAIL' and all(row['status']=='FAIL' for row in proof['sources'])
    assert proof['mocked_network'] is False and proof['technical_existing_dossier_chain']=='N/A'
    assert proof['human_independent_review'] is proof['llm_evaluated'] is proof['production_release_ready'] is False
