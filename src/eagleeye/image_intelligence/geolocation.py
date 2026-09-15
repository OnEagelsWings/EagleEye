from __future__ import annotations

import datetime as _dt
import io
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from PIL import Image

POLICY_VERSION = "phase15.visual-geolocation.v1.hypothesis-only"
MANIPULATION_POLICY_VERSION = "phase15.image-manipulation-signals.v1.non-conclusive"
ALLOWED_CUE_KINDS = {
    "ocr_placename",
    "visual_clue",
    "analyst_observation",
    "local_landmark_reference",
    "source_context",
}
MAX_CUES = 64
MAX_HYPOTHESES = 12


def _clamp01(value: Any) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, v))


def _norm_text(value: Any, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _parse_exif_dt(value: Any) -> _dt.datetime | None:
    text = _norm_text(value, 64)
    if not text:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return _dt.datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


@dataclass(frozen=True)
class GeoCue:
    kind: str
    label: str
    confidence: float
    source_ref: str = ""
    city: str = ""
    country: str = ""
    latitude: float | None = None
    longitude: float | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "GeoCue":
        kind = _norm_text(value.get("kind"), 80).lower()
        if kind not in ALLOWED_CUE_KINDS:
            raise ValueError("unsupported_visual_cue_kind")
        label = _norm_text(value.get("label"), 240)
        if not label:
            raise ValueError("visual_cue_label_required")
        confidence = _clamp01(value.get("confidence", 0.0))
        lat = value.get("latitude")
        lon = value.get("longitude")
        lat_f = float(lat) if lat is not None else None
        lon_f = float(lon) if lon is not None else None
        if lat_f is not None and not -90 <= lat_f <= 90:
            raise ValueError("invalid_visual_cue_latitude")
        if lon_f is not None and not -180 <= lon_f <= 180:
            raise ValueError("invalid_visual_cue_longitude")
        return cls(
            kind=kind,
            label=label,
            confidence=confidence,
            source_ref=_norm_text(value.get("source_ref"), 500),
            city=_norm_text(value.get("city"), 160),
            country=_norm_text(value.get("country"), 160),
            latitude=lat_f,
            longitude=lon_f,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "confidence": round(self.confidence, 6),
            "source_ref": self.source_ref,
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "classification": "visual_indication",
            "requires_human_review": True,
            "scene_location_confirmed": False,
        }


class VisualGeoManipulation355:
    """Pure-local conservative visual geolocation and technical-signal analysis.

    This component does not fetch external data, identify people, or declare authenticity.
    Visual location outputs are hypotheses. Embedded GPS remains metadata evidence only.
    """

    def technical_signals(self, data: bytes, *, inspection: dict[str, Any]) -> dict[str, Any]:
        raw = bytes(data)
        signals: list[dict[str, Any]] = []
        exif = inspection.get("exif") if isinstance(inspection.get("exif"), dict) else {}
        reasons = set(str(x) for x in inspection.get("reason_codes") or [])

        if "declared_mime_magic_mismatch" in reasons:
            signals.append({
                "signal": "declared_mime_magic_mismatch",
                "classification": "technical_manipulation_signal",
                "strength": "medium",
                "explanation": "Declared media type differs from decoded raster magic.",
            })

        software = _norm_text(exif.get("Software"), 240)
        if software:
            signals.append({
                "signal": "editing_software_metadata_present",
                "classification": "technical_manipulation_signal",
                "strength": "low",
                "value": software,
                "explanation": "Software metadata may indicate processing, but does not prove deceptive manipulation.",
            })

        original = _parse_exif_dt(exif.get("DateTimeOriginal"))
        digitized = _parse_exif_dt(exif.get("DateTimeDigitized"))
        modified = _parse_exif_dt(exif.get("DateTime"))
        if original and digitized and original > digitized:
            signals.append({
                "signal": "exif_original_after_digitized",
                "classification": "technical_manipulation_signal",
                "strength": "medium",
                "explanation": "EXIF chronology is internally inconsistent.",
            })
        if original and modified and modified < original:
            signals.append({
                "signal": "exif_modified_before_original",
                "classification": "technical_manipulation_signal",
                "strength": "medium",
                "explanation": "EXIF modification time precedes capture time.",
            })

        try:
            with Image.open(io.BytesIO(raw)) as img:
                quant = getattr(img, "quantization", None)
                if isinstance(quant, dict) and quant:
                    signals.append({
                        "signal": "jpeg_quantization_present",
                        "classification": "technical_encoding_observation",
                        "strength": "informational",
                        "table_count": len(quant),
                        "explanation": "JPEG quantization tables are encoding observations, not evidence of manipulation.",
                    })
                if getattr(img, "n_frames", 1) and int(getattr(img, "n_frames", 1)) > 1:
                    signals.append({
                        "signal": "multi_frame_raster",
                        "classification": "technical_encoding_observation",
                        "strength": "informational",
                        "frames": int(getattr(img, "n_frames", 1)),
                    })
        except Exception:
            signals.append({
                "signal": "secondary_decoder_inspection_unavailable",
                "classification": "technical_analysis_limit",
                "strength": "informational",
            })

        return {
            "policy": MANIPULATION_POLICY_VERSION,
            "signals": signals,
            "signal_count": len(signals),
            "manipulation_confirmed": False,
            "authenticity_confirmed": False,
            "forgery_claim_allowed": False,
            "requires_human_review": bool(signals),
            "epistemic_note": "Technical signals can motivate review but cannot by themselves establish deceptive editing or authenticity.",
            "network_used": False,
        }

    def geolocation(self, *, inspection: dict[str, Any], cues: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
        clean: list[GeoCue] = []
        for raw in list(cues)[:MAX_CUES]:
            if not isinstance(raw, dict):
                continue
            clean.append(GeoCue.from_mapping(raw))

        gps_fact: dict[str, Any] | None = None
        gps = inspection.get("gps") if isinstance(inspection.get("gps"), dict) else None
        if gps and isinstance(gps.get("decimal_derivation"), dict):
            d = gps["decimal_derivation"]
            try:
                lat = float(d["latitude"]); lon = float(d["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    gps_fact = {
                        "classification": "deterministic_derivation_from_metadata",
                        "latitude": lat,
                        "longitude": lon,
                        "source": "embedded_exif_gps",
                        "scene_location_confirmed": False,
                        "requires_human_review": True,
                    }
            except Exception:
                gps_fact = None

        grouped: dict[str, list[GeoCue]] = {}
        for cue in clean:
            key = (cue.city + "|" + cue.country).casefold().strip("|")
            if not key and cue.latitude is not None and cue.longitude is not None:
                key = f"{round(cue.latitude, 3)}|{round(cue.longitude, 3)}"
            if not key:
                key = cue.label.casefold()
            grouped.setdefault(key, []).append(cue)

        hypotheses: list[dict[str, Any]] = []
        for key, items in grouped.items():
            kinds = sorted({c.kind for c in items})
            independent = len(kinds)
            raw_score = sum(c.confidence for c in items) / max(1, len(items))
            cap = 0.65 if independent <= 1 else 0.82 if independent == 2 else 0.9
            score = min(cap, raw_score + min(0.12, 0.04 * max(0, independent - 1)))
            exemplar = max(items, key=lambda c: c.confidence)
            hypotheses.append({
                "classification": "geolocation_hypothesis",
                "candidate_key": key,
                "label": exemplar.label,
                "city": exemplar.city,
                "country": exemplar.country,
                "latitude": exemplar.latitude,
                "longitude": exemplar.longitude,
                "confidence": round(score, 6),
                "independent_cue_kinds": kinds,
                "cue_count": len(items),
                "cues": [c.as_dict() for c in items],
                "requires_human_review": True,
                "scene_location_confirmed": False,
            })

        if gps_fact:
            gps_coord = (gps_fact["latitude"], gps_fact["longitude"])
            for h in hypotheses:
                if h.get("latitude") is not None and h.get("longitude") is not None:
                    km = _distance_km(gps_coord, (float(h["latitude"]), float(h["longitude"])))
                    h["distance_to_embedded_gps_km"] = round(km, 3)
                    h["gps_consistency"] = "consistent" if km <= 25 else "inconsistent"

        hypotheses.sort(key=lambda h: (-float(h["confidence"]), -int(h["cue_count"]), str(h["candidate_key"])))
        hypotheses = hypotheses[:MAX_HYPOTHESES]
        return {
            "policy": POLICY_VERSION,
            "embedded_gps": gps_fact,
            "visual_cues": [c.as_dict() for c in clean],
            "hypotheses": hypotheses,
            "unknown_is_valid": True,
            "scene_location_confirmed": False,
            "metadata_gps_is_not_scene_confirmation": True,
            "network_used": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY_VERSION,
            "metadata_gps_preserved_as_metadata": True,
            "visual_cues_supported": sorted(ALLOWED_CUE_KINDS),
            "geolocation_output": "hypothesis_only",
            "unknown_is_valid": True,
            "landmark_reference_similarity": "candidate_only",
            "manipulation_signal_policy": MANIPULATION_POLICY_VERSION,
            "manipulation_confirmed": False,
            "authenticity_confirmed": False,
            "direct_network": False,
            "direct_database": False,
            "face_identity": False,
        }
