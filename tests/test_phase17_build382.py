import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from eagleeye_pro.phase17.investigation_control381 import (  # noqa: E402
    AccessBasis, SourceExecutionMode, SourceRegistryEntry, default_registry,
)
from eagleeye_pro.phase17.source_registry_persistence382 import (  # noqa: E402
    InvestigationControlPlane382,
    SourceRegistryRepository382,
    create_reference_repository,
)

READY = {
    "evidence": {"state": "ready"},
    "crawler": {"state": "ready"},
    "operations": {"state": "ready"},
    "opsec": {"state": "ready"},
    "graph": {"state": "ready"},
    "search": {"state": "degraded"},
    "image": {"state": "not_validated"},
    "ai": {"state": "ready"},
}


class TestRepository382(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.repo = SourceRegistryRepository382(self.conn)
        self.repo.seed(default_registry().all())

    def tearDown(self):
        self.conn.close()

    def test_schema_integrity(self):
        s = self.repo.schema_integrity()
        self.assertEqual(s["integrity_check"], "ok")
        self.assertTrue(s["required_tables_present"])

    def test_seed_is_idempotent(self):
        self.assertEqual(self.repo.seed(default_registry().all()), 0)

    def test_revision_append_only_on_change(self):
        original = self.repo.load_registry().get("sec.edgar")
        self.assertIsNotNone(original)
        changed = SourceRegistryEntry(
            source_id=original.source_id,
            name=original.name,
            access_basis=original.access_basis,
            execution_mode=original.execution_mode,
            jurisdictions=original.jurisdictions,
            source_classes=original.source_classes,
            entity_types=original.entity_types,
            access_methods=original.access_methods,
            endpoint=original.endpoint,
            terms_reference=original.terms_reference,
            external_validation_state=original.external_validation_state,
            notes="Build 382 revision test",
        )
        result = self.repo.upsert_source(changed, actor="tester", reason="change")
        self.assertTrue(result["changed"])
        self.assertEqual(result["revision"], 2)
        self.assertEqual(len(self.repo.revision_history("sec.edgar")), 2)

    def test_unchanged_source_does_not_add_revision(self):
        entry = self.repo.load_registry().get("sec.edgar")
        self.repo.upsert_source(entry, actor="tester", reason="same")
        self.assertEqual(len(self.repo.revision_history("sec.edgar")), 1)

    def test_invalid_source_still_uses_381_governance(self):
        with self.assertRaises(Exception):
            self.repo.upsert_source(SourceRegistryEntry(
                source_id="bad", name="Bad", access_basis=AccessBasis.PUBLIC,
                execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
                endpoint="http://example.test",
            ), actor="x", reason="x")

    def test_registry_fingerprint_stable(self):
        self.assertEqual(self.repo.registry_fingerprint(), self.repo.registry_fingerprint())

    def test_candidate_scope_insert(self):
        self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="candidate")
        self.assertEqual(self.repo.case_scope("CASE-382")[0]["state"], "candidate")

    def test_approval_requires_reviewer(self):
        with self.assertRaises(ValueError):
            self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="approved", confirmation="APPROVE SOURCE")

    def test_approval_requires_exact_confirmation(self):
        with self.assertRaises(ValueError):
            self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="approved", reviewer="analyst", confirmation="yes")

    def test_approval_does_not_create_execution_authority(self):
        self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="approved", reviewer="analyst", confirmation="APPROVE SOURCE")
        cp = InvestigationControlPlane382(self.repo, READY)
        snap = cp.snapshot("CASE-382")
        self.assertFalse(snap["execution_authority"])

    def test_unknown_source_scope_rejected(self):
        with self.assertRaises(KeyError):
            self.repo.set_case_scope(case_id="CASE-382", source_id="unknown", state="candidate")

    def test_bad_case_id_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.case_scope("bad case")

    def test_coverage_result_requires_evidence(self):
        with self.assertRaises(ValueError):
            self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="succeeded")

    def test_planned_coverage_does_not_require_evidence(self):
        oid = self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="planned")
        self.assertTrue(oid.startswith("cov382-"))

    def test_no_result_requires_evidence(self):
        with self.assertRaises(ValueError):
            self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="no_result_observed")

    def test_no_result_never_means_nonexistence(self):
        self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="candidate")
        self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="no_result_observed", evidence_ref="evidence:receipt-1")
        report = self.repo.coverage_report("CASE-382", requested_source_classes=["corporate"])
        self.assertFalse(report.no_result_is_nonexistence)
        self.assertTrue(any(g.gap_type == "coverage_gap" for g in report.gaps))

    def test_success_covers_source_class(self):
        self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="candidate")
        self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="succeeded", evidence_ref="evidence:receipt-2")
        report = self.repo.coverage_report("CASE-382", requested_source_classes=["corporate"])
        self.assertIn("corporate", report.covered_source_classes)
        self.assertFalse(any(g.gap_type == "coverage_gap" and g.key == "corporate" for g in report.gaps))

    def test_registry_gap(self):
        report = self.repo.coverage_report("CASE-382", requested_source_classes=["maritime_unknown_class"])
        self.assertTrue(any(g.gap_type == "registry_gap" for g in report.gaps))

    def test_selection_gap(self):
        report = self.repo.coverage_report("CASE-382", requested_source_classes=["procurement"])
        self.assertTrue(any(g.gap_type == "selection_gap" for g in report.gaps))

    def test_stale_source_gap(self):
        self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="candidate")
        self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="stale", evidence_ref="evidence:stale")
        report = self.repo.coverage_report("CASE-382")
        self.assertTrue(any(g.gap_type == "stale_source" for g in report.gaps))

    def test_failed_source_gap(self):
        self.repo.set_case_scope(case_id="CASE-382", source_id="sec.edgar", state="candidate")
        self.repo.record_coverage(case_id="CASE-382", source_id="sec.edgar", state="failed", evidence_ref="evidence:failed")
        report = self.repo.coverage_report("CASE-382")
        self.assertTrue(any(g.gap_type == "failed_or_blocked" for g in report.gaps))

    def test_file_backed_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "registry.sqlite")
            c1 = sqlite3.connect(path)
            r1 = SourceRegistryRepository382(c1)
            r1.seed(default_registry().all())
            fp = r1.registry_fingerprint()
            c1.close()
            c2 = sqlite3.connect(path)
            r2 = SourceRegistryRepository382(c2)
            self.assertEqual(fp, r2.registry_fingerprint())
            self.assertEqual(r2.load_registry().coverage()["source_count"], 6)
            c2.close()


