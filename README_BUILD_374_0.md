# EagleEye PersonOSINT Pro – Build 374.0

Build 374 adds a case-scoped operational workflow around the existing crawler, analyst graph, AI investigator and OPSEC supervisor.

Key controls:
- explicit source and case request budgets;
- max active crawler jobs per workflow;
- PAUSE/RESUME semantics without force-killing active workers;
- two-step analyst HANDOFF/ACCEPT;
- workflow-bound graph navigation and manual crawler starts;
- OPSEC detection of post-activation bypass jobs;
- zero new Build-374 data tables.

Local qualification does not replace an external multi-user analyst pilot.
