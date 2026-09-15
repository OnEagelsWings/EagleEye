"""EagleEye Phase 17 overlays."""

from .investigation_control381 import (  # noqa: F401
    BUILD as BUILD_381,
    GlobalSourceRegistry381,
    InvestigationControlPlane381,
    SourceRegistryEntry,
    default_registry,
)
from .source_registry_persistence382 import (  # noqa: F401
    BUILD as BUILD_382,
    CoverageGap,
    CoverageReport382,
    InvestigationControlPlane382,
    PersistentResearchPlan382,
    SourceRegistryRepository382,
    create_reference_repository,
)
from .source_planner383 import (  # noqa: F401
    BUILD as BUILD_383,
    AcquisitionPlan383,
    AcquisitionTemplate383,
    PlannerGap383,
    PlannedSourceStep383,
    SourcePlanner383,
    SourcePlannerRepository383,
    SourceRequirement383,
    create_reference_repository383,
)
from .jurisdiction_intelligence384 import (  # noqa: F401
    BUILD as BUILD_384,
    CONFIRM_WAVES,
    CoverageObjective384,
    JurisdictionIntelligence384,
    JurisdictionProfile384,
    JurisdictionRepository384,
    ResearchWave384,
    WavePlan384,
    WaveStep384,
    create_reference_repository384,
)
from .acquisition_orchestrator385 import (  # noqa: F401
    BUILD as BUILD_385,
    CONFIRM_PREPARE,
    AcquisitionOrchestrator385,
    AcquisitionPacket385,
    AcquisitionPacketItem385,
    SourceCapability385,
)

from .execution_authority386 import BUILD as BUILD_386, ExecutionAuthority386  # noqa: F401
from .controlled_executor387 import BUILD as BUILD_387, ControlledExecutor387  # noqa: F401

from .research_wave_execution388 import BUILD as BUILD_388, GovernedResearchWave388  # noqa: F401
from .result_intake389 import BUILD as BUILD_389, ResultIntake389, EvidenceCandidate389  # noqa: F401
from .evidence_review390 import (  # noqa: F401
    BUILD as BUILD_390,
    CONFIRM_ASSESS,
    CONFIRM_FINALIZE,
    CONFIRM_INDEPENDENCE,
    EvidenceReviewCorroboration390,
    SourceIndependenceProfile390,
)

from .investigation_synthesis391 import (  # noqa: F401
    BUILD as BUILD_391,
    CONFIRM_CLAIM_REVIEW,
    CONFIRM_HYPOTHESIS_REVIEW,
    CONFIRM_KERNEL_ADMISSION,
    CONFIRM_SNAPSHOT,
    InvestigationSynthesis391,
)

from .case_reasoning392 import (  # noqa: F401
    BUILD as BUILD_392,
    CONFIRM_PLAN_REVIEW,
    CONFIRM_KERNEL_ADMISSION as CONFIRM_REASONING_KERNEL_ADMISSION,
    CaseReasoningWorkspace392,
)
from .investigator_dialogue393 import (  # noqa: F401
    BUILD as BUILD_393,
    CONFIRM_PROPOSAL_REVIEW,
    CONFIRM_KERNEL_ADMISSION as CONFIRM_CHALLENGE_KERNEL_ADMISSION,
    InvestigatorDialogueChallenge393,
)


from .discussion_revision394 import (  # noqa: F401
    BUILD as BUILD_394,
    CONFIRM_REVISION_REVIEW,
    CONFIRM_APPLY_REVISION,
    CONFIRM_KERNEL_ADMISSION as CONFIRM_DISCUSSION_KERNEL_ADMISSION,
    InvestigatorDiscussionRevision394,
)

from .case_reconciliation396 import (  # noqa: F401
    BUILD as BUILD_396,
    CONFIRM_BASELINE,
    CONFIRM_REVIEW as CONFIRM_REANALYSIS_REVIEW,
    CONFIRM_BRANCH as CONFIRM_REANALYSIS_BRANCH,
    CONFIRM_ADVANCE,
    CaseStateReconciliation396,
)

from .argumentative_analyst397 import (  # noqa: F401
    BUILD as BUILD_397,
    CONFIRM_REVIEW as CONFIRM_ANALYST_RECOMMENDATION_REVIEW,
    ArgumentativeAIAnalyst397,
)

from .model_holdout398 import (  # noqa: F401
    BUILD as BUILD_398,
    CONFIRM_FREEZE_SUITE, CONFIRM_EXTERNAL_RUN, CONFIRM_HUMAN_REVIEW, CONFIRM_FREEZE_BASELINE,
    ModelHoldoutEvaluation398,
)

from .target_soak399 import (  # noqa: F401
    BUILD as BUILD_399, CONFIRM_FREEZE_PLAN, CONFIRM_IMPORT_EXTERNAL, CONFIRM_REVIEW as CONFIRM_SOAK_REVIEW, CONFIRM_INTERNAL_SIM, TargetEnvironmentSoak399,
)

from .final_acceptance400 import (  # noqa: F401
    BUILD as BUILD_400, CONFIRM_RUN as CONFIRM_PHASE17_FINAL_RUN, CONFIRM_REVIEW as CONFIRM_PHASE17_FINAL_REVIEW, Phase17FinalAcceptance400,
)
