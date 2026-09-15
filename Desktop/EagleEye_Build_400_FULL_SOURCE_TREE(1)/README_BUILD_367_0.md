# EagleEye Build 367.0 – Procurement / Public Money

Phase 16 build 7/20.

## What changed

Build 367 adds governed public procurement and public-spending evidence:

- USAspending specific award: exact generated award ID, public GET API.
- TED published notice XML: exact `NNNNNN-YYYY` publication number, public direct XML link.
- TED Search API v3: visible as plan-only; no POST execution in this build.
- Source review and explicit `LIVE` confirmation before external execution.
- Case-scoped receipts, safe AI context, money-flow leads and review-only corporate correlations.

## Start

Windows: `START_EAGLEEYE_PRO.bat`  
Cross-platform: `python EAGLEEYE_PRO_367_0.py`

## Release truthfulness

Build acceptance can pass without external network validation. `production_release_ready` remains false until the broader Phase-16 external validation and professional pilot gates are completed.
