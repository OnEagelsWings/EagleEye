"""Schutzregeln der Firecrawl-Anbindung (PR #95) – vorher ungetestet.

Firecrawl ist ein kostenpflichtiger Fremddienst. Geprüft wird ohne Netz: nur freigegebene Behördenseiten,
kein Abruf ohne Schlüssel, keine Weitergabe fremder Treffer, Grenzen bei Abrufziel und Antwort.
"""
from __future__ import annotations

import io
import json
import urllib.request

import pytest

from eagleeye_pro.real_providers import service as rp


class _Svc(rp.RealProviderConnectorService):
    def __init__(self):  # ohne Datenbank: nur die reinen Prüf- und Auswerteteile
        pass


@pytest.fixture()
def svc():
    return _Svc()


@pytest.mark.parametrize("query", [
    "site:evil.example Bundestag",              # nicht freigegebene Seite
    "Bundestag Haushalt",                      # ohne Seitenangabe
    "site:www.bundestag.de x site:evil.example",  # zweite Seitenangabe eingeschmuggelt
    "site:www.bundestag.de \r\nHost: x",        # Zeilenumbruch
])
def test_search_requires_single_approved_institutional_site(svc, monkeypatch, query):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "dummy")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **k: pytest.fail("kein Netzaufruf erwartet"))
    with pytest.raises(ValueError):
        svc._firecrawl("firecrawl_search", query)


@pytest.mark.parametrize("url", [
    "http://www.bundestag.de/start",               # kein https
    "https://evil.example/start",                  # fremde Seite
    "https://user:pw@www.bundestag.de/",           # Zugangsdaten
    "https://www.bundestag.de:8443/",              # anderer Port
    "https://www.bundestag.de/suche?q=Mustermann", # Parameter (könnten Falldaten tragen)
])
def test_scrape_and_crawl_reject_unapproved_targets(svc, monkeypatch, url):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "dummy")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **k: pytest.fail("kein Netzaufruf erwartet"))
    for op in ("firecrawl_scrape", "firecrawl_crawl"):
        with pytest.raises(ValueError):
            svc._firecrawl(op, url)


def test_no_call_without_key_and_unknown_operation(svc, monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **k: pytest.fail("kein Netzaufruf ohne Schlüssel"))
    with pytest.raises(RuntimeError, match="key missing"):
        svc._firecrawl("firecrawl_scrape", "https://www.bundestag.de/")
    with pytest.raises(ValueError):
        svc._firecrawl("firecrawl_map", "https://www.bundestag.de/")


def test_scrape_sends_privacy_options_and_bounds_response(svc, monkeypatch):
    sent = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(self, req, timeout=None):
        sent["url"], sent["body"], sent["auth"] = req.full_url, json.loads(req.data), req.headers.get("Authorization")
        return Resp(json.dumps({"success": True, "data": {"url": "https://www.bundestag.de/", "markdown": "Text"}}).encode())

    monkeypatch.setenv("FIRECRAWL_API_KEY", "geheim")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    svc._firecrawl("firecrawl_scrape", "https://www.bundestag.de/")
    assert sent["url"] == "https://api.firecrawl.dev/v2/scrape" and sent["auth"] == "Bearer geheim"
    assert sent["body"]["storeInCache"] is False and sent["body"]["redactPII"] is True and sent["body"]["onlyMainContent"] is True

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda self, req, timeout=None: Resp(b"x" * 2_000_001))
    with pytest.raises(ValueError, match="too large"):
        svc._firecrawl("firecrawl_scrape", "https://www.bundestag.de/")


def test_results_from_other_sites_are_dropped(svc):
    payload = {"success": True, "data": {"web": [
        {"url": "https://www.bundestag.de/a", "title": "Drucksache", "description": "Text"},
        {"url": "https://tracker.example/a", "title": "fremd"},
        {"url": "http://www.bundestag.de/b", "title": "ohne https"},
        {"url": "https://user@www.who.int/x", "title": "mit Zugangsdaten"}]}}
    out = svc._normalize_payload("firecrawl_search", payload, "site:www.bundestag.de x")
    assert [r["url"] for r in out] == ["https://www.bundestag.de/a"]
    assert svc._normalize_payload("firecrawl_search", {"success": False}, "q") == []


def test_ordinary_german_queries_are_accepted(svc, monkeypatch):
    """Regression: das Muster schloss die Buchstaben „r“ und „n“ aus statt der Zeilenumbrüche (r"[^\\\\r\\\\n]")."""
    seen = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(self, req, timeout=None):
        seen.append(json.loads(req.data)["query"])
        return Resp(json.dumps({"success": True, "data": {"web": []}}).encode())

    monkeypatch.setenv("FIRECRAWL_API_KEY", "dummy")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    for q in ("site:www.bundestag.de Bundestag Drucksache Rüstungsexport", "site:www.destatis.de Bevölkerung nach Ländern"):
        svc._firecrawl("firecrawl_search", q)
    assert len(seen) == 2


def test_firecrawl_is_registered_as_key_required_and_review_first():
    fire = [c for c in rp.REAL_CONNECTORS if c.connector_key.startswith("firecrawl_")]
    assert {c.connector_key for c in fire} == {"firecrawl_search", "firecrawl_scrape", "firecrawl_crawl"}
    assert all(c.requires_api_key and c.env_var_name == "FIRECRAWL_API_KEY" for c in fire)
