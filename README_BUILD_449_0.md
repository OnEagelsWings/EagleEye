# EagleEye Build 449.0 — Human Review & Team Workflow

Build 449 formalizes the human-review layer around the Build-447 Evidence → Claims → Dossier chain and integrates it into the Build-448 Investigator Workspace.

## Core workflow

```
Investigator / Analyst
  -> request review
  -> optional reviewer assignment
  -> independent reviewer claims task
  -> review decision + rationale
  -> immutable review audit
```

The requester cannot complete the same review. For Claims and Dossiers the object creator cannot act as reviewer either.

## Reviewable objects

Build 449 manages formal review tasks for:

- Evidence
- Claims
- Dossier revisions
- Dossier export approval

The final object-level decision is still executed by the Build-447 review functions, preserving the established Evidence/Claim/Dossier semantics and exact confirmation phrases.

## Four-eyes dossier release

Dossier release now has a formal sequence:

1. report author/investigator creates the dossier revision;
2. independent reviewer approves the dossier;
3. export requester creates a separate export-review task;
4. independent reviewer approves or denies the export;
5. an authorized executor, different from the approving reviewer, executes the Build-447 export.

The current Build-449 app removes the direct Build-447 Evidence/Claim/Dossier review and export mutation routes so the primary API surface cannot bypass the team workflow. Compatibility apps for older builds retain those historical routes.

## Review queue

Each case has a review queue with:

- pending tasks;
- explicitly claimed tasks;
- optional named reviewer assignment;
- requester/creator/reviewer identity;
- decision and rationale;
- stale-object detection;
- comments;
- challenge;
- agreement;
- counter-hypothesis.

If the reviewed object changes after the request was created, the review becomes `stale` and must be requested again.

## Roles

Build 449 uses the existing Phase-15 team RBAC:

- Case Lead
- Investigator
- Analyst
- Reviewer
- Report Author
- Read Only

Review permissions remain capability-based and case-scoped.

## Workspace integration

The primary eight-view workspace remains unchanged. Build 449 adds the formal workflow exactly where it is needed:

- Evidence: request Evidence review instead of direct self-review;
- Claims: request independent Claim review;
- Dossier: request independent Dossier approval;
- Dossier export: request and complete four-eyes export approval;
- OPSEC & Team: review queue, team membership, claiming, review rationale and review discussion.

## Boundaries

Build 449 does not:

- decide whether a Claim is objectively true;
- auto-accept Evidence;
- auto-accept Claims;
- auto-approve Dossiers;
- auto-export;
- expand network authority;
- replace investigator judgement.

Production readiness remains false.

Next: **Build 450 — Investigation Workflow Hard Checkpoint**.
