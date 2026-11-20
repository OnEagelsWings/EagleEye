"""Integration smoke for the public-research-only entry in EagleEye 500 menu."""
from pathlib import Path
import unittest


class EagleEyeMenuIntegrationTests(unittest.TestCase):
    def test_menu_launches_only_isolated_research_module(self):
        source_root = Path(__file__).resolve().parents[2]
        launcher = source_root / "START_HIER.bat"
        self.assertTrue(launcher.is_file(), "EagleEye integrated menu missing")
        raw = launcher.read_bytes().decode("utf-8-sig", errors="replace")
        six = [line.strip() for line in raw.splitlines()
               if line.lower().startswith('if "%wahl%"=="6"')]
        self.assertEqual(len(six), 1)
        self.assertIn("tools\\research_exchange\\START_RESEARCH_BRIDGE_WINDOWS.cmd",
                      six[0])
        self.assertNotIn("START_EAGLEEYE_PRO.bat", six[0])
        self.assertNotIn("PersonOSINT", six[0])

    def test_no_desktop_keys_or_case_files_in_bundle(self):
        source_root = Path(__file__).resolve().parents[2]
        bridge_root = source_root / "tools" / "research_exchange"
        self.assertTrue((bridge_root / "desktop_ui.py").is_file())
        self.assertTrue((bridge_root / "install_local.py").is_file())
        self.assertTrue((bridge_root / "START_RESEARCH_BRIDGE_WINDOWS.cmd").is_file())
        self.assertFalse((bridge_root / "secrets").exists())
        self.assertFalse((bridge_root / "approval.dpapi").exists())


if __name__ == "__main__":
    unittest.main()
