"""Build 499: source-bound, idempotent cross-SQLite outbox for graph candidates."""
import pytest
from eagleeye.application import personosint494 as po,transfer499
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.interfaces.web.app499 import create_workspace_app499
from test_build471_local_ai import workspace

ws=pytest.mark.parametrize("workspace",[create_workspace_app499],indirect=True)
@ws
def test_transfer_is_unverified_and_idempotent_with_stored_case_document(workspace):
    app,client,user,cid,document_id,other,*_=workspace
    ctx=app.state.context
    x=po.parse_entity_suggestions(__import__("json").dumps({
        "case":{"reference":"SYN-ONLY-499"},
        "entities":[{"id":17,"type":"person","label":"Synthetic Example Person"}]}).encode())
    po.queue(ctx,user,cid,x)
    candidate=po.candidates(ctx,cid)[0]
    reviewed=po.review(ctx,user,cid,candidate["candidate_id"],"for_manual_entry",
                       "Public documentation is insufficient for identity; allow unverified graph staging.")
    with pytest.raises(transfer499.TransferError,match="previously stored"):
        transfer499.transfer(ctx,user,cid,candidate["candidate_id"],"not-in-case",
                             "This document does not belong to this case so it must be rejected.",base_dir=ctx.base_dir)
    item=transfer499.transfer(ctx,user,cid,candidate["candidate_id"],document_id,
                  "This is a manually reviewed unverified candidate with linked case document.",base_dir=ctx.base_dir)
    assert item["state"]=="completed"
    assert item["entity_id"].startswith("po499_")
    assert transfer499.transfer(ctx,user,cid,candidate["candidate_id"],document_id,
                 "This is a manually reviewed unverified candidate with linked case document.",base_dir=ctx.base_dir)["entity_id"]==item["entity_id"]
    assert transfer499.rows(ctx,other)==[]
    with EntityRegistry461(ctx.base_dir/"entity_registry_462.sqlite3") as db:
        g=db.graph(cid); matches=[z for z in g["entities"] if z["id"]==item["entity_id"]]
    assert len(matches)==1 and "Unverifizierter" in matches[0]["notes"]
    assert g["relations"]==[]
    assert client.get("/workbench/transfer499",params={"case_id":cid}).status_code==200
    assert client.get("/workbench/transfer499",params={"case_id":"unknown"}).status_code==403

@ws
def test_unreviewed_entity_cannot_be_imported(workspace):
    app,client,user,cid,document_id,*_=workspace;ctx=app.state.context
    d=po.parse_entity_suggestions(__import__("json").dumps({
        "case":{"reference":"SYN-499-X"},
        "entities":[{"id":42,"type":"company","label":"Example Test GmbH"}]}).encode())
    po.queue(ctx,user,cid,d);cand=po.candidates(ctx,cid)[0]
    with pytest.raises(transfer499.TransferError,match="reviewed"):
        transfer499.transfer(ctx,user,cid,cand["candidate_id"],document_id,
                 "This candidate has not completed the required review and must be blocked.",base_dir=ctx.base_dir)
    assert transfer499.rows(ctx,cid)==[]
