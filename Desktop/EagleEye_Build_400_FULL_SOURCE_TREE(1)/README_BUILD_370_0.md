# EagleEye PersonOSINT Pro – Build 370.0

Build 370 adds a controlled read-only Tor gateway on top of the Build-369 production crawler. It uses a loopback SOCKS5 endpoint, per-search SOCKS-auth isolation, no local onion DNS, a dedicated Tor crawler queue, Tor-specific backpressure and lease recovery. Tor execution requires an exact reviewed v3 onion source, case RBAC and explicit `TOR_LIVE` confirmation.

Build 370 also makes crawler development mandatory in every remaining Phase-16 build through Build 380. The roadmap is exposed in runtime status and documented in the Phase-16 masterplan.

No ControlPort/NEWNYM, Tor process control, torrc mutation, credentials/forms/uploads/payments or access-control bypass are introduced. External Tor/onion validation is never inferred from local fixture tests.
