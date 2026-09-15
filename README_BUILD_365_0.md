# EagleEye Build 365.0 — Operations

Build 365 is Phase 16 build 5/20. It adds the operational layer required to run EagleEye as a controlled investigation workspace rather than merely a collection of features.

## Main additions
- Case-scoped Operations Console: `/cases/{case_id}/operations`
- Queue/job metrics and worker lease health
- Crawler, evidence/search and security-event metrics
- Case-scoped merged operational trace
- Incident Console
- Local operational-readiness assessment
- AI operational preflight and dossier operations context
- Defensive, case-local OPSEC circuit breaker

## Start
- Windows: `START_EAGLEEYE_PRO.bat`
- POSIX: `./START_EAGLEEYE_PRO.sh`
- Direct: `python EAGLEEYE_PRO_365_0.py`

## Security boundary
Build 365 does not grant the AI or OPSEC supervisor autonomous system/network administration. External actions remain behind the existing approved gateways, RBAC and confirmation boundaries.

## Validation status
Local operational runtime is live-validated. External multi-user operations, load testing and production deployment remain not run. `production_release_ready=false` remains intentional.
