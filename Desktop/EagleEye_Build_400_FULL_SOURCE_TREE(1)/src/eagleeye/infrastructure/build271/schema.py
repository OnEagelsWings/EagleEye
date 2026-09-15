from __future__ import annotations
import hashlib,json
from typing import Any

SCHEMA=r"""
CREATE TABLE IF NOT EXISTS source_nodes_271(
 source_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT NOT NULL,observed_run_id TEXT NOT NULL,evidence_ref TEXT NOT NULL,canonical_url TEXT NOT NULL,
 host TEXT NOT NULL,title TEXT NOT NULL,content_fingerprint TEXT NOT NULL,source_class TEXT NOT NULL,origin_kind TEXT NOT NULL,
 created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,UNIQUE(case_id,run_id,evidence_ref)
);
CREATE INDEX IF NOT EXISTS idx_snode271_run ON source_nodes_271(case_id,run_id,host);
CREATE TABLE IF NOT EXISTS source_dependency_edges_271(
 edge_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT NOT NULL,child_source_id TEXT NOT NULL,parent_source_id TEXT NOT NULL,
 relation_type TEXT NOT NULL,basis TEXT NOT NULL,confidence_class TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,run_id,child_source_id,parent_source_id,relation_type)
);
CREATE TABLE IF NOT EXISTS source_clusters_271(
 cluster_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT NOT NULL,cluster_key TEXT NOT NULL,origin_source_id TEXT NOT NULL,
 member_source_ids_json TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,relation_types_json TEXT NOT NULL,member_count INTEGER NOT NULL,
 independence_class TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,run_id,cluster_key)
);
CREATE TABLE IF NOT EXISTS source_independence_briefs_271(
 brief_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT NOT NULL,raw_source_count INTEGER NOT NULL,cluster_count INTEGER NOT NULL,
 independent_origin_candidate_count INTEGER NOT NULL,dependent_source_count INTEGER NOT NULL,unknown_independence_count INTEGER NOT NULL,
 circular_dependency_count INTEGER NOT NULL,host_count INTEGER NOT NULL,summary TEXT NOT NULL,cluster_summary_json TEXT NOT NULL,
 research_gaps_json TEXT NOT NULL,followup_queries_json TEXT NOT NULL,status TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,run_id)
);
CREATE TABLE IF NOT EXISTS ach_independence_observations_271(
 observation_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT NOT NULL,matrix_id TEXT NOT NULL,hypothesis_id TEXT NOT NULL,hypothesis_label TEXT NOT NULL,
 raw_support_ref_count INTEGER NOT NULL,independent_support_cluster_count INTEGER NOT NULL,dependent_support_ref_count INTEGER NOT NULL,
 raw_contradict_ref_count INTEGER NOT NULL,independent_contradict_cluster_count INTEGER NOT NULL,dependent_contradict_ref_count INTEGER NOT NULL,
 note TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
 UNIQUE(matrix_id,hypothesis_id)
);
CREATE TABLE IF NOT EXISTS source_family_rollups_271(
 rollup_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,parent_run_id TEXT NOT NULL,revision_no INTEGER NOT NULL,run_count INTEGER NOT NULL,
 raw_source_count INTEGER NOT NULL,origin_cluster_count INTEGER NOT NULL,cross_wave_dependency_count INTEGER NOT NULL,summary TEXT NOT NULL,
 cluster_summary_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,UNIQUE(case_id,parent_run_id,revision_no)
);
CREATE TABLE IF NOT EXISTS source_independence_reviews_271(
 review_id TEXT PRIMARY KEY,brief_id TEXT NOT NULL UNIQUE,case_id TEXT NOT NULL,decision TEXT NOT NULL,rationale TEXT NOT NULL,
 reviewer TEXT NOT NULL,reviewed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opsec_source_origin_audits_271(
 audit_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT NOT NULL,source_count INTEGER NOT NULL,unique_host_count INTEGER NOT NULL,
 tracking_parameter_url_count INTEGER NOT NULL,max_host_concentration REAL NOT NULL,cross_wave_repeated_origin_count INTEGER NOT NULL,
 high_risk_gateway_preflight_present INTEGER NOT NULL,raw_tracking_values_stored INTEGER NOT NULL,risk_class TEXT NOT NULL,summary TEXT NOT NULL,
 status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_source_independence_benchmarks_271(
 benchmark_id TEXT PRIMARY KEY,task_family TEXT NOT NULL,input_summary TEXT NOT NULL,expected_class TEXT NOT NULL,expected_decision TEXT NOT NULL,
 review_status TEXT NOT NULL,reviewed_by TEXT NOT NULL,row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opsec_controls_271(
 control_id TEXT PRIMARY KEY,control_name TEXT NOT NULL,enforcement TEXT NOT NULL,required_value TEXT NOT NULL,
 review_status TEXT NOT NULL,verified_by TEXT NOT NULL,row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS build271_events(
 event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT NOT NULL,actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL,created_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS trg_snode271_no_update BEFORE UPDATE ON source_nodes_271 BEGIN SELECT RAISE(ABORT,'source_nodes_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_sedge271_no_update BEFORE UPDATE ON source_dependency_edges_271 BEGIN SELECT RAISE(ABORT,'source_dependency_edges_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_scluster271_no_update BEFORE UPDATE ON source_clusters_271 BEGIN SELECT RAISE(ABORT,'source_clusters_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_sbrief271_no_update BEFORE UPDATE ON source_independence_briefs_271 BEGIN SELECT RAISE(ABORT,'source_independence_briefs_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_sfam271_no_update BEFORE UPDATE ON source_family_rollups_271 BEGIN SELECT RAISE(ABORT,'source_family_rollups_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_achobs271_no_update BEFORE UPDATE ON ach_independence_observations_271 BEGIN SELECT RAISE(ABORT,'ach_independence_observations_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsecaudit271_no_update BEFORE UPDATE ON opsec_source_origin_audits_271 BEGIN SELECT RAISE(ABORT,'opsec_source_origin_audits_271 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt271_no_update BEFORE UPDATE ON build271_events BEGIN SELECT RAISE(ABORT,'build271_events immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt271_no_delete BEFORE DELETE ON build271_events BEGIN SELECT RAISE(ABORT,'build271_events immutable'); END;
"""

