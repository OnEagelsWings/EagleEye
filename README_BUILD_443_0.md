# EagleEye Build 443.0 — Live News Acquisition

Build 443 adds a dedicated live acquisition path for public news feeds while preserving the Build-441/442 network and provenance boundaries.

## Supported feeds

- RSS 2.x
- Atom
- JSON Feed

Registered sources must use source type \`rss\`, \`news\` or \`api\` and access mode \`public\`.

Authenticated feeds, paywall bypass, cookie sessions, JavaScript rendering and login automation are not supported.

## Acquisition chain

A Build-443 feed task flows through:

\`421 source -> 425 task -> 442 hardened retrieval -> 422 feed event -> 423 feed fingerprint -> normalized feed entries -> derived 422/423 item observations -> 429 news items -> 431 provenance/syndication analysis\`

The raw feed body is held only in memory while being parsed. Build 443 does not introduce a second raw-payload store.

## Feed-item semantics

Build 443 persists only items with:

- a non-empty title;
- a public HTTP(S) canonical URL;
- a valid publication timestamp;
- an article host inside the source's reviewed allowlist.

The source's base host is allowed automatically. Additional article hosts may be declared explicitly in:

\`coverage.allowed_article_hosts\`

This supports publishers whose feed and article hosts differ without permitting arbitrary cross-domain expansion.

Duplicate \`source_id + external_id\` entries are skipped.

## Semantic extraction

Build 443 does **not** automatically manufacture Build-430 entities, events or claims from titles and summaries. Feed metadata is a source observation, not an independent truth statement.

Build 430 remains available for a later real semantic extraction step.

## Live execution

Live execution requires the exact confirmation:

\`NEWS443_LIVE\`

All network access still inherits Build 442:

- robots.txt fail-closed;
- public DNS validation and task-scoped IP pinning;
- DNS-rebinding defense;
- bounded retry/backoff;
- per-source rate limiting;
- exact source-host feed retrieval;
- TLS validation;
- same-host redirects only;
- byte/time budgets.

## Current limits

Build 443 fetches and normalizes the feed itself. It does not automatically fetch every article body referenced by the feed.

After Build 443:

- hardened Surface-Web retrieval: implemented;
- live public News feed acquisition: implemented;
- 429/431 integration: implemented;
- automatic 430 semantic extraction: false;
- Public-Social acquisition: incomplete;
- general live collection: incomplete;
- production readiness: false.

Build 444 should implement controlled Public-Social acquisition. Build 445 remains the Data Acquisition Hard Checkpoint.
