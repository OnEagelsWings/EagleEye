# Build 455 — Full Operations / Real-Source Research Gate

Build 455 is the first five-build hard checkpoint after Build 450. It validates the retained governed investigation chain together with the operational work added in Builds 451–454.

## Hard-checkpoint contract

Build 455 requires three distinct classes of evidence:

1. **Engineering regression** — the complete repository regression and explicit Phase-18–20 chain.
2. **Real public-source case** — a bounded non-fixture research case acquired through the existing hardened acquisition boundary and carried through reviewed Evidence, Claim, Dossier and export.
3. **Persistence/recovery** — a verified recovery point plus an actual AppContext close/reopen followed by reference and physical export hash verification.

A deterministic self-test alone cannot satisfy the Build-455 operational gate.

## Real-source qualification case

The CI qualification harness uses only deliberately low-risk public reference material:

- the IANA example-domains help page as the supporting source;
- the public example.com page as explicit counter/context evidence;
- a public Google DNS JSON lookup for Build-454 infrastructure integration.

The claim is deliberately narrow: IANA designates example.com as a reserved example domain for documentation, while the live page demonstrates that a reserved example domain can still be publicly served. The counterevidence/uncertainty is preserved rather than discarded.

The two Evidence items must originate from Build-442 external-validation runs. A plain manually inserted Acquisition Event cannot satisfy the Build-455 gate.

## Operational chain exercised

Real public acquisition → Build-422 event → Build-423 content observation → Build-447 Evidence → independent Build-449 Evidence review → Claim with support and counterevidence → independent Claim review → Living Dossier → independent Dossier review → separate export approval → authorized export executor → JSON/DOCX/PDF/manifest/ZIP hash verification → Build-453 recovery point → actual close/reopen → reference and artifact revalidation.

Build 454 is also exercised with a supplemental real public DNS smoke and an XRef run. These observations are deliberately **non-gating** for the Build-455 operational PASS because Build-454 provider imports do not yet carry the same Build-442 external-validation proof used for the two Evidence sources. Full external provider qualification therefore remains HOLD and moves into the post-455 connector/security qualification work.

## What PASS means

A Build-455 operational PASS means this bounded, public research workflow is demonstrably usable on the tested commit and platform profile.

It does **not** mean:

- every news/social/registry/Tor connector has been externally qualified;
- native Windows kernel containment is production-qualified;
- every external endpoint is permanently available;
- factual truth is automatically certified;
- external beta users have validated usability;
- the project is production-release ready.

Those remain separate gates.

## Install / verify

```bash
python INSTALL_EAGLEEYE_455.py
python INSTALL_EAGLEEYE_455.py --check
```

The complete checkpoint source ZIP is generated only after the Linux real-source qualification succeeds. Windows separately verifies the installer and isolated runtime.
