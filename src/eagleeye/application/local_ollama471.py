"""Bounded Ollama transport for current workspaces without historical service bootstrapping."""
import json
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect blocked", headers, fp)


class LocalOllama471:
    # A numeric literal and fixed port avoid DNS, proxy and arbitrary endpoint routing.
    ENDPOINT = "http://127.0.0.1:11434"
    PATHS = {("GET", "/api/tags"), ("POST", "/api/show"), ("POST", "/api/chat")}

    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, payload=None, *, timeout=5):
        if (method, path) not in self.PATHS:
            raise ValueError("Unsupported local model operation")
        raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        req = urllib.request.Request(self.ENDPOINT + path, data=raw, method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self.opener.open(req, timeout=timeout) as response:
                if "json" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError("Local model returned non-JSON data")
                data = response.read(128_001)
                if len(data) > 128_000:
                    raise ValueError("Local model response exceeds limit")
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError("Local model returned a non-object response")
                return result
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectionError("Local Ollama unavailable") from exc
