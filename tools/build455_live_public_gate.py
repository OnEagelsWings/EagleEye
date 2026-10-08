from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request

from eagleeye_pro.core.app_context import AppContext

BASE = Path(".build455-live-qualification").resolve()
RESULT = Path("build455_live_result.json").resolve()
ADMIN_PASSWORD = "Build455AdminPassword!2026"
REVIEWER_PASSWORD = "Build455ReviewerPassword!2026"
FP_ADMIN = "build455-live-admin"
FP_REVIEWER = "build455-live-reviewer"


def login(ctx, username, password, fingerprint):
    issued = ctx.team_identity_359.authenticate(
        username=username, password=password, client_fingerprint=fingerprint
    )
    if issued is None:
        raise RuntimeError("authentication failed for " + username)
    ident = ctx.team_identity_359.validate_session(
        issued.token, client_fingerprint=fingerprint, touch=False
    )
    if ident is None:
        raise RuntimeError("session validation failed for " + username)
    return ident, issued


def setup_users(ctx):
    bootstrap = ctx.team_identity_359.create_initial_admin(
        username="admin455",
        display_name="Build 455 Administrator",
        password=ADMIN_PASSWORD,
    )
    ctx.team_governance_359.create_user(
        identity=bootstrap,
        username="reviewer455",
        display_name="Build 455 Independent Reviewer",
        global_role="reviewer",
        password=REVIEWER_PASSWORD,
    )
    admin, admin_session = login(ctx, "admin455", ADMIN_PASSWORD, FP_ADMIN)
    reviewer, reviewer_session = login(ctx, "reviewer455", REVIEWER_PASSWORD, FP_REVIEWER)
    return admin, reviewer, admin_session, reviewer_session


def complete_review(ctx, reviewer, request, decision, note):
    claimed = ctx.build449.claim_review_449(identity=reviewer, review_id=request["review_id"])
    if claimed["state"] != "claimed":
        raise RuntimeError("review could not be claimed")
    confirmation = {
        "evidence": "REVIEW EVIDENCE 447",
        "claim": "REVIEW CLAIM 447",
        "dossier": "APPROVE DOSSIER 447",
        "dossier_export": "APPROVE DOSSIER EXPORT 449",
    }[request["object_type"]]
    return ctx.build449.complete_review_449(
        identity=reviewer,
        review_id=request["review_id"],
        decision=decision,
        note=note,
        confirmation=confirmation,
    )


def external_surface(ctx, admin, case_id, *, name, base_url, target):
    host = urllib.parse.urlsplit(target).hostname
    source = ctx.build421.register_source(
        identity=admin,
        name=name,
        source_type="website",
        access_mode="public",
        base_url=base_url,
        capabilities=["public_pages", "build455_live_qualification"],
        coverage={"build455_real_source": True},
        license_note="Public source used only for bounded Build-455 operational qualification.",
    )
    task = ctx.crawler_core_425.create_task(
        identity=admin,
        case_id=case_id,
        source_id=source["source_id"],
        target=target,
        objective="Build 455 real-source operational research qualification",
        scope={"allowed_hosts": [host]},
        budget={"max_pages": 1, "max_bytes": 800000, "max_seconds": 25},
    )
    result = ctx.build442.validate_external_surface_task_442(
        identity=admin,
        task_id=task["task_id"],
        confirmation="VALIDATE442_EXTERNAL",
    )
    if result.get("result") != "PASS":
        raise RuntimeError("external surface validation did not pass for " + target)
    surface = result.get("surface") or {}
    if not surface.get("event_id") or not surface.get("content_id"):
        raise RuntimeError("external surface result is missing acquisition references")
    return {"source": source, "task": task, "result": result, "surface": surface}


def live_json_get(url):
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "EagleEye-Build455-Qualification/1.0",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if int(response.status) != 200:
            raise RuntimeError("provider returned HTTP " + str(response.status))
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise RuntimeError("provider response exceeded qualification byte limit")
        media = str(response.headers.get("content-type") or "application/json").split(";", 1)[0]
        final_url = response.geturl()
    if final_url != url:
        raise RuntimeError("qualification provider redirect not allowed")
    return body, media


