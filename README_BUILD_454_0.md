# Build 454 — Cross-Reference Engine + Domain Infrastructure Intelligence

Build 454 is the final focused development build before the Build-455 hard checkpoint. It adds public infrastructure intelligence and an explainable cross-reference layer while preserving EagleEye's evidence-first, review-first model.

## Public infrastructure intelligence

Build 454 can prepare governed public lookups for:

- domain RDAP;
- Google Public DNS over HTTPS for A, AAAA, MX and NS records;
- Certificate Transparency observations through crt.sh;
- IP RDAP pivots;
- RIPEstat Network Info pivots for prefix/ASN observations.

The module itself does not open sockets. A lookup is only a plan until the existing governed acquisition chain retrieves it. Imported payloads must be bound to a Build-422 acquisition event and Build-423 content object, and the supplied payload SHA-256 must exactly match the referenced content object.

No port scanning, service probing, credential collection, access-control bypass or ownership/control determination is introduced.

## Cross-Reference Engine

The XRef engine correlates already-observed case data and produces review candidates from:

- exact shared Entity-Resolution anchors;
- Entity ↔ Domain anchors;
- shared public infrastructure such as IP, MX, CNAME or nameserver observations;
- historical web captures from Build 453;
- provenance references attached to each signal.

Shared infrastructure is deliberately attenuated when it is common across many domains. A shared CDN IP, nameserver, registrar or mail provider is never treated as proof of common ownership or control.

The engine can also return a shortest candidate path between two case nodes. Such a path is an investigative lead, not a verified causal or ownership chain.

## Investigation workflow

A typical Build-454 domain pivot is:

Domain → RDAP/DNS/CT plans → governed acquisition → provenance-bound import → IP pivots → RDAP/RIPEstat → XRef run → review candidates → analyst review.

The XRef engine never merges identities automatically and never promotes a relationship to a fact.

## Test cadence

Build 454 is a focused development build. It runs current 454 regressions, compile/import smoke, lightweight UI checks and isolated Linux/Windows runtime installation. The complete repository regression and full real-source investigation are reserved for Build 455.

Build 455 must test the complete case → live public acquisition → Evidence → Claims → independent review → graph/timeline → dossier → export → restart/reference chain.
