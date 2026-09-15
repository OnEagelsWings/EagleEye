# Release Notes — Build 384.0

Phase 17 now runs on the actual Build-380 source tree rather than as an overlay. The current application pointer, web health endpoint, generic launchers, package version and ServiceRegistry all target Build 384. The new planning layer is canonical-DB-backed, audit-logged, case-scoped and network-silent.

A performance issue caused by repeated full operational readiness evaluation during bursts of non-executing planning was removed using a sub-second planning-preflight cache. This cache never grants execution authority; later GO/execution remains subject to the live crawler and OPSEC gates.
