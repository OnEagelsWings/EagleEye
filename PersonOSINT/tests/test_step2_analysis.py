"""Schritt 2: Kandidatengruppen, Admiralty-Bewertung, Mehrfachbelege, Widersprüche, Red Flags."""
from __future__ import annotations

from conftest import add_user, build_app, setup_admin
from personosint import analysis
from test_personosint import FakeHttp

CH = "https://api.company-information.service.gov.uk"
ROUTES = {
    f"{CH}/search/officers": (200, {"items": [
        {"title": "Max MUSTERMANN", "date_of_birth": {"month": 5, "year": 1980}, "address_snippet": "Kai 1, Hamburg", "links": {"self": "/officers/a1/appointments"}},
        {"title": "Max MUSTERMANN", "date_of_birth": {"month": 2, "year": 1955}, "address_snippet": "9 Rue X, Lyon", "links": {"self": "/officers/b2/appointments"}}]}),
    f"{CH}/officers/a1/appointments": (200, {"items": [
        {"appointed_to": {"company_name": "HAFEN BETEILIGUNGS GMBH", "company_status": "active"}, "officer_role": "director", "appointed_on": "2019-03-01"},
        {"appointed_to": {"company_name": "ALPHA SHELL LTD", "company_status": "dissolved"}, "officer_role": "director", "appointed_on": "2020-01-01", "resigned_on": "2020-03-01"},
        {"appointed_to": {"company_name": "BETA SHELL LTD", "company_status": "liquidation"}, "officer_role": "director", "appointed_on": "2020-02-01", "resigned_on": "2020-05-01"},
        {"appointed_to": {"company_name": "GAMMA SHELL LTD", "company_status": "active"}, "officer_role": "director", "appointed_on": "2020-04-01", "resigned_on": "2020-12-01"}]}),
    f"{CH}/officers/b2/appointments": (200, {"items": [
        {"appointed_to": {"company_name": "LYON BOULANGERIE LTD", "company_status": "active"}, "officer_role": "secretary", "appointed_on": "1990-01-01"}]}),
    "https://api.opencorporates.com/v0.4/officers/search": (200, {"results": {"officers": [
        {"officer": {"name": "MAX MUSTERMANN", "position": "director", "start_date": "2019-03-01", "opencorporates_url": "https://opencorporates.com/officers/9",
                     "company": {"name": "Hafen Beteiligungs GmbH", "jurisdiction_code": "gb"}}}]}}),
    "https://api.github.com/search/users": (200, {"items": [{"login": "maxm", "html_url": "https://github.com/maxm"}]}),
}
SUBJECT = {"label": "Max Mustermann", "data": {"geburtsdatum": "1980-05-17"},
           "identifiers": [{"kind": "employer", "value": "Hafen Beteiligungs GmbH"}, {"kind": "location", "value": "Hamburg"}]}


