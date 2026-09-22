# EagleEye Build 429.0 — News Connector Layer

Build 429 adds the normalized ingestion boundary for public news data. News items may originate from RSS, Atom, lawful APIs, public datasets or manual imports, but all are normalized into the same case-scoped provenance model.

Every item must reference a Build-421 news-capable source, a matching Build-422 acquisition event and a Build-423 content object. The normalized record stores canonical URL, headline, publisher, author, publication time, language, external source ID and connector metadata. Source-local external IDs are deduplicated.

Build 429 deliberately does not contain a generic live network executor. Retrieval remains governed by the acquisition/crawler boundary. A publisher's claim is not treated as independent corroboration merely because multiple downstream outlets repeat it. Build 430 will add news entity/event extraction and the next hard qualification checkpoint.
