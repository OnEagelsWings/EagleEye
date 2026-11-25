"""Dokumente als Belege: PDF, Word, Bild-Scans, Text und E-Mails importieren, seitenweise erschließen
und – wenn Tesseract installiert ist – gescannte Seiten per Texterkennung (OCR) lesbar machen.

Übernommen aus Build 492 (Tool-Auswahl A1) mit zwei bewussten Abweichungen:
* **kein PyMuPDF** (AGPL – laut Lizenzbefund der Tool-Auswahl ein Problem bei Weitergabe); Text über
  ``pypdf`` (BSD), Seitenbilder für OCR über ``pypdfium2`` (Apache-2.0/BSD);
* **Tesseract direkt** statt OCRmyPDF: Das Original bleibt unverändert versiegelt, die erkannte Schrift
  ist eine Lesehilfe mit Seitenangabe und Erkennungssicherheit.

Nichts hiervon bestätigt eine Aussage. Erwähnungen von Fallpersonen sind Hinweise mit Seitenzahl.
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from .db import now_iso
from .matching import fold

MAX_UPLOAD = 25_000_000
MAX_PAGES = 400
MAX_OCR_PAGES = 40
MAX_PAGE_CHARS = 30_000
OCR_DPI = 200
SCAN_THRESHOLD = 40  # weniger Zeichen auf einer PDF-Seite = vermutlich Scan


class DocumentError(Exception):
    pass


# --------------------------------------------------------------------------- Texterkennung

def ocr_status() -> dict[str, Any]:
    """Ist die Texterkennung nutzbar? Liefert Version, Sprachen und einen verständlichen Hinweis."""
    try:
        import pytesseract

        version = str(pytesseract.get_tesseract_version()).splitlines()[0]
        langs = sorted(set(pytesseract.get_languages(config="")) - {"osd"})
    except Exception:  # noqa: BLE001 - Programm oder Python-Baustein fehlt
        return {"available": False, "engine": "", "languages": [],
                "hint": "Texterkennung nicht installiert. Server: Paket „tesseract-ocr“ mit Sprachpaket „deu“ (im Docker-Image mit EAGLEEYE_WITH_OCR=1 "
                        "enthalten). Windows: Tesseract-Installer der UB Mannheim mit Sprache Deutsch."}
    return {"available": True, "engine": f"tesseract {version}", "languages": langs,
            "hint": "" if "deu" in langs else "Sprachpaket Deutsch (deu) fehlt – Umlaute werden schlechter erkannt."}


def _ocr_lang() -> str:
    langs = ocr_status()["languages"]
    return "+".join(x for x in ("deu", "eng") if x in langs) or "eng"


def ocr_image(image) -> tuple[str, float | None]:
    """Erkannter Text (Absätze) und mittlere Wort-Sicherheit in Prozent."""
    import pytesseract

    data = pytesseract.image_to_data(image, lang=_ocr_lang(), config="--psm 3", output_type=pytesseract.Output.DICT)
    paragraphs: dict[tuple[int, int], list[str]] = {}
    conf: list[float] = []
    for i, word in enumerate(data["text"]):
        word = str(word or "").strip()
        try:
            c = float(data["conf"][i])
        except (TypeError, ValueError):
            c = -1.0
        if not word or c < 0:
            continue
        paragraphs.setdefault((data["block_num"][i], data["par_num"][i]), []).append(word)
        conf.append(c)
    text = "\n\n".join(" ".join(words) for _, words in sorted(paragraphs.items()))
    return text, (round(sum(conf) / len(conf), 1) if conf else None)


# --------------------------------------------------------------------------- Formate

def detect(filename: str, content: bytes) -> str:
    head = content[:2048]
    if head.lstrip().startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if "word/document.xml" in z.namelist():
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except zipfile.BadZipFile:
            pass
        raise DocumentError("Dieses Archiv-/Office-Format wird nicht unterstützt (möglich: PDF, DOCX, Bild, Text, E-Mail).")
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    lower = filename.lower()
    sample = content[:8192]
    control = sum(1 for b in sample if b < 9 or 13 < b < 32)
    if b"\x00" in sample or control > len(sample) * 0.02:
        raise DocumentError("Unbekanntes Dateiformat (möglich: PDF, DOCX, Bild, Text, E-Mail).")
    try:
        text = content[:200_000].decode("utf-8")
    except UnicodeDecodeError:
        text = content[:200_000].decode("cp1252", "replace")
    if lower.endswith(".eml") or re.match(r"(?im)^(from|received|return-path|mime-version|message-id):", text[:2000] or ""):
        return "message/rfc822"
    if "<html" in text[:4000].lower() or lower.endswith((".html", ".htm")):
        return "text/html"
    return "text/plain"


def _clip(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text or "").replace("\x00", "")
    return text[:MAX_PAGE_CHARS]


def _pdf_pages(content: bytes, use_ocr: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise DocumentError("Das PDF ist passwortgeschützt und kann nicht gelesen werden.") from None
        total = len(reader.pages)
    except DocumentError:
        raise
    except Exception as exc:  # noqa: BLE001 - defektes PDF
        raise DocumentError(f"Das PDF konnte nicht gelesen werden: {exc}"[:200]) from exc
    if total > MAX_PAGES:
        raise DocumentError(f"Das PDF hat {total} Seiten – maximal {MAX_PAGES} werden unterstützt. Bitte teilen.")
    pages: list[dict[str, Any]] = []
    scans: list[int] = []
    for i in range(total):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:  # noqa: BLE001 - einzelne defekte Seite überspringen
            text = ""
        pages.append({"page": i + 1, "text": _clip(text), "method": "pdf_text"})
        if len(text.strip()) < SCAN_THRESHOLD:
            scans.append(i)
    info = {"pages": total, "scan_pages": len(scans), "ocr_pages": 0, "title": ""}
    try:
        info["title"] = str((reader.metadata or {}).get("/Title") or "").strip()[:200]
    except Exception:  # noqa: BLE001
        pass
    if scans and use_ocr:
        import pypdfium2 as pdfium

        confs: list[float] = []
        pdf = pdfium.PdfDocument(content)
        try:
            for i in scans[:MAX_OCR_PAGES]:
                image = pdf[i].render(scale=OCR_DPI / 72).to_pil()
                text, conf = ocr_image(image)
                if text.strip():
                    pages[i] = {"page": i + 1, "text": _clip(text), "method": "ocr", "confidence": conf}
                    info["ocr_pages"] += 1
                    if conf is not None:
                        confs.append(conf)
        finally:
            pdf.close()
        if confs:
            info["ocr_confidence"] = round(sum(confs) / len(confs), 1)
        if len(scans) > MAX_OCR_PAGES:
            info["hinweis"] = f"Texterkennung auf die ersten {MAX_OCR_PAGES} gescannten Seiten begrenzt."
    elif scans:
        info["hinweis"] = f"{len(scans)} Seite(n) ohne lesbaren Text (vermutlich Scan) – Texterkennung ist nicht installiert."
    return pages, info


def _docx_pages(content: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import docx

    try:
        doc = docx.Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise DocumentError(f"Das Word-Dokument konnte nicht gelesen werden: {exc}"[:200]) from exc
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    title = str(doc.core_properties.title or "").strip()[:200]
    # Word kennt keine festen Seiten – in lesbare Abschnitte teilen, damit Fundstellen auffindbar bleiben
    pages, buf, size = [], [], 0
    for part in parts:
        buf.append(part)
        size += len(part)
        if size >= 3000:
            pages.append({"page": len(pages) + 1, "text": _clip("\n".join(buf)), "method": "docx"})
            buf, size = [], 0
    if buf or not pages:
        pages.append({"page": len(pages) + 1, "text": _clip("\n".join(buf)), "method": "docx"})
    return pages, {"pages": len(pages), "title": title, "seitenangabe": "Abschnitt (Word hat keine festen Seiten)"}


def _image_pages(content: bytes, use_ocr: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except Exception as exc:  # noqa: BLE001 - defekt oder zu groß (Schutz vor Bildbomben greift in Pillow)
        raise DocumentError(f"Das Bild konnte nicht gelesen werden: {exc}"[:200]) from exc
    info: dict[str, Any] = {"pages": 1, "scan_pages": 1, "ocr_pages": 0, "bildgroesse": f"{image.width}×{image.height}"}
    if not use_ocr:
        info["hinweis"] = "Bild ohne Texterkennung gespeichert – Texterkennung ist nicht installiert."
        return [{"page": 1, "text": "", "method": "bild"}], info
    text, conf = ocr_image(image.convert("RGB"))
    info["ocr_pages"] = 1 if text.strip() else 0
    if conf is not None:
        info["ocr_confidence"] = conf
    return [{"page": 1, "text": _clip(text), "method": "ocr", "confidence": conf}], info


def _text_pages(content: bytes, ctype: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("cp1252", "replace")
    info: dict[str, Any] = {}
    if ctype == "message/rfc822":
        msg = email.message_from_string(text, policy=email.policy.default)
        body = msg.get_body(preferencelist=("plain", "html"))
        payload = body.get_content() if body is not None else ""
        if body is not None and body.get_content_type() == "text/html":
            from . import webarchive
            payload = webarchive.extract_main_text(payload, "")["text"]
        head = [f"{k}: {msg.get(k)}" for k in ("From", "To", "Cc", "Date", "Subject", "Message-ID") if msg.get(k)]
        attachments = [part.get_filename() for part in msg.iter_attachments() if part.get_filename()]
        if attachments:
            head.append("Anhänge (nicht importiert): " + ", ".join(attachments))
        info = {"title": str(msg.get("Subject") or "")[:200], "email_von": str(msg.get("From") or "")[:200], "email_datum": str(msg.get("Date") or "")[:60]}
        text = "\n".join(head) + "\n\n" + str(payload)
    elif ctype == "text/html":
        from . import webarchive
        found = webarchive.extract_main_text(text, "")
        info = {"title": found.get("title", "")}
        text = found["text"]
    pages = [{"page": i + 1, "text": text[o:o + 6000], "method": "text"} for i, o in enumerate(range(0, min(len(text), 6000 * MAX_PAGES), 6000))]
    info["pages"] = len(pages) or 1
    return pages or [{"page": 1, "text": "", "method": "text"}], info


def analyse(filename: str, content: bytes, use_ocr: bool | None = None) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Reine Auswertung ohne Speicherung: (Dateityp, Seiten, Angaben)."""
    if not content:
        raise DocumentError("Die Datei ist leer.")
    if len(content) > MAX_UPLOAD:
        raise DocumentError("Die Datei ist größer als 25 MB.")
    ctype = detect(filename, content)
    status = ocr_status()
    use = status["available"] if use_ocr is None else (use_ocr and status["available"])
    if ctype == "application/pdf":
        pages, info = _pdf_pages(content, use)
    elif ctype.endswith("wordprocessingml.document"):
        pages, info = _docx_pages(content)
    elif ctype.startswith("image/"):
        pages, info = _image_pages(content, use)
    else:
        pages, info = _text_pages(content, ctype)
    if info.get("ocr_pages"):
        info["ocr_engine"] = status["engine"]
    return ctype, pages, info


