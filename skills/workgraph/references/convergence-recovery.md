# Convergence and recovery

Use this reference only for blocked gates, correction churn, exhausted budgets, or snapshot recovery.

## Targeted correction

Fix only the evidence-backed BLOCKER/MAJOR items named by the gate. Preserve the existing WRITE set unless the failure proves that another node is required; then request context expansion with that evidence. Record how many blocking issues the cycle introduced and resolved.

Stop targeted fixes when either condition is true:

- the configured fix budget is exhausted; or
- two consecutive cycles do not reduce blocking risk and churn is not improving.

At that point, report the architectural choice or external decision needed. Do not keep trying variants.

## Snapshot recovery

WorkGraph snapshots restore graph/project-state records only. They never reset, overwrite, or delete source files. A restore creates a pre-restore safety snapshot. If the snapshot Git revision differs from the current repository, require an explicit revision-mismatch override and state that code remains unchanged.

Use the last stable snapshot as evidence for a human-led source recovery decision. Never translate it into a destructive Git command without a separate explicit user request.

## Non-blocking findings

MINOR, OPTIONAL, and SPECULATIVE findings remain backlog/deferred items. They do not reopen a SHIPPABLE task unless new reproducible evidence establishes a requirement, contract, test, or security violation.
