# Regression summary — Build 413.0
- Build 413 dedicated acceptance/security suite: 12/12 PASS.
- Python compileall for Phase-18, Build-413 service/app and AppContext: PASS.
- Builds 407–412 historical suite sampled: 37 PASS / 11 FAIL before carry-forward hardening; failures were old version-coherence/health assertions after runtime advanced to 413.0.
- Build 413 additionally changes 407/408 mutation APIs to require canonical case authorization; old tests that intentionally omit identity are historical-boundary tests, not current acceptance criteria.
- No production-release claim.
