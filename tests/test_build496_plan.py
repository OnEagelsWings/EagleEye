"""Build 496: case-scoped persisted plans and review gates, no network actions."""
import hashlib

import pytest

from eagleeye.application import plan496 as p
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app496 import create_workspace_app496
from test_build471_local_ai import workspace  # noqa: F401

ws = pytest.mark.parametrize("workspace", [create_workspace_app496], indirect=True)


def login(workspace):
    app, client, *_ = workspace
    sess = app.state.context.team_identity_359.authenticate(
        username="qa471", password="Build471!Password_88",
        client_fingerprint=hashlib.sha256(b"testclient||testclient").hexdigest())
    client.cookies.clear()
    client.cookies.set(COOKIE, sess.token)
    client.cookies.set(CSRF_COOKIE, sess.csrf_token)
    return sess.csrf_token


def form(client, route, cid, csrf, **extras):
    return client.post(route, data={"case_id": cid, "csrf": csrf, **extras}, follow_redirects=False)


@ws
def test_full_plan_lifecycle_with_canonical_case_audit(workspace):
    app, client, user, cid, doc, other, *_ = workspace
    ctx = app.state.context
    token = login(workspace)
    view = client.get("/workbench/plan496", params={"case_id": cid})
    assert view.status_code == 200
    assert "Ermittlungsplanung" in view.text
    assert "keine Genehmigung" in view.text or "keine Genehmigung" in view.text.lower()
    r = form(client, "/workbench/plan496/new", cid, token,
             objective="Öffentliche Firmeneinträge mit Originalen vergleichen",
             scope="Nur öffentliche Unternehmensregister und offizielle Dokumente; keine Personenüberwachung.")
    assert r.status_code == 303, r.text
    plan = p.list_plans(ctx, cid)[0]
    assert plan["state"] == "draft"
    assert not p.list_plans(ctx, other)
    step = form(client, "/workbench/plan496/step", cid, token, plan_id=plan["plan_id"],
                kind="manual_source",
                instruction="Öffentliches Handelsregister öffnen, Originalquelle dokumentieren.")
    assert step.status_code == 303, step.text
    steps = p.list_steps(ctx,cid,plan["plan_id"])
    assert len(steps) == 1 and steps[0]["state"] == "proposed"
    assert form(client, "/workbench/plan496/review", cid, token, plan_id=plan["plan_id"],
                expected_hash="bad", decision="approved",
                reason="Quellen und Grenzen sind vollständig nachvollziehbar beschrieben.").status_code == 409
    good = form(client, "/workbench/plan496/review", cid, token, plan_id=plan["plan_id"],
                expected_hash=plan["record_hash"], decision="approved",
                reason="Recherche ausschließlich in öffentlichen Registern mit überprüfbaren Fundstellen.")
    assert good.status_code == 303, good.text
    plan = p.get_plan(ctx,cid,plan["plan_id"])
    assert plan["state"] == "approved"
    assert form(client, "/workbench/plan496/step", cid, token, plan_id=plan["plan_id"],
                kind="manual_source",instruction="Noch eine Quelle prüfen und Dokumentation erstellen.").status_code == 422
    step = steps[0]
    result = form(client, "/workbench/plan496/annotate", cid, token, plan_id=plan["plan_id"],
                  step_id=step["step_id"], expected_hash=step["record_hash"], decision="done",
                  note="Die Registrierung wurde manuell in der Originalquelle geprüft, weitere Belege fehlen.")
    assert result.status_code == 303, result.text
    current = p.list_steps(ctx,cid,plan["plan_id"])[0]
    assert current["state"] == "done"
    assert form(client, "/workbench/plan496/annotate", cid, token, plan_id=plan["plan_id"],
                step_id=step["step_id"], expected_hash=step["record_hash"], decision="blocked",
                note="Zweite Prüfung wäre unzulässig, Vorgang wird nicht wiederholt.").status_code == 409
    assert ctx.db.one("SELECT count(*) AS n FROM provider_runs_120")["n"] == 0
    assert client.get("/workbench/plan496", params={"case_id": other, "plan_id":plan["plan_id"]}).status_code == 404


@ws
def test_plan_proposals_no_live_network_and_bounded_providers(workspace, monkeypatch):
    app, client, user, cid, doc, other, *_ = workspace
    ctx = app.state.context
    csrf = login(workspace)
    plan = p.create_plan(ctx,user,cid,"Investigative Prüfung zu synthetischen Unternehmensdaten",
                         "Nur synthetische Testdaten und erlaubte öffentliche Registerseiten.")
    # A named provider may be proposed, not executed.
    step = p.add_step(ctx,user,cid,plan["plan_id"],"provider_proposal",
                      "Kontrollierte öffentliche GitHub-Metadaten prüfen.",
                      "github_public_profile_120")
    assert step["provider_key"] == "github_public_profile_120"
    with pytest.raises(p.PlanError, match="Unknown provider"):
        p.add_step(ctx,user,cid,plan["plan_id"],"provider_proposal",
                   "Unbekannten Provider niemals direkt ausführen.","nonexistent_provider_000")
    with pytest.raises(p.PlanError, match="Only provider proposals"):
        p.add_step(ctx,user,cid,plan["plan_id"],"manual_source",
                   "Keine unbekannten Provider einschleusen.","github_public_profile_120")
    assert ctx.db.one("SELECT count(*) AS n FROM provider_runs_120")["n"] == 0
    assert client.get("/workbench/plan496",params={"case_id":cid,"plan_id":plan["plan_id"]}).status_code == 200
    assert "github_public_profile_120" in client.get(
        "/workbench/plan496",params={"case_id":cid,"plan_id":plan["plan_id"]}).text
    assert client.get("/workbench/plan496",params={"case_id":"wrong"}).status_code == 403
    assert form(client,"/workbench/plan496/new",cid,"incorrect",
                objective="Unbefugte Daten sammeln und speichern",
                scope="Diese Aktion ist absichtlich ungültig und bleibt gesperrt.").status_code == 403


@ws
def test_plan_review_integrity_and_rejected_state(workspace):
    app, client, user, cid, doc, other, *_ = workspace
    ctx = app.state.context
    csrf = login(workspace)
    plan = p.create_plan(ctx,user,cid,"Öffentliche Dokumentation unabhängiger Bestandsdaten",
                         "Nur geeignete öffentliche Quellen; keine versteckten Ausforschungen.")
    step = p.add_step(ctx,user,cid,plan["plan_id"],"hypothesis_check",
                      "Gegenbelege identifizieren und offene Annahmen dokumentieren.")
    rejected = p.review_plan(ctx,user,cid,plan["plan_id"],"rejected",
                             "Die Quellenstrategie ist für diesen Auftrag noch nicht tragfähig.",plan["record_hash"])
    assert rejected["state"] == "rejected"
    with pytest.raises(p.PlanError,match="Only approved"):
        p.annotate_step(ctx,user,cid,plan["plan_id"],step["step_id"],"done",
                        "Nicht genehmigte Schritte dürfen nicht bestätigt werden.",step["record_hash"])
    ctx.db.execute("UPDATE case_plan_steps_496 SET instruction='tampered' WHERE step_id=?",(step["step_id"],))
    with pytest.raises(p.PlanError,match="integrity"):
        p.list_steps(ctx,cid,plan["plan_id"])


def test_unicode_control_held_out():
    with pytest.raises(p.PlanError,match="Unicode"):
        p._safe_text("Gültiger Name mit Unicode Bidi \u202e Zeichen",field="objective",minimum=1,maximum=100)
