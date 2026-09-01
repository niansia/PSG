# Task Contract and review boundary

The Task Contract is the durable boundary for one unit of work. It tells a builder what the user asked for, what may be read or changed, which review findings belong to this task, and what evidence is required before PSG can return `SHIPPABLE`.

It is not a replacement for Git. Git remains the implementation source of truth; the contract governs how an Agent may work against that truth.

## Contract contents

| Boundary | Stored meaning |
| --- | --- |
| Goal | Intent and acceptance criteria |
| Context | Targets, related graph state, and relevant constraints |
| Mutation | Authorized write, read-only, forbidden, frozen, and locked nodes |
| Scope | Non-goals and explicitly out-of-scope work |
| Review | Which evidence-backed findings may block this task |
| Completion | Required acceptance, verification, policy, review, and freshness checks |
| Risk | Risk level, review policy, and review/fix budgets |

Each contract also records its schema version and a canonical hash. Reviews and approvals refer to that hash so they cannot silently apply to a different boundary.

## Draft and sealed states

A newly opened task is `DRAFT`. It expresses intent, criteria, targets, and constraints, but it does not yet grant write authority.

The first successful context build localizes the request and seals the mutation boundary:

```text
User request
     ↓
DRAFT contract — no write authority
     ↓ localization
SEALED contract — authorized write/read-only/forbidden boundary is hashed
     ↓
Builder may edit inside the sealed boundary
```

After sealing, context can expand but write authority cannot. A newly discovered file may become useful reading context; it does not become writable merely because a router or reviewer found it.

When an inferred boundary is broad or risky, PSG marks it as requiring scope approval. `psg task approve-scope TASK_ID` is an interactive user-owned action and is deliberately unavailable through ordinary MCP. Approval binds to the current contract hash and cannot be reused after the boundary changes.

PSG v1 does not include an automatic task-amendment engine. If the requested work genuinely needs a different mutation boundary, open a new task rather than silently widening the current one.

## Review relation is separate from severity

Every Issue has exactly one `relation_to_task` value from this closed set:

| Relation | May block the current task? |
| --- | ---: |
| `caused_by_patch` | Yes, with sufficient evidence |
| `violates_acceptance` | Yes, with sufficient evidence |
| `violates_project_constraint` | Yes, with sufficient evidence |
| `pre_existing` | No; follow-up only |
| `unrelated` | No; follow-up only |
| `future_improvement` | No; follow-up only |

Severity describes impact. Relation describes whether the finding belongs to this task. A serious pre-existing bug remains serious, but it does not turn an unrelated patch into a project-wide repair.

Agents do not set `blocks_current_task`. The runtime derives it only when all of the following are true:

1. The Issue is open.
2. Severity is `blocker` or `major`.
3. Relation is one of the first three values above.
4. Evidence is sufficient for that relation.

Evidence requirements are relation-specific:

- `violates_acceptance` must reference a real acceptance-criterion ID.
- `violates_project_constraint` must reference a Constraint, accepted Decision, policy, or affected frozen/locked node.
- `caused_by_patch` must identify affected nodes, concrete diff/runtime evidence, or a failed verification.

Open findings outside this rule remain visible as follow-up work. They are not discarded, and they do not reopen the current task.

## No scope expansion by review

A reviewer may read, analyze, report, classify, attach evidence, and propose follow-up work. A reviewer may not:

- change the goal or acceptance criteria;
- widen write authority or unlock a node;
- override an accepted Decision or project Constraint;
- convert follow-up work into current work; or
- replace user approval with an actor label or model claim.

Review records include the contract hash. A review against another or mutated contract cannot satisfy the current review requirement.

## Completion and convergence

The ship gate considers the current contract, the actual Git state, trusted and fresh evidence, runtime-counted budgets, and only current-task blockers. A task becomes `SHIPPABLE` when:

- mandatory acceptance criteria pass;
- required deterministic verification passes;
- the actual mutation stays inside policy and the sealed boundary;
- no evidence-backed current-task `blocker` or `major` remains open;
- evidence matches the current worktree;
- any required high-risk user approval is present; and
- review and targeted-fix counts remain inside their configured limits.

Pre-existing issues, unrelated findings, minor suggestions, accepted debt, and future improvements may remain visible after the gate passes. They do not automatically restart general review.

> **Review the task, not the universe. When the contract is satisfied, stop.**

## Handoff packs

`psg handoff [TASK_ID]` creates a read-only, minimum-sufficient review pack containing:

- the Task Contract and its boundary;
- changed files and symbols;
- relevant Constraints and Decisions;
- trusted verification and acceptance status;
- accepted debt and known Issues;
- current ship state; and
- the same blocking/follow-up classification rule.

The default output is stored under ignored local state. Building a handoff does not change task status or append an event. See [CLI and MCP](cli-and-mcp.md) for command details and [architecture](architecture.md) for the graph projection.
