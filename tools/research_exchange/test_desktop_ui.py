"""Opt-in real Tk integration smoke test, no network access or private data.

Run explicitly on an interactive Windows desktop:
EAGLEEYE_RUN_GUI_SMOKE=1 python -m unittest test_desktop_ui -v
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signed_approval import CONFIRMATION


@unittest.skipUnless(os.environ.get("EAGLEEYE_RUN_GUI_SMOKE") == "1",
                     "GUI smoke requires explicit interactive desktop opt-in")
class DesktopUISmokeTests(unittest.TestCase):
    def test_create_preview_and_sign_synthetic_without_network(self):
        from desktop_ui import ResearchBridgeWindow

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("workspace/outbox", "workspace/inbox",
                        "workspace/git", "workspace/audit"):
                (root / rel).mkdir(parents=True)
            window = ResearchBridgeWindow(root)
            window.withdraw()
            try:
                window.topic.insert(0, "Synthetic public astronomy")
                window.summary.insert("1.0", "Fictional study item for smoke test")
                window._create_draft()
                window.update()
                self.assertEqual(len(window._outbound_names), 1)
                self.assertEqual(window._previewed, window._outbound_names[0])
                window.confirmation.insert(0, CONFIRMATION)
                with patch("desktop_workflow.read_key", return_value=b"z" * 32), \
                     patch("desktop_workflow.publish") as never_publish:
                    window._approve_outbound()
                    self.assertIsNotNone(window._receipt)
                    self.assertEqual(window._receipt[0], window._outbound_names[0])
                    never_publish.assert_not_called()
            finally:
                window.destroy()

    def test_local_inbound_review_button_does_not_publish(self):
        import json
        from staging_db import StagingDB
        from desktop_ui import ResearchBridgeWindow

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("workspace/outbox", "workspace/inbox",
                        "workspace/git", "workspace/audit"):
                (root / rel).mkdir(parents=True)
            item = {"schema": 1,
                    "id": "00000000-0000-4000-8000-000000000099",
                    "kind": "research_result", "classification": "public-topic",
                    "topic": "Synthetic historical physics",
                    "summary": "Test fixture only", "sources": [], "synthetic": True}
            StagingDB(root / "workspace" / "staging.sqlite").stage(
                json.dumps(item).encode(), "a" * 40)
            window = ResearchBridgeWindow(root)
            window.withdraw()
            try:
                window.in_list.selection_set(0)
                window._preview_inbound()
                with patch("desktop_ui.simpledialog.askstring", return_value=CONFIRMATION), \
                     patch("desktop_workflow.read_key", return_value=b"z" * 32), \
                     patch("desktop_workflow.publish") as never_publish:
                    window._review_inbound("approved")
                    self.assertEqual(window.workflow.audit_events()[-1]["status"],
                                     "inbound-approved")
                    never_publish.assert_not_called()
            finally:
                window.destroy()


if __name__ == "__main__":
    unittest.main()
