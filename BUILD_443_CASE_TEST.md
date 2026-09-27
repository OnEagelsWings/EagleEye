# Build 443 case-specific qualification

Use a dedicated synthetic/demo case.

## Deterministic qualification

\`\`\`
POST /api/build443/cases/{case_id}/news/selftest
\`\`\`

The self-test opens no external sockets. It:

1. registers a synthetic RSS source;
2. creates a Build-443 feed task;
3. replays robots.txt and one RSS response through the Build-442 hardening path;
4. parses two dated public items;
5. creates derived 422 acquisition events;
6. fingerprints normalized item content through Build 423;
7. creates two Build-429 news items;
8. runs Build-431 provenance analysis;
9. verifies no fake Build-430 semantic claims were created;
10. verifies Build-443 record integrity.

## Optional live run

For a reviewed public source, create a feed task and execute it with:

\`\`\`json
{"confirmation":"NEWS443_LIVE"}
\`\`\`

Do not use authenticated feeds, private/internal endpoints, paywalled login flows, confidential data or sensitive personal information during beta qualification.
