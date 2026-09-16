from __future__ import annotations

from eagleeye_pro.phase18.security_gate401 import SecurityQualificationGate401
from eagleeye_pro.phase18.authorization_matrix402 import AuthorizationMatrixAudit402
from eagleeye_pro.phase18.negative_path403 import NegativePathFramework403
from eagleeye_pro.phase18.ai_review_gate404 import AIReviewGate404
from eagleeye_pro.phase18.source_registry405 import SourceRegistryV2405
from eagleeye.application.build401.service import Build401SecurityQualificationHardeningService
from eagleeye.application.build402.service import Build402AuthorizationMatrixAuditService
from eagleeye.application.build403.service import Build403NegativePathFrameworkService
from eagleeye.application.build404.service import Build404AIReviewGateService
from eagleeye.application.build405.service import Build405SourceRegistryV2Service


def install_phase18_405(ctx):
    """Install Builds 401-405 on an existing Build-400 AppContext for feedback-branch execution.

    This is intentionally a compatibility bootstrap for public review. It does not
    alter execution authority and should eventually be replaced by canonical
    ServiceRegistry registrations after review.
    """
    if getattr(ctx, 'build405', None) is not None:
        return ctx
    ctx.security_gate_401 = SecurityQualificationGate401(
        holdout398=ctx.model_holdout_398,
        soak399=ctx.target_soak_399,
        acceptance400=ctx.phase17_final_acceptance_400,
        build400=ctx.build400,
    )
    ctx.build401 = Build401SecurityQualificationHardeningService(
        ctx.db, ctx.audit, build400=ctx.build400, gate401=ctx.security_gate_401,
        install_dir=ctx.install_dir, actor=ctx.actor,
    )
    ctx.authorization_matrix_402 = AuthorizationMatrixAudit402(
        governance=ctx.team_governance_359, identity=ctx.team_identity_359,
    )
    ctx.build402 = Build402AuthorizationMatrixAuditService(
        ctx.db, ctx.audit, build401=ctx.build401, matrix402=ctx.authorization_matrix_402,
        install_dir=ctx.install_dir, actor=ctx.actor,
    )
    ctx.negative_path_403 = NegativePathFramework403(
        build401=ctx.build401, build402=ctx.build402,
        soak399=ctx.target_soak_399, acceptance400=ctx.phase17_final_acceptance_400,
    )
    ctx.build403 = Build403NegativePathFrameworkService(
        ctx.db, ctx.audit, build402=ctx.build402, framework403=ctx.negative_path_403,
        install_dir=ctx.install_dir, actor=ctx.actor,
    )
    ctx.ai_review_gate_404 = AIReviewGate404(
        ctx.db, ctx.audit, build403=ctx.build403, actor=ctx.actor,
    )
    ctx.build404 = Build404AIReviewGateService(
        ctx.db, ctx.audit, build403=ctx.build403, gate404=ctx.ai_review_gate_404,
        install_dir=ctx.install_dir, actor=ctx.actor,
    )
    ctx.source_registry_v2_405 = SourceRegistryV2405(
        ctx.db, ctx.audit, runtime384=ctx.phase17_runtime_384, actor=ctx.actor,
    )
    ctx.build405 = Build405SourceRegistryV2Service(
        ctx.db, ctx.audit, build404=ctx.build404, registry405=ctx.source_registry_v2_405,
        install_dir=ctx.install_dir, actor=ctx.actor,
    )
    return ctx
