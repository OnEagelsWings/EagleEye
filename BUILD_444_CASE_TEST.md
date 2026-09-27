# Build 444 case-specific qualification

Use a dedicated synthetic/demo case.

## Deterministic qualification

```
POST /api/build444/cases/{case_id}/social/selftest
```

The self-test opens no external sockets. It:

1. registers a synthetic public social source;
2. creates one Build-444 single-endpoint task;
3. replays robots.txt and one public JSON response through Build 442;
4. validates one normalized public post;
5. creates derived Build-422/423 provenance;
6. creates a non-fixture Build-432 observation;
7. confirms no pagination or social-graph enumeration occurred;
8. verifies Build-444 integrity.

Automated tests additionally cover Mastodon public/unlisted filtering, Bluesky AppView normalization, duplicate suppression, object-host allowlists, credential-like JSON rejection and exact live confirmation.

## Optional live run

For a reviewed public social endpoint:

```json
{"confirmation":"SOCIAL444_LIVE"}
```

Do not use authenticated endpoints, private/direct content, internal services, messaging functions or follower/following enumeration during beta qualification.
