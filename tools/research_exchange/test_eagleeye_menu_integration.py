"""Integration smoke for the public-research-only entry in EagleEye 500 menu."""
from pathlib import Path
import unittest


class EagleEyeMenuIntegrationTests(unittest.TestCase):
    def test_menu_launches_only_isolated_research_module(self):
        source_root = Path(__file__).resolve().parents[2]
        launcher = source_root / "START_HIER.bat"
        self.assertTrue(launcher.is_file(), "EagleEye integrated menu missing")
        raw = launcher.read_bytes().decode("utf-8-sig", errors="replace")
        lines = [line.strip() for line in raw.splitlines()]
        # The menu only accepts fixed CHOICE keys (no free console input in CMD commands).
        choice = [line for line in lines if line.lower().startswith("choice /c ")]
        self.assertEqual(len(choice), 1)
        keys = choice[0].split()[2].lower()
        self.assertIn("6", keys)
        level = keys.index("6") + 1
        self.assertIn("if errorlevel %d goto action6" % level, [line.lower() for line in lines])
        start = lines.index(":action6")
        block = lines[start + 1:lines.index("goto menu", start)]
        self.assertEqual(len(block), 1)
        self.assertIn("tools\\research_exchange\\START_RESEARCH_BRIDGE_WINDOWS.cmd", block[0])
        self.assertNotIn("START_EAGLEEYE_PRO.bat", block[0])
        self.assertNotIn("PersonOSINT", block[0])
        self.assertFalse(any("set /p" in line.lower() for line in lines))

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