def _setup(tmp_path, backend="sqlite"):
    app = build_app(tmp_path, backend, http=FakeHttp(ROUTES))
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    admin.put("/api/admin/sources/companies_house/key", json={"key": "k"})
    case = anna.post("/api/cases", json={"title": "Namensvetter", "case_type": "personensuche", "purpose": "Identifizierung der richtigen Person",
                                         "legal_basis": "Berechtigtes Interesse", "opsec_level": 1, "subject": SUBJECT}).json()
    cid = case["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    r = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["companies_house", "opencorporates", "github"]})
    assert r.status_code == 200, r.text
    return app, admin, anna, cid, sid


def test_candidate_groups_separate_namesakes(tmp_path, backend):
    app, admin, anna, cid, sid = _setup(tmp_path, backend)
    groups = anna.get(f"/api/cases/{cid}/candidates", params={"entity_id": sid}).json()
    kand = [g for g in groups if g["kind"] == "kandidat"]
    assert len(kand) == 2
    a, b = kand
    assert a["label"] == "Kandidat A" and a["births"] == ["1980-05"] and a["count"] == 2      # Companies House #1 + OpenCorporates
    assert any("passt zum Profil" in r for r in a["reasons"]) and any("Organisation" in r for r in a["reasons"])
    assert b["births"] == ["1955-02"] and any("NICHT" in r for r in b["reasons"]) and b["score"] < a["score"]
    loose = next(g for g in groups if g["kind"] == "lose")
    assert loose["members"][0]["source"] == "GitHub"

    # Vor der Prüfung widersprechen sich die Geburtsdaten -> Widerspruch + Red Flag
    asm = anna.get(f"/api/cases/{cid}/assessment").json()
    assert any(c["predicate"] == "geburtsdatum" for c in asm["contradictions"])
    assert any(r["rule"] == "identitaet_unsicher" for r in asm["redflags"])

    # Gruppe A bestätigen, Gruppe B verwerfen
    r = anna.post(f"/api/cases/{cid}/candidates/review", json={"finding_ids": a["finding_ids"], "status": "bestätigt", "note": "Geburtsmonat passt"})
    assert r.status_code == 200 and "Alpha Shell Ltd" in r.json()["created"]
    anna.post(f"/api/cases/{cid}/candidates/review", json={"finding_ids": b["finding_ids"], "status": "verworfen", "note": "anderes Geburtsjahr"})
    asm = anna.get(f"/api/cases/{cid}/assessment").json()
    assert asm["contradictions"] == []
    assert not any(r["rule"] == "identitaet_unsicher" for r in asm["redflags"])
    facts = {(f["source_key"], f["predicate"], f["object_label"]): f for f in asm["facts"]}
    hafen_ch = facts[("companies_house", "funktion_bei", "Hafen Beteiligungs Gmbh")]
    assert hafen_ch["corroboration"] == 2 and hafen_ch["code"] == "A1"                     # zwei Quellen, bestätigt
    assert facts[("companies_house", "funktion_bei", "Alpha Shell Ltd")]["code"] == "A2"
    assert facts[("companies_house", "funktion_bei", "Lyon Boulangerie Ltd")]["code"] == "A5"   # verworfen
    rules = {r["rule"]: r for r in asm["redflags"]}
    assert {"aufgeloeste_firmen", "kurze_mandate", "haeufige_wechsel"} <= set(rules)
    assert rules["aufgeloeste_firmen"]["confirmed"] and len(rules["aufgeloeste_firmen"]["fact_ids"]) == 2
    assert asm["stats"]["corroborated"] >= 2 and asm["stats"]["confirmed"] >= 5

    # Analystin überschreibt eine Bewertung
    fid = facts[("companies_house", "funktion_bei", "Gamma Shell Ltd")]["id"]
    assert anna.patch(f"/api/cases/{cid}/facts/{fid}", json={"credibility": 4, "reliability": "B", "note": "Registerauszug widersprüchlich"}).status_code == 200
    f2 = next(f for f in anna.get(f"/api/cases/{cid}/assessment").json()["facts"] if f["id"] == fid)
    assert f2["code"] == "B4" and f2["note"]
    assert anna.patch(f"/api/cases/{cid}/facts/{fid}", json={"credibility": 9}).status_code == 422


def test_redflag_rule_config(tmp_path):
    app, admin, anna, cid, sid = _setup(tmp_path)
    groups = anna.get(f"/api/cases/{cid}/candidates", params={"entity_id": sid}).json()
    anna.post(f"/api/cases/{cid}/candidates/review", json={"finding_ids": groups[0]["finding_ids"], "status": "bestätigt"})
    cfg = admin.get("/api/admin/redflag-rules").json()
    assert cfg["kurze_mandate"]["enabled"] and cfg["sanktion"]["severity"] == "hoch"
    cfg["kurze_mandate"]["enabled"] = False
    cfg["aufgeloeste_firmen"]["severity"] = "hoch"
    assert admin.put("/api/admin/redflag-rules", json={k: {"enabled": v["enabled"], "severity": v["severity"]} for k, v in cfg.items()}).status_code == 200
    rules = {r["rule"]: r for r in anna.get(f"/api/cases/{cid}/assessment").json()["redflags"]}
    assert "kurze_mandate" not in rules and rules["aufgeloeste_firmen"]["severity"] == "hoch"
    assert anna.get("/api/admin/redflag-rules").status_code == 403


def _fact(i, pred, subj, obj, **kw):
    return {"id": i, "predicate": pred, "subject_label": subj, "subject_entity_id": None, "object_label": obj, "status": "bestätigt",
            "source_key": "x", "source_label": "X", "reliability": "B", "credibility": 0, "norm_key": f"{subj}|{pred}|{obj}",
            "valid_from": kw.get("vf", ""), "valid_to": kw.get("vt", ""), "data": kw.get("data", {})}


def test_rules_on_synthetic_facts():
    facts = [_fact(i, "firmensitz", f"Firma {i}", "Hauptstraße 1, 10115 Berlin") for i in range(1, 4)]
    facts += [_fact(10 + i, "funktion_bei", "Erika", f"Firma Nr {i}") for i in range(10)]
    facts += [_fact(30, "sanktioniert", "Erika", "EU-Liste"), _fact(31, "pep", "Erika", "Ministerin")]
    res = analysis.assess(facts, {})
    rules = {r["rule"] for r in analysis.red_flags(res, analysis.rule_config(""))}
    assert {"sammeladresse", "viele_mandate", "sanktion", "pep"} <= rules
    flags = analysis.red_flags(res, analysis.rule_config(""))
    assert flags[0]["severity"] == "hoch"                      # nach Schweregrad sortiert
