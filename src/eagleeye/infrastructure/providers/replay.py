from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .contracts import ProviderReplayError, ProviderTransportResponse
from .policy import redact_url_secrets, sanitize_mapping


class ReplayFixtureStore:
    """Content-addressed sanitized provider response fixtures."""

    SAFE_RESPONSE_HEADERS = {
        "cache-control", "content-language", "content-length", "content-type", "date",
        "etag", "last-modified", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
        "x-ratelimit-reset",
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def request_fingerprint(provider_key: str, url: str) -> str:
        material = f"{provider_key}\0GET\0{redact_url_secrets(url)}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _sanitized_json_body(response: ProviderTransportResponse) -> bytes:
        try:
            decoded = response.body.decode("utf-8")
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderReplayError(
                "replay recording requires a JSON response that can be safely sanitized"
            ) from exc
        sanitized = sanitize_mapping(parsed)
        return json.dumps(
            sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def save(
        self,
        provider_key: str,
        response: ProviderTransportResponse,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fingerprint = self.request_fingerprint(provider_key, response.requested_url)
        sanitized_body = self._sanitized_json_body(response)
        payload = {
            "format": "eagleeye-provider-replay-120-v1",
            "provider_key": provider_key,
            "request_fingerprint": fingerprint,
            "requested_url": redact_url_secrets(response.requested_url),
            "final_url": redact_url_secrets(response.final_url),
            "status_code": int(response.status_code),
            "headers": {
                str(key): str(value)
                for key, value in response.headers.items()
                if str(key).casefold() in self.SAFE_RESPONSE_HEADERS
            },
            "body_base64": base64.b64encode(sanitized_body).decode("ascii"),
            "body_sanitized": True,
            "elapsed_ms": int(response.elapsed_ms),
            "metadata": sanitize_mapping(metadata or {}),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        provider_dir = self.root / provider_key
        provider_dir.mkdir(parents=True, exist_ok=True)
        path = provider_dir / f"{fingerprint}_{digest[:16]}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
        return {
            "request_fingerprint": fingerprint,
            "path": str(path),
            "sha256": digest,
            "bytes": len(encoded),
            "response_sha256": hashlib.sha256(sanitized_body).hexdigest(),
            "sanitized": True,
        }

    def load(self, path: str | Path, expected_sha256: str) -> ProviderTransportResponse:
        fixture_path = Path(path)
        try:
            fixture_path.resolve().relative_to(self.root.resolve())
        except ValueError as exc:
            raise ProviderReplayError("replay fixture path escapes provider replay root") from exc
        if not fixture_path.is_file():
            raise ProviderReplayError("replay fixture is missing")
        encoded = fixture_path.read_bytes()
        actual = hashlib.sha256(encoded).hexdigest()
        if actual != expected_sha256:
            raise ProviderReplayError("replay fixture integrity check failed")
        try:
            payload = json.loads(encoded.decode("utf-8"))
            body = base64.b64decode(payload["body_base64"], validate=True)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderReplayError("replay fixture is malformed") from exc
        if payload.get("format") != "eagleeye-provider-replay-120-v1":
            raise ProviderReplayError("unsupported replay fixture format")
        if payload.get("body_sanitized") is not True:
            raise ProviderReplayError("replay fixture is not marked as sanitized")
        return ProviderTransportResponse(
            requested_url=str(payload["requested_url"]),
            final_url=str(payload["final_url"]),
            status_code=int(payload["status_code"]),
            headers={str(k): str(v) for k, v in dict(payload.get("headers", {})).items()},
            body=body,
            elapsed_ms=int(payload.get("elapsed_ms", 0)),
        )
