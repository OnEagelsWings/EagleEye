"""Build 493: one-way, review-only intake of PersonOSINT 1.4 case JSON exports.

Never attach a foreign case database, infer shared identity, import permissions,
or promote a PersonOSINT finding to verified Evidence or a confirmed graph edge.
Only bounded public HTTPS leads can cross this interoperability boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.parse import urlsplit

MAX_EXPORT_BYTES = 1_000_000
MAX_FINDINGS = 2_000
MAX_LEADS = 50
REJECTED = {"verworfen", "abgelehnt", "rejected", "discarded"}


class PersonOSINTImportError(ValueError):
    """Malformed, oversized or unsupported external case data."""


@dataclass(frozen=True)
class ProposedLead:
    url: str
    title: str
    note: str


@dataclass(frozen=True)
class ImportPreview:
    foreign_case: str
    leads: tuple[ProposedLead, ...]
    skipped: int


def _single_line(value: object, limit: int) -> str:
    if not isinstance(value, (str, int)):
        return ""
    return " ".join(str(value).split())[:limit]


def parse_personosint_export(raw: bytes) -> ImportPreview:
    """Parse the actual PersonOSINT /api/cases/{id}/export/case.json layout.

    The source file is never persisted. Only public link leads are returned.
    Case ownership, source reliability and prior reviews are NOT inherited.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EXPORT_BYTES:
        raise PersonOSINTImportError("PersonOSINT JSON must be between 1 byte and 1 MB.")
    try:
        document = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError) as exc:
        raise PersonOSINTImportError("Invalid UTF-8 JSON export.") from exc
    if not isinstance(document, dict):
        raise PersonOSINTImportError("Expected one PersonOSINT case export object.")
    case = document.get("case")
    findings = document.get("findings")
    if not isinstance(case, dict) or not isinstance(findings, list):
        raise PersonOSINTImportError("Missing PersonOSINT case or findings list.")
    case_ref = _single_line(case.get("reference") or case.get("id"), 80)
    if not case_ref:
        raise PersonOSINTImportError("Export case identifier is missing.")
    if len(findings) > MAX_FINDINGS:
        raise PersonOSINTImportError("Too many source findings for one controlled import.")

    leads: list[ProposedLead] = []
    seen: set[str] = set()
    skipped = 0
    for item in findings:
        if not isinstance(item, dict):
            skipped += 1
            continue
        status = _single_line(item.get("status"), 50).casefold()
        url = _single_line(item.get("url"), 1801)
        if status in REJECTED or not url or len(url) > 1800:
            skipped += 1
            continue
        try:
            parsed = urlsplit(url)
            eligible = (parsed.scheme == "https" and bool(parsed.hostname) and
                        not parsed.username and not parsed.password and
                        parsed.port in (None, 443))
        except ValueError:
            eligible = False
        if not eligible or url in seen:
            skipped += 1
            continue
        title = _single_line(item.get("title"), 240) or "PersonOSINT Recherchefund"
        if len(title) < 4:
            title = "PersonOSINT Recherchefund"
        source = _single_line(item.get("source"), 100) or "nicht angegeben"
        note = ("Externer PersonOSINT-Fallexport " + case_ref + "; Quelle: " + source +
                "; vorheriger Trefferstatus: " + (status or "unbekannt") +
                ". Nur ungeprüfter Suchhinweis; kein Beleg und kein Identitätsnachweis.")
        leads.append(ProposedLead(url=url, title=title, note=note[:1600]))
        seen.add(url)
        if len(leads) > MAX_LEADS:
            raise PersonOSINTImportError("More than 50 usable leads; split the import into reviewed batches.")
    if not leads:
        raise PersonOSINTImportError("No public HTTPS source leads found in the export.")
    return ImportPreview(foreign_case=case_ref, leads=tuple(leads), skipped=skipped)
