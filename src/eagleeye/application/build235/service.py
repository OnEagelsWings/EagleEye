from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from eagleeye_pro.core.database import dumps, new_id, now_ts


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


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


class Build235CanonicalInvestigationKernelService:
    """Canonical, provenance-preserving investigation data model.

    Build 235 does not destructively migrate legacy tables. It creates stable canonical
    object IDs, append-only revisions, reviewed typed links and explicit aliases back to
    historical records. Candidate relationships remain candidates until independently
    reviewed. The service performs no autonomous source/network action.
    """

    BUILD = "235.0"
    OBJECT_TYPES = {"entity", "claim", "evidence", "source", "hypothesis", "task", "finding"}
    FACT_STATES = {"candidate", "reviewed", "accepted", "rejected", "superseded", "open", "closed"}
    RELATIONS = {
        "about", "sourced_from", "supports", "contradicts", "derived_from", "depends_on",
        "mentions", "related_to", "same_as_candidate", "relationship", "produced_by", "addresses",
    }

    def __init__(self, db: Any, audit: Any, *, cases: Any, conversation: Any | None = None, actor: str = "local-analyst") -> None:
        self.db, self.audit, self.cases, self.conversation, self.actor = db, audit, cases, conversation, actor
        if conversation is not None:
            setattr(conversation, "_canonical_kernel_235", self)

    # ---- canonical objects -------------------------------------------------
    def create_object(
        self, *, case_id: str, object_type: str, label: str, subtype: str = "", canonical_key: str = "",
        state: str = "candidate", confidence: float = .5, payload: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None, actor: str = "", confirmation: str,
    ) -> dict[str, Any]:
        self.cases.get_case(case_id)
        typ = _text(object_type, 40).lower()
        if typ not in self.OBJECT_TYPES:
            raise ValueError("unsupported canonical object type")
        if confirmation != f"KERNEL OBJECT 235 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        lbl = _text(label, 1200)
        if not lbl:
            raise ValueError("label required")
        key = _text(canonical_key, 1000).lower()
        if not key:
            key = _hash({"type": typ, "subtype": subtype, "label": " ".join(lbl.lower().split())})
        existing = self.db.one("SELECT object_id FROM canonical_objects_235 WHERE case_id=? AND object_type=? AND canonical_key=?", (case_id, typ, key))
        if existing:
            return self.get_object(existing["object_id"])
        who, now, oid = actor or self.actor, now_ts(), new_id(f"k{typ}235")
        core = {"object_id": oid, "case_id": case_id, "object_type": typ, "subtype": _text(subtype, 120), "label": lbl, "canonical_key": key, "created_by": who, "created_at": now}
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO canonical_objects_235 VALUES(?,?,?,?,?,?,?,?,?)", (oid, case_id, typ, core["subtype"], lbl, key, who, now, _hash(core)))
            self._append_revision(oid, case_id, state, confidence, dict(payload or {}), dict(provenance or {}), who, supersedes="")
        self._event(case_id, "canonical_object_created", typ, oid, {"subtype": core["subtype"], "label": lbl}, who)
        return self.get_object(oid)

    def revise_object(
        self, *, object_id: str, state: str, confidence: float, payload: Mapping[str, Any], provenance: Mapping[str, Any],
        actor: str, confirmation: str,
    ) -> dict[str, Any]:
        obj = self._object_row(object_id)
        if confirmation != f"KERNEL REVISION 235 {object_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        latest = self._latest_revision(object_id)
        rid = self._append_revision(object_id, obj["case_id"], state, confidence, dict(payload), dict(provenance), actor, supersedes=latest["revision_id"] if latest else "")
        self._event(obj["case_id"], "canonical_object_revised", obj["object_type"], object_id, {"revision_id": rid, "state": state}, actor)
        return self.get_object(object_id)

    def create_entity(self, *, case_id: str, label: str, entity_type: str, attributes: Mapping[str, Any] | None = None, confidence: float = .5, actor: str = "", confirmation: str) -> dict[str, Any]:
        key_material = {"entity_type": _text(entity_type, 120).lower(), "label": " ".join(_text(label, 1200).lower().split())}
        return self.create_object(case_id=case_id, object_type="entity", subtype=entity_type, label=label, canonical_key=_hash(key_material), state="candidate", confidence=confidence, payload={"attributes": dict(attributes or {})}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)

    def create_claim(self, *, case_id: str, claim_text: str, confidence: float = .5, about_object_id: str = "", actor: str = "", confirmation: str) -> dict[str, Any]:
        claim = self.create_object(case_id=case_id, object_type="claim", subtype="assertion", label=claim_text, canonical_key=_hash({"claim": " ".join(_text(claim_text).lower().split())}), state="candidate", confidence=confidence, payload={"claim_text": _text(claim_text)}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)
        if about_object_id:
            self.create_link(case_id=case_id, source_object_id=claim["object_id"], relation_type="about", target_object_id=about_object_id, confidence=confidence, evidence_refs=[], actor=actor or self.actor, confirmation=f"KERNEL LINK 235 {case_id} ANLEGEN")
        return claim

    def create_source(self, *, case_id: str, label: str, url: str = "", source_class: str = "public_web", actor: str = "", confirmation: str) -> dict[str, Any]:
        host = urlparse(_text(url, 4000)).hostname or ""
        key = _hash({"url": _text(url, 4000), "label": " ".join(_text(label).lower().split()), "class": source_class})
        return self.create_object(case_id=case_id, object_type="source", subtype=source_class, label=label, canonical_key=key, state="candidate", confidence=.5, payload={"url": _text(url, 4000), "host": host, "source_class": _text(source_class, 120)}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)

    def create_evidence(self, *, case_id: str, title: str, statement: str, source_object_id: str = "", confidence: float = .5, actor: str = "", confirmation: str) -> dict[str, Any]:
        ev = self.create_object(case_id=case_id, object_type="evidence", subtype="statement", label=title, canonical_key=_hash({"title": _text(title), "statement": _text(statement)}), state="candidate", confidence=confidence, payload={"statement": _text(statement)}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)
        if source_object_id:
            self.create_link(case_id=case_id, source_object_id=ev["object_id"], relation_type="sourced_from", target_object_id=source_object_id, confidence=confidence, evidence_refs=[], actor=actor or self.actor, confirmation=f"KERNEL LINK 235 {case_id} ANLEGEN")
        return ev

    def create_hypothesis(self, *, case_id: str, statement: str, confidence: float = .5, actor: str = "", confirmation: str) -> dict[str, Any]:
        return self.create_object(case_id=case_id, object_type="hypothesis", subtype="working_hypothesis", label=statement, canonical_key=_hash({"hypothesis": _text(statement).lower()}), state="candidate", confidence=confidence, payload={"statement": _text(statement)}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)

    def create_task(self, *, case_id: str, title: str, objective: str, priority: int = 50, actor: str = "", confirmation: str) -> dict[str, Any]:
        return self.create_object(case_id=case_id, object_type="task", subtype="research_task", label=title, canonical_key=_hash({"task": _text(title).lower(), "objective": _text(objective).lower()}), state="open", confidence=1.0, payload={"objective": _text(objective), "priority": max(0, min(100, int(priority)))}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)

    def create_finding(self, *, case_id: str, title: str, conclusion: str, confidence: float, evidence_ids: Sequence[str], actor: str = "", confirmation: str) -> dict[str, Any]:
        finding = self.create_object(case_id=case_id, object_type="finding", subtype="analytical_finding", label=title, canonical_key=_hash({"finding": _text(title).lower(), "conclusion": _text(conclusion).lower()}), state="candidate", confidence=confidence, payload={"conclusion": _text(conclusion), "evidence_ids": list(evidence_ids)}, provenance={"origin": "build235_manual"}, actor=actor, confirmation=confirmation)
        for eid in evidence_ids:
            self.create_link(case_id=case_id, source_object_id=finding["object_id"], relation_type="derived_from", target_object_id=eid, confidence=confidence, evidence_refs=[eid], actor=actor or self.actor, confirmation=f"KERNEL LINK 235 {case_id} ANLEGEN")
        return finding

    # ---- links and review --------------------------------------------------
    def create_link(self, *, case_id: str, source_object_id: str, relation_type: str, target_object_id: str, confidence: float = .5, evidence_refs: Sequence[str] = (), actor: str = "", confirmation: str) -> dict[str, Any]:
        if confirmation != f"KERNEL LINK 235 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        src, dst = self._object_row(source_object_id), self._object_row(target_object_id)
        if src["case_id"] != case_id or dst["case_id"] != case_id:
            raise ValueError("cross-case links are prohibited")
        relation = _text(relation_type, 160).lower()
        base = relation.split(":", 1)[0]
        if base not in self.RELATIONS:
            raise ValueError("unsupported relation type")
        existing = self.db.one("SELECT * FROM canonical_links_235 WHERE case_id=? AND source_object_id=? AND relation_type=? AND target_object_id=?", (case_id, source_object_id, relation, target_object_id))
        if existing:
            return self._link_payload(existing)
        who, now, lid = actor or self.actor, now_ts(), new_id("klink235")
        refs = list(dict.fromkeys(_text(x, 200) for x in evidence_refs if _text(x, 200)))[:100]
        payload = {"link_id": lid, "case_id": case_id, "source_object_id": source_object_id, "relation_type": relation, "target_object_id": target_object_id, "confidence": self._confidence(confidence), "evidence_refs": refs, "created_by": who, "created_at": now}
        self.db.execute("INSERT INTO canonical_links_235 VALUES(?,?,?,?,?,?,?,?,?,?)", (lid, case_id, source_object_id, relation, target_object_id, payload["confidence"], dumps(refs), who, now, _hash(payload)))
        self._event(case_id, "canonical_link_created", "link", lid, {"relation_type": relation, "source": source_object_id, "target": target_object_id}, who)
        return {**payload, "review_status": "unreviewed"}

    def review_link(self, *, link_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        link = self._link_row(link_id)
        if confirmation != f"KERNEL LINK REVIEW 235 {link_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == link["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"accepted", "rejected", "needs_more_evidence"}:
            raise ValueError("invalid link review decision")
        if self.db.one("SELECT review_id FROM canonical_link_reviews_235 WHERE link_id=?", (link_id,)):
            raise ValueError("link already reviewed")
        note = _text(rationale, 6000)
        if len(note) < 8:
            raise ValueError("substantive rationale required")
        rid, now = new_id("klinkreview235"), now_ts()
        payload = {"review_id": rid, "link_id": link_id, "case_id": link["case_id"], "decision": decision, "rationale": note, "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO canonical_link_reviews_235 VALUES(?,?,?,?,?,?,?,?)", (rid, link_id, link["case_id"], decision, note, reviewer, now, _hash(payload)))
        self._event(link["case_id"], "canonical_link_reviewed", "link", link_id, {"decision": decision}, reviewer)
        return payload

    # ---- compatibility adapters ------------------------------------------
    def adopt_legacy(self, *, case_id: str, namespace: str, legacy_type: str, legacy_id: str, object_type: str, subtype: str, label: str, payload: Mapping[str, Any], actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"KERNEL ADAPTER 235 {case_id} UEBERNEHMEN":
            raise PermissionError("explicit approval required")
        alias = self.db.one("SELECT * FROM canonical_aliases_235 WHERE case_id=? AND namespace=? AND legacy_type=? AND legacy_id=?", (case_id, namespace, legacy_type, legacy_id))
        if alias:
            return {"object": self.get_object(alias["object_id"]), "alias": alias, "created": False}
        obj = self.create_object(case_id=case_id, object_type=object_type, subtype=subtype, label=label, canonical_key=_hash({"namespace": namespace, "legacy_type": legacy_type, "legacy_id": legacy_id}), state="candidate", confidence=.5, payload=dict(payload), provenance={"origin": "legacy_adapter", "namespace": namespace, "legacy_type": legacy_type, "legacy_id": legacy_id}, actor=actor, confirmation=f"KERNEL OBJECT 235 {case_id} ANLEGEN")
        aid, now = new_id("kalias235"), now_ts()
        row = {"alias_id": aid, "case_id": case_id, "namespace": _text(namespace, 120), "legacy_type": _text(legacy_type, 120), "legacy_id": _text(legacy_id, 500), "object_id": obj["object_id"], "adapter_version": self.BUILD, "created_by": actor, "created_at": now}
        self.db.execute("INSERT INTO canonical_aliases_235 VALUES(?,?,?,?,?,?,?,?,?,?)", (aid, case_id, row["namespace"], row["legacy_type"], row["legacy_id"], obj["object_id"], self.BUILD, actor, now, _hash(row)))
        self._event(case_id, "legacy_reference_adopted", object_type, obj["object_id"], {"namespace": namespace, "legacy_type": legacy_type, "legacy_id": legacy_id}, actor)
        return {"object": obj, "alias": row, "created": True}

    def import_core_case(self, *, case_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"KERNEL IMPORT 235 {case_id} STARTEN":
            raise PermissionError("explicit approval required")
        self.cases.get_case(case_id)
        imported, existing = Counter(), Counter()
        specs: list[tuple[str, str, str, str, list[dict[str, Any]]]] = []
        specs.append(("core", "target", "entity", "person_target", self.db.all("SELECT * FROM targets WHERE case_id=?", (case_id,))))
        specs.append(("core", "evidence_item", "evidence", "legacy_evidence", self.db.all("SELECT * FROM evidence_items WHERE case_id=?", (case_id,))))
        if self._table_exists("evidence_sources_211"):
            specs.append(("build211", "evidence_source", "source", "evidence_source", self.db.all("SELECT * FROM evidence_sources_211 WHERE case_id=?", (case_id,))))
        if self._table_exists("evidence_statements_211"):
            specs.append(("build211", "evidence_statement", "evidence", "evidence_statement", self.db.all("SELECT * FROM evidence_statements_211 WHERE case_id=?", (case_id,))))
        if self._table_exists("investigation_hypotheses_227"):
            specs.append(("build227", "hypothesis", "hypothesis", "conversation_hypothesis", self.db.all("SELECT * FROM investigation_hypotheses_227 WHERE case_id=?", (case_id,))))
        for namespace, legacy_type, object_type, subtype, rows in specs:
            for row in rows:
                legacy_id = next((str(row.get(k)) for k in ("target_id", "evidence_id", "source_id", "statement_id", "hypothesis_id") if row.get(k)), "")
                if not legacy_id:
                    continue
                label = next((str(row.get(k)) for k in ("name", "title", "statement", "hypothesis_text", "source_name", "url") if row.get(k)), f"{legacy_type}:{legacy_id}")
                adopted = self.adopt_legacy(case_id=case_id, namespace=namespace, legacy_type=legacy_type, legacy_id=legacy_id, object_type=object_type, subtype=subtype, label=label, payload=row, actor=actor, confirmation=f"KERNEL ADAPTER 235 {case_id} UEBERNEHMEN")
                (imported if adopted["created"] else existing)[object_type] += 1
        result = {"case_id": case_id, "imported": dict(imported), "already_mapped": dict(existing), "destructive_migration": False}
        self._event(case_id, "canonical_import_completed", "case", case_id, result, actor)
        return result

    # ---- views, integrity and AI context ---------------------------------
    def get_object(self, object_id: str) -> dict[str, Any]:
        obj = self._object_row(object_id)
        rev = self._latest_revision(object_id)
        aliases = self.db.all("SELECT namespace,legacy_type,legacy_id,adapter_version FROM canonical_aliases_235 WHERE object_id=? ORDER BY namespace,legacy_type", (object_id,))
        out = dict(obj)
        if rev:
            out.update({"revision_id": rev["revision_id"], "revision_no": rev["revision_no"], "state": rev["state"], "confidence": rev["confidence"], "payload": _loads(rev["payload_json"], {}), "provenance": _loads(rev["provenance_json"], {})})
        out["aliases"] = aliases
        return out

    def case_snapshot(self, *, case_id: str) -> dict[str, Any]:
        objects = self.db.all("SELECT * FROM canonical_objects_235 WHERE case_id=? ORDER BY created_at,object_id", (case_id,))
        links = self.db.all("SELECT l.*,r.decision AS review_decision FROM canonical_links_235 l LEFT JOIN canonical_link_reviews_235 r ON r.link_id=l.link_id WHERE l.case_id=? ORDER BY l.created_at,l.link_id", (case_id,))
        counts = Counter(x["object_type"] for x in objects)
        accepted = sum(1 for x in links if x.get("review_decision") == "accepted")
        unresolved = sum(1 for x in links if x.get("review_decision") not in {"accepted", "rejected"})
        integrity = self.validate_case(case_id=case_id)
        return {"case_id": case_id, "object_count": len(objects), "link_count": len(links), "accepted_link_count": accepted, "unresolved_link_count": unresolved, "object_counts": dict(counts), "integrity": integrity}

    def create_snapshot(self, *, case_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"KERNEL SNAPSHOT 235 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        summary = self.case_snapshot(case_id=case_id)
        content = self.conversation_context(case_id=case_id, limit=1000)
        sid, now = new_id("ksnapshot235"), now_ts()
        payload = {**summary, "snapshot_id": sid, "content_sha256": _hash(content), "created_by": actor, "created_at": now}
        self.db.execute("INSERT INTO canonical_snapshots_235 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (sid, case_id, summary["object_count"], summary["link_count"], summary["accepted_link_count"], summary["unresolved_link_count"], dumps(summary["object_counts"]), dumps(summary["integrity"]), payload["content_sha256"], actor, now, _hash(payload)))
        self._event(case_id, "canonical_snapshot_created", "snapshot", sid, {"content_sha256": payload["content_sha256"]}, actor)
        return payload

    def validate_case(self, *, case_id: str) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        for obj in self.db.all("SELECT object_id FROM canonical_objects_235 WHERE case_id=?", (case_id,)):
            if not self._latest_revision(obj["object_id"]):
                issues.append({"object_id": obj["object_id"], "issue": "missing_revision"})
        bad_links = self.db.all("""SELECT l.link_id FROM canonical_links_235 l LEFT JOIN canonical_objects_235 s ON s.object_id=l.source_object_id LEFT JOIN canonical_objects_235 t ON t.object_id=l.target_object_id WHERE l.case_id=? AND (s.object_id IS NULL OR t.object_id IS NULL OR s.case_id<>l.case_id OR t.case_id<>l.case_id)""", (case_id,))
        issues.extend({"link_id": x["link_id"], "issue": "broken_or_cross_case_link"} for x in bad_links)
        duplicate_aliases = self.db.all("SELECT namespace,legacy_type,legacy_id,COUNT(*) AS n FROM canonical_aliases_235 WHERE case_id=? GROUP BY namespace,legacy_type,legacy_id HAVING COUNT(*)>1", (case_id,))
        issues.extend({"issue": "duplicate_legacy_alias", **x} for x in duplicate_aliases)
        return {"ok": not issues, "issues": issues, "gate": "CANONICAL_KERNEL_PASS" if not issues else "CANONICAL_KERNEL_REVIEW"}

    def conversation_context(self, *, case_id: str, limit: int = 30) -> dict[str, Any]:
        lim = max(1, min(200, int(limit)))
        rows = self.db.all("SELECT * FROM canonical_objects_235 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, lim * 4))
        groups: dict[str, list[dict[str, Any]]] = {k: [] for k in self.OBJECT_TYPES}
        for row in rows:
            rev = self._latest_revision(row["object_id"])
            if not rev:
                continue
            groups[row["object_type"]].append({"object_id": row["object_id"], "subtype": row["subtype"], "label": row["label"], "state": rev["state"], "confidence": round(float(rev["confidence"]), 3), "payload": _loads(rev["payload_json"], {})})
        accepted_links = self.db.all("""SELECT l.link_id,l.source_object_id,l.relation_type,l.target_object_id,l.confidence FROM canonical_links_235 l JOIN canonical_link_reviews_235 r ON r.link_id=l.link_id AND r.decision='accepted' WHERE l.case_id=? ORDER BY r.reviewed_at DESC LIMIT ?""", (case_id, lim))
        candidate_links = self.db.all("""SELECT l.link_id,l.source_object_id,l.relation_type,l.target_object_id,l.confidence FROM canonical_links_235 l LEFT JOIN canonical_link_reviews_235 r ON r.link_id=l.link_id WHERE l.case_id=? AND (r.decision IS NULL OR r.decision='needs_more_evidence') ORDER BY l.created_at DESC LIMIT ?""", (case_id, min(lim, 12)))
        return {
            "kernel_build": self.BUILD,
            "entities": groups["entity"][:lim], "claims": groups["claim"][:lim], "evidence": groups["evidence"][:lim],
            "sources": groups["source"][:lim], "hypotheses": groups["hypothesis"][:lim], "tasks": groups["task"][:lim], "findings": groups["finding"][:lim],
            "accepted_links": accepted_links, "candidate_links_not_facts": candidate_links,
            "integrity": self.validate_case(case_id=case_id),
        }

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        snap = self.case_snapshot(case_id=case_id)
        recent = self.db.all("SELECT object_id,object_type,subtype,label,created_at FROM canonical_objects_235 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        links = self.db.all("SELECT l.link_id,l.relation_type,l.source_object_id,l.target_object_id,l.confidence,COALESCE(r.decision,'unreviewed') AS review_status FROM canonical_links_235 l LEFT JOIN canonical_link_reviews_235 r ON r.link_id=l.link_id WHERE l.case_id=? ORDER BY l.created_at DESC LIMIT 20", (case_id,))
        aliases = self.db.all("SELECT namespace,legacy_type,legacy_id,object_id FROM canonical_aliases_235 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        return {**snap, "recent_objects": recent, "recent_links": links, "recent_aliases": aliases}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        counts = " · ".join(f"{esc(k)}: <strong>{v}</strong>" for k, v in sorted(data["object_counts"].items())) or "Noch keine kanonischen Objekte"
        objects = "".join(f"<tr><td><code>{esc(x['object_id'])}</code></td><td>{esc(x['object_type'])}</td><td>{esc(x['subtype'])}</td><td>{esc(x['label'])}</td></tr>" for x in data["recent_objects"]) or "<tr><td colspan='4'>Noch keine Objekte.</td></tr>"
        links = "".join(f"<tr><td><code>{esc(x['link_id'])}</code></td><td>{esc(x['relation_type'])}</td><td><code>{esc(x['source_object_id'])}</code> → <code>{esc(x['target_object_id'])}</code></td><td>{esc(x['review_status'])}</td></tr>" for x in data["recent_links"]) or "<tr><td colspan='4'>Noch keine Beziehungen.</td></tr>"
        return f"""
<section class='card' id='build235_kernel'><h2>Canonical Investigation Kernel · Build 235</h2>
<p>Ein verbindliches Fallmodell für Entity/Person → Claim → Evidence → Source → Relationship → Hypothesis → Task → Finding. Historische Module werden nicht destruktiv migriert; Adapter halten die Herkunft nachvollziehbar.</p>
<p><strong>Kernel:</strong> {counts} · Links: <strong>{data['link_count']}</strong> · akzeptiert: <strong>{data['accepted_link_count']}</strong> · ungeklärt: <strong>{data['unresolved_link_count']}</strong> · Integrity: <strong>{esc(data['integrity']['gate'])}</strong></p>
<div class='grid two'>
<div class='card'><h3>Bestehenden Fallbestand kanonisieren</h3><form method='post' action='/build235/import-core'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Core-/Evidence-/Hypothesen-IDs verlustfrei abbilden</button></form><p class='muted'>Kein Löschen, kein automatisches Identity-Merging.</p></div>
<div class='card'><h3>Entity anlegen</h3><form method='post' action='/build235/entity-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='label' placeholder='Name / Bezeichnung' required><input name='entity_type' value='person' placeholder='Typ'><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><button>Entity als Kandidat anlegen</button></form></div>
<div class='card'><h3>Claim anlegen</h3><form method='post' action='/build235/claim-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><textarea name='claim_text' placeholder='Prüfbare Behauptung' required></textarea><input name='about_object_id' placeholder='Optional: Entity-ID'><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><button>Claim anlegen</button></form></div>
<div class='card'><h3>Kanonisches Objekt</h3><form method='post' action='/build235/object-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='object_type'><option>source</option><option>evidence</option><option>hypothesis</option><option>task</option><option>finding</option><option>entity</option><option>claim</option></select><input name='subtype' placeholder='Subtype'><input name='label' placeholder='Label / Aussage / Aufgabe' required><select name='state'><option>candidate</option><option>open</option><option>reviewed</option></select><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><textarea name='payload_json' placeholder='Optionale strukturierte JSON-Daten'>{{}}</textarea><button>Objekt anlegen</button></form></div>
<div class='card'><h3>Kanonische Beziehung</h3><form method='post' action='/build235/link-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_object_id' placeholder='Source Object-ID' required><input name='relation_type' value='related_to' placeholder='Relation' required><input name='target_object_id' placeholder='Target Object-ID' required><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><button>Beziehung als Kandidat anlegen</button></form></div>
<div class='card'><h3>Beziehung prüfen</h3><form method='post' action='/build235/link-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='link_id' placeholder='Link-ID' required><select name='decision'><option>accepted</option><option>needs_more_evidence</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Review speichern</button></form></div>
</div>
<div class='table-wrap'><table><thead><tr><th>ID</th><th>Typ</th><th>Subtype</th><th>Label</th></tr></thead><tbody>{objects}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Link</th><th>Relation</th><th>Objekte</th><th>Review</th></tr></thead><tbody>{links}</tbody></table></div>
</section>"""

    # ---- internal ----------------------------------------------------------
    def _append_revision(self, object_id: str, case_id: str, state: str, confidence: float, payload: Mapping[str, Any], provenance: Mapping[str, Any], actor: str, supersedes: str) -> str:
        st = _text(state, 60).lower()
        if st not in self.FACT_STATES:
            raise ValueError("invalid canonical object state")
        row = self.db.one("SELECT COALESCE(MAX(revision_no),0) AS n FROM canonical_object_revisions_235 WHERE object_id=?", (object_id,)) or {"n": 0}
        no, rid, now = int(row["n"]) + 1, new_id("krev235"), now_ts()
        p, prov = dict(payload), dict(provenance)
        material = {"revision_id": rid, "object_id": object_id, "case_id": case_id, "revision_no": no, "state": st, "confidence": self._confidence(confidence), "payload": p, "provenance": prov, "supersedes_revision_id": supersedes, "created_by": actor, "created_at": now}
        self.db.execute("INSERT INTO canonical_object_revisions_235 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (rid, object_id, case_id, no, st, material["confidence"], dumps(p), dumps(prov), supersedes, actor, now, _hash(material)))
        return rid

    def _object_row(self, object_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM canonical_objects_235 WHERE object_id=?", (object_id,))
        if not row:
            raise KeyError("canonical object not found")
        return row

    def _latest_revision(self, object_id: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM canonical_object_revisions_235 WHERE object_id=? ORDER BY revision_no DESC LIMIT 1", (object_id,))

    def _link_row(self, link_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM canonical_links_235 WHERE link_id=?", (link_id,))
        if not row:
            raise KeyError("canonical link not found")
        return row

    def _link_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        review = self.db.one("SELECT decision FROM canonical_link_reviews_235 WHERE link_id=?", (row["link_id"],))
        return {**dict(row), "evidence_refs": _loads(row.get("evidence_refs_json"), []), "review_status": review["decision"] if review else "unreviewed"}

    def _confidence(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build235_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "GENESIS"
        eid, now = new_id("evt235"), now_ts()
        material = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": dict(payload), "previous_hash": previous, "created_at": now}
        event_hash = _hash(material)
        self.db.execute("INSERT INTO build235_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(dict(payload)), previous, event_hash, now))
        try:
            self.audit.log(event_type, object_type, object_id, case_id, dict(payload))
        except Exception:
            pass
