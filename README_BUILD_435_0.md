# EagleEye Build 435.0 — Isolated Tor Research Worker

Build 435 introduces the Phase-19 isolated Tor research worker and is the 435 hard checkpoint.

The worker only accepts explicitly registered `tor_onion` sources with `tor_public` access, exact reviewed v3 onion hosts, standard HTTP/HTTPS ports and read-only GET retrieval. A task requires a human approval reference. Live execution additionally requires the operator to repeat that approval reference and send the exact confirmation `TOR435_LIVE`.

Live traffic can only use the pre-existing controlled Build-370 loopback Tor SOCKS gateway. The worker does not spawn Tor, mutate torrc, use a ControlPort, request NEWNYM, send destination credentials/cookies, submit forms, upload data, execute JavaScript, bypass access controls or autonomously expand scope. SOCKS authentication isolation is per task and onion DNS resolution remains inside Tor.

Successful textual responses are recorded as Build-422 `tor_public` acquisition events with status `quarantined`, then fingerprinted through Build 423. They remain `quarantined_for_review` until a human records `accept_for_analysis` or `reject`. Review does not promote a source claim to fact.

The deterministic case self-test opens no external sockets. External onion validation is not claimed by the hard checkpoint unless it has actually been run separately. Production readiness remains false.
