"""Bring Build-492 source families into the canonical Build-456 source-lineage review.

A source family is only a suggestion. Nothing is counted differently until a person
with ``source.review`` confirms, with a rationale, that the evidence items of a family
share one origin. The confirmation is written as ordinary Build-456 lineage reviews
(one per evidence item, same independence group), so claims then count the family as a
single origin through the existing mechanism.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from eagleeye_pro.phase20.entity_lineage456 import LINEAGE_CONFIRM

GROUP_PREFIX = "family492:"


def evidence_by_document(ctx, case_id: str) -> dict[str, str]:
    """document_id -> evidence_id for documents promoted via 'Quelle -> Evidence' (481)."""
    from eagleeye.interfaces.web.bridge481 import _records  # integrity-checked rows

    return {row["document_id"]: row["evidence_id"] for row in _records(ctx, case_id)}


def member_states(ctx, identity: dict, case_id: str, members: list[dict]) -> list[dict]:
    """Per family member: evidence id, evidence review state and current lineage."""
    mapping = evidence_by_document(ctx, case_id)
    out = []
    for member in members:
        evidence_id = mapping.get(member["document_id"], "")
        state = {"document_id": member["document_id"], "evidence_id": evidence_id,
                 "evidence_state": "", "lineage_reviewed": False, "group": "", "evidence_hash": ""}
        if evidence_id:
            evidence = ctx.evidence_claims_dossier_447.evidence(evidence_id)
            lineage = ctx.entity_lineage_456.evidence_lineage(identity=identity, evidence_id=evidence_id)
            state.update(evidence_state=str(evidence.get("review_state") or ""),
                         lineage_reviewed=bool(lineage.get("reviewed")),
                         group=str(lineage.get("independence_group") or ""),
                         evidence_hash=str(evidence.get("record_hash") or ""))
        out.append(state)
    return out


def family_status(states: list[dict]) -> str:
    """'one_origin' | 'split' | 'open' | 'too_few' for a family's evidence members."""
    with_evidence = [s for s in states if s["evidence_id"]]
    if len(with_evidence) < 2:
        return "too_few"
    reviewed_groups = {s["group"] for s in with_evidence if s["lineage_reviewed"]}
    if len(reviewed_groups) > 1:
        return "split"
    if len(reviewed_groups) == 1 and all(s["lineage_reviewed"] for s in with_evidence):
        return "one_origin"
    return "open"


def confirm_family(ctx, *, identity: dict, case_id: str, family: dict, document_ids: list[str],
                   rationale: str) -> list[dict]:
    """Record one 456 lineage review per evidence item of the family, all in one group.

    ``family`` must be freshly computed by the caller; ``document_ids`` must be exactly
    the family members that have evidence, so a stale form cannot confirm a changed family.
    """
    rationale = " ".join(str(rationale or "").split())
    if not 12 <= len(rationale) <= 3000:
        raise ValueError("Bitte begründen, warum diese Belege einen gemeinsamen Ursprung haben (12–3000 Zeichen).")
    mapping = evidence_by_document(ctx, case_id)
    members = [m for m in family["members"] if m["document_id"] in mapping]
    if len(members) < 2:
        raise ValueError("Mindestens zwei Belege der Familie müssen bereits als Evidence übernommen sein.")
    if sorted(document_ids) != sorted(m["document_id"] for m in members):
        raise ValueError("Die Quellfamilie hat sich seit dem Öffnen der Seite verändert. Bitte neu laden und erneut prüfen.")
    earliest = members[0]  # family members are sorted by first appearance in the case
    earliest_evidence = mapping[earliest["document_id"]]
    group = GROUP_PREFIX + earliest_evidence
    origin = earliest.get("source_url") or ("urn:eagleeye:evidence:" + earliest_evidence)
    host = urlsplit(earliest.get("source_url") or "").hostname or "ohne Quellen-URL"
    detail = (f" [Quellfamilie Build 492: {family['size']} Dokumente, Ähnlichkeit "
              f"{family['min_similarity']}–{family['max_similarity']}, frühester Beleg im Fall: {earliest['title']}]")
    results = []
    with ctx.db.transaction(immediate=True):
        for member in members:
            evidence_id = mapping[member["document_id"]]
            evidence = ctx.evidence_claims_dossier_447.evidence(evidence_id)
            results.append(ctx.entity_lineage_456.review_source_lineage(
                identity=identity, evidence_id=evidence_id, source_family=GROUP_PREFIX + host,
                independence_group=group, origin_key=origin,
                source_role="primary" if member is earliest else "mirror", countable=True,
                rationale=(rationale + detail)[:4000], confirmation=LINEAGE_CONFIRM,
                expected_evidence_hash=evidence["record_hash"]))
        ctx.audit.log("source_family_confirmed_492", "operational_case", case_id, case_id,
                      {"evidence": [mapping[m["document_id"]] for m in members], "independence_group": group,
                       "truth_determined": False})
    return results
