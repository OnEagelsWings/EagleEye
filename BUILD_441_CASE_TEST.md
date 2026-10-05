# Build 441 case-specific qualification

Use a dedicated synthetic/demo case.

## Endpoint

\`\`\`
POST /api/build441/cases/{case_id}/retrieval/selftest
\`\`\`

The deterministic qualification:

1. registers a synthetic public Surface-Web source;
2. creates one bounded Build-425 crawl task;
3. replays a robots.txt response that allows the target;
4. replays one public text response;
5. validates DNS policy against a synthetic globally routable address;
6. routes the result through Build 425 -> acquisition event -> content store;
7. confirms the task is completed and the Build-441 run is integrity-valid.

No external network connection is opened by the self-test.

Additional automated tests cover:

- robots disallow;
- private/reserved IP rejection;
- cross-host redirect blocking;
- unsafe content-type blocking;
- fixture live-execution denial;
- authorization and version/launcher contracts.
