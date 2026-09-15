# EagleEye

EagleEye is an evidence-first, provenance-first OSINT and investigation platform developed as a human-governed AI-assisted system.

## Current import target

**Build 400.0**

A dedicated branch `eagleeye/build-400` has been created for the Build 400 source import.

### Repository safety rules

Do not commit runtime secrets, credentials, `.env` files, local databases, case evidence, caches, machine-local state, or private investigation data.

The Build 400 package was preflight-checked before repository import preparation; no obvious `.env`, private-key, database, or real API-token files were identified in the package scan.
