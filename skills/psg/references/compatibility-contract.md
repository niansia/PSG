# Authority, compatibility, and debt

Read this reference only when another skill makes a conflicting recommendation, a dependency change is proposed, or intentional debt is recorded/reviewed.

## Authority and scope

Resolve a conflict only inside the domain where sources overlap. Apply this order:

1. host/platform mandatory rules;
2. current explicit user instruction;
3. accepted PSG project constraints and decisions;
4. repository-native authority such as `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, build/test configuration, and architecture documents;
5. task-specific skill instructions;
6. general skills and preferences;
7. PSG heuristics;
8. model suggestions.

PSG is not an exclusive coding mode. Security, testing, frontend, simplicity, and review skills may operate normally inside the current task and write scope. They may not widen scope, unlock a node, weaken verification, reopen accepted debt, or supersede a decision. Use `conflict_record` to defer/report a conflicting suggestion. A user override must be represented by a new Decision.

## Dependency discipline

Read the project's `dependencies` policy. Under the default conservative policy, prefer:

1. standard library;
2. native platform capability;
3. an existing dependency;
4. a new dependency only with explicit task justification.

PSG carries the project policy; it does not impose one universal framework philosophy. If dependency-manifest additions are required, put the concrete reason in the task's dependency justifications before validation.

## Accepted debt

Debt is valid only when it records:

- what is intentionally imperfect;
- why the tradeoff is accepted;
- its operating ceiling;
- a concrete revisit trigger.

Use `debt_record`, or a structured source annotation:

```text
psg-debt: linear scan for v1; why=small input; ceiling=50000 records; revisit=records > 30000
```

If the trigger is not met, ordinary review must return `DO_NOT_REOPEN`. Attach new evidence with `debt_review` before promoting it into active work. A finding tied to accepted, not-due debt remains deferred/non-blocking.
