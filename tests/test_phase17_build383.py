import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from eagleeye_pro.phase17.source_planner383 import (  # noqa: E402
    CONFIRM_INFERRED_SELECTORS,
    SourcePlanner383,
    SourcePlannerRepository383,
    TEMPLATES,
    create_reference_repository383,
)

READY = {
    "evidence": {"state": "ready"}, "crawler": {"state": "ready"},
    "operations": {"state": "ready"}, "opsec": {"state": "ready"},
    "graph": {"state": "ready"}, "search": {"state": "degraded"},
    "image": {"state": "not_validated"}, "ai": {"state": "ready"},
}


class TestTaxonomy383(unittest.TestCase):
    def test_corporate_inference(self):
        req = SourcePlanner383.infer_requirements("Map company directors and shareholders")
        self.assertIn("corporate", {x.source_class for x in req})
        self.assertIn("reference", {x.source_class for x in req})

    def test_german_procurement_inference(self):
        req = SourcePlanner383.infer_requirements("Prüfe Vergabe und öffentliche Aufträge")
        classes = {x.source_class for x in req}
        self.assertIn("procurement", classes)
        self.assertIn("public_money", classes)

    def test_legal_inference(self):
        req = SourcePlanner383.infer_requirements("Find court and insolvency records")
        self.assertIn("legal", {x.source_class for x in req})

    def test_archive_inference(self):
        req = SourcePlanner383.infer_requirements("Find historical archive snapshots")
        self.assertIn("archive", {x.source_class for x in req})

    def test_sanctions_inference(self):
        req = SourcePlanner383.infer_requirements("Check sanctions watchlist records")
        self.assertIn("sanctions", {x.source_class for x in req})

    def test_empty_mission_rejected(self):
        with self.assertRaises(ValueError):
            SourcePlanner383.infer_requirements("   ")

    def test_templates_have_no_execution_authority(self):
        self.assertTrue(TEMPLATES)
        self.assertTrue(all(t.review_required and not t.execution_authority for t in TEMPLATES))