class TestControlPlane382(unittest.TestCase):
    def setUp(self):
        self.repo = create_reference_repository()
        self.cp = InvestigationControlPlane382(self.repo, READY)

    def tearDown(self):
        self.repo.db.close()

    def test_snapshot_ready_and_persistent(self):
        s = self.cp.snapshot("CASE-382")
        self.assertTrue(s["research_ready"])
        self.assertTrue(s["persistence"]["required_tables_present"])
        self.assertEqual(s["network_requests_created"], 0)
        self.assertEqual(s["mutations_performed"], 0)

    def test_plan_persisted(self):
        p = self.cp.plan_research(case_id="CASE-382", mission="Corporate map", source_classes=["corporate"])
        row = self.repo.get_plan(p.plan_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["plan_hash"], p.plan_hash)

    def test_plan_requires_go_and_no_execution(self):
        p = self.cp.plan_research(case_id="CASE-382", mission="Corporate map", source_classes=["corporate"])
        self.assertTrue(p.requires_go)
        self.assertFalse(p.execution_authority)
        self.assertFalse(p.scope_expansion_authority)
        self.assertEqual(p.network_requests_created, 0)

    def test_plan_creates_candidate_scope_only(self):
        p = self.cp.plan_research(case_id="CASE-382", mission="Procurement", source_classes=["procurement"])
        states = {x["source_id"]: x["state"] for x in self.repo.case_scope("CASE-382")}
        self.assertEqual(set(p.source_ids), set(states))
        self.assertTrue(all(v == "candidate" for v in states.values()))

    def test_plan_deterministic_hash(self):
        p1 = self.cp.plan_research(case_id="CASE-382", mission="Corporate map", source_classes=["corporate"])
        p2 = self.cp.plan_research(case_id="CASE-382", mission="Corporate map", source_classes=["corporate"])
        self.assertEqual(p1.plan_hash, p2.plan_hash)
        self.assertEqual(p1.plan_id, p2.plan_id)

    def test_opsec_hold_blocks_plan(self):
        providers = dict(READY)
        providers["opsec"] = {"state": "hold"}
        cp = InvestigationControlPlane382(self.repo, providers)
        with self.assertRaises(RuntimeError):
            cp.plan_research(case_id="CASE-382", mission="x")

    def test_operations_hold_blocks_plan(self):
        providers = dict(READY)
        providers["operations"] = {"state": "ready", "circuit_open": True}
        cp = InvestigationControlPlane382(self.repo, providers)
        with self.assertRaises(RuntimeError):
            cp.plan_research(case_id="CASE-382", mission="x")

    def test_empty_registry_is_not_faked(self):
        repo = SourceRegistryRepository382(sqlite3.connect(":memory:"))
        try:
            cp = InvestigationControlPlane382(repo, READY)
            p = cp.plan_research(case_id="CASE-382", mission="x", source_classes=["corporate"])
            self.assertEqual(p.source_ids, ())
            report = repo.coverage_report("CASE-382", requested_source_classes=["corporate"])
            self.assertTrue(any(g.gap_type == "registry_gap" for g in report.gaps))
        finally:
            repo.db.close()


if __name__ == "__main__":
    unittest.main()
