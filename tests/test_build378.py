from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app378 import create_workspace_app378
from eagleeye_pro.core.app_context import AppContext

PW = "Orbit-Pine-Quartz-378!"
SEED = "https://example.org/voice378-source"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test378")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin378", display_name="Admin 378", password=PW)
    return {**u, "session_id": "admin-session-378"}


def case(c, a):
    return c.build378.team_create_case(identity=a, title="Voice Validation Case", client="QA", purpose="authorized voice crawler validation", legal_basis="public_data")


def source(c, *, url=SEED, max_pages=1, name="Voice Source"):
    s = c.crawler_frontier_352.register_source(display_name=name, seed_urls=[url], terms_ref="public read-only terms", max_depth=0, max_pages=max_pages, requests_per_minute=5, max_response_bytes=100000)
    if s["review_status"] == "pending_review":
        s = c.crawler_frontier_352.review_source(s["source_id"], decision="approve_read_only", rationale="reviewed public source", reviewer="admin378")
    return s


def workflow(c, a, cid, sources, *, case_budget=80, source_budget=30, max_active=4):
    return c.build378.configure_case_workflow(
        case_id=cid,
        identity=a,
        source_budgets={s["source_id"]: source_budget for s in sources},
        case_request_budget=case_budget,
        max_active_crawls=max_active,
        confirmation="WORKFLOW",
    )


def preview(c, a, cid, sources, text="Starte Suche mit den ausgewählten Quellen"):
    return c.build378.voice_crawler_propose(case_id=cid, identity=a, transcript=text, source_ids=[s["source_id"] for s in sources])


def test_version(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build378.version_status() == {"runtime_build":"378.0","schema_version":"378.0","package_version":"378.0.0","coherent":True}


def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build378.phase16_status(); assert s["builds_completed"]==18 and s["crawler_improvement_build"]==378


def test_schema_no_new_tables(tmp_path):
    with ctx(tmp_path) as c:
        m=c.build378.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(165,133,8) and m["voice_validation_new_tables"]==0
        assert not any("378" in r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))


def test_voice_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build378.voice_status(); assert s["required_confirmation"]=="VOICE CRAWL" and not s["direct_network_authority"] and not s["source_auto_selection"] and not s["automatic_execution"]


