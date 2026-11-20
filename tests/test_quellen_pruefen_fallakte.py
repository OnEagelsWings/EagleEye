"""Prüfwerkzeug für die Quellen der Fallakte: eine Testabfrage je Quelle, nichts gespeichert, Zustände richtig eingeordnet."""
import importlib.util
from pathlib import Path
from urllib.parse import urlsplit

from eagleeye.infrastructure.providers import ProviderTransportError, ProviderTransportResponse, ProviderValidationError
from eagleeye.infrastructure.providers.adapters import default_adapters

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("quellen_pruefen_fallakte", ROOT / "tools" / "quellen_pruefen_fallakte.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class FakeTransport:
    def __init__(self):
        self.calls = []

    def fetch(self, request, *, allowed_hosts, timeout_seconds, max_response_bytes):
        host = urlsplit(request.url).hostname
        self.calls.append(host)
        assert host in allowed_hosts and request.method == "GET"
        assert not {k.casefold() for k in request.headers} & {"authorization", "cookie", "x-api-key"}
        if host == "lobid.org":
            raise ProviderValidationError("provider DNS resolution failed: lobid.org")
        if host == "api.gleif.org":
            raise ProviderTransportError("timed out")
        status = {"api.crossref.org": 429, "api.github.com": 403, "hub.docker.com": 404}.get(host, 200)
        return ProviderTransportResponse(request.url, request.url, status, {"Content-Type": "application/json"}, b"{}")


def test_every_source_gets_at_most_one_safe_request_and_clear_state(tmp_path, capsys):
    adapters = default_adapters()
    transport = FakeTransport()
    rows = {r["key"]: r for r in (tool.check(a, transport) for a in adapters)}
    assert len(transport.calls) <= len(adapters)
    assert rows["lobid_gnd_persons_public_501"]["state"] == "nicht erreichbar"
    assert rows["gleif_lei_public_135"]["state"] == "nicht erreichbar"
    assert rows["crossref_topics_public_501"]["state"] == "gebremst"
    assert rows["github_public_profile_120"]["state"] == "abgewiesen"
    # Kontoquelle des PersonOSINT-Motors: 404 heißt „gibt es nicht“ – die Quelle antwortet.
    assert rows["personosint_dockerhub_501"]["state"] == "antwortet"
    assert sum(r["state"] == "antwortet" for r in rows.values()) >= 30
    # Testbegriffe sind unkritisch (keine echten Zielpersonen außer einer bekannten historischen Person).
    assert {r.get("query") for r in rows.values()} <= set(tool.TEST_QUERIES) | {None}
    text = tool.report(list(rows.values()))
    assert text.startswith("# Quellen der EagleEye-Fallakte") and "| GND / lobid – Personen | nicht erreichbar |" in text