class TestPlanner383(unittest.TestCase):
    def setUp(self):
        self.repo = create_reference_repository383()
        self.planner = SourcePlanner383(self.repo, READY)

    def tearDown(self):
        self.repo.db.close()

    def test_schema_contains_383_tables(self):
        state = self.repo.schema_integrity()
        self.assertTrue(state["build383_tables_present"])
        self.assertEqual(state["build383_missing_tables"], [])

    def test_inferred_plan_requires_selector_review(self):
        p = self.planner.plan(case_id="CASE-383", mission="Investigate company directors")
        self.assertEqual(p.selector_state, "proposed_inferred")
        self.assertTrue(p.requires_selector_review)
        self.assertIsNone(p.underlying_plan_id)
        self.assertEqual(self.repo.case_scope("CASE-383"), ())

    def test_confirmed_inference_creates_candidate_scope_only(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Investigate company directors",
            confirmation=CONFIRM_INFERRED_SELECTORS,
        )
        self.assertEqual(p.selector_state, "confirmed_inferred")
        self.assertFalse(p.requires_selector_review)
        self.assertIsNotNone(p.underlying_plan_id)
        states = self.repo.case_scope("CASE-383")
        self.assertTrue(states)
        self.assertTrue(all(r["state"] == "candidate" for r in states))

    def test_bad_confirmation_rejected(self):
        with self.assertRaises(ValueError):
            self.planner.plan(case_id="CASE-383", mission="Investigate company", confirmation="yes")

    def test_explicit_selectors_do_not_need_inference_confirmation(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Case work", source_classes=["corporate"],
            jurisdictions=["US"], entity_types=["company"],
        )
        self.assertEqual(p.selector_state, "explicit")
        self.assertFalse(p.requires_selector_review)
        self.assertIsNotNone(p.underlying_plan_id)

    def test_steps_rank_sec_for_us_corporate(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Corporate case", source_classes=["corporate"],
            jurisdictions=["US"], entity_types=["company"],
        )
        corporate_steps = [s for s in p.steps if s.source_class == "corporate"]
        self.assertTrue(corporate_steps)
        self.assertEqual(corporate_steps[0].source_id, "sec.edgar")

    def test_global_source_still_ranked_for_non_us(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Corporate case", source_classes=["corporate"],
            jurisdictions=["DE"], entity_types=["company"],
        )
        ids = [s.source_id for s in p.steps]
        self.assertIn("gleif.lei", ids)

    def test_registry_gap_for_sanctions(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Sanctions check", source_classes=["sanctions"]
        )
        self.assertTrue(any(g.gap_type == "registry_gap" and g.key == "sanctions" for g in p.gaps))

    def test_jurisdiction_gap(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Procurement case", source_classes=["procurement"],
            jurisdictions=["BR"],
        )
        self.assertTrue(any(g.gap_type == "jurisdiction_gap" for g in p.gaps))

    def test_validation_gap_visible(self):
        p = self.planner.plan(
            case_id="CASE-383", mission="Corporate case", source_classes=["corporate"]
        )
        self.assertTrue(any(g.gap_type == "validation_gap" for g in p.gaps))

    def test_unknown_mission_without_explicit_selector_has_selector_gap(self):
        p = self.planner.plan(case_id="CASE-383", mission="Analyse the subject")
        self.assertEqual(p.active_source_classes, ())
        self.assertTrue(any(g.gap_type == "selector_gap" for g in p.gaps))
        self.assertEqual(p.steps, ())

    def test_plan_is_network_silent(self):
        p = self.planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])
        self.assertEqual(p.network_requests_created, 0)
        self.assertFalse(p.execution_authority)
        self.assertFalse(p.scope_expansion_authority)
        self.assertTrue(p.requires_go)

    def test_step_is_review_required_and_non_executing(self):
        p = self.planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])
        self.assertTrue(p.steps)
        self.assertTrue(all(s.requires_human_review and not s.execution_authority for s in p.steps))

    def test_plan_persisted(self):
        p = self.planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])
        row = self.repo.load_acquisition_plan(p.plan_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["plan_hash"], p.plan_hash)
        self.assertEqual(len(row["steps"]), len(p.steps))

    def test_deterministic_plan_id(self):
        p1 = self.planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])
        p2 = self.planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])
        self.assertEqual(p1.plan_id, p2.plan_id)
        self.assertEqual(p1.plan_hash, p2.plan_hash)

    def test_opsec_hold_blocks_planning(self):
        providers = dict(READY)
        providers["opsec"] = {"state": "hold"}
        planner = SourcePlanner383(self.repo, providers)
        with self.assertRaises(RuntimeError):
            planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])

    def test_operations_hold_blocks_planning(self):
        providers = dict(READY)
        providers["operations"] = {"state": "ready", "circuit_open": True}
        planner = SourcePlanner383(self.repo, providers)
        with self.assertRaises(RuntimeError):
            planner.plan(case_id="CASE-383", mission="Corporate case", source_classes=["corporate"])

    def test_limit_validation(self):
        with self.assertRaises(ValueError):
            self.planner.plan(case_id="CASE-383", mission="x", source_classes=["corporate"], per_class_limit=0)
        with self.assertRaises(ValueError):
            self.planner.plan(case_id="CASE-383", mission="x", source_classes=["corporate"], per_class_limit=11)

    def test_file_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "planner.sqlite")
            conn = sqlite3.connect(path)
            repo = SourcePlannerRepository383(conn)
            from eagleeye_pro.phase17.investigation_control381 import default_registry
            repo.seed(default_registry().all())
            planner = SourcePlanner383(repo, READY)
            p = planner.plan(case_id="CASE-PERSIST", mission="Corporate", source_classes=["corporate"])
            conn.close()
            conn2 = sqlite3.connect(path)
            repo2 = SourcePlannerRepository383(conn2)
            self.assertIsNotNone(repo2.load_acquisition_plan(p.plan_id))
            conn2.close()

    def test_inference_does_not_approve_sources(self):
        self.planner.plan(
            case_id="CASE-383", mission="Investigate company directors",
            confirmation=CONFIRM_INFERRED_SELECTORS,
        )
        self.assertFalse(any(r["state"] == "approved" for r in self.repo.case_scope("CASE-383")))

    def test_explicit_sanctions_gap_does_not_invent_source(self):
        p = self.planner.plan(case_id="CASE-383", mission="Sanctions", source_classes=["sanctions"])
        self.assertEqual(p.steps, ())
        self.assertTrue(any(g.gap_type == "registry_gap" for g in p.gaps))


if __name__ == "__main__":
    unittest.main()
