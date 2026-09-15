from __future__ import annotations

import hashlib
import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts

_TOKEN_RE = re.compile(r"[\w@.+-]{2,}", re.UNICODE)
_NEGATION_TERMS = {
    "nicht", "kein", "keine", "nie", "widerspruch", "falsch", "veraltet", "anders",
    "not", "no", "never", "contradiction", "false", "outdated", "different", "denied",
}
_PROMPT_INJECTION_RE = re.compile(
    r"(?i)(ignore (?:all|previous) instructions|system prompt|developer message|execute (?:this|the) tool|"
    r"do not cite|forget the evidence|überspringe .*anweisung|ignoriere .*anweisung|führe .*befehl aus)"
)


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 200_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _tokens(value: Any) -> list[str]:
    return [x.casefold() for x in _TOKEN_RE.findall(_text(value, 200_000))]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.0


def _canonical_url(value: str) -> str:
    raw = _text(value, 4000).strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return ""
        host = parts.hostname.casefold()
        port = parts.port
        netloc = host if not port or (parts.scheme == "https" and port == 443) or (parts.scheme == "http" and port == 80) else f"{host}:{port}"
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        return urlunsplit((parts.scheme.casefold(), netloc, path.rstrip("/") or "/", parts.query, ""))
    except Exception:
        return ""


def _parse_time(value: str) -> datetime | None:
    text = _text(value, 80).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


