from __future__ import annotations

from eagleeye_pro.phase18.bootstrap405 import install_phase18_405
from eagleeye_pro.phase18.connector_fabric407 import ConnectorDataFabric407
from eagleeye_pro.phase18.federated_search408 import FederatedSearch408
from eagleeye_pro.phase18.retrieval_quality409 import RetrievalQualityCoverage409
from eagleeye_pro.phase18.feedback_qualification410 import FeedbackQualification410
from eagleeye.application.build406.service import Build406FeedbackRemediationService
from eagleeye.application.build407.service import Build407ConnectorDataFabricService
from eagleeye.application.build408.service import Build408FederatedSearchService
from eagleeye.application.build409.service import Build409RetrievalQualityCoverageService
from eagleeye.application.build410.service import Build410FeedbackQualificationService


def install_phase18_410(ctx):
    """Install the reviewed Phase-18 406-410 cycle on top of the 401-405 feedback bootstrap."""
    ctx=install_phase18_405(ctx)
    if getattr(ctx,'build410',None) is not None:
        return ctx
    ctx.build406=Build406FeedbackRemediationService(
        ctx.db,ctx.audit,build405=ctx.build405,matrix402=ctx.authorization_matrix_402,
        holdout398=ctx.model_holdout_398,soak399=ctx.target_soak_399,gate404=ctx.ai_review_gate_404,
        install_dir=ctx.install_dir,actor=ctx.actor,
    )
    ctx.connector_fabric_407=ConnectorDataFabric407(
        ctx.db,ctx.audit,registry405=ctx.source_registry_v2_405,governance=ctx.team_governance_359,actor=ctx.actor,
    )
    ctx.build407=Build407ConnectorDataFabricService(
        ctx.db,ctx.audit,build406=ctx.build406,fabric407=ctx.connector_fabric_407,registry405=ctx.source_registry_v2_405,
        install_dir=ctx.install_dir,actor=ctx.actor,
    )
    ctx.federated_search_408=FederatedSearch408(
        ctx.db,ctx.audit,fabric407=ctx.connector_fabric_407,registry405=ctx.source_registry_v2_405,actor=ctx.actor,
    )
    ctx.build408=Build408FederatedSearchService(
        ctx.db,ctx.audit,build407=ctx.build407,search408=ctx.federated_search_408,registry405=ctx.source_registry_v2_405,
        install_dir=ctx.install_dir,actor=ctx.actor,
    )
    ctx.retrieval_quality_409=RetrievalQualityCoverage409(
        ctx.db,ctx.audit,search408=ctx.federated_search_408,fabric407=ctx.connector_fabric_407,
        registry405=ctx.source_registry_v2_405,actor=ctx.actor,
    )
    ctx.build409=Build409RetrievalQualityCoverageService(
        ctx.db,ctx.audit,build408=ctx.build408,quality409=ctx.retrieval_quality_409,
        install_dir=ctx.install_dir,actor=ctx.actor,
    )
    ctx.feedback_qualification_410=FeedbackQualification410(
        build409=ctx.build409,registry405=ctx.source_registry_v2_405,actor=ctx.actor,
    )
    ctx.build410=Build410FeedbackQualificationService(
        ctx.db,ctx.audit,build409=ctx.build409,qualification410=ctx.feedback_qualification_410,
        install_dir=ctx.install_dir,actor=ctx.actor,
    )
    return ctx
