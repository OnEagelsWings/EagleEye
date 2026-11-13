"""Build 499 follow-up: an interrupted transfer must be completable on retry.

Regression for a review finding: the retry compared the graph entry against notes
built from the *newly typed* rationale, so any different wording left the transfer
stuck in "staged" with "Existing external graph entry differs".
"""
import json

import pytest
from eagleeye.application import personosint494 as po, transfer499
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.interfaces.web.app499 import create_workspace_app499
from test_build471_local_ai import workspace  # noqa: F401

ws = pytest.mark.parametrize("workspace", [create_workspace_app499], indirect=True)
FIRST = "First rationale text that is long enough to pass the validation."
OTHER = "A different but equally valid rationale typed on the retry attempt."


def _reviewed_candidate(ctx, user, cid):
    preview = po.parse_entity_suggestions(json.dumps({
        "case": {"reference": "SYN-499-RETRY"},
        "entities": [{"id": 1, "type": "person", "label": "Synthetic Retry Person"}]}).encode())
    po.queue(ctx, user, cid, preview)
    candidate = po.candidates(ctx, cid)[0]
    po.review(ctx, user, cid, candidate["candidate_id"], "for_manual_entry",
              "Reviewed for unverified staging only; no identity claim.")
    return candidate["candidate_id"]


def _back_to_staged(ctx, candidate_id):
    """Simulate a crash after the graph write but before the journal was completed."""
    row = dict(ctx.db.one("SELECT * FROM case_entity_transfers_499 WHERE candidate_id=?", (candidate_id,)))
    row.update(state="staged", completed_at="")
    row["record_hash"] = transfer499._hash(row)
    ctx.db.execute("UPDATE case_entity_transfers_499 SET state='staged',completed_at='',record_hash=? WHERE candidate_id=?",
                   (row["record_hash"], candidate_id))
    ctx.db.conn.commit()


@ws
def test_retry_after_crash_completes_even_with_different_rationale(workspace):
    app, client, user, cid, document_id, *_ = workspace
    ctx = app.state.context
    candidate_id = _reviewed_candidate(ctx, user, cid)
    first = transfer499.transfer(ctx, user, cid, candidate_id, document_id, FIRST, base_dir=ctx.base_dir)
    _back_to_staged(ctx, candidate_id)
    again = transfer499.transfer(ctx, user, cid, candidate_id, document_id, OTHER, base_dir=ctx.base_dir)
    assert again["state"] == "completed" and again["entity_id"] == first["entity_id"]
    # Journal and graph keep the rationale recorded when the transfer was staged.
    assert again["rationale"] == FIRST
    with EntityRegistry461(ctx.base_dir / "entity_registry_462.sqlite3") as db:
        nodes = [e for e in db.graph(cid)["entities"] if e["id"] == first["entity_id"]]
    assert len(nodes) == 1 and FIRST in nodes[0]["notes"] and OTHER not in nodes[0]["notes"]


@ws
def test_retry_before_graph_write_uses_staged_rationale(workspace):
    app, client, user, cid, document_id, *_ = workspace
    ctx = app.state.context
    candidate_id = _reviewed_candidate(ctx, user, cid)
    first = transfer499.transfer(ctx, user, cid, candidate_id, document_id, FIRST, base_dir=ctx.base_dir)
    _back_to_staged(ctx, candidate_id)
    # Crash before the graph write: remove the node as if it had never been written.
    with EntityRegistry461(ctx.base_dir / "entity_registry_462.sqlite3") as db:
        db.db.execute("DELETE FROM entity461 WHERE id=?", (first["entity_id"],))
        db.db.commit()
    done = transfer499.transfer(ctx, user, cid, candidate_id, document_id, OTHER, base_dir=ctx.base_dir)
    assert done["state"] == "completed"
    with EntityRegistry461(ctx.base_dir / "entity_registry_462.sqlite3") as db:
        nodes = [e for e in db.graph(cid)["entities"] if e["id"] == first["entity_id"]]
    assert len(nodes) == 1 and FIRST in nodes[0]["notes"]
