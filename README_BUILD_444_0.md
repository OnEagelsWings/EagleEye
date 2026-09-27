# EagleEye Build 444.0 — Controlled Public-Social Acquisition

Build 444 adds a deliberately narrow live path for clearly public social-platform data.

## Supported adapters

- Mastodon public JSON status/timeline responses
- Bluesky public AppView JSON post/feed/thread responses
- `generic_public` only with the explicit `eagleeye_public_social_v1` schema

Every source must be registered as:

- `source_type = social`
- `access_mode = public`
- `coverage.social_adapter` set explicitly

Generic sources additionally require:

`coverage.generic_schema = eagleeye_public_social_v1`

## Acquisition chain

`421 social source -> 425 single-endpoint task -> 442 hardened retrieval -> 422/423 parent response -> normalized public objects -> derived 422/423 objects -> 432 social observations`

The endpoint response is held only in memory while being parsed. Build 444 does not add a second raw-response store.

## Deliberate limits

Build 444 does not:

- authenticate;
- use cookies or sessions;
- access private/direct content;
- send messages;
- execute JavaScript;
- enumerate followers/following graphs;
- auto-discover endpoints;
- automatically paginate;
- expand from one reviewed endpoint into a broader crawl.

At most 50 returned objects from the single reviewed endpoint are considered in one run.

## Visibility and timestamps

Only `public` and `unlisted` objects are accepted.

Posts/threads require a valid source publication timestamp. Generic public profile/account observations may use collection time, but are explicitly marked as `observed_at_collection_time` rather than pretending that collection time is a publication time.

## Host scope

The endpoint itself must remain on the exact registered source host.

Canonical social-object URLs must be on the source host or an explicitly reviewed host in:

`coverage.allowed_object_hosts`

This is particularly relevant for Bluesky, where a public AppView endpoint and the canonical `bsky.app` object URL may use different hosts.

## Response safety

Build 444 accepts JSON only. Responses containing credential/session-like keys such as access tokens, refresh tokens, cookies, sessions or client secrets are rejected rather than persisted.

## Live execution

Live execution requires:

`SOCIAL444_LIVE`

The request still inherits Build 442 DNS rebinding protection, IP pinning, robots policy, TLS validation, retry/backoff, rate control and byte/time budgets.

## Readiness

After Build 444, the three core public acquisition paths planned before the Build-445 gate exist:

- ordinary Surface-Web retrieval;
- public News feed acquisition;
- controlled Public-Social JSON acquisition.

This still does not equal production readiness. Build 445 must qualify the acquisition stack end to end and explicitly identify any adapter-dependent, externally unvalidated or incomplete areas.
