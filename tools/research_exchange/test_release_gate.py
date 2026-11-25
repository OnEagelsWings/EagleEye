"""Release-gate evaluations never perform GitHub, network or filesystem writes."""
import unittest
from release_gate import REQUIRED, evaluate


class ReleaseGateTests(unittest.TestCase):
    def fixture(self, result="passed"):
        return dict(app_id="eagleeye-public-research-bridge",
                    version="1.0.0-rc2",
                    checks={item: result for item in REQUIRED})

    def test_pending_blocks_release(self):
        record = self.fixture()
        record["checks"]["release_owner_approval"] = "pending"
        report = evaluate(record)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["blocked"], ["release_owner_approval"])
        self.assertTrue(report["no_automatic_merge_or_release"])

    def test_missing_gate_fails_closed(self):
        record = self.fixture()
        del record["checks"]["audit_independent_anchor"]
        with self.assertRaises(ValueError):
            evaluate(record)

    def test_unknown_gate_fails_closed(self):
        record = self.fixture()
        record["checks"]["surveillance_monitoring"] = "passed"
        with self.assertRaises(ValueError):
            evaluate(record)

    def test_invalid_status_fails_closed(self):
        record = self.fixture()
        record["checks"]["eagleeye_ci"] = "maybe"
        with self.assertRaises(ValueError):
            evaluate(record)

    def test_all_green_only_reports_manual_readiness(self):
        report = evaluate(self.fixture())
        self.assertEqual(report["status"], "READY_FOR_MANUAL_RELEASE")
        self.assertTrue(report["no_automatic_merge_or_release"])


if __name__ == "__main__":
    unittest.main()
