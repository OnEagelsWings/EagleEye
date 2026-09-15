from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass
from typing import Any, Iterable

from PIL import Image

POLICY_VERSION = "phase15.image-similarity.v1.local-only"
AHASH_SIZE = 8
DHASH_SIZE = 8
EMBED_RGB_SIZE = (4, 4)
EMBED_LUMA_SIZE = (8, 6)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bits_to_hex(bits: Iterable[bool]) -> str:
    value = 0
    count = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
        count += 1
    width = max(1, (count + 3) // 4)
    return f"{value:0{width}x}"


def _hex_hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        raise ValueError("hash_length_mismatch")
    return (int(a, 16) ^ int(b, 16)).bit_count()


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 1e-12:
        return [0.0 for _ in values]
    return [round(v / norm, 8) for v in values]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("embedding_shape_mismatch")
    av = math.sqrt(sum(v * v for v in a)); bv = math.sqrt(sum(v * v for v in b))
    if av <= 1e-12 or bv <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (av * bv)))


def _open_rgb(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(bytes(data))) as img:
        img.seek(0)
        return img.convert("RGB")


def average_hash(data: bytes) -> str:
    img = _open_rgb(data).convert("L").resize((AHASH_SIZE, AHASH_SIZE), Image.Resampling.LANCZOS)
    vals = list(img.getdata())
    avg = sum(vals) / len(vals)
    return _bits_to_hex(v >= avg for v in vals)


def difference_hash(data: bytes) -> str:
    img = _open_rgb(data).convert("L").resize((DHASH_SIZE + 1, DHASH_SIZE), Image.Resampling.LANCZOS)
    vals = list(img.getdata())
    bits: list[bool] = []
    row_width = DHASH_SIZE + 1
    for y in range(DHASH_SIZE):
        base = y * row_width
        for x in range(DHASH_SIZE):
            bits.append(vals[base + x] > vals[base + x + 1])
    return _bits_to_hex(bits)


def local_embedding(data: bytes) -> list[float]:
    """Deterministic handcrafted local visual descriptor, not a semantic/identity embedding."""
    img = _open_rgb(data)
    rgb = img.resize(EMBED_RGB_SIZE, Image.Resampling.LANCZOS)
    rgb_vals: list[float] = []
    for r, g, b in list(rgb.getdata()):
        rgb_vals.extend([(float(r) - 127.5) / 127.5, (float(g) - 127.5) / 127.5, (float(b) - 127.5) / 127.5])
    lum = img.convert("L").resize(EMBED_LUMA_SIZE, Image.Resampling.LANCZOS)
    lvals = [(float(v) - 127.5) / 127.5 for v in list(lum.getdata())]
    return _normalize(rgb_vals + lvals)


@dataclass(frozen=True)
class SimilarityThresholds:
    exact_ahash_distance: int = 0
    near_ahash_distance: int = 8
    near_dhash_distance: int = 8
    variant_dhash_distance: int = 12
    near_cosine: float = 0.94
    variant_cosine: float = 0.88


class ImageSimilarity354:
    """Pure local image similarity. No face identity, geolocation, network, or database access."""

    def __init__(self, *, thresholds: SimilarityThresholds | None = None) -> None:
        self.thresholds = thresholds or SimilarityThresholds()

    def fingerprint(self, data: bytes) -> dict[str, Any]:
        raw = bytes(data)
        if not raw:
            raise ValueError("empty_image")
        return {
            "policy": POLICY_VERSION,
            "sha256": _sha(raw),
            "ahash64": average_hash(raw),
            "dhash64": difference_hash(raw),
            "local_embedding_v1": local_embedding(raw),
            "embedding_kind": "handcrafted_visual_descriptor_not_identity_or_biometric_embedding",
            "network_used": False,
        }

    def compare_fingerprints(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        exact = bool(left.get("sha256") and left.get("sha256") == right.get("sha256"))
        ah = _hex_hamming(str(left["ahash64"]), str(right["ahash64"]))
        dh = _hex_hamming(str(left["dhash64"]), str(right["dhash64"]))
        cos = round(_cosine(list(left["local_embedding_v1"]), list(right["local_embedding_v1"])), 6)
        if exact:
            relation = "exact_duplicate_candidate"
        elif ah <= self.thresholds.near_ahash_distance and dh <= self.thresholds.near_dhash_distance and cos >= self.thresholds.near_cosine:
            relation = "near_duplicate_candidate"
        elif dh <= self.thresholds.variant_dhash_distance and cos >= self.thresholds.variant_cosine:
            relation = "visual_variant_candidate"
        else:
            relation = "no_similarity_lead"
        return {
            "policy": POLICY_VERSION,
            "relation": relation,
            "exact_sha256": exact,
            "ahash_hamming": ah,
            "dhash_hamming": dh,
            "local_embedding_cosine": cos,
            "requires_human_review": relation != "no_similarity_lead",
            "identity_confirmed": False,
            "same_person_confirmed": False,
            "same_location_confirmed": False,
            "same_source_confirmed": False,
        }

    def compare_bytes(self, left: bytes, right: bytes) -> dict[str, Any]:
        return self.compare_fingerprints(self.fingerprint(left), self.fingerprint(right))

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY_VERSION,
            "exact_sha256": True,
            "average_hash_64": True,
            "difference_hash_64": True,
            "local_embedding": True,
            "embedding_kind": "handcrafted_visual_descriptor_not_identity_or_biometric_embedding",
            "direct_network": False,
            "direct_database": False,
            "face_identity": False,
            "geolocation": False,
        }