class Build225HybridInvestigativeRetrievalService:
    """Claim-centred, provenance-aware retrieval for the consolidated investigator.

    The service reranks the case memory by claim relevance, evidence stance,
    temporal fit, source quality and source-origin independence. It never treats
    duplicate reporting as independent confirmation and always attempts to include
    counter-evidence when available.
    """

    BUILD = "225.0"
    RETRIEVAL_MODE = "claim_centric_hybrid_v2"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        local_ai: Any,
        conversation: Any,
        workspace: Any,
        consolidation: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.local_ai, self.conversation = local_ai, conversation
        self.workspace, self.consolidation = workspace, consolidation
        self.actor = actor
        # Backward-compatible hook: Build 216 keeps its public API while using V2.
        self.conversation._retrieval_v2 = self

    # ---------- claims and provenance ----------
    def refresh_indexes(self, *, case_id: str, actor: str = "system") -> dict[str, Any]:
        self._case(case_id)
        base = self.conversation.index_case_sources(case_id=case_id, actor=actor)
        claims = self._sync_claims(case_id, actor)
        nodes, edges = self._sync_lineage(case_id, actor)
        self._event(case_id, "retrieval_indexes_refreshed", "case", case_id, {
            "memory_chunks": int(base.get("chunk_count") or 0), "claims": claims,
            "lineage_nodes": nodes, "inferred_edges": edges,
        }, actor)
        return {"case_id": case_id, "memory_chunks": int(base.get("chunk_count") or 0), "claims": claims, "lineage_nodes": nodes, "inferred_edges": edges}

    def create_claim(
        self,
        *,
        case_id: str,
        subject_ref: str,
        predicate: str,
        canonical_text: str,
        normalized_value: Any,
        language: str,
        claim_kind: str,
        confidence: float,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"CLAIM 225 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if claim_kind not in {"observation", "inference", "hypothesis", "question"}:
            raise ValueError("invalid claim kind")
        text = _text(canonical_text, 20_000).strip()
        if not text or not _text(predicate, 300).strip() or not _text(subject_ref, 500).strip():
            raise ValueError("subject, predicate and canonical text required")
        cid, now = new_id("claim225"), now_ts()
        payload = {
            "claim_id": cid, "case_id": case_id, "source_statement_id": "",
            "subject_ref": _text(subject_ref, 500), "predicate": _text(predicate, 300),
            "canonical_text": text, "normalized_value": normalized_value,
            "language": _text(language, 20) or "und", "claim_kind": claim_kind,
            "confidence": _clamp(confidence), "review_status": "candidate",
            "first_seen": now, "last_seen": now, "created_by": created_by,
            "created_at": now, "updated_at": now,
        }
        self.db.execute("INSERT INTO retrieval_claims_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            cid, case_id, "", payload["subject_ref"], payload["predicate"], text,
            dumps(normalized_value), payload["language"], claim_kind, payload["confidence"],
            "candidate", now, now, created_by, now, now, _hash(payload),
        ))
        self._event(case_id, "retrieval_claim_created", "claim", cid, {"predicate": payload["predicate"], "claim_kind": claim_kind}, created_by)
        return payload

    def link_evidence(
        self,
        *,
        claim_id: str,
        source_ref: str,
        source_type: str,
        stance: str,
        strength: float,
        temporal_relation: str,
        rationale: str,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        claim = self._claim(claim_id)
        if confirmation != f"CLAIM EVIDENCE 225 {claim_id} VERKNUEPFEN":
            raise PermissionError("explicit approval required")
        if stance not in {"supports", "contradicts", "context", "unknown"}:
            raise ValueError("invalid evidence stance")
        if temporal_relation not in {"current", "historical", "superseded", "unknown"}:
            raise ValueError("invalid temporal relation")
        valid = self.workspace._valid_refs(claim["case_id"], [source_ref])
        if valid != [source_ref]:
            raise ValueError("source reference is not valid in this case")
        node = self.db.one("SELECT node_id FROM source_lineage_nodes_225 WHERE case_id=? AND source_ref=? ORDER BY updated_at DESC LIMIT 1", (claim["case_id"], source_ref))
        lid, now = new_id("claimlink225"), now_ts()
        payload = {
            "link_id": lid, "case_id": claim["case_id"], "claim_id": claim_id,
            "source_ref": source_ref, "source_type": _text(source_type, 100),
            "lineage_node_id": (node or {}).get("node_id", ""), "stance": stance,
            "strength": _clamp(strength), "temporal_relation": temporal_relation,
            "rationale": _text(rationale, 5000), "review_status": "reviewed",
            "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            """INSERT INTO claim_evidence_links_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(case_id,claim_id,source_ref,stance) DO UPDATE SET strength=excluded.strength,temporal_relation=excluded.temporal_relation,rationale=excluded.rationale,review_status='reviewed',created_by=excluded.created_by,created_at=excluded.created_at,payload_sha256=excluded.payload_sha256""",
            (lid, claim["case_id"], claim_id, source_ref, payload["source_type"], payload["lineage_node_id"], stance, payload["strength"], temporal_relation, payload["rationale"], "reviewed", created_by, now, _hash(payload)),
        )
        self._event(claim["case_id"], "claim_evidence_linked", "claim", claim_id, {"source_ref": source_ref, "stance": stance, "strength": payload["strength"]}, created_by)
        return payload

    def add_lineage_edge(
        self,
        *,
        case_id: str,
        parent_node_id: str,
        child_node_id: str,
        relation_type: str,
        confidence: float,
        basis: str,
        reviewer: str,
        confirmation: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"SOURCE LINEAGE 225 {case_id} VERKNUEPFEN":
            raise PermissionError("explicit approval required")
        if relation_type not in {"direct_copy", "quotation", "summary", "derived", "same_origin", "independent", "unknown"}:
            raise ValueError("invalid lineage relation")
        if parent_node_id == child_node_id:
            raise ValueError("self lineage is not allowed")
        rows = self.db.all("SELECT node_id FROM source_lineage_nodes_225 WHERE case_id=? AND node_id IN (?,?)", (case_id, parent_node_id, child_node_id))
        if len(rows) != 2:
            raise ValueError("lineage nodes must belong to the case")
        eid, now = new_id("lineage225"), now_ts()
        payload = {"edge_id": eid, "case_id": case_id, "parent_node_id": parent_node_id, "child_node_id": child_node_id, "relation_type": relation_type, "confidence": _clamp(confidence), "basis": _text(basis, 5000), "review_status": "reviewed", "reviewed_by": reviewer, "created_by": reviewer, "created_at": now}
        self.db.execute(
            """INSERT INTO source_lineage_edges_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(case_id,parent_node_id,child_node_id,relation_type) DO UPDATE SET confidence=excluded.confidence,basis=excluded.basis,review_status='reviewed',reviewed_by=excluded.reviewed_by,payload_sha256=excluded.payload_sha256""",
            (eid, case_id, parent_node_id, child_node_id, relation_type, payload["confidence"], payload["basis"], "reviewed", reviewer, reviewer, now, _hash(payload)),
        )
        self._event(case_id, "source_lineage_reviewed", "lineage_edge", eid, {"relation_type": relation_type, "confidence": payload["confidence"]}, reviewer)
        return payload

    # ---------- canonical V2 retrieval ----------
    def retrieve(
        self,
        *,
        case_id: str,
        session_id: str,
        query_text: str,
        query_language: str,
        limit: int = 12,
        target_claim_id: str = "",
    ) -> dict[str, Any]:
        session = self.conversation._session(session_id)
        if session["case_id"] != case_id:
            raise ValueError("session and case mismatch")
        query = _text(query_text, 30_000).strip()
        if not query:
            raise ValueError("query required")
        if _PROMPT_INJECTION_RE.search(query):
            # User questions may discuss prompt injection, but are not allowed to alter retrieval policy.
            query = _PROMPT_INJECTION_RE.sub("[UNTRUSTED_INSTRUCTION_REMOVED]", query)
        config = self.consolidation.ensure_case_config(case_id=case_id, actor="retrieval225")
        effective_limit = max(3, min(int(limit), int(config.get("max_retrieval_chunks") or 12), 24))
        self.refresh_indexes(case_id=case_id, actor="retrieval225")

        claims = self.db.all("SELECT * FROM retrieval_claims_225 WHERE case_id=? AND review_status NOT IN ('rejected','superseded') ORDER BY updated_at DESC", (case_id,))
        claim = self._select_claim(claims, query, target_claim_id)
        claim_id = (claim or {}).get("claim_id", "")
        claim_terms = set(_tokens(" ".join([
            (claim or {}).get("subject_ref", ""), (claim or {}).get("predicate", ""),
            (claim or {}).get("canonical_text", ""),
        ])))
        query_terms = _tokens(query)
        qset = set(query_terms) | claim_terms
        chunks = self.db.all("SELECT * FROM ai_memory_chunks_216 WHERE case_id=? AND status='active' ORDER BY created_at", (case_id,))
        if not chunks:
            return self._store_empty_run(session_id, case_id, claim_id, query, query_language)

        explicit_links: dict[str, dict[str, Any]] = {}
        if claim_id:
            for row in self.db.all("SELECT * FROM claim_evidence_links_225 WHERE case_id=? AND claim_id=? AND review_status<>'rejected'", (case_id, claim_id)):
                explicit_links[row["source_ref"]] = row
        lineage = {row["source_ref"]: row for row in self.db.all("SELECT * FROM source_lineage_nodes_225 WHERE case_id=? AND status='active'", (case_id,))}
        group_sizes = Counter((lineage.get(row["source_ref"]) or {}).get("independence_group") or row["independence_key"] for row in chunks)
        embedding_model, query_vector = self._query_embedding(session, query)

        doc_sets = [set(_loads(row.get("lexical_terms_json"), [])) for row in chunks]
        df = Counter(term for terms in doc_sets for term in terms)
        n = max(1, len(chunks))
        scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
        for row, terms_set in zip(chunks, doc_sets):
            terms = _loads(row.get("lexical_terms_json"), [])
            tf = Counter(terms)
            lexical_raw = 0.0
            matched: list[str] = []
            for term in qset:
                if term in tf:
                    idf = math.log(1.0 + (n + 1) / (1 + df[term]))
                    lexical_raw += idf * (1.0 + math.log(tf[term]))
                    matched.append(term)
            lexical = lexical_raw / (lexical_raw + 3.0) if lexical_raw > 0 else 0.0
            semantic: float | None = None
            if query_vector and row.get("embedding_model") == embedding_model:
                vec = [float(x) for x in _loads(row.get("embedding_json"), [])]
                if vec and len(vec) == len(query_vector):
                    dot = sum(a * b for a, b in zip(query_vector, vec))
                    qn = math.sqrt(sum(x * x for x in query_vector))
                    vn = math.sqrt(sum(x * x for x in vec))
                    semantic = dot / (qn * vn) if qn and vn else 0.0
            if lexical <= 0 and (semantic is None or semantic < 0.10):
                continue

            content_terms = set(terms)
            entity_score = len(claim_terms & content_terms) / max(1, len(claim_terms)) if claim_terms else len(set(query_terms) & content_terms) / max(1, len(set(query_terms)))
            temporal_score, temporal_relation = self._temporal_score(claim, row.get("observed_at", ""))
            quality = _clamp(row.get("quality_score") or 0.5)
            node = lineage.get(row["source_ref"], {})
            group = node.get("independence_group") or row["independence_key"]
            group_size = max(1, group_sizes[group])
            independence = 1.0 / math.sqrt(group_size)
            lineage_penalty = max(0.0, 1.0 - independence)
            link = explicit_links.get(row["source_ref"])
            stance = (link or {}).get("stance") or ("contradicts" if int(row.get("contradiction_signal") or 0) else "context")
            stance_strength = _clamp((link or {}).get("strength") or (0.65 if stance == "contradicts" else 0.45))
            contradiction_bonus = 0.13 * stance_strength if stance == "contradicts" else 0.07 * stance_strength if stance == "supports" else 0.0
            semantic_value = max(0.0, semantic or 0.0)
            final = (
                0.29 * lexical + 0.20 * semantic_value + 0.16 * entity_score +
                0.10 * temporal_score + 0.15 * quality + 0.10 * independence +
                contradiction_bonus - 0.08 * lineage_penalty
            )
            if any(term in _NEGATION_TERMS for term in content_terms) and claim_id:
                final += 0.025
            details = {
                "lexical_score": lexical, "semantic_score": semantic,
                "entity_score": entity_score, "temporal_score": temporal_score,
                "temporal_relation": temporal_relation, "quality_score": quality,
                "independence_score": independence, "lineage_penalty": lineage_penalty,
                "contradiction_bonus": contradiction_bonus, "matched_terms": sorted(set(matched)),
                "stance": stance, "stance_strength": stance_strength,
                "independence_group": group, "origin_key": node.get("origin_key", ""),
            }
            scored.append((max(0.0, final), row, details))
        scored.sort(key=lambda item: (-item[0], -item[2]["quality_score"], item[1]["source_ref"]))

        selected: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
        per_type: Counter[str] = Counter()
        per_group: Counter[str] = Counter()
        for item in scored:
            row, detail = item[1], item[2]
            if per_type[row["source_type"]] >= 4 or per_group[detail["independence_group"]] >= 1:
                continue
            selected.append(item)
            per_type[row["source_type"]] += 1
            per_group[detail["independence_group"]] += 1
            if len(selected) >= effective_limit:
                break
        selected = self._ensure_stance(selected, scored, "supports", effective_limit)
        selected = self._ensure_stance(selected, scored, "contradicts", effective_limit)
        selected.sort(key=lambda item: (-item[0], item[1]["source_ref"]))

        refs = [row["source_ref"] for _, row, _ in selected]
        supports = [row["source_ref"] for _, row, d in selected if d["stance"] == "supports"]
        contradicts = [row["source_ref"] for _, row, d in selected if d["stance"] == "contradicts"]
        contexts = [row["source_ref"] for _, row, d in selected if d["stance"] not in {"supports", "contradicts"}]
        groups = [d["independence_group"] for _, _, d in selected]
        source_diversity = len({row["source_type"] for _, row, _ in selected}) / max(1, len(selected))
        lineage_diversity = len(set(groups)) / max(1, len(groups))
        run_id, created = new_id("retrieval225"), now_ts()
        score_details = {row["source_ref"]: {"final_score": score, **detail} for score, row, detail in selected}
        payload = {
            "retrieval_run_id": run_id, "session_id": session_id, "case_id": case_id,
            "target_claim_id": claim_id, "query_text": query, "query_language": query_language,
            "retrieval_mode": self.RETRIEVAL_MODE, "selected_refs": refs,
            "supporting_refs": supports, "contradicting_refs": contradicts,
            "context_refs": contexts, "score_details": score_details,
            "source_diversity": source_diversity, "lineage_diversity": lineage_diversity,
            "counterevidence_included": bool(contradicts), "candidate_count": len(scored),
            "selected_count": len(selected), "created_at": created,
        }
        self.db.execute("INSERT INTO retrieval_runs_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            run_id, session_id, case_id, claim_id, query, query_language, self.RETRIEVAL_MODE,
            dumps(refs), dumps(supports), dumps(contradicts), dumps(contexts), dumps(score_details),
            source_diversity, lineage_diversity, int(bool(contradicts)), len(scored), len(selected), created, _hash(payload),
        ))
        selected_ref_set = set(refs)
        for rank, (score, row, detail) in enumerate(scored, start=1):
            rid = new_id("retrievalresult225")
            result_payload = {"result_id": rid, "retrieval_run_id": run_id, "source_ref": row["source_ref"], "rank": rank, "selected": row["source_ref"] in selected_ref_set, **detail}
            self.db.execute("INSERT INTO retrieval_results_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                rid, run_id, case_id, row["source_ref"], row["source_type"], detail["stance"], score,
                detail["lexical_score"], detail["semantic_score"], detail["entity_score"], detail["temporal_score"],
                detail["quality_score"], detail["independence_score"], detail["lineage_penalty"], detail["contradiction_bonus"],
                rank, int(row["source_ref"] in selected_ref_set), dumps(detail), created, _hash(result_payload),
            ))

        selected_chunks = []
        for score, row, detail in selected:
            metadata = _loads(row.get("metadata_json"), {})
            metadata.update({
                "retrieval225": {"final_score": score, **detail},
                "target_claim_id": claim_id,
                "counterevidence": detail["stance"] == "contradicts",
                "prompt_injection_signal": bool(_PROMPT_INJECTION_RE.search(_text(row.get("content"), 30_000))),
            })
            selected_chunks.append({
                "source_ref": row["source_ref"], "source_type": row["source_type"],
                "title": row["title"], "content": _text(row["content"], 12_000),
                "language": row["language"], "quality_score": row["quality_score"],
                "observed_at": row["observed_at"], "contradiction_signal": detail["stance"] == "contradicts",
                "stance": detail["stance"], "metadata": metadata,
            })
        self._event(case_id, "claim_centric_retrieval_completed", "retrieval_run", run_id, {
            "target_claim_id": claim_id, "selected_count": len(selected), "candidate_count": len(scored),
            "counterevidence_included": bool(contradicts), "lineage_diversity": lineage_diversity,
        }, self.actor)
        return {
            **payload, "selected_chunks": selected_chunks,
            "contradiction_included": bool(contradicts),
            "source_type_counts": dict(Counter(row["source_type"] for _, row, _ in selected)),
            "claim": self._public_claim(claim) if claim else None,
            "claim_centric": True, "human_review_required": True,
        }

    def review_retrieval(
        self,
        *,
        retrieval_run_id: str,
        decision: str,
        correct_refs: Sequence[str],
        missing_refs: Sequence[str],
        wrongly_ranked_refs: Sequence[str],
        rationale: str,
        reviewer: str,
        confirmation: str,
    ) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM retrieval_runs_225 WHERE retrieval_run_id=?", (retrieval_run_id,))
        if not run:
            raise KeyError(retrieval_run_id)
        if confirmation != f"RETRIEVAL REVIEW 225 {retrieval_run_id} FREIGEBEN":
            raise PermissionError("explicit approval required")
        if decision not in {"useful", "partially_useful", "misleading", "insufficient"}:
            raise ValueError("invalid review decision")
        all_refs = list(dict.fromkeys([*correct_refs, *missing_refs, *wrongly_ranked_refs]))
        valid = self.workspace._valid_refs(run["case_id"], all_refs)
        if set(valid) != set(all_refs):
            raise ValueError("all review references must belong to the case")
        selected = _loads(run["selected_refs_json"], [])
        training = self.conversation.create_training_example(
            case_id=run["case_id"], task_type="contradiction_analysis" if _loads(run["contradicting_refs_json"], []) else "evidence_analysis",
            language=run["query_language"], difficulty="retrieval_review",
            input_payload={"query": run["query_text"], "target_claim_id": run["target_claim_id"], "selected_refs": selected},
            expected_output={"decision": decision, "correct_refs": list(correct_refs), "missing_refs": list(missing_refs), "wrongly_ranked_refs": list(wrongly_ranked_refs)},
            evidence_refs=list(dict.fromkeys([*selected, *missing_refs])),
            negative_constraints=["do not count copied sources as independent", "retrieve counter-evidence", "do not cite another case", "do not treat a hypothesis as an observation"],
            label="human_claim_retrieval_review", rationale=_text(rationale, 5000), created_by=reviewer,
            confirmation=f"TRAINING EXAMPLE 216 {run['case_id']} ANLEGEN",
        )
        review_id, now = new_id("retrievalreview225"), now_ts()
        payload = {"review_id": review_id, "retrieval_run_id": retrieval_run_id, "case_id": run["case_id"], "decision": decision, "correct_refs": list(correct_refs), "missing_refs": list(missing_refs), "wrongly_ranked_refs": list(wrongly_ranked_refs), "rationale": _text(rationale, 5000), "training_example_id": training["example_id"], "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO retrieval_reviews_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            review_id, retrieval_run_id, run["case_id"], decision, dumps(list(correct_refs)), dumps(list(missing_refs)), dumps(list(wrongly_ranked_refs)), payload["rationale"], training["example_id"], reviewer, now, _hash(payload),
        ))
        self._event(run["case_id"], "claim_retrieval_reviewed", "retrieval_run", retrieval_run_id, {"decision": decision, "training_example_id": training["example_id"]}, reviewer)
        return payload

    # ---------- workspace ----------
    def workspace_data(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        return {
            "claims": self.db.all("SELECT * FROM retrieval_claims_225 WHERE case_id=? ORDER BY updated_at DESC LIMIT 30", (case_id,)),
            "runs": self.db.all("SELECT * FROM retrieval_runs_225 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "nodes": self.db.all("SELECT * FROM source_lineage_nodes_225 WHERE case_id=? ORDER BY updated_at DESC LIMIT 40", (case_id,)),
            "edges": self.db.all("SELECT * FROM source_lineage_edges_225 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)),
            "reviews": self.db.all("SELECT * FROM retrieval_reviews_225 WHERE case_id=? ORDER BY reviewed_at DESC LIMIT 20", (case_id,)),
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.workspace_data(case_id)
        esc = lambda value: html.escape(str(value if value is not None else ""), quote=True)
        claims = "".join(
            f"<tr><td>{esc(r['predicate'])}</td><td>{esc(_text(r['canonical_text'],180))}</td><td>{esc(r['claim_kind'])}</td><td>{esc(r['review_status'])}</td><td><code>{esc(r['claim_id'])}</code></td></tr>"
            for r in data["claims"]
        ) or "<tr><td colspan='5'>Noch keine Claims indexiert.</td></tr>"
        runs = "".join(
            f"<tr><td>{esc(_text(r['query_text'],180))}</td><td>{esc(r['selected_count'])}</td><td>{esc(bool(r['counterevidence_included']))}</td><td>{esc(round(float(r['lineage_diversity']),2))}</td><td><code>{esc(r['retrieval_run_id'])}</code></td></tr>"
            for r in data["runs"]
        ) or "<tr><td colspan='5'>Noch keine V2-Retrievalläufe.</td></tr>"
        return f"""
<section class='card' id='build225_retrieval'>
<h2>Fallarbeitsraum 225 · Hybrid Investigative Retrieval 2.0</h2>
<p>Claim-zentrierte Suche mit Quellenursprung, Gegenbelegen, zeitlicher Einordnung und unabhängiger Quellengewichtung. Dieselbe Retrieval-Schicht versorgt den lokalen AI-Chat.</p>
<div class='grid'>
<div class='card'><h3>Claims und Herkunft aktualisieren</h3><form method='post' action='/build225/index-refresh'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Fallindex 225 aktualisieren</button></form><p>{len(data['claims'])} Claims · {len(data['nodes'])} Herkunftsknoten · {len(data['edges'])} Kanten</p></div>
<div class='card'><h3>Claim anlegen</h3><form method='post' action='/build225/claim-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='subject_ref' placeholder='Person/Entität' required><input name='predicate' placeholder='Behauptungstyp' required><textarea name='canonical_text' rows='4' placeholder='Prüfbare Behauptung oder Frage' required></textarea><input name='language' value='de'><select name='claim_kind'><option>observation</option><option>inference</option><option>hypothesis</option><option>question</option></select><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><button>Claim als Kandidat sichern</button></form></div>
<div class='card'><h3>Claim-zentrierte Suche</h3><form method='post' action='/build225/retrieve'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Build-216-Session-ID' required><input name='target_claim_id' placeholder='Claim-ID optional'><input name='query_language' value='de'><textarea name='query_text' rows='4' placeholder='Welche Belege stützen oder widerlegen die Behauptung?' required></textarea><button>Hybrid Retrieval starten</button></form></div>
<div class='card'><h3>Retrieval bewerten</h3><form method='post' action='/build225/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='retrieval_run_id' placeholder='Retrieval-Run-ID' required><select name='decision'><option>useful</option><option>partially_useful</option><option>misleading</option><option>insufficient</option></select><input name='correct_refs' placeholder='Korrekte IDs, kommagetrennt'><input name='missing_refs' placeholder='Fehlende IDs, kommagetrennt'><input name='wrongly_ranked_refs' placeholder='Falsch priorisierte IDs'><textarea name='rationale' rows='3' placeholder='Begründung' required></textarea><button>Review und Trainingssignal speichern</button></form></div>
</div>
<h3>Aktive Claims</h3><div class='table-wrap'><table><thead><tr><th>Prädikat</th><th>Claim</th><th>Art</th><th>Status</th><th>ID</th></tr></thead><tbody>{claims}</tbody></table></div>
<h3>Letzte Retrievalläufe</h3><div class='table-wrap'><table><thead><tr><th>Frage</th><th>Auswahl</th><th>Gegenbeleg</th><th>Herkunftsdiversität</th><th>ID</th></tr></thead><tbody>{runs}</tbody></table></div>
</section>
"""

    # ---------- internals ----------
    def _sync_claims(self, case_id: str, actor: str) -> int:
        now = now_ts()
        count = 0
        for row in self.db.all("SELECT * FROM evidence_statements_211 WHERE case_id=? ORDER BY created_at", (case_id,)):
            canonical = f"{row['entity_ref']} · {row['predicate']}: {row.get('original_value') or row.get('value_json')}"
            claim_id = "claim225_stmt_" + row["statement_id"]
            payload = {"claim_id": claim_id, "case_id": case_id, "source_statement_id": row["statement_id"], "subject_ref": row["entity_ref"], "predicate": row["predicate"], "canonical_text": canonical, "normalized_value": _loads(row["value_json"], row["value_json"]), "language": row.get("value_language") or "und", "claim_kind": row["statement_kind"], "confidence": _clamp(row["confidence"]), "review_status": row["review_status"], "first_seen": row["first_seen"], "last_seen": row["last_seen"], "created_by": row["created_by"], "created_at": row["created_at"], "updated_at": now}
            self.db.execute(
                """INSERT INTO retrieval_claims_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(claim_id) DO UPDATE SET canonical_text=excluded.canonical_text,normalized_value_json=excluded.normalized_value_json,confidence=excluded.confidence,review_status=excluded.review_status,last_seen=excluded.last_seen,updated_at=excluded.updated_at,payload_sha256=excluded.payload_sha256""",
                (claim_id, case_id, row["statement_id"], row["entity_ref"], row["predicate"], canonical, row["value_json"], row.get("value_language") or "und", row["statement_kind"], _clamp(row["confidence"]), row["review_status"], row["first_seen"], row["last_seen"], row["created_by"], row["created_at"], now, _hash(payload)),
            )
            # A statement is evidence for itself, but its kind remains explicit.
            stance = "supports" if row["statement_kind"] == "observation" else "context"
            link_id = "claimlink225_stmt_" + row["statement_id"]
            link_payload = {"claim_id": claim_id, "source_ref": row["statement_id"], "stance": stance, "strength": _clamp(row["confidence"])}
            self.db.execute(
                """INSERT INTO claim_evidence_links_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(case_id,claim_id,source_ref,stance) DO UPDATE SET strength=excluded.strength,review_status=excluded.review_status,payload_sha256=excluded.payload_sha256""",
                (link_id, case_id, claim_id, row["statement_id"], "evidence_statement", "", stance, _clamp(row["confidence"]), "unknown", "Originating statement", "reviewed", actor, now, _hash(link_payload)),
            )
            count += 1
        return count

    def _sync_lineage(self, case_id: str, actor: str) -> tuple[int, int]:
        chunks = self.db.all("SELECT * FROM ai_memory_chunks_216 WHERE case_id=? AND status='active' ORDER BY created_at", (case_id,))
        now = now_ts()
        prepared: list[dict[str, Any]] = []
        for row in chunks:
            metadata = _loads(row.get("metadata_json"), {})
            url = self._url_for_chunk(case_id, row)
            origin_key = _canonical_url(url) or _text(row.get("independence_key"), 500) or f"{row['source_type']}:{row['source_ref']}"
            content_hash = hashlib.sha256(re.sub(r"\s+", " ", _text(row.get("content"), 200_000)).strip().casefold().encode("utf-8")).hexdigest()
            prepared.append({"row": row, "metadata": metadata, "url": url, "origin_key": origin_key, "content_hash": content_hash})
        content_counts = Counter(item["content_hash"] for item in prepared)
        groups: dict[str, list[str]] = defaultdict(list)
        content_groups: dict[str, list[str]] = defaultdict(list)
        node_by_ref: dict[str, str] = {}
        for item in prepared:
            row = item["row"]
            # Exact copies across different hosts share a group; otherwise the original source lineage is decisive.
            independence_group = ("content:" + item["content_hash"]) if content_counts[item["content_hash"]] > 1 else ("origin:" + item["origin_key"])
            node_id = "lineage225_" + hashlib.sha256(f"{case_id}|{row['source_type']}|{row['source_ref']}".encode()).hexdigest()[:32]
            payload = {"node_id": node_id, "case_id": case_id, "source_ref": row["source_ref"], "source_type": row["source_type"], "origin_key": item["origin_key"], "independence_group": independence_group, "canonical_url": item["url"], "title": row["title"], "content_sha256": item["content_hash"], "observed_at": row["observed_at"], "source_quality": _clamp(row["quality_score"]), "metadata": item["metadata"], "updated_at": now}
            self.db.execute(
                """INSERT INTO source_lineage_nodes_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(case_id,source_ref,source_type) DO UPDATE SET origin_key=excluded.origin_key,independence_group=excluded.independence_group,canonical_url=excluded.canonical_url,title=excluded.title,content_sha256=excluded.content_sha256,observed_at=excluded.observed_at,source_quality=excluded.source_quality,status='active',metadata_json=excluded.metadata_json,updated_at=excluded.updated_at,payload_sha256=excluded.payload_sha256""",
                (node_id, case_id, row["source_ref"], row["source_type"], item["origin_key"], independence_group, item["url"], row["title"], item["content_hash"], row["observed_at"], _clamp(row["quality_score"]), "active", dumps(item["metadata"]), row["created_at"], now, _hash(payload)),
            )
            groups[item["origin_key"]].append(node_id)
            content_groups[item["content_hash"]].append(node_id)
            node_by_ref[row["source_ref"]] = node_id
        for ref, node_id in node_by_ref.items():
            self.db.execute("UPDATE claim_evidence_links_225 SET lineage_node_id=? WHERE case_id=? AND source_ref=? AND lineage_node_id=''", (node_id, case_id, ref))
        edges = 0
        for relation, grouped in (("same_origin", groups), ("direct_copy", content_groups)):
            for _key, nodes in grouped.items():
                if len(nodes) < 2:
                    continue
                parent = sorted(nodes)[0]
                for child in sorted(nodes)[1:]:
                    edge_id = "lineageedge225_" + hashlib.sha256(f"{case_id}|{parent}|{child}|{relation}".encode()).hexdigest()[:32]
                    payload = {"parent": parent, "child": child, "relation": relation, "confidence": 1.0 if relation == "direct_copy" else 0.85}
                    before = self.db.one("SELECT edge_id FROM source_lineage_edges_225 WHERE edge_id=?", (edge_id,))
                    self.db.execute("INSERT OR IGNORE INTO source_lineage_edges_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (edge_id, case_id, parent, child, relation, payload["confidence"], "Deterministic exact content/origin grouping", "inferred", "", actor, now, _hash(payload)))
                    if not before:
                        edges += 1
        return len(chunks), edges

    def _url_for_chunk(self, case_id: str, row: Mapping[str, Any]) -> str:
        ref = row["source_ref"]
        if row["source_type"] == "evidence_statement":
            found = self.db.one("SELECT s.canonical_url FROM evidence_statements_211 st JOIN evidence_sources_211 s ON s.source_id=st.source_id WHERE st.case_id=? AND st.statement_id=?", (case_id, ref))
            return _canonical_url((found or {}).get("canonical_url", ""))
        if row["source_type"] in {"social_candidate", "digital_source_candidate"}:
            table = "social_candidates_213" if row["source_type"] == "social_candidate" else "digital_source_results_218"
            id_col = "candidate_id" if row["source_type"] == "social_candidate" else "result_id"
            found = self.db.one(f"SELECT profile_url FROM {table} WHERE case_id=? AND {id_col}=?", (case_id, ref))
            return _canonical_url((found or {}).get("profile_url", ""))
        if row["source_type"] == "source_pack2_candidate":
            found = self.db.one("SELECT canonical_url FROM source_results_220 WHERE case_id=? AND result_id=?", (case_id, ref))
            return _canonical_url((found or {}).get("canonical_url", ""))
        return ""

    def _select_claim(self, claims: Sequence[Mapping[str, Any]], query: str, requested: str) -> Mapping[str, Any] | None:
        if requested:
            for claim in claims:
                if claim["claim_id"] == requested:
                    return claim
            raise ValueError("target claim does not belong to this case")
        q = set(_tokens(query))
        ranked: list[tuple[float, Mapping[str, Any]]] = []
        for claim in claims:
            terms = set(_tokens(f"{claim['subject_ref']} {claim['predicate']} {claim['canonical_text']}"))
            overlap = len(q & terms) / max(1, len(q | terms))
            score = overlap + 0.05 * _clamp(claim["confidence"])
            ranked.append((score, claim))
        ranked.sort(key=lambda item: (-item[0], item[1]["claim_id"]))
        if not ranked or ranked[0][0] < 0.03:
            return None
        top = ranked[0][1]
        # Do not silently choose among competing statements about the same attribute.
        if any(c["claim_id"] != top["claim_id"] and c["subject_ref"] == top["subject_ref"] and c["predicate"] == top["predicate"] for _score, c in ranked):
            return None
        if len(ranked) > 1 and abs(ranked[0][0] - ranked[1][0]) < 0.03:
            return None
        return top

    def _query_embedding(self, session: Mapping[str, Any], query: str) -> tuple[str, list[float]]:
        model = _text(session.get("embedding_model"), 200).strip()
        if not model:
            return "", []
        try:
            config = self.local_ai.ensure_case_config(case_id=session["case_id"], actor="retrieval225")
            self.local_ai._preflight(session["case_id"], config)
            response = self.local_ai._request(config["endpoint"], "POST", "/api/embed", {"model": model, "input": query, "truncate": True}, timeout=90.0, max_bytes=4_000_000)
            vectors = response.get("embeddings") or []
            return (model, [float(x) for x in vectors[0]]) if vectors and vectors[0] else ("", [])
        except Exception:
            return "", []

    def _temporal_score(self, claim: Mapping[str, Any] | None, observed_at: str) -> tuple[float, str]:
        if not claim:
            return (0.5 if observed_at else 0.35, "unknown")
        claim_last = _parse_time(claim.get("last_seen", ""))
        observed = _parse_time(observed_at)
        if not claim_last or not observed:
            return 0.45, "unknown"
        days = abs((observed - claim_last).total_seconds()) / 86400.0
        if days <= 30:
            return 1.0, "current"
        if days <= 365:
            return 0.75, "historical"
        return 0.45, "historical"

    def _ensure_stance(self, selected: list[tuple[float, dict[str, Any], dict[str, Any]]], scored: Sequence[tuple[float, dict[str, Any], dict[str, Any]]], stance: str, limit: int) -> list[tuple[float, dict[str, Any], dict[str, Any]]]:
        if any(item[2]["stance"] == stance for item in selected):
            return selected
        candidate = next((item for item in scored if item[2]["stance"] == stance), None)
        if not candidate:
            return selected
        if len(selected) >= limit:
            # Replace the lowest-scored context item, never the only opposite stance.
            replaceable = [i for i, item in enumerate(selected) if item[2]["stance"] == "context"]
            if replaceable:
                selected[replaceable[-1]] = candidate
        else:
            selected.append(candidate)
        return selected

    def _store_empty_run(self, session_id: str, case_id: str, claim_id: str, query: str, language: str) -> dict[str, Any]:
        rid, now = new_id("retrieval225"), now_ts()
        payload = {"retrieval_run_id": rid, "session_id": session_id, "case_id": case_id, "target_claim_id": claim_id, "query_text": query, "query_language": language, "retrieval_mode": self.RETRIEVAL_MODE, "selected_refs": [], "supporting_refs": [], "contradicting_refs": [], "context_refs": [], "score_details": {}, "source_diversity": 0.0, "lineage_diversity": 0.0, "counterevidence_included": False, "candidate_count": 0, "selected_count": 0, "created_at": now}
        self.db.execute("INSERT INTO retrieval_runs_225 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, session_id, case_id, claim_id, query, language, self.RETRIEVAL_MODE, "[]", "[]", "[]", "[]", "{}", 0.0, 0.0, 0, 0, 0, now, _hash(payload)))
        return {**payload, "selected_chunks": [], "contradiction_included": False, "source_type_counts": {}, "claim": None, "claim_centric": True, "human_review_required": True}

    def _claim(self, claim_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM retrieval_claims_225 WHERE claim_id=?", (claim_id,))
        if not row:
            raise KeyError(claim_id)
        return dict(row)

    def _public_claim(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "normalized_value": _loads(row.get("normalized_value_json"), {})}

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build225_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        event_id, now = new_id("evt225"), now_ts()
        safe = {k: v for k, v in dict(payload).items() if k not in {"query_text", "content", "prompt", "response", "target_value", "token", "authorization", "password"}}
        body = {"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build225_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, safe)
        return event_id
