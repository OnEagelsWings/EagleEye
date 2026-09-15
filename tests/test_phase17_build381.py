import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from eagleeye_pro.phase17.investigation_control381 import (  # noqa: E402
    AccessBasis,
    CapabilityState,
    GlobalSourceRegistry381,
    InvestigationControlPlane381,
    RegistryValidationError,
    SourceExecutionMode,
    SourceRegistryEntry,
    default_registry,
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


class TestSourceRegistry381(unittest.TestCase):
    def test_default_seed_registry_loads(self):
        r = default_registry()
        self.assertGreaterEqual(r.coverage()["source_count"], 6)
        self.assertEqual(r.coverage()["network_requests_created"], 0)

    def test_registry_is_deterministic(self):
        self.assertEqual(default_registry().coverage()["registry_fingerprint"], default_registry().coverage()["registry_fingerprint"])

    def test_credentials_in_url_rejected(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="bad.creds", name="bad", access_basis=AccessBasis.PUBLIC,
                endpoint="https://user:password@example.test/data", terms_reference="terms")])

    def test_secret_query_rejected(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="bad.token", name="bad", access_basis=AccessBasis.PUBLIC,
                endpoint="https://example.test/?api_key=secret", terms_reference="terms")])

    def test_http_executable_rejected(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="bad.http", name="bad", access_basis=AccessBasis.PUBLIC,
                execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
                endpoint="http://example.test/", terms_reference="terms")])

    def test_http_plan_only_allowed(self):
        r = GlobalSourceRegistry381([SourceRegistryEntry(
            source_id="legacy.http", name="legacy", access_basis=AccessBasis.PUBLIC,
            execution_mode=SourceExecutionMode.PLAN_ONLY,
            endpoint="http://example.test/", terms_reference="terms")])
        self.assertIsNotNone(r.get("legacy.http"))

    def test_licensed_requires_license_reference(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="licensed.no-ref", name="x", access_basis=AccessBasis.LICENSED,
                execution_mode=SourceExecutionMode.PLAN_ONLY)])

    def test_authorized_requires_terms_reference(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="auth.no-ref", name="x", access_basis=AccessBasis.AUTHORIZED,
                execution_mode=SourceExecutionMode.PLAN_ONLY)])

    def test_provenance_cannot_be_disabled(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="bad.prov", name="x", access_basis=AccessBasis.PUBLIC,
                provenance_required=False, execution_mode=SourceExecutionMode.PLAN_ONLY)])

    def test_human_source_review_cannot_be_disabled(self):
        with self.assertRaises(RegistryValidationError):
            GlobalSourceRegistry381([SourceRegistryEntry(
                source_id="bad.review", name="x", access_basis=AccessBasis.PUBLIC,
                human_source_review_required=False, execution_mode=SourceExecutionMode.PLAN_ONLY)])

    def test_id_collision_rejected(self):
        r = GlobalSourceRegistry381()
        r.register(SourceRegistryEntry(source_id="same.id", name="A", access_basis=AccessBasis.PUBLIC))
        with self.assertRaises(RegistryValidationError):
            r.register(SourceRegistryEntry(source_id="same.id", name="B", access_basis=AccessBasis.PUBLIC))

    def test_candidate_jurisdiction(self):
        c = default_registry().candidate_sources(jurisdictions=["US"])
        self.assertTrue(any(x.source_id == "sec.edgar" for x in c))

    def test_candidate_source_class(self):
        c = default_registry().candidate_sources(source_classes=["procurement"])
        ids = {x.source_id for x in c}
        self.assertIn("usaspending.awards", ids)
        self.assertIn("eu.ted", ids)

    def test_candidate_entity_type(self):
        c = default_registry().candidate_sources(entity_types=["filing"])
        self.assertEqual(c[0].source_id, "sec.edgar")

    def test_candidate_limit(self):
        self.assertEqual(len(default_registry().candidate_sources(limit=2)), 2)


class TestControlPlane381(unittest.TestCase):
    def setUp(self):
        self.cp = InvestigationControlPlane381(default_registry(), READY)

    def test_snapshot_ready(self):
        s = self.cp.snapshot("CASE-381")
        self.assertTrue(s.research_ready)
        self.assertFalse(s.operations_hold)
        self.assertFalse(s.opsec_hold)
        self.assertEqual(s.network_requests_created, 0)
        self.assertEqual(s.mutations_performed, 0)

    def test_missing_critical_holds(self):
        p = dict(READY)
        del p["evidence"]
        s = InvestigationControlPlane381(default_registry(), p).snapshot("CASE-381")
        self.assertFalse(s.research_ready)
        self.assertIn("missing:evidence", s.reasons)

    def test_operations_circuit_holds(self):
        p = dict(READY)
        p["operations"] = {"state": "ready", "circuit_open": True}
        s = InvestigationControlPlane381(default_registry(), p).snapshot("CASE-381")
        self.assertFalse(s.research_ready)
        self.assertTrue(s.operations_hold)

    def test_opsec_circuit_holds(self):
        p = dict(READY)
        p["opsec"] = {"state": "hold"}
        s = InvestigationControlPlane381(default_registry(), p).snapshot("CASE-381")
        self.assertFalse(s.research_ready)
        self.assertTrue(s.opsec_hold)

    def test_case_mismatch_holds_critical(self):
        p = dict(READY)
        p["crawler"] = {"state": "ready", "case_mismatch": True}
        s = InvestigationControlPlane381(default_registry(), p).snapshot("CASE-381")
        self.assertFalse(s.research_ready)
        self.assertEqual(s.capability_states["crawler"], CapabilityState.HOLD.value)

    def test_invalid_case_rejected(self):
        with self.assertRaises(ValueError):
            self.cp.snapshot("")

    def test_plan_requires_go(self):
        p = self.cp.plan_research(case_id="CASE-381", mission="Map corporate connections", jurisdictions=["US"], entity_types=["company"])
        self.assertTrue(p.requires_go)
        self.assertFalse(p.execution_authority)
        self.assertFalse(p.scope_expansion_authority)
        self.assertEqual(p.network_requests_created, 0)

    def test_plan_has_hash(self):
        p = self.cp.plan_research(case_id="CASE-381", mission="Map corporate connections", source_classes=["corporate"])
        self.assertEqual(len(p.plan_hash), 64)

    def test_empty_mission_rejected(self):
        with self.assertRaises(ValueError):
            self.cp.plan_research(case_id="CASE-381", mission="")

    def test_held_control_plane_refuses_plan(self):
        p = dict(READY)
        p["opsec"] = {"state": "hold"}
        with self.assertRaises(RuntimeError):
            InvestigationControlPlane381(default_registry(), p).plan_research(case_id="CASE-381", mission="x")

    def test_plan_does_not_mark_plan_only_source_live(self):
        p = self.cp.plan_research(case_id="CASE-381", mission="Procurement", source_classes=["procurement"])
        ted = [x for x in p.source_candidates if x.source_id == "eu.ted"][0]
        self.assertEqual(ted.execution_mode, SourceExecutionMode.PLAN_ONLY)

    def test_snapshot_hash_deterministic(self):
        self.assertEqual(self.cp.snapshot("CASE-381").snapshot_hash, self.cp.snapshot("CASE-381").snapshot_hash)


if __name__ == "__main__":
    unittest.main()
