# OPSEC Policy — Build 380

OPSEC remains defensive and case-scoped. It detects operational job payloads that claim production override, final-gate bypass, forced production candidacy or skipped external qualification. Queued/workflow-paused jobs are cancelled; running jobs are marked for controlled drain rather than force-killed. No system mutation authority is added.