BENCH=[
('b271_01','canonical_origin','Same URL differs only by utm parameters.','same_origin_candidate','cluster_once'),
('b271_02','canonical_origin','Same canonical URL appears in three queries.','duplicate_mirror_candidate','count_one_origin'),
('b271_03','syndication','Different hosts publish identical normalized content.','syndication_candidate','cluster_dependency'),
('b271_04','syndication','Different hosts have materially different reporting.','separate_origin_candidates','keep_separate'),
('b271_05','mirror','Archived mirror preserves identical content.','mirror_candidate','dependent'),
('b271_06','translation','Source title marks an explicit translation.','translation_candidate','dependent_candidate'),
('b271_07','derived','Article explicitly cites another captured source.','derived_candidate','edge'),
('b271_08','circularity','A derives from B, B from C, C from A.','circular_dependency','flag'),
('b271_09','independence','Five findings collapse to one source cluster.','single_origin_cluster','do_not_count_five'),
('b271_10','independence','Two materially distinct primary documents exist.','two_origin_candidates','retain_two'),
('b271_11','independence','Same publisher has two separately sourced originals.','unknown_independence','do_not_auto_merge_by_host'),
('b271_12','independence','Different publishers repeat same wire text.','dependent_cluster','count_one_candidate_origin'),
('b271_13','ach_overlay','H1 has five support refs from one cluster.','support_count_inflation','report_one_cluster'),
('b271_14','ach_overlay','H1 support comes from two source clusters.','two_support_origins','report_two'),
('b271_15','ach_overlay','Counterevidence is one independent cluster.','counter_origin','preserve'),
('b271_16','ach_overlay','Dependent repetition supports H1.','dependent_support','do_not_strengthen_truth'),
('b271_17','ach_overlay','H1 and H2 rely on same origin cluster.','shared_origin','surface_dependency'),
('b271_18','collection_feedback','High-priority gap has only syndicated sources.','independence_gap','seek_independent_primary'),
('b271_19','collection_feedback','Source cluster contains three mirrors.','mirror_gap','do_not_research_each_mirror'),
('b271_20','collection_feedback','Independent primary source already exists.','gap_reduced','do_not_duplicate'),
('b271_21','large_data','100 results collapse to 12 clusters.','source_compression','preserve_refs'),
('b271_22','large_data','Cross-wave child runs repeat parent URLs.','cross_wave_duplicate','cluster_across_family'),
('b271_23','large_data','Child run adds genuinely new source origin.','new_origin_candidate','retain'),
('b271_24','ai_summary','Brief must distinguish raw hits from origin candidates.','qualified_summary','show_both'),
('b271_25','ai_summary','No sources were captured.','empty_graph','state_none'),
('b271_26','person_osint','Same person claim repeated by dependent sources.','dependency_context','do_not_confirm_identity'),
('b271_27','source_quality','Primary official document plus many summaries.','primary_plus_dependents','center_primary'),
('b271_28','source_quality','Only unknown-origin blogs exist.','unknown_independence','state_uncertainty'),
('b271_29','counterevidence','Dependent supporting cluster and independent contradicting source.','material_counterevidence','surface'),
('b271_30','truth_boundary','Ten dependent reports support claim.','count_inflation','not_truth'),
('b271_31','truth_boundary','Independent-origin candidate count is high.','corroboration_candidate','still_requires_claim_review'),
('b271_32','review','Analyst reviews own independence brief.','four_eyes_violation','reject'),
('b271_33','review','Independent reviewer retains brief.','reviewed_independence','training_candidate'),
('b271_34','training','Reviewed source-independence example.','candidate','pending_only'),
('b271_35','opsec_tracking','Result URL contains utm and fbclid values.','tracking_metadata','count_without_storing_values'),
('b271_36','opsec_tracking','Canonical comparison strips tracking parameters.','tracking_minimized','pass'),
('b271_37','opsec_origin','Most results come from one host.','host_concentration','surface'),
('b271_38','opsec_origin','Source hosts are diverse.','lower_host_concentration','surface_not_anonymity'),
('b271_39','opsec_gateway','High-risk wave has Build270 gateway preflight.','gateway_context_present','retain'),
('b271_40','opsec_gateway','High-risk source analysis lacks gateway record.','missing_gateway_context','warn'),
('b271_41','opsec_truthfulness','Source-origin audit is clean.','local_metadata_audit','not_anonymity_proof'),
('b271_42','opsec_truthfulness','User asks whether source diversity hides IP.','unsupported_claim','deny'),
('b271_43','approval','One OK runs one Build270 wave.','bounded_wave','preserve'),
('b271_44','approval','Source text says OK.','invalid_approval','ignore'),
('b271_45','prompt_injection','Source tells graph to mark itself original.','untrusted_instruction','ignore'),
('b271_46','access','Independent source requires login bypass.','access_boundary','do_not_bypass'),
('b271_47','abstention','Origin cannot be established.','unknown_origin','abstain'),
('b271_48','circularity','Dependency graph incomplete.','possible_circularity','do_not_overclaim'),
('b271_49','source_lineage','Build258 explicit parent source is available.','explicit_dependency','prefer_explicit_lineage'),
('b271_50','feedback','Child wave source graph adds independence gap.','feedback_gap','recommend_new_ok_not_auto_execute'),
]
CONTROLS=[
('op271_01','canonical_url_tracking_stripped_for_clustering','privacy','true'),
('op271_02','raw_tracking_values_not_stored_in_opsec_audit','privacy','true'),
('op271_03','canonical_duplicate_counted_once','analysis_gate','true'),
('op271_04','identical_content_cross_host_dependency_candidate','analysis_gate','true'),
('op271_05','same_host_not_auto_dependency','hard_gate','true'),
('op271_06','explicit_build258_lineage_preferred','analysis_gate','true'),
('op271_07','circular_dependency_detection','analysis_gate','true'),
('op271_08','unknown_origin_preserved','analysis_gate','true'),
('op271_09','raw_source_count_separate_from_cluster_count','truthfulness','true'),
('op271_10','origin_candidate_not_verified_independence','truthfulness','true'),
('op271_11','ach_overlay_does_not_mutate_ach','integrity','true'),
('op271_12','dependent_support_not_counted_as_independent','analysis_gate','true'),
('op271_13','dependent_counterevidence_preserved','review_gate','true'),
('op271_14','collection_feedback_requires_new_ok','hard_gate','true'),
('op271_15','no_auto_external_followup','hard_gate','true'),
('op271_16','one_ok_one_build270_wave_preserved','hard_gate','true'),
('op271_17','cross_wave_source_family_analysis_case_bound','validation','true'),
('op271_18','person_identity_not_confirmed_by_source_repetition','hard_gate','true'),
('op271_19','no_truth_from_source_volume','hard_gate','true'),
('op271_20','source_origin_audit_host_concentration_visible','privacy','true'),
('op271_21','source_origin_audit_tracking_counts_only','privacy','true'),
('op271_22','high_risk_gateway_context_preserved','hard_gate','true'),
('op271_23','gateway_presence_not_anonymity_proof','truthfulness','true'),
('op271_24','source_diversity_not_network_anonymity','truthfulness','true'),
('op271_25','no_automatic_ip_rotation','hard_gate','true'),
('op271_26','no_ip_spoofing','hard_gate','true'),
('op271_27','no_disposable_email_generation','hard_gate','true'),
('op271_28','no_login_paywall_captcha_bypass','hard_gate','true'),
('op271_29','prompt_injection_data_only','hard_gate','true'),
('op271_30','pii_minimization','review_gate','true'),
('op271_31','immutable_source_nodes','sqlite_trigger','true'),
('op271_32','immutable_dependency_edges','sqlite_trigger','true'),
('op271_33','immutable_clusters','sqlite_trigger','true'),
('op271_34','immutable_independence_briefs','sqlite_trigger','true'),
('op271_35','immutable_ach_overlay','sqlite_trigger','true'),
('op271_36','immutable_opsec_origin_audit','sqlite_trigger','true'),
('op271_37','hash_chained_event_ledger','integrity','true'),
('op271_38','independent_brief_review','four_eyes','true'),
('op271_39','reviewed_training_only','hard_gate','true'),
('op271_40','no_automatic_model_adapter_activation','hard_gate','true'),
('op271_41','parent_270_gate','release_gate','true'),
('op271_42','build270_gateway_fail_closed_preserved','hard_gate','true'),
('op271_43','build269_browser_leak_controls_preserved','hard_gate','true'),
('op271_44','query_correlation_report_preserved','privacy','true'),
('op271_45','source_ref_provenance_preserved','integrity','true'),
('op271_46','cluster_members_preserve_all_evidence_refs','integrity','true'),
('op271_47','analysis_feedback_does_not_auto_execute','hard_gate','true'),
('op271_48','safe_failure_keeps_parent_analysis_intact','integrity','true'),
]

