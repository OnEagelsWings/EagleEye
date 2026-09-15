from __future__ import annotations

import hashlib
import io
import json
import shutil
import warnings
from dataclasses import dataclass
from typing import Any, Callable

from PIL import ExifTags, Image, IptcImagePlugin

POLICY_VERSION = "phase15.image-intelligence.v1.secure-ingest"
MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_DIMENSION = 12_000
MAX_FRAMES = 50
MAX_METADATA_ITEMS = 512
MAX_METADATA_TEXT = 4096
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "TIFF", "BMP"}
FORMAT_MEDIA = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "TIFF": "image/tiff",
    "BMP": "image/bmp",
}


class ImageInspectionError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return {"binary_sha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
    text = str(value)
    return text[:MAX_METADATA_TEXT]


def _safe_tree(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "<depth-limit>"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= MAX_METADATA_ITEMS:
                out["<truncated>"] = True
                break
            out[str(k)[:160]] = _safe_tree(v, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_safe_tree(v, depth=depth + 1) for v in list(value)[:MAX_METADATA_ITEMS]]
    return _safe_scalar(value)


def _detect_magic(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG", "image/png"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "GIF", "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP", "image/webp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "TIFF", "image/tiff"
    if data.startswith(b"BM"):
        return "BMP", "image/bmp"
    raise ImageInspectionError("unsupported_or_missing_raster_magic")


def _rational(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        try:
            return float(value.numerator) / float(value.denominator)
        except Exception as exc:
            raise ValueError("invalid rational") from exc


def _gps_decimal(gps: dict[str, Any]) -> dict[str, float] | None:
    try:
        lat = gps.get("GPSLatitude")
        lon = gps.get("GPSLongitude")
        lat_ref = str(gps.get("GPSLatitudeRef") or "").upper()
        lon_ref = str(gps.get("GPSLongitudeRef") or "").upper()
        if not isinstance(lat, (list, tuple)) or not isinstance(lon, (list, tuple)) or len(lat) < 3 or len(lon) < 3:
            return None
        la = _rational(lat[0]) + _rational(lat[1]) / 60.0 + _rational(lat[2]) / 3600.0
        lo = _rational(lon[0]) + _rational(lon[1]) / 60.0 + _rational(lon[2]) / 3600.0
        if lat_ref == "S":
            la *= -1
        if lon_ref == "W":
            lo *= -1
        if not (-90 <= la <= 90 and -180 <= lo <= 180):
            return None
        return {"latitude": round(la, 8), "longitude": round(lo, 8)}
    except Exception:
        return None


def _extract_exif(img: Image.Image) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    warnings_out: list[str] = []
    facts: dict[str, Any] = {}
    gps_named: dict[str, Any] = {}
    try:
        exif = img.getexif()
        for key, value in list(exif.items())[:MAX_METADATA_ITEMS]:
            name = ExifTags.TAGS.get(key, str(key))
            if name == "GPSInfo":
                continue
            facts[str(name)] = _safe_tree(value)
        try:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, "IFD") else {}
        except Exception:
            gps_ifd = {}
        for key, value in list((gps_ifd or {}).items())[:64]:
            gps_named[str(ExifTags.GPSTAGS.get(key, key))] = _safe_tree(value)
    except Exception as exc:
        warnings_out.append(f"exif_parse:{type(exc).__name__}")
    gps = {"raw_metadata": gps_named, "decimal_derivation": _gps_decimal(gps_named)} if gps_named else None
    return facts, gps, warnings_out


def _extract_iptc(img: Image.Image) -> tuple[dict[str, Any], list[str]]:
    warnings_out: list[str] = []
    out: dict[str, Any] = {}
    try:
        raw = IptcImagePlugin.getiptcinfo(img) or {}
        for idx, (key, value) in enumerate(raw.items()):
            if idx >= MAX_METADATA_ITEMS:
                break
            if isinstance(key, tuple):
                name = f"{key[0]}:{key[1]}"
            else:
                name = str(key)
            if isinstance(value, bytes):
                try:
                    out[name] = value.decode("utf-8")[:MAX_METADATA_TEXT]
                except Exception:
                    out[name] = _safe_tree(value)
            elif isinstance(value, list):
                vals = []
                for item in value[:64]:
                    if isinstance(item, bytes):
                        try: vals.append(item.decode("utf-8")[:MAX_METADATA_TEXT])
                        except Exception: vals.append(_safe_tree(item))
                    else: vals.append(_safe_tree(item))
                out[name] = vals
            else:
                out[name] = _safe_tree(value)
    except Exception as exc:
        warnings_out.append(f"iptc_parse:{type(exc).__name__}")
    return out, warnings_out


def _extract_xmp(img: Image.Image) -> tuple[dict[str, Any], list[str]]:
    warnings_out: list[str] = []
    out: dict[str, Any] = {}
    try:
        getter = getattr(img, "getxmp", None)
        if callable(getter):
            xmp = getter() or {}
            if isinstance(xmp, dict):
                out = _safe_tree(xmp)
    except Exception as exc:
        warnings_out.append(f"xmp_parse:{type(exc).__name__}")
    return out, warnings_out


@dataclass(frozen=True)
class ImageLimits:
    max_input_bytes: int = MAX_INPUT_BYTES
    max_pixels: int = MAX_PIXELS
    max_dimension: int = MAX_DIMENSION
    max_frames: int = MAX_FRAMES


class ImageIntelligenceAgent353:
    """Pure local image analysis. No network, identity confirmation, or geolocation inference.

    The agent receives bytes from a controlled caller. It does not fetch files itself and does
    not mutate the database. Persistence/review remains in the application service.
    """

    def __init__(self, *, limits: ImageLimits | None = None) -> None:
        self.limits = limits or ImageLimits()

    def inspect_bytes(self, data: bytes, *, declared_media_type: str = "", filename: str = "") -> dict[str, Any]:
        raw = bytes(data)
        if not raw:
            raise ImageInspectionError("empty_image")
        if len(raw) > self.limits.max_input_bytes:
            raise ImageInspectionError("image_input_too_large")
        magic_format, magic_media = _detect_magic(raw)
        declared = str(declared_media_type or "").split(";", 1)[0].strip().lower()
        reason_codes: list[str] = []
        if declared and declared != magic_media:
            reason_codes.append("declared_mime_magic_mismatch")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as probe:
                    fmt = str(probe.format or "").upper()
                    width, height = map(int, probe.size)
                    frames = int(getattr(probe, "n_frames", 1) or 1)
                    mode = str(probe.mode or "")
                    if fmt not in SUPPORTED_FORMATS or fmt != magic_format:
                        raise ImageInspectionError("decoder_magic_format_mismatch")
                    if width <= 0 or height <= 0 or width > self.limits.max_dimension or height > self.limits.max_dimension:
                        raise ImageInspectionError("image_dimensions_out_of_bounds")
                    if width * height > self.limits.max_pixels:
                        raise ImageInspectionError("image_pixel_budget_exceeded")
                    if frames > self.limits.max_frames:
                        raise ImageInspectionError("image_frame_budget_exceeded")
                    probe.verify()
        except Image.DecompressionBombWarning as exc:
            raise ImageInspectionError("decompression_bomb_warning") from exc
        except Image.DecompressionBombError as exc:
            raise ImageInspectionError("decompression_bomb_error") from exc
        except ImageInspectionError:
            raise
        except Exception as exc:
            raise ImageInspectionError(f"decoder_verify_failed:{type(exc).__name__}") from exc

        metadata_warnings: list[str] = []
        with Image.open(io.BytesIO(raw)) as img:
            exif, gps, w1 = _extract_exif(img)
            iptc, w2 = _extract_iptc(img)
            xmp, w3 = _extract_xmp(img)
            metadata_warnings.extend(w1 + w2 + w3)

        observations: list[dict[str, Any]] = [
            {"kind": "metadata_fact", "namespace": "container", "field": "sha256", "value": _sha(raw)},
            {"kind": "metadata_fact", "namespace": "container", "field": "format", "value": magic_format},
            {"kind": "metadata_fact", "namespace": "container", "field": "media_type", "value": magic_media},
            {"kind": "metadata_fact", "namespace": "container", "field": "width", "value": width},
            {"kind": "metadata_fact", "namespace": "container", "field": "height", "value": height},
            {"kind": "metadata_fact", "namespace": "container", "field": "frames", "value": frames},
        ]
        for key, value in list(exif.items())[:MAX_METADATA_ITEMS]:
            observations.append({"kind": "metadata_fact", "namespace": "exif", "field": key, "value": value})
        if gps and gps.get("raw_metadata"):
            observations.append({"kind": "metadata_fact", "namespace": "exif.gps", "field": "raw_gps", "value": gps["raw_metadata"]})
        if gps and gps.get("decimal_derivation"):
            observations.append({
                "kind": "deterministic_derivation",
                "namespace": "exif.gps",
                "field": "decimal_coordinates",
                "value": gps["decimal_derivation"],
                "derived_from": "embedded_EXIF_GPS_metadata",
                "not_visual_geolocation": True,
            })
        disposition = "quarantine" if reason_codes else "review_pending"
        return {
            "policy": POLICY_VERSION,
            "sha256": _sha(raw),
            "size_bytes": len(raw),
            "filename": str(filename or "")[:260],
            "declared_media_type": declared,
            "magic_media_type": magic_media,
            "format": magic_format,
            "width": width,
            "height": height,
            "pixels": width * height,
            "frames": frames,
            "mode": mode,
            "disposition": disposition,
            "reason_codes": reason_codes,
            "exif": exif,
            "iptc": iptc,
            "xmp": xmp,
            "gps": gps,
            "metadata_warnings": metadata_warnings,
            "observations": observations,
            "epistemic_boundaries": {
                "metadata_is_not_identity_confirmation": True,
                "embedded_gps_is_not_visual_geolocation": True,
                "visual_city_guess_generated": False,
                "face_identity_confirmation": False,
                "reverse_image_search_performed": False,
                "manipulation_authenticity_conclusion": False,
            },
        }

    def ocr(self, data: bytes, *, backend: Callable[[Image.Image], str] | None = None, language: str = "eng") -> dict[str, Any]:
        inspection = self.inspect_bytes(data)
        with Image.open(io.BytesIO(bytes(data))) as img:
            safe = img.convert("RGB")
            if backend is not None:
                text = str(backend(safe) or "")
                engine = "injected_local_test_backend"
                engine_available = True
            else:
                if shutil.which("tesseract") is None:
                    return {
                        "policy": POLICY_VERSION,
                        "status": "unavailable",
                        "engine": "tesseract",
                        "engine_available": False,
                        "text": "",
                        "requires_human_review": True,
                        "classification": "derived_text_not_metadata",
                    }
                try:
                    import pytesseract  # type: ignore
                    text = str(pytesseract.image_to_string(safe, lang=language, config="--psm 6") or "")
                    engine = "tesseract_local"
                    engine_available = True
                except Exception as exc:
                    return {
                        "policy": POLICY_VERSION,
                        "status": "error",
                        "engine": "tesseract_local",
                        "engine_available": True,
                        "error": f"{type(exc).__name__}:{exc}"[:500],
                        "text": "",
                        "requires_human_review": True,
                        "classification": "derived_text_not_metadata",
                    }
        text = text[:200_000]
        return {
            "policy": POLICY_VERSION,
            "status": "completed",
            "engine": engine,
            "engine_available": engine_available,
            "image_sha256": inspection["sha256"],
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
            "requires_human_review": True,
            "classification": "derived_text_not_metadata",
            "not_identity_confirmation": True,
            "not_geolocation_fact": True,
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY_VERSION,
            "supported_formats": sorted(SUPPORTED_FORMATS),
            "max_input_bytes": self.limits.max_input_bytes,
            "max_pixels": self.limits.max_pixels,
            "max_dimension": self.limits.max_dimension,
            "max_frames": self.limits.max_frames,
            "local_ocr_available": shutil.which("tesseract") is not None,
            "network_access": False,
            "face_identity_confirmation": False,
            "visual_geolocation": False,
            "reverse_image_search": False,
        }
