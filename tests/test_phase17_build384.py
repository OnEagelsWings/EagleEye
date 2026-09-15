import sqlite3
import unittest

from eagleeye_pro.phase17.jurisdiction_intelligence384 import (
    CONFIRM_WAVES,
    JurisdictionIntelligence384,
    JurisdictionProfile384,
    create_reference_repository384,
)
from eagleeye_pro.phase17.source_planner383 import CONFIRM_INFERRED_SELECTORS


class ReadyProvider:
    def __init__(self, state="ready"):
        self.state = state
    def status_for_case(self, case_id):
        return {"state": self.state}


class Build384Tests(unittest.TestCase):
    def setUp(self):
        self.repo = create_reference_repository384(sqlite3.connect(":memory:"))
        self.providers = {
            "operations": ReadyProvider(), "opsec": ReadyProvider(), "evidence": ReadyProvider(),
            "crawler": ReadyProvider(), "search": ReadyProvider(), "graph": ReadyProvider(),
        }
        self.service = JurisdictionIntelligence384(self.repo, self.providers)

    def test_schema(self):
        integrity = self.repo.schema_integrity()
        self.assertTrue(integrity["build384_tables_present"])

    def test_profiles_are_non_executing(self):
        profiles = self.repo.load_jurisdiction_profiles()
        self.assertIn("us", profiles)
        self.assertFalse(profiles["us"].execution_authority)

    def test_profile_cannot_grant_execution(self):
        with self.assertRaises(ValueError):
            self.repo.upsert_jurisdiction_profile(JurisdictionProfile384("x", ("corporate",), execution_authority=True))

    def test_preview_does_not_execute(self):
        plan = self.service.plan_waves(
            case_id="c1", mission="company procurement and regulatory records",
            jurisdictions=("us",), entity_types=("organization",),
            selector_confirmation=CONFIRM_INFERRED_SELECTORS,
        )
        self.assertTrue(plan.requires_wave_confirmation)
        self.assertEqual(plan.confirmation_state, "preview")
        self.assertFalse(plan.execution_authority)
        self.assertFalse(plan.scope_expansion_authority)
        self.assertEqual(plan.network_requests_created, 0)

    def test_confirmed_wave_still_non_executing(self):
        plan = self.service.plan_waves(
            case_id="c2", mission="company procurement",
            jurisdictions=("us",), source_classes=("corporate", "procurement"),
            wave_confirmation=CONFIRM_WAVES,
        )
        self.assertFalse(plan.requires_wave_confirmation)
        self.assertEqual(plan.confirmation_state, "confirmed")
        self.assertFalse(plan.execution_authority)
        for wave in plan.waves:
            self.assertTrue(wave.requires_go)
            self.assertFalse(wave.execution_authority)

    def test_invalid_wave_confirmation(self):
        with self.assertRaises(ValueError):
            self.service.plan_waves(case_id="c3", mission="company", source_classes=("corporate",), wave_confirmation="yes")

    def test_hold_blocks_planning(self):
        providers = dict(self.providers)
        providers["opsec"] = ReadyProvider("hold")
        service = JurisdictionIntelligence384(self.repo, providers)
        with self.assertRaises(RuntimeError):
            service.plan_waves(case_id="c4", mission="company", source_classes=("corporate",))

    def test_coverage_objectives_exist(self):
        plan = self.service.plan_waves(
            case_id="c5", mission="company", source_classes=("corporate",), jurisdictions=("us",)
        )
        self.assertTrue(plan.coverage_objectives)
        self.assertEqual(plan.coverage_objectives[0].source_class, "corporate")

    def test_unknown_jurisdiction_exposes_gap(self):
        plan = self.service.plan_waves(
            case_id="c6", mission="procurement", source_classes=("procurement",), jurisdictions=("xx",)
        )
        self.assertTrue(any(g.gap_type in {"jurisdiction_gap", "registry_gap", "planning_gap"} for g in plan.gaps))

    def test_wave_size_bound(self):
        plan = self.service.plan_waves(
            case_id="c7", mission="company government archive regulation",
            source_classes=("corporate", "government", "archive", "regulatory"),
            max_steps_per_wave=2,
        )
        self.assertTrue(all(len(w.steps) <= 2 for w in plan.waves))

    def test_persistence(self):
        plan = self.service.plan_waves(case_id="c8", mission="company", source_classes=("corporate",))
        row = self.repo.db.execute("SELECT plan_hash FROM research_wave_plan_384 WHERE wave_plan_id=?", (plan.wave_plan_id,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], plan.plan_hash)

    def test_deterministic(self):
        kwargs = dict(case_id="c9", mission="company", source_classes=("corporate",), jurisdictions=("us",))
        a = self.service.plan_waves(**kwargs)
        b = self.service.plan_waves(**kwargs)
        self.assertEqual(a.plan_hash, b.plan_hash)
        self.assertEqual(a.wave_plan_id, b.wave_plan_id)

    def test_no_empty_mission(self):
        with self.assertRaises(ValueError):
            self.service.plan_waves(case_id="c10", mission="", source_classes=("corporate",))

    def test_max_steps_bounds(self):
        with self.assertRaises(ValueError):
            self.service.plan_waves(case_id="c11", mission="company", source_classes=("corporate",), max_steps_per_wave=0)
        with self.assertRaises(ValueError):
            self.service.plan_waves(case_id="c12", mission="company", source_classes=("corporate",), max_steps_per_wave=21)


if __name__ == "__main__":
    unittest.main()