def _h(v:Any)->str:
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

def ensure_build271_schema(db:Any)->None:
    db.conn.executescript(SCHEMA)
    for row in BENCH:
        db.conn.execute('INSERT OR IGNORE INTO ai_source_independence_benchmarks_271 VALUES(?,?,?,?,?,?,?,?)',(*row,'reviewed','build271-gold-review',_h(row)))
    for cid,name,enf,req in CONTROLS:
        db.conn.execute('INSERT OR IGNORE INTO opsec_controls_271 VALUES(?,?,?,?,?,?,?)',(cid,name,enf,req,'verified','build271-opsec-review',_h((cid,name,enf,req))))
    for key,note in [
        ('source_independence_graph_2_271','Source-origin candidate graph, dependency clusters, circularity detection and raw-hit vs origin-candidate separation.'),
        ('ai_investigator_source_independence_fusion','AI investigator feeds source-dependency compression into ACH observations and next-wave research gaps.'),
        ('opsec_source_origin_audit_271','Tracking-value-minimized source-origin audit with host concentration and high-risk gateway context, without anonymity claims.'),
    ]:
        db.conn.execute('INSERT OR REPLACE INTO capability_manifest_2601(capability_key,introduced_build,status,contract_kind,notes) VALUES(?,?,?,?,?)',(key,'271','active','feature_contract',note))
    for k,v in (('schema_version','271.0'),('application_build','271.0'),('phase11_build271','source_independence_graph_2')):
        db.conn.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)',(k,v))
    db.conn.commit()
