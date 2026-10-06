# EagleEye Phase 18–20 Feedback Policy

Starting with Build 401, development proceeds in five-build feedback cycles.

- 401–405 → publish to GitHub and request Codex/Copilot + external tester review
- 406–410 → integrate material findings, then publish again
- continue in five-build increments through Build 460

Every material P0/P1 finding blocks the next public-cycle merge until fixed and regression-tested. P2/P3 findings are triaged into the active plan when they materially affect security, correctness, installation, data integrity or investigation usability. Every fixed defect receives a permanent regression test. Production readiness remains false until the Phase-20 release gate is independently satisfied.

From 2026-10-05, every fifth build (450, 455, 460, 465, ...) must additionally
qualify a complete operational research workflow. See
`PHASE_20_RESEARCH_MILESTONES.md` for mandatory evidence and HOLD conditions.