def test_crawler_increment(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build378.crawler_status(); assert s["voice_to_crawler_intent_preview"] and s["voice_edit_reconfirmation"] and s["voice_preview_hash_provenance"] and not s["voice_direct_network_authority"]


def test_empty_transcript_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        with pytest.raises(ValueError): c.build378.voice_crawler_propose(case_id=cid,identity=a,transcript="",source_ids=[])


def test_explicit_source_selection_required(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        # Configure a workflow so the source-selection reason is isolated.
        s=source(c); workflow(c,a,cid,[s])
        p=c.build378.voice_crawler_propose(case_id=cid,identity=a,transcript="Starte Suche",source_ids=[])
        assert p["state"]=="blocked_preview" and "explicit_source_selection_required" in p["preview"]["block_reasons"]


def test_max_two_voice_sources(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        ss=[source(c,url=f"https://voice{i}.example.org/",name=f"S{i}") for i in range(3)]
        workflow(c,a,cid,ss)
        with pytest.raises(ValueError): preview(c,a,cid,ss)


def test_allowed_preview(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s])
        assert p["state"]=="confirmation_available" and p["preview"]["allowed_for_confirmation"] and p["preview"]["required_confirmation"]=="VOICE CRAWL"


def test_preview_hash_is_bound(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s])
        assert len(p["preview"]["preview_hash"])==64
        row=c.db.one("SELECT task_json FROM phase15_agent_tasks WHERE task_id=?",(p["intent_id"],)); task=json.loads(row["task_json"]); assert task["input_payload"]["preview_hash"]==p["preview"]["preview_hash"]


def test_preview_budget_visible(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c,max_pages=2); workflow(c,a,cid,[s],source_budget=20); p=preview(c,a,cid,[s])
        assert p["preview"]["estimated_max_requests"]==5 and p["preview"]["source_packets"][0]["remaining_workflow_requests"]==20


def test_wrong_confirmation_never_queues(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="CRAWL")
        assert out["state"]=="confirmation_required" and not out["executed"] and c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type='governed_crawl_v1'",(cid,))["c"]==0


def test_exact_confirmation_queues_via_workflow(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL")
        assert out["executed"] and out["state"]=="queued_via_case_workflow" and len(out["queued"])==1
        row=c.job_engine_348.get(out["queued"][0]["job_id"]); payload=json.loads(row["payload_json"]); assert payload["phase16_case_workflow_v374"] and payload["phase16_voice_crawler_v378"]


def test_voice_job_has_no_direct_network_authority(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL")
        payload=json.loads(c.job_engine_348.get(out["queued"][0]["job_id"])["payload_json"]); assert payload["voice_direct_network_authority"] is False and payload["voice_automatic_scope_expansion"] is False


def test_result_persisted(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL")
        results=c.kernel_task_repository_344.list_results(p["intent_id"]); assert results and results[-1]["status"]=="completed" and results[-1]["gateway_used"]=="search"


def test_interactions_include_result(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL")
        rows=c.build378.voice_crawler_interactions(case_id=cid); assert rows[0]["intent_id"]==p["intent_id"] and rows[0]["task_integrity_valid"] and rows[0]["results"]


def test_edit_transcript_requires_new_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL",edited_transcript="Starte Recherche mit ausgewählter Quelle")
        assert out["state"]=="reconfirmation_required_after_edit" and not out["executed"] and out["revised_intent"]["intent_id"]!=p["intent_id"]
        assert c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type='governed_crawl_v1'",(cid,))["c"]==0


def test_edit_source_requires_new_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s1=source(c,url="https://example.org/a"); s2=source(c,url="https://example.net/b"); workflow(c,a,cid,[s1,s2]); p=preview(c,a,cid,[s1]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL",source_ids=[s2["source_id"]])
        assert out["state"]=="reconfirmation_required_after_edit" and out["revised_intent"]["preview"]["selected_source_ids"]==[s2["source_id"]]


def test_paused_workflow_blocks_preview(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.build378.pause_case_workflow(case_id=cid,identity=a,reason="analyst review",confirmation="PAUSE"); p=preview(c,a,cid,[s])
        assert not p["preview"]["allowed_for_confirmation"] and any(x.startswith("workflow_not_active") for x in p["preview"]["block_reasons"])


def test_fresh_preflight_blocks_if_paused_after_preview(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); c.build378.pause_case_workflow(case_id=cid,identity=a,reason="pause before confirm",confirmation="PAUSE"); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL")
        assert out["state"]=="blocked_on_fresh_preflight" and not out["executed"]


def test_source_not_in_workflow_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s1=source(c,url="https://example.org/a"); s2=source(c,url="https://example.net/b"); workflow(c,a,cid,[s1]); p=preview(c,a,cid,[s2])
        assert any("source_not_in_case_workflow" in x for x in p["preview"]["block_reasons"])


def test_source_budget_block(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c,max_pages=4); workflow(c,a,cid,[s],source_budget=4); p=preview(c,a,cid,[s]); assert any("source_request_budget_exceeded" in x for x in p["preview"]["block_reasons"])


def test_case_budget_block(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c,max_pages=4); workflow(c,a,cid,[s],case_budget=4,source_budget=20); p=preview(c,a,cid,[s]); assert "case_request_budget_exceeded" in p["preview"]["block_reasons"]


def test_voice_request_budget_block(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s1=source(c,url="https://example.org/a",max_pages=14); s2=source(c,url="https://example.net/b",max_pages=14); workflow(c,a,cid,[s1,s2],case_budget=100,source_budget=50); p=preview(c,a,cid,[s1,s2]); assert "voice_request_budget_exceeded" in p["preview"]["block_reasons"]


def test_unreviewed_source_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.db.execute("UPDATE phase15_sources SET review_status='pending_review' WHERE source_id=?",(s["source_id"],)); p=preview(c,a,cid,[s]); assert any("source_not_approved_read_only" in x for x in p["preview"]["block_reasons"])


def test_disabled_source_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.db.execute("UPDATE phase15_crawler_policies SET enabled=0 WHERE source_id=?",(s["source_id"],)); p=preview(c,a,cid,[s]); assert any("source_disabled" in x for x in p["preview"]["block_reasons"])


def test_authenticated_source_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.db.execute("UPDATE phase15_crawler_policies SET auth_type='api_key' WHERE source_id=?",(s["source_id"],)); p=preview(c,a,cid,[s]); assert any("authenticated_source_requires_separate_manual_path" in x for x in p["preview"]["block_reasons"])


def test_onion_source_blocked_from_standard_voice_path(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.db.execute("UPDATE phase15_sources SET source_kind='darknet_onion', locator=? WHERE source_id=?",("http://"+"a"*56+".onion",s["source_id"])); p=preview(c,a,cid,[s]); assert any("tor_requires_separate_manual_gate" in x for x in p["preview"]["block_reasons"])


def test_connector_source_blocked_from_standard_voice_path(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); manifest=c.db.one("SELECT connector_key FROM phase15_connector_manifests LIMIT 1")
        if not manifest: pytest.skip("no connector manifest initialized")
        c.db.execute("INSERT OR REPLACE INTO phase15_connector_source_links(source_id,connector_key,identifier,created_at,record_hash) VALUES(?,?,?,?,?)",(s["source_id"],manifest["connector_key"],"fixture","2026-09-10T05:00:00+00:00","f"*64)); p=preview(c,a,cid,[s]); assert any("provider_connector_requires_separate_live_gate" in x for x in p["preview"]["block_reasons"])


def test_source_health_block(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.db.execute("UPDATE phase15_crawler_policies SET source_health='rate_limited' WHERE source_id=?",(s["source_id"],)); p=preview(c,a,cid,[s]); assert any("source_health_block:rate_limited" in x for x in p["preview"]["block_reasons"])


def test_push_to_talk_requires_human_start(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        with pytest.raises(PermissionError): c.build378.voice_crawler_transcribe(case_id=cid,identity=a,audio=b"abc",media_type="audio/wav",human_started=False,source_ids=[])


def test_push_to_talk_rejects_media_type(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        with pytest.raises(ValueError): c.build378.voice_crawler_transcribe(case_id=cid,identity=a,audio=b"abc",media_type="application/octet-stream",human_started=True,source_ids=[])


def test_push_to_talk_local_transcriber_no_audio_persistence(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); c.voice_gateway_358.transcriber=lambda audio,mt,lang:"Starte Suche mit ausgewählter Quelle"
        out=c.build378.voice_crawler_transcribe(case_id=cid,identity=a,audio=b"RIFFfixture",media_type="audio/wav",human_started=True,source_ids=[s["source_id"]])
        assert out["status"]=="transcribed" and out["audio_persisted"] is False and out["audio_deleted_after_transcription"] and not out["network_used_by_voice_gateway"] and out["preview"]["allowed_for_confirmation"]


def test_stt_runtime_missing_returns_manual_transcript(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        def missing(*_): raise RuntimeError("local_stt_model_not_configured")
        c.voice_gateway_358.transcriber=missing
        out=c.build378.voice_crawler_transcribe(case_id=cid,identity=a,audio=b"RIFFfixture",media_type="audio/wav",human_started=True,source_ids=[])
        assert out["requires_manual_transcript"] and not out["intent_created"] and out["audio_persisted"] is False


def test_ai_dossier_has_voice_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); preview(c,a,cid,[s]); out=c.build378.run_autonomous_investigation(case_id=cid,max_ticks=1)
        assert "phase16_voice_validation_v378" in out["dossier"] and out["direct_voice_network_authority"] is False


def test_opsec_detects_direct_network_claim(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL"); jid=out["queued"][0]["job_id"]
        row=c.job_engine_348.get(jid); payload=json.loads(row["payload_json"]); payload["voice_direct_network_authority"]=True; c.case_workflow_374._rehash_job(jid,payload=payload)
        o=c.build378.autonomous_opsec_protect(case_id=cid); assert any(v["job_id"]==jid and v["reason"]=="voice_direct_network_authority_claim" for v in o["voice_crawler_violations"]); assert jid in o["cancelled_voice_crawler_jobs"]


def test_opsec_detects_preview_hash_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); workflow(c,a,cid,[s]); p=preview(c,a,cid,[s]); out=c.build378.voice_crawler_confirm(intent_id=p["intent_id"],identity=a,confirmation="VOICE CRAWL"); jid=out["queued"][0]["job_id"]
        row=c.job_engine_348.get(jid); payload=json.loads(row["payload_json"]); payload["voice_preview_hash_v378"]="0"*64; c.case_workflow_374._rehash_job(jid,payload=payload)
        o=c.build378.autonomous_opsec_protect(case_id=cid); assert any(v["reason"]=="voice_preview_hash_mismatch" for v in o["voice_crawler_violations"])


def test_opsec_status_no_system_mutation(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_378.status(); assert not s["system_mutations"] and not s["firewall_mutation"] and not s["tor_configuration_mutation"] and s["voice_preview_hash_binding"]


def test_no_direct_network_imports_in_new_core(tmp_path):
    root=Path(__file__).parents[1]
    for rel in ["src/eagleeye/phase16/voice_live_validation378.py","src/eagleeye/application/build378/service.py"]:
        tree=ast.parse((root/rel).read_text()); imports={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}|{str(n.module or '').split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        assert not ({"requests","httpx","urllib","socket","ssl","subprocess"}&imports)


def test_health_reports_truthful_boundaries(tmp_path):
    app=create_workspace_app378(base_dir=tmp_path); client=TestClient(app); h=client.get("/health").json(); assert h["build"]=="378.0" and h["voice_live_validation"] and h["voice_direct_network_authority"] is False and h["external_voice_validation"]=="not_run"; app.state.context.close()


def test_web_unauthorized_voice_preview(tmp_path):
    app=create_workspace_app378(base_dir=tmp_path); client=TestClient(app); r=client.post("/api/cases/case-x/voice378/crawler-intent/preview",json={"transcript":"Starte Suche","source_ids":[]}); assert r.status_code==401; app.state.context.close()


def test_roadmap_marks_378_increment(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"CRAWLER_ROADMAP_BUILD_370_TO_380.md").read_text(encoding="utf-8").casefold(); assert "378" in t and "voice" in t and "crawler" in t


def test_masterplan_phase_progress(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text(encoding="utf-8"); assert "378" in t and ("18/20" in t or "18 of 20" in t)


def test_service_gate_has_no_literal_true(tmp_path):
    with ctx(tmp_path) as c: assert c.build378.active_gate_literal_true_lines()==[]
