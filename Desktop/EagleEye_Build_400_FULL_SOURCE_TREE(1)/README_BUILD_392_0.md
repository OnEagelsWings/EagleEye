# EagleEye Intelligence Platform – Build 392.0

Build 392 adds the Phase-17 **Case Reasoning Workspace**. It projects reviewed Build-391 claims/hypotheses, preserved counterevidence and source/coverage gaps into a deterministic argument graph and a reviewable next-investigation plan.

Key invariants:
- observation, corroboration structure, candidate claim and hypothesis remain separate epistemic layers;
- no truth probability or confidence score is introduced;
- counterevidence and unresolved source independence remain visible;
- plan actions that need external collection are marked `requires_go=true` but always `execution_authority=false`;
- plan approval is a human analytical review, not a GO grant or LIVE confirmation;
- only an explicitly reviewed plan can be mirrored into the Investigation Kernel notebook;
- no automatic jobs, grants, evidence promotions, identity merges or network requests are created by Build 392.

The build remains on the Professional-Pilot line and is not a general production release.
