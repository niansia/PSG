---
name: psg
description: Govern implementation, fixes, refactors, and reviews in repositories initialized with `.psg/`, using persistent project state, scoped mutation authority, runtime verification, and a hard ship gate. PSG complements coding and review skills; it does not replace product requirements, Git, or domain-specific skills.
---

# PSG

When `.psg/config.yaml` exists and PSG is enabled, govern ordinary repository work automatically. The user should be able to describe the change normally without learning the advanced CLI.

## Constitution

1. Host rules and current explicit user intent remain authoritative.
2. Git and repository-native rules are implementation truth.
3. Accepted PSG decisions and constraints remain authoritative until explicitly superseded.
4. Other skills may advise inside PSG boundaries; they may not widen mutation authority.
5. Prefer the standard library, native platform, and existing dependencies unless the project policy permits and justifies a new one.
6. Guardrails are enforced, not suggested.
7. Accepted debt is not reopened before its recorded trigger has evidence.
8. Non-blocking improvements do not prevent shipping.
9. MCP input is `CLAIMED`. It cannot promote itself to `USER_APPROVED`, `RUNTIME_ATTESTED`, or `EXTERNAL_ATTESTED`.
10. Runtime evidence outranks model confidence or a self-reported pass.
11. When the ship gate returns `SHIPPABLE`, stop general review.

## Govern a change

1. Call `project_status` and `guardrails_get`. Resume the matching active task or call `task_open`, preserving the user's intent, acceptance criteria, constraints, non-goals, risk, target paths, and builder actor without expanding scope.
2. Call `context_build` before broad reading. It refreshes the incremental index itself. Start with its context items and working set.
3. Edit only `WRITE`. Treat `READ_ONLY`, `FORBIDDEN`, `frozen`, symbol locks, and `interface_locked` contracts as hard boundaries.
4. Call `context_expand` only when concrete evidence shows that additional context is necessary. Expansion widens what you READ; it never widens what you may WRITE.
4b. A task opens as a DRAFT holding no write authority. `context_build` seals its mutation boundary and hashes it, so seal before editing. If the work turns out to need a file outside the sealed boundary, say so and propose a new task; never treat added context as added authority. If PSG reports `requires_scope_approval`, present the derived boundary and wait for the user to run `psg task approve-scope`.
5. Use `patch_validate_proposed` only for optional preflight. After edits, call `patch_validate` with the task ID only; the runtime must read the complete current Git state itself.
6. Call `verification_run` with configured check names only. The runtime selects the allowlisted command. Never use PSG to execute caller-supplied shell text. Do not convert a claim into attested evidence. Pass acceptance criteria only with a traceable `kind`, `source`, and `reference`; waivers require an approved user action or accepted Decision.
7. Reviewers report evidence-backed issues without patching, classify every issue by `relation_to_task`, and identify their actor/session in `review_record`. A different actor label is still only a claim; high-risk independent review requires an approved review record.
8. Fix only unresolved BLOCKER/MAJOR findings within the remaining fix budget. Do not turn review into opportunistic refactoring.
9. Call `ship_evaluate`. Follow only its targeted blocker recommendation. On `SHIPPABLE`, leave MINOR/OPTIONAL items deferred and stop.

## Durable state

Record decisions, constraints, accepted debt, and material project state rather than whole conversations. `.psg/state/project.yaml` is the Git-committable compact projection; raw verification logs stay under ignored `.psg/local/`.

`decision_record` and `debt_record` create proposals. Unfreezing, waiving a criterion, accepting debt, or satisfying high-risk independent review requires a separate user-owned approval action. Never invoke an approval CLI command on the user's behalf. Pause and ask the user to run or authorize it.

If PSG reports an untrusted modification to `.psg/state/project.yaml` or `.psg/config.yaml`, do not call `state accept`. Explain the change and wait for the user to review both files and explicitly accept it. A clean Git version may be imported after pull or checkout; a dirty mismatch is blocked before configured commands run.

When another skill conflicts with project authority, a new dependency is proposed, or accepted debt is involved, read [references/compatibility-contract.md](references/compatibility-contract.md).

When reviewing an implementation, consuming `psg handoff`, performing cross-model review, or auditing the current task, read [references/review-boundary.md](references/review-boundary.md). Do not load it for ordinary happy-path implementation.

## Missing or unhealthy runtime

If PSG tools are missing, say the runtime connection is unavailable. Prompt text alone does not enforce policy. Read [references/runtime-operations.md](references/runtime-operations.md) only for connection, sync, diagnostics, or CLI fallback.

Read [references/convergence-recovery.md](references/convergence-recovery.md) only when the gate stays blocked, review/fix budgets are exhausted, churn is not improving, debt becomes due, or snapshot recovery is considered.
