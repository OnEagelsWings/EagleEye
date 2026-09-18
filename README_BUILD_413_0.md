# EagleEye Build 413.0 — Investigation Planner

Build 413 implements the Phase-18 Investigation Planner: case-scoped objective, subquestions, source strategy, stop conditions and risk/OPSEC constraints. Plans are immutable decision-support records and consume retrieval-quality, temporal and explicit relationship context from Builds 409–412.

Security invariants: no network execution, no execution authority, no automatic GO, no automatic stop, no truth determination, no automatic evidence promotion, no autonomous scope expansion. Creation requires canonical case-scoped `research.run` authorization.

Carry-forward hardening from public review is integrated in the Build-413 tree: Build 407 plan/intake mutations and Build 408 search/result mutations require case authorization; Build 407 integrity verification covers plan hashes and orphaned intake.

Status: Build-413 dedicated suite 12/12 PASS; compilation PASS. Historical 407–412 suites are not counted as Build-413 acceptance because their version-coherence assertions intentionally pin older runtime versions and pre-hardening API assumptions. `production_release_ready=false` remains unchanged.
