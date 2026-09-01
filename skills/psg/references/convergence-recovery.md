# Convergence and recovery

Use this reference only for blocked gates, correction churn, exhausted budgets, or snapshot recovery.

## Targeted correction

Fix only the evidence-backed BLOCKER/MAJOR items named by the gate. Preserve the existing WRITE set unless the failure proves that another node is required; then request context expansion with that evidence. Caller-reported introduced/resolved counts are advisory; PSG derives blocker changes from its issue records.

The hard stopping condition is the runtime-counted fix budget. Review rounds are also counted by the runtime. Churn remains an advisory diagnostic rather than a security decision. When a hard budget is exhausted, report the architectural choice or external decision needed. Do not keep trying variants.

## Snapshot recovery

PSG snapshots restore graph/project-state records only. They never reset, overwrite, or delete source files. A restore creates a pre-restore safety snapshot. If the snapshot Git revision differs from the current repository, require an explicit revision-mismatch override and state that code remains unchanged.

Use the last stable snapshot as evidence for a human-led source recovery decision. Never translate it into a destructive Git command without a separate explicit user request.

## Non-blocking findings

MINOR, OPTIONAL, and SPECULATIVE findings remain backlog/deferred items. They do not reopen a SHIPPABLE task unless new reproducible evidence establishes a requirement, contract, test, or security violation.

Accepted Debt nodes also stay deferred while their revisit trigger is unmet. Use `debt_review` with new evidence to propose that a trigger is due; the trigger needs user approval before it reopens governance state. Do not repeatedly rediscover the same accepted tradeoff in general review.