# --------------------------------------------------------------------------- Speichern und Erwähnungen

def import_document(p, case_id: int, filename: str, content: bytes, entity_id: int | None = None, note: str = "") -> dict[str, Any]:
    from .service import current_user

    case = p.get_case(case_id)
    if entity_id:
        p._entity(case_id, entity_id)  # noqa: SLF001
    filename = re.sub(r"[^\w.\- ()äöüÄÖÜß]", "_", Path(filename or "dokument").name)[:120] or "dokument"
    ctype, pages, info = analyse(filename, content)
    digest = hashlib.sha256(content).hexdigest()
    if p.db.one("SELECT id FROM evidence WHERE case_id = ? AND sha256 = ? AND kind = 'dokument'", (case_id, digest)):
        raise DocumentError("Dieses Dokument ist in diesem Fall bereits vorhanden (gleiche Prüfsumme).")
    text = "\n\n".join(pg["text"] for pg in pages).strip()
    title = info.pop("title", "") or Path(filename).stem
    user = current_user.get()
    eid = p.db.insert("evidence", {
        "case_id": case_id, "url": "", "final_url": "", "status": 0, "content_type": ctype, "size": len(content), "sha256": digest,
        "title": title[:300], "excerpt": text[:1500], "file": "", "archive_url": "", "egress": "lokal (Datei-Import)",
        "username": user["username"] if user else "system", "retrieved_at": now_iso(), "note": (note or "")[:500],
        "kind": "dokument", "filename": filename, "meta": info, "entity_id": entity_id})
    folder = Path(p.data_dir) / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    base = f"{eid}_{digest[:16]}"
    (folder / f"{base}.enc").write_bytes(p.vault.encrypt(content))
    (folder / f"{base}.txt.enc").write_bytes(p.vault.encrypt(json.dumps({"pages": pages}, ensure_ascii=False).encode("utf-8")))
    p.db.update("evidence", eid, {"file": f"{base}.enc", "text_file": f"{base}.txt.enc"})
    p.log(case_id, "Dokument importiert", f"{filename} · {info.get('pages', 1)} Seite(n)"
          + (f", {info['ocr_pages']} per Texterkennung" if info.get("ocr_pages") else "") + f" · {len(content)} Bytes · SHA-256 {digest}")
    p.touch(case_id)
    del case
    return p.db.one("SELECT * FROM evidence WHERE id = ?", (eid,))


def mentions(p, case_id: int, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Auf welchen Seiten werden Personen/Organisationen des Falls genannt? Hinweis, keine Bestätigung."""
    ents = p.db.all("SELECT id, label, type FROM entities WHERE case_id = ? AND type IN ('person', 'organisation')", (case_id,))
    folded = [(pg["page"], " " + re.sub(r"[^a-z0-9]+", " ", fold(pg.get("text", ""))) + " ") for pg in pages]
    out = []
    for e in ents:
        needle = re.sub(r"[^a-z0-9]+", " ", fold(e["label"])).strip()
        tokens = needle.split()
        if len(needle) < 4:
            continue
        variants = {needle}
        if e["type"] == "person" and len(tokens) >= 2:
            variants.add(f"{tokens[-1]} {' '.join(tokens[:-1])}")  # „Nachname, Vorname“
        hit = [pg for pg, text in folded if any(f" {v} " in text for v in variants)]
        if hit:
            out.append({"entity_id": e["id"], "label": e["label"], "type": e["type"], "pages": hit[:50]})
    return sorted(out, key=lambda m: (-len(m["pages"]), m["label"]))
