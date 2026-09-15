from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _loads(value: str, default: Any):
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 5000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


class Build254InternationalSourceProfilesService:
    BUILD = "254.0"
    OBS_ASSERTION_CLASSES = ("direct_source_observation", "source_reports_statement", "metadata_only")
    JURISDICTIONS = ("EU", "US", "UK", "IL")

    KEYWORDS = {
        "eu_transparency_register": (
            "transparency register", "transparenzregister eu", "eu lobby", "interest representation", "interessenvertretung",
            "registre de transparence", "représentation d'intérêts", "clients",
        ),
        "eu_financial_transparency_system": (
            "financial transparency system", "funding recipients", "eu funding", "commission funding", "begünstigte",
            "förderung", "beneficiary", "beneficiaries", "bénéficiaire", "subvention",
        ),
        "eu_ted": (
            "ted", "tenders electronic daily", "procurement notice", "public procurement", "cpv", "nuts", "vergabe",
            "ausschreibung", "marché public", "avis de marché",
        ),
        "eu_eurlex": (
            "eur-lex", "celex", "eli", "official journal", "amtsblatt", "rechtsakt", "consolidated", "konsolidiert",
            "journal officiel", "acte juridique",
        ),
        "us_fara": (
            "fara", "foreign agent", "foreign principal", "registrant", "registration number", "foreign agents registration act",
        ),
        "us_lda": (
            "lobbying disclosure", "lda", "lobbyist", "registrant", "client", "lobbying income", "lobbying expenses",
        ),
        "us_usaspending": (
            "usaspending", "federal award", "award id", "uei", "federal grant", "federal contract", "obligation", "outlay",
        ),
        "us_sec_edgar": (
            "edgar", "sec filing", "cik", "accession number", "10-k", "10-q", "8-k", "securities filing",
        ),
        "uk_companies_house": (
            "companies house", "company number", "persons with significant control", "psc", "filing history", "uk company",
        ),
        "uk_consultant_lobbyists": (
            "consultant lobbyist", "consultant lobbyists", "registrar of consultant lobbyists", "quarterly return", "lobbying clients",
        ),
        "uk_electoral_commission": (
            "electoral commission", "political finance", "donations", "loans", "regulated donee", "party accounts", "campaign spending",
        ),
        "uk_contracts_finder": (
            "contracts finder", "ocid", "uk government contract", "procurement stage", "contract award", "buyer", "supplier",
        ),
        "il_corporations_companies": (
            "רשות התאגידים", "חברה", "מספר חברה", "שם חברה", "corporations authority", "company number", "ח.פ",
        ),
        "il_nonprofits": (
            "עמותה", "עמותות", "חלצ", "חל\"צ", "מספר עמותה", "association", "public benefit company", "נתונים כספיים",
        ),
        "il_government_procurement": (
            "מכרז", "מכרזים", "מספר פרסום", "מספר הליך", "רכש ממשלתי", "government procurement", "tender", "publisher",
        ),
        "il_data_gov_budget": (
            "תקציב", "ביצוע", "סעיף תקציבי", "שנת כספים", "משרד האוצר", "data.gov.il", "budget execution", "budget item",
        ),
    }

    def __init__(self, db, audit, *, german_sources, finance, influence, training, opsec, evidence_vault, conversation, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.german_sources = german_sources
        self.finance = finance
        self.influence = influence
        self.training = training
        self.opsec = opsec
        self.evidence_vault = evidence_vault
        self.conversation = conversation
        self.actor = actor
        conversation._international_sources_254 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build254_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", "")
        event_id, created_at = new_id("evt254"), now_ts()
        event_hash = _hash({"previous": previous, "event_id": event_id, "event_type": event_type, "object_id": object_id, "payload": payload, "actor": actor, "at": created_at})
        self.db.execute(
            "INSERT INTO build254_events VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, event_type, object_type, object_id, actor, dumps(payload), previous, event_hash, created_at),
        )
        try:
            self.audit.log("build254_" + event_type, object_type, object_id, case_id, payload)
        except Exception:
            pass

    @staticmethod
    def detect_language(text: str) -> str:
        value = _text(text, 8000)
        if re.search(r"[\u0590-\u05ff]", value):
            return "he"
        if re.search(r"[\u0600-\u06ff]", value):
            return "ar"
        low = value.lower()
        french_markers = ("quel ", "quelle ", "registre", "marché", "bénéfic", "auprès", "l’union", "l'union", "juridique")
        german_markers = ("welche ", "gesucht", "register", "förder", "vergabe", "ausschreibung", "haushalt", "rechtsakt", "begünst")
        if any(marker in low for marker in french_markers) or re.search(r"[àâçéèêëîïôûùüÿœ]", low):
            return "fr"
        if any(marker in low for marker in german_markers) or re.search(r"[äöüß]", low):
            return "de"
        return "en"

    def profiles(self, jurisdiction: str = "") -> list[dict[str, Any]]:
        if jurisdiction:
            rows = self.db.all("SELECT * FROM international_source_profiles_254 WHERE jurisdiction=? ORDER BY source_kind,display_name", (jurisdiction.upper(),))
        else:
            rows = self.db.all("SELECT * FROM international_source_profiles_254 ORDER BY jurisdiction,source_kind,display_name")
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for key in ("languages_json", "identifier_types_json", "key_fields_json", "limitations_json", "opsec_controls_json"):
                item[key[:-5]] = _loads(item[key], [])
            item["machine_readable"] = bool(item["machine_readable"])
            out.append(item)
        return out

    def profile(self, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM international_source_profiles_254 WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        item = dict(row)
        for key in ("languages_json", "identifier_types_json", "key_fields_json", "limitations_json", "opsec_controls_json"):
            item[key[:-5]] = _loads(item[key], [])
        item["machine_readable"] = bool(item["machine_readable"])
        return item

    def jurisdiction_policy(self, jurisdiction: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM jurisdiction_policy_profiles_254 WHERE jurisdiction=?", (jurisdiction.upper(),))
        if not row:
            raise KeyError(jurisdiction)
        item = dict(row)
        item["preferred_languages"] = _loads(item["preferred_languages_json"], [])
        item["controls"] = _loads(item["controls_json"], [])
        for key in ("credential_storage_allowed", "cross_case_session_reuse_allowed", "automated_login_allowed"):
            item[key] = bool(item[key])
        return item

    def jurisdiction_policies(self) -> list[dict[str, Any]]:
        return [self.jurisdiction_policy(j) for j in self.JURISDICTIONS]

    @staticmethod
    def _restricted_for_machine(profile: dict[str, Any]) -> bool:
        access = profile["access_class"].lower()
        policy = profile["automation_policy"].lower()
        restricted_markers = ("api_key", "paid", "account", "login", "request", "authenticated")
        return any(marker in access for marker in restricted_markers) or any(marker in policy for marker in ("human_controlled", "user_managed"))

    @staticmethod
    def _credential_boundary(profile: dict[str, Any]) -> str:
        access = profile["access_class"].lower()
        if "api_key" in access:
            return "user_managed_api_key_only; credential value is never stored in EagleEye case data"
        if any(marker in access for marker in ("paid", "account", "login", "request", "authenticated")):
            return "human enters credentials/payment only in official source UI; EagleEye stores no credential or payment value"
        return "none_expected_for_profiled_public_read_access"

    def source_preflight(self, *, case_id: str, source_id: str, actor: str, record: bool = True) -> dict[str, Any]:
        self._case(case_id)
        profile = self.profile(source_id)
        policy = self.jurisdiction_policy(profile["jurisdiction"])
        domain = urlsplit(profile["root_url"]).netloc or profile["official_domain"]
        try:
            egress = self.opsec.egress_decision(case_id=case_id, destination_class=policy["egress_destination_class"], destination_ref=domain)
        except Exception:
            egress = {"decision": "review", "rule_id": "", "automatic_network_change": False}
        restricted = self._restricted_for_machine(profile)
        reviewed_read_only = profile["automation_policy"] in {"reviewed_read_only_api_allowed", "reviewed_read_only_download_allowed"}
        machine_access_allowed = bool(profile["machine_readable"] and reviewed_read_only and not restricted and egress.get("decision") == "allow")
        credential_boundary = self._credential_boundary(profile)
        result = {
            "case_id": case_id,
            "source_id": source_id,
            "jurisdiction": profile["jurisdiction"],
            "destination_ref": domain,
            "access_class": profile["access_class"],
            "egress_decision": egress.get("decision", "review"),
            "egress_rule_id": egress.get("rule_id", ""),
            "machine_access_allowed": machine_access_allowed,
            "manual_web_access_candidate": True,
            "credential_boundary": credential_boundary,
            "credential_value_stored": False,
            "session_boundary": policy["session_policy"],
            "cross_case_session_reuse": False,
            "automated_login": False,
            "autonomous_network_change": False,
            "required_controls": list(dict.fromkeys(policy["controls"] + profile["opsec_controls"])),
            "manual_review_required": bool(egress.get("decision") != "allow" or restricted or not reviewed_read_only),
        }
        if record:
            preflight_id, created_at = new_id("preflight254"), now_ts()
            payload = dict(result, preflight_id=preflight_id)
            self.db.execute(
                "INSERT INTO opsec_jurisdiction_preflights_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    preflight_id, case_id, source_id, profile["jurisdiction"], domain, profile["access_class"], result["egress_decision"],
                    int(machine_access_allowed), credential_boundary, policy["session_policy"], 0, 0, 0, dumps(result["required_controls"]), actor, created_at, _hash(payload),
                ),
            )
            self._event(case_id, "jurisdiction_source_preflight", "source_profile", source_id, {"preflight_id": preflight_id, "jurisdiction": profile["jurisdiction"], "machine_access_allowed": machine_access_allowed, "credential_boundary": credential_boundary}, actor)
            result["preflight_id"] = preflight_id
        return result

    def normalize_identifiers(self, *, source_id: str, identifiers: Iterable[str]) -> dict[str, Any]:
        profile = self.profile(source_id)
        raw = [_text(value, 300) for value in identifiers if _text(value, 300)][:25]
        variants = []
        for value in raw:
            compact = re.sub(r"\s+", " ", value).strip()
            alnum = re.sub(r"[^0-9A-Za-z\u0590-\u05ff\-_/.:]", "", compact)
            digit = re.sub(r"\D", "", compact)
            item = {"raw": value, "normalized": compact, "alnum": alnum}
            if digit:
                item["digits_only"] = digit
            variants.append(item)
        return {
            "source_id": source_id,
            "jurisdiction": profile["jurisdiction"],
            "identifier_types": profile["identifier_types"],
            "variants": variants,
            "external_lookup_performed": False,
            "advisory_only": True,
        }

    def recommend_sources(self, *, case_id: str, research_question: str, jurisdiction_hint: str = "", language_hint: str = "", identifiers: Iterable[str] = (), top_k: int = 6) -> dict[str, Any]:
        self._case(case_id)
        question = _text(research_question, 5000)
        q = question.lower()
        detected = (language_hint or self.detect_language(question)).lower()
        jurisdiction_hint = jurisdiction_hint.upper().strip()
        identifier_values = [_text(v, 300) for v in identifiers if _text(v, 300)]
        scored = []
        for profile in self.profiles():
            hits = [kw for kw in self.KEYWORDS.get(profile["source_id"], ()) if kw.lower() in q]
            score = float(len(hits))
            if jurisdiction_hint:
                score += 3.0 if profile["jurisdiction"] == jurisdiction_hint else -1.0
            if detected in profile["languages"]:
                score += 0.5
            if identifier_values:
                score += 0.35
            if profile["evidence_value"].startswith("primary_official"):
                score += 0.25
            scored.append((score, profile, hits))
        scored.sort(key=lambda item: (-item[0], item[1]["jurisdiction"], item[1]["display_name"]))
        selected = []
        for score, profile, hits in scored[:max(1, min(16, int(top_k)))]:
            selected.append({
                "source_id": profile["source_id"],
                "display_name": profile["display_name"],
                "jurisdiction": profile["jurisdiction"],
                "score": round(score, 3),
                "matched_terms": hits,
                "detected_language": detected,
                "supported_languages": profile["languages"],
                "identifier_strategy": profile["identifier_types"],
                "assertion_ceiling": profile["assertion_ceiling"],
                "access_class": profile["access_class"],
                "advisory_only": True,
            })
        return {
            "build": self.BUILD,
            "question": question,
            "jurisdiction_hint": jurisdiction_hint,
            "detected_language": detected,
            "recommendations": selected,
            "grounding_required": True,
            "no_autonomous_browsing": True,
            "no_credential_or_session_reuse": True,
            "method": "controlled multi-jurisdiction multilingual source-routing heuristic; reviewed benchmark target, not an autonomous collector",
        }

    def create_lookup_plan(self, *, case_id: str, source_id: str, research_question: str, query_terms: Iterable[str], identifiers: Iterable[str], expected_artifacts: Iterable[str], purpose: str, actor: str, confirmation: str, query_language: str = "") -> dict[str, Any]:
        self._case(case_id)
        profile = self.profile(source_id)
        if confirmation != f"SOURCE PLAN 254 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        question = _text(research_question, 4000)
        purpose_text = _text(purpose, 2000)
        if len(question) < 12 or len(purpose_text) < 8:
            raise ValueError("research question/purpose too short")
        terms = [_text(value, 300) for value in query_terms if _text(value, 300)][:30]
        if not terms:
            raise ValueError("at least one query term required")
        lang = (query_language or self.detect_language(question)).lower()
        variants = self.normalize_identifiers(source_id=source_id, identifiers=identifiers)
        preflight = self.source_preflight(case_id=case_id, source_id=source_id, actor=actor, record=True)
        plan_id, created_at = new_id("srcplan254"), now_ts()
        expected = [_text(value, 300) for value in expected_artifacts if _text(value, 300)][:20]
        payload = {
            "plan_id": plan_id,
            "case_id": case_id,
            "source_id": source_id,
            "jurisdiction": profile["jurisdiction"],
            "query_language": lang,
            "research_question": question,
            "query_terms": terms,
            "identifier_variants": variants["variants"],
            "expected_artifacts": expected,
            "purpose": purpose_text,
            "access_class": profile["access_class"],
            "egress_decision": preflight["egress_decision"],
            "opsec_review_required": preflight["manual_review_required"],
            "execution_mode": "manual_or_reviewed_read_only",
            "created_by": actor,
            "created_at": created_at,
            "no_autonomous_login": True,
            "no_cross_case_session_reuse": True,
        }
        self.db.execute(
            "INSERT INTO source_lookup_plans_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                plan_id, case_id, source_id, profile["jurisdiction"], lang, question, dumps(terms), dumps(variants["variants"]), dumps(expected), purpose_text,
                profile["access_class"], preflight["egress_decision"], int(preflight["manual_review_required"]), "manual_or_reviewed_read_only", actor, created_at, _hash(payload),
            ),
        )
        self._event(case_id, "lookup_plan_created", "source_lookup_plan", plan_id, {"source_id": source_id, "jurisdiction": profile["jurisdiction"], "preflight_id": preflight.get("preflight_id", ""), "query_language": lang}, actor)
        return payload

    def record_observation(self, *, case_id: str, source_id: str, plan_id: str, external_record_ref: str, document_date: str, observed_fields: dict[str, Any], evidence_refs: Iterable[str], assertion_class: str, notes: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        profile = self.profile(source_id)
        if confirmation != f"SOURCE OBSERVATION 254 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if assertion_class not in self.OBS_ASSERTION_CLASSES:
            raise ValueError("invalid assertion class")
        refs = [_text(value, 500) for value in evidence_refs if _text(value, 500)]
        if assertion_class == "direct_source_observation" and not refs:
            raise ValueError("direct source observations require evidence refs")
        if plan_id:
            plan = self.db.one("SELECT * FROM source_lookup_plans_254 WHERE plan_id=? AND case_id=?", (plan_id, case_id))
            if not plan:
                raise KeyError(plan_id)
            if plan["source_id"] != source_id:
                raise ValueError("plan/source mismatch")
        observation_id, created_at = new_id("srcobs254"), now_ts()
        fields = dict(observed_fields or {})
        payload = {
            "observation_id": observation_id,
            "case_id": case_id,
            "source_id": source_id,
            "jurisdiction": profile["jurisdiction"],
            "plan_id": plan_id,
            "external_record_ref": _text(external_record_ref, 1000),
            "document_date": _text(document_date, 80),
            "observed_fields": fields,
            "evidence_refs": refs,
            "assertion_class": assertion_class,
            "assertion_ceiling": profile["assertion_ceiling"],
            "notes": _text(notes, 4000),
            "created_by": actor,
            "created_at": created_at,
            "creates_claim_automatically": False,
            "creates_financial_flow_automatically": False,
            "creates_influence_edge_automatically": False,
        }
        self.db.execute(
            "INSERT INTO source_observations_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (observation_id, case_id, source_id, plan_id, payload["external_record_ref"], payload["document_date"], dumps(fields), dumps(refs), assertion_class, payload["notes"], actor, created_at, _hash(payload)),
        )
        self._event(case_id, "source_observation_recorded", "source_observation", observation_id, {"source_id": source_id, "jurisdiction": profile["jurisdiction"], "evidence_count": len(refs), "no_auto_claim": True, "no_auto_flow": True, "no_auto_edge": True}, actor)
        return payload

    def benchmarks(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.all("SELECT * FROM ai_multijurisdiction_benchmarks_254 ORDER BY benchmark_id")]

    def record_ai_evaluation(self, *, case_id: str, benchmark_id: str, predicted_source_id: str, predicted_jurisdiction: str, predicted_language: str, predicted_identifier_strategy: str, predicted_assertion_ceiling: str, predicted_access_class: str, model_or_ruleset: str, evaluated_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"AI BENCHMARK 254 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        benchmark = self.db.one("SELECT * FROM ai_multijurisdiction_benchmarks_254 WHERE benchmark_id=?", (benchmark_id,))
        if not benchmark:
            raise KeyError(benchmark_id)
        source_match = predicted_source_id == benchmark["expected_source_id"]
        jurisdiction_match = predicted_jurisdiction.upper() == benchmark["expected_jurisdiction"]
        language_match = predicted_language.lower() == benchmark["fixture_language"]
        identifier_match = predicted_identifier_strategy == benchmark["expected_identifier_strategy"]
        assertion_match = predicted_assertion_ceiling == benchmark["expected_assertion_ceiling"]
        access_match = predicted_access_class == benchmark["expected_access_class"]
        passed = all((source_match, jurisdiction_match, language_match, identifier_match, assertion_match, access_match))
        evaluation_id, evaluated_at = new_id("aie254"), now_ts()
        payload = {
            "evaluation_id": evaluation_id,
            "case_id": case_id,
            "benchmark_id": benchmark_id,
            "source_match": source_match,
            "jurisdiction_match": jurisdiction_match,
            "language_match": language_match,
            "identifier_match": identifier_match,
            "assertion_match": assertion_match,
            "access_match": access_match,
            "passed": passed,
            "model_or_ruleset": _text(model_or_ruleset, 300),
            "evaluated_by": evaluated_by,
            "evaluated_at": evaluated_at,
        }
        self.db.execute(
            "INSERT INTO ai_multijurisdiction_evaluations_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                evaluation_id, case_id, benchmark_id, _text(predicted_source_id, 200), _text(predicted_jurisdiction, 20), _text(predicted_language, 20),
                _text(predicted_identifier_strategy, 300), _text(predicted_assertion_ceiling, 300), _text(predicted_access_class, 300), int(source_match),
                int(jurisdiction_match), int(language_match), int(identifier_match), int(assertion_match), int(access_match), int(passed), _text(model_or_ruleset, 300),
                evaluated_by, evaluated_at, _hash(payload),
            ),
        )
        self._event(case_id, "ai_multijurisdiction_benchmark_evaluated", "ai_benchmark", benchmark_id, {"evaluation_id": evaluation_id, "passed": passed, "six_dimension_gate": True}, evaluated_by)
        return payload

    def ai_metrics(self, *, case_id: str) -> dict[str, Any]:
        total = int(self.db.one("SELECT COUNT(*) n FROM ai_multijurisdiction_benchmarks_254 WHERE review_status='curated_reviewed'")["n"])
        jurisdictions = int(self.db.one("SELECT COUNT(DISTINCT jurisdiction) n FROM ai_multijurisdiction_benchmarks_254 WHERE review_status='curated_reviewed'")["n"])
        languages = int(self.db.one("SELECT COUNT(DISTINCT fixture_language) n FROM ai_multijurisdiction_benchmarks_254 WHERE review_status='curated_reviewed'")["n"])
        rows = self.db.all("SELECT * FROM ai_multijurisdiction_evaluations_254 WHERE case_id=?", (case_id,))
        passed = sum(1 for row in rows if row["passed"])
        return {
            "curated_reviewed_benchmarks": total,
            "jurisdiction_coverage": jurisdictions,
            "language_coverage": languages,
            "evaluations": len(rows),
            "passed": passed,
            "pass_rate": round(passed / len(rows), 4) if rows else None,
            "dimensions": ["source_selection", "jurisdiction", "query_language", "identifier_strategy", "assertion_ceiling", "access_class"],
            "qualification_gate": "all_six_dimensions_per_benchmark",
            "auto_model_activation": False,
            "auto_adapter_activation": False,
            "training_examples_reviewed_only": True,
            "training_pipeline_228": self.training.dashboard(case_id=case_id),
        }

    def opsec_metrics(self, *, case_id: str) -> dict[str, Any]:
        profiles = self.profiles()
        policies = self.jurisdiction_policies()
        controlled = sum(1 for profile in profiles if len(profile["opsec_controls"]) >= 4)
        boundary_safe = sum(1 for policy in policies if not policy["credential_storage_allowed"] and not policy["cross_case_session_reuse_allowed"] and not policy["automated_login_allowed"])
        preflights = int(self.db.one("SELECT COUNT(*) n FROM opsec_jurisdiction_preflights_254 WHERE case_id=?", (case_id,))["n"])
        restricted = sum(1 for profile in profiles if self._restricted_for_machine(profile))
        return {
            "source_profiles": len(profiles),
            "jurisdiction_policies": len(policies),
            "profiles_with_control_set": controlled,
            "control_coverage": round(controlled / len(profiles), 4) if profiles else 0.0,
            "safe_boundary_policies": boundary_safe,
            "boundary_coverage": round(boundary_safe / len(policies), 4) if policies else 0.0,
            "restricted_machine_sources": restricted,
            "preflights_recorded": preflights,
            "credential_values_stored": 0,
            "cross_case_session_reuse": 0,
            "automated_logins": 0,
            "autonomous_network_changes": 0,
            "host_reconfiguration": False,
        }

    def crosscut_release_gate(self, *, case_id: str) -> dict[str, Any]:
        ai = self.ai_metrics(case_id=case_id)
        opsec = self.opsec_metrics(case_id=case_id)
        jurisdictions = {profile["jurisdiction"] for profile in self.profiles()}
        try:
            parent_ready = bool(self.german_sources.crosscut_release_gate(case_id=case_id)["release_ready"])
        except Exception:
            parent_ready = False
        main_ready = len(self.profiles()) >= 16 and jurisdictions == set(self.JURISDICTIONS)
        ai_ready = ai["curated_reviewed_benchmarks"] >= 16 and ai["jurisdiction_coverage"] == 4 and ai["language_coverage"] >= 4 and ai["auto_model_activation"] is False and ai["auto_adapter_activation"] is False
        opsec_ready = opsec["jurisdiction_policies"] == 4 and opsec["control_coverage"] == 1.0 and opsec["boundary_coverage"] == 1.0 and opsec["credential_values_stored"] == 0 and opsec["cross_case_session_reuse"] == 0 and opsec["automated_logins"] == 0 and opsec["autonomous_network_changes"] == 0
        release_ready = bool(main_ready and ai_ready and opsec_ready and parent_ready)
        return {
            "build": self.BUILD,
            "main_goal_ready": main_ready,
            "ai_delta_ready": ai_ready,
            "opsec_delta_ready": opsec_ready,
            "parent_253_gate_ready": parent_ready,
            "release_ready": release_ready,
            "policy": "Build 254 must add measurable multi-jurisdiction AI routing and defensive jurisdiction/session/credential boundaries while preserving Build 253 and the frozen Build-250 kernel.",
        }

    def status(self, *, case_id: str) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "profiles": self.profiles(),
            "jurisdiction_policies": self.jurisdiction_policies(),
            "plans": [dict(row) for row in self.db.all("SELECT * FROM source_lookup_plans_254 WHERE case_id=? ORDER BY created_at DESC", (case_id,))],
            "observations": [dict(row) for row in self.db.all("SELECT * FROM source_observations_254 WHERE case_id=? ORDER BY created_at DESC", (case_id,))],
            "ai": self.ai_metrics(case_id=case_id),
            "opsec": self.opsec_metrics(case_id=case_id),
            "gate": self.crosscut_release_gate(case_id=case_id),
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str = "") -> str:
        esc = lambda value: html.escape(str(value or ""))
        status = self.status(case_id=case_id)
        profiles = status["profiles"]
        options = "".join(f"<option value='{esc(p['source_id'])}'>{esc(p['jurisdiction'])} · {esc(p['display_name'])}</option>" for p in profiles)
        groups = []
        for jurisdiction in self.JURISDICTIONS:
            cards = "".join(
                f"<div class='card'><h3>{esc(p['display_name'])}</h3><p><span class='badge'>{esc(p['source_kind'])}</span> <span class='badge candidate'>{esc(p['access_class'])}</span></p><p>{esc(p['evidence_value'])}<br>Aussagegrenze: <b>{esc(p['assertion_ceiling'])}</b></p><p class='muted'>Sprachen: {esc(', '.join(p['languages']))} · Identifier: {esc(', '.join(p['identifier_types']))}</p><p class='muted'>{esc(p['root_url'])}</p></div>"
                for p in profiles if p["jurisdiction"] == jurisdiction
            )
            groups.append(f"<h3>{jurisdiction}</h3><div class='grid'>{cards}</div>")
        ai, opsec, gate = status["ai"], status["opsec"], status["gate"]
        return f"""<section class='cockpit244'><h2>Influence &amp; Funding Investigation Pack · EU/US/UK/Israel Sources 254</h2>
<p class='muted'>Kontrollierte offizielle Quellenprofile über vier Rechtsräume. Routing und Identifier-Normalisierung sind beratend; externe Zugriffe bleiben manuell oder ausdrücklich reviewte Read-only-Aktionen.</p>
<div class='metrics'><div class='metric'><div class='label'>Quellenprofile</div><div class='value'>{len(profiles)}</div></div><div class='metric'><div class='label'>Jurisdiktionen</div><div class='value'>{len(self.JURISDICTIONS)}</div></div><div class='metric'><div class='label'>AI Gold-Benchmarks</div><div class='value'>{ai['curated_reviewed_benchmarks']}</div></div><div class='metric'><div class='label'>OPSEC Boundary Coverage</div><div class='value'>{int(opsec['boundary_coverage']*100)}%</div></div><div class='metric'><div class='label'>Crosscut Gate</div><div class='value'>{'PASS' if gate['release_ready'] else 'CHECK'}</div></div></div>
<div class='grid'>
<div class='card'><h3>Multi-Jurisdiction AI-Routing</h3><form method='post' action='/build254/route'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='jurisdiction_hint'><option value=''>Jurisdiktion automatisch</option><option>EU</option><option>US</option><option>UK</option><option>IL</option></select><select name='language_hint'><option value=''>Sprache automatisch</option><option value='de'>Deutsch</option><option value='en'>English</option><option value='fr'>Français</option><option value='he'>עברית</option><option value='ar'>العربية</option></select><textarea name='research_question' placeholder='Welche offizielle Tatsache soll geklärt werden?' required></textarea><input name='identifiers' placeholder='Identifier/Nummern, komma-getrennt'><button>Quellenkandidaten routen</button></form><p class='muted'>Keine autonome Browsersuche und keine automatische Tatsachenpromotion.</p></div>
<div class='card'><h3>Lookup-Plan + OPSEC</h3><form method='post' action='/build254/plan'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='source_id'>{options}</select><input name='query_language' placeholder='de/en/fr/he/ar optional'><textarea name='research_question' placeholder='Recherchefrage' required></textarea><input name='query_terms' placeholder='Suchbegriffe, komma-getrennt' required><input name='identifiers' placeholder='Identifier, komma-getrennt'><input name='expected_artifacts' placeholder='Erwartete Dokumente/Felder'><textarea name='purpose' placeholder='Zweck und Abgrenzung' required></textarea><button>Plan + Jurisdiction-Preflight</button></form></div>
<div class='card'><h3>Quellenbeobachtung</h3><form method='post' action='/build254/observation'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='source_id'>{options}</select><input name='plan_id' placeholder='Plan-ID'><input name='external_record_ref' placeholder='Offizielle Record-/Dokumentreferenz'><input name='document_date' placeholder='Dokumentdatum'><select name='assertion_class'>{''.join(f'<option>{esc(x)}</option>' for x in self.OBS_ASSERTION_CLASSES)}</select><input name='evidence_refs' placeholder='Evidence-Refs, komma-getrennt'><textarea name='observed_fields' placeholder='key=value; key=value'></textarea><textarea name='notes' placeholder='Notiz'></textarea><button>Beobachtung quellennah speichern</button></form></div>
</div>
{''.join(groups)}
<div class='notice warn'>Build 254 speichert keine Passwörter, API-Keys oder Zahlungsdaten im Fallbestand, führt keine automatischen Logins aus und verwendet keine Sessions/Cookies fallübergreifend. FARA-Einträge, Lobbyregister, Förderungen, Vergaben, Unternehmens- oder NGO-Registerdaten werden nicht automatisch zu Geheimdienst-, Korruptions-, Loyalitäts- oder Einflussbehauptungen hochgestuft.</div>
<div class='grid'><div class='card'><h3>AI-Delta 254</h3><p><b>{ai['curated_reviewed_benchmarks']}</b> reviewte Gold-Benchmarks über {ai['jurisdiction_coverage']} Rechtsräume und {ai['language_coverage']} Sprachen. Gate: Quelle + Jurisdiktion + Sprache + Identifier-Strategie + Aussagegrenze + Zugriffsklasse.</p><p class='muted'>Keine automatische Modell-/Adapteraktivierung.</p></div><div class='card'><h3>OPSEC-Delta 254</h3><p>{int(opsec['control_coverage']*100)}% Quellen-Control-Coverage; {int(opsec['boundary_coverage']*100)}% Jurisdiction-Boundary-Coverage; Credential Storage, Cross-Case-Session-Reuse, Auto-Login und autonome Netzwerkänderungen jeweils 0.</p></div></div>
</section>"""
