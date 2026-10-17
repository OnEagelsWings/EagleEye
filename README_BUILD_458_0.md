# Build 458 — Document Intelligence 2.0

Build 458 extends the verified Build-457 Investigator Workspace with **real page-position
document anchors**. It uses offline PyMuPDF extraction, no string scraping of binary PDFs.

## What is implemented

- Accept PDF (up to 12 MiB and 160 pages), UTF-8 TXT and Markdown.
- Extract page-numbered text blocks with bounding boxes, ordered block numbers,
  normalized text hashes and a stable source-document SHA-256.
- Classify likely figure/table captions and footnote **candidates** conservatively.
- Store uploaded source bytes under internal generated identifiers in the case data
  directory; no caller-provided server file path is accepted. No remote fetch.
- Explicitly mark pages without a usable PDF text layer as `ocr_required`.
  **No unattended OCR**, since that could silently introduce incorrect text.
- Require human extraction review before attaching a source anchor to a canonical
  Evidence-Claim link. Attachments verify current Evidence, Claim link, document
  and anchor hashes. Stale links become `current:false`, never self-heal.
- Preserve source provenance and exact section excerpt in a case-scoped
  citation manifest view. Claim truth or Evidence acceptance is never inferred.

## Local run

```powershell
python INSTALL_EAGLEEYE_458.py
python INSTALL_EAGLEEYE_458.py --check
./START_EAGLEEYE_PRO.bat
```

After login, visit `/documents458?case_id=<your-case-id>` or work through the
authenticated API:

`POST /api/build458/cases/{case_id}/documents` — multipart upload (file,
title, source_url).

`GET /api/build458/documents/{document_id}/anchors` — show precise page/block anchors.

`POST /api/build458/documents/{document_id}/review` — extraction review.
Requires `expected_document_hash`, decision (approve/reject), note, and
`REVIEW DOCUMENT EXTRACTION 458` confirmation.

`POST /api/build458/claims/{claim_id}/citations` — review-bound anchor citation.
Requires a canonical Claim Evidence link ID, exact current Evidence and anchor
record hashes, a note, and `LINK DOCUMENT ANCHOR 458` confirmation.

`GET /api/build458/claims/{claim_id}/citations` — resolved references with
source-location text and explicit `current` / `reference_ready` flags.

## Limits and remaining work

Build 458 deliberately does **not** claim table-cell geometry extraction,
OCR transcription accuracy, or automatic insertion of document anchors in every
legacy Dossier export type. Accurate tables, OCR and full export coverage remain
validation/integration work for Build 459–460.

## Tests

```bash
python -m pytest -q tests/test_build458_document_intelligence.py
```

Every-fifth-build full end-to-end regression remains reserved for Build 460.