def main():
    if BASE.exists():
        shutil.rmtree(BASE)
    if RESULT.exists():
        RESULT.unlink()

    with AppContext(base_dir=BASE) as ctx:
        admin, reviewer, _admin_session, reviewer_session = setup_users(ctx)

        qcase = ctx.build450.prepare_investigation_workflow_qualification_case_450(
            identity=admin, reviewer_username=reviewer["username"]
        )
        ctx.build450.consent_investigation_workflow_qualification_case_450(
            case_id=qcase["case_id"],
            confirmation="CONSENT BUILD 450 QUALIFICATION",
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        engineering = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=qcase["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        if engineering["engineering_result"] != "pass":
            raise RuntimeError("retained Build-450 governed workflow did not pass")

        case = ctx.team_governance_359.create_case(
            identity=admin,
            title="Build 455 Real Public Source Qualification",
            client="EagleEye internal qualification",
            purpose="Verify bounded public-source research from acquisition through reviewed export.",
            legal_basis="public_data",
        )
        case_id = case["case_id"]
        ctx.team_governance_359.assign_case_role(
            identity=admin,
            case_id=case_id,
            username=reviewer["username"],
            case_role="reviewer",
            notes="Independent Build-455 operational qualification reviewer.",
        )

        iana = external_surface(
            ctx, admin, case_id,
            name="IANA Example Domains Help",
            base_url="https://www.iana.org/",
            target="https://www.iana.org/help/example-domains",
        )
        example = external_surface(
            ctx, admin, case_id,
            name="Example.com Public Page",
            base_url="https://example.com/",
            target="https://example.com/",
        )

        sync = ctx.build447.sync_case_evidence_447(identity=admin, case_id=case_id)
        if int(sync.get("created") or 0) < 2:
            raise RuntimeError("real-source Evidence synchronization did not create two items")
        evidence = ctx.build447.case_evidence_447(case_id)
        by_event = {x["event_id"]: x for x in evidence}
        support = by_event[iana["surface"]["event_id"]]
        counter = by_event[example["surface"]["event_id"]]

        for item, note in (
            (support, "Independent review: official IANA source is accepted as support for the reserved-example-domain designation."),
            (counter, "Independent review: the live example.com page is accepted as counter/context showing that reserved example infrastructure is publicly served."),
        ):
            req = ctx.build449.request_review_449(
                identity=admin,
                object_type="evidence",
                object_id=item["evidence_id"],
                note="Build 455 independent real-source Evidence review.",
                assigned_to=reviewer["username"],
            )
            done = complete_review(ctx, reviewer, req, "accepted", note)
            if done["object"]["review_state"] != "accepted":
                raise RuntimeError("evidence review failed")

        claim = ctx.build447.propose_claim_447(
            identity=admin,
            case_id=case_id,
            statement=(
                "IANA designates example.com as a reserved example domain for documentation; "
                "its live public web presence should not be interpreted as evidence of ordinary registrability."
            ),
            support_evidence_ids=[support["evidence_id"]],
            contradiction_evidence_ids=[counter["evidence_id"]],
            uncertainty_note=(
                "The public example.com page demonstrates that the reserved domain is actively served; "
                "this qualifies the operational interpretation but does not negate the IANA reservation."
            ),
        )
        claim_req = ctx.build449.request_review_449(
            identity=admin,
            object_type="claim",
            object_id=claim["claim_id"],
            note="Build 455 independent claim review with explicit counterevidence.",
            assigned_to=reviewer["username"],
        )
        claim_done = complete_review(
            ctx, reviewer, claim_req, "accepted_for_dossier",
            "Claim is narrowly limited to the IANA designation and explicitly preserves the live-page counterevidence."
        )
        if claim_done["object"]["state"] != "accepted_for_dossier":
            raise RuntimeError("claim review failed")

        # Exercise Build 454 with a real public DNS provider response.
        infra_plan = ctx.infrastructure_454.plan_domain(
            identity=admin, case_id=case_id, domain="example.com"
        )
        dns_lookup = next(
            x for x in infra_plan["lookups"]
            if x["provider"] == "dns_google" and "type=A" in x["request_url"]
        )
        dns_body, dns_media = live_json_get(dns_lookup["request_url"])
        dns_source = ctx.build421.register_source(
            identity=admin,
            name="Google Public DNS Build 455",
            source_type="api",
            access_mode="public",
            base_url="https://dns.google/",
            capabilities=["public_dns", "build455_live_qualification"],
            coverage={"build455_real_source": True},
            license_note="Public DNS provider used for bounded Build-455 infrastructure qualification.",
        )
        dns_event = ctx.build422.record_event(
            identity=admin,
            case_id=case_id,
            source_id=dns_source["source_id"],
            target=dns_lookup["request_url"],
            method="api",
            status="retrieved",
            content_sha256=hashlib.sha256(dns_body).hexdigest(),
            media_type=dns_media,
            bytes_count=len(dns_body),
            provenance={"build": "455.0", "qualification_live_provider_fetch": True},
            usage={"public_only": True, "read_only": True},
        )
        dns_content = ctx.build423.ingest_content(
            identity=admin,
            event_id=dns_event["event_id"],
            content=dns_body,
            media_type=dns_media,
            metadata={"build455_live_provider": "dns.google"},
        )
        infra = ctx.infrastructure_454.import_payload(
            identity=admin,
            lookup_id=dns_lookup["lookup_id"],
            payload=dns_body.decode("utf-8"),
            event_id=dns_event["event_id"],
            content_id=dns_content["content_id"],
            source_ref=dns_lookup["request_url"],
        )
        if not any(x["fact_type"] in {"ip", "ipv6"} for x in infra["facts"]):
            raise RuntimeError("real public DNS import produced no address fact")

        ctx.entity_resolution_115.register_entity(
            case_id=case_id,
            entity_type="organisation",
            display_name="Build 455 Qualification Target",
            created_by=admin["username"],
            source_entity_id="build455:qualification-target",
            anchors=[{
                "type": "domain",
                "value": "example.com",
                "reliability": .95,
                "source_ref": "analyst:build455:bounded-target",
            }],
        )
        xref = ctx.xref_454.run_case(identity=admin, case_id=case_id)
        if int(xref.get("candidate_count") or 0) < 1:
            raise RuntimeError("Build-454 XRef integration produced no candidate")

        dossier = ctx.build447.build_dossier_447(
            identity=admin,
            case_id=case_id,
            title="Build 455 Real-Source Qualification Dossier",
        )
        dossier_req = ctx.build449.request_review_449(
            identity=admin,
            object_type="dossier",
            object_id=dossier["revision_id"],
            note="Build 455 independent real-source Dossier review.",
            assigned_to=reviewer["username"],
        )
        dossier_done = complete_review(
            ctx, reviewer, dossier_req, "approved_for_export",
            "Dossier preserves the reviewed public sources, counterevidence and uncertainty boundary."
        )
        if dossier_done["object"]["state"] != "approved_for_export":
            raise RuntimeError("dossier review failed")

        export_req = ctx.build449.request_review_449(
            identity=admin,
            object_type="dossier_export",
            object_id=dossier["revision_id"],
            note="Build 455 independent four-eyes export approval.",
            assigned_to=reviewer["username"],
        )
        export_done = complete_review(
            ctx, reviewer, export_req, "approve",
            "Independent reviewer approves the bounded qualification package; this is not a truth or production certification."
        )
        if export_done["review"]["decision"] != "approve":
            raise RuntimeError("export approval failed")
        exported = ctx.build449.execute_approved_export_449(
            identity=admin,
            review_id=export_req["review_id"],
            confirmation="EXPORT DOSSIER 447",
        )

        recovery = ctx.recovery_453.create_recovery_point(
            identity=admin,
            label="Build 455 before restart verification",
            confirmation="RECOVERY 453 CREATE",
        )

        qualified = ctx.build455.qualify_operational_research_case_455(
            identity=admin,
            case_id=case_id,
            support_evidence_id=support["evidence_id"],
            counter_evidence_id=counter["evidence_id"],
            claim_id=claim["claim_id"],
            revision_id=dossier["revision_id"],
            export_id=exported["export"]["export_id"],
            recovery_id=recovery["recovery_id"],
        )
        if qualified["live_case_result"] != "pass":
            raise RuntimeError("Build-455 live case did not pass before restart")
        qualification_id = qualified["qualification_id"]

    # Actual close/reopen boundary.
    with AppContext(base_dir=BASE) as ctx:
        admin, _session = login(ctx, "admin455", ADMIN_PASSWORD, FP_ADMIN)
        restart = ctx.build455.verify_operational_research_restart_455(
            identity=admin,
            qualification_id=qualification_id,
        )
        if restart["overall_result"] != "pass":
            raise RuntimeError("Build-455 restart/reference verification did not pass")
        status = ctx.build455.build455_status()
        if not status["operational_research_gate_pass"]:
            raise RuntimeError("Build-455 operational research gate status is not PASS")
        latest = ctx.build455.operational_research_latest_455()

    result = {
        "build": "455.0",
        "result": "PASS",
        "qualification_id": qualification_id,
        "case_id": case_id,
        "engineering_result": latest["engineering_result"],
        "live_case_result": latest["live_case_result"],
        "restart_result": latest["restart_result"],
        "overall_result": latest["overall_result"],
        "package_hash": latest["report"]["package_hash"],
        "support_url": latest["report"]["support_evidence"]["url"],
        "counterevidence_url": latest["report"]["counterevidence"]["url"],
        "infrastructure_fact_count": latest["report"]["infrastructure_fact_count"],
        "xref_candidate_count": latest["report"]["xref_candidate_count"],
        "all_connector_families_external_validation": latest["report"]["all_connector_families_external_validation"],
        "production_release_ready": False,
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"BUILD455_LIVE_GATE_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
