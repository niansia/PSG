# PSG v1.0 architecture

PSG is a non-exclusive governance layer for coding agents. Git and source files remain authoritative; the project graph adds durable intent, constraints, provenance, evidence, and convergence state.

```text
User request + existing Skills
            │
            ▼
        PSG Skill
            │
     MCP tools / JSON CLI
            │
            ▼
        PSG runtime
  ┌─────────┼──────────────┬────────────────┐
  │         │              │                │
Indexer  ContextRouter  PolicyEngine  Verification/Convergence
  │         │              │                │
  └─────────┴─────── project graph ─────────┘
                    │
         portable YAML ⇄ local SQLite/events
                    │
                    ▼
           Git repository + real checks
```

## State model

The graph contains code-derived nodes (`File`, `Symbol`, `Snapshot`) and durable project-state nodes (`Task`, `Requirement`, `Constraint`, `Decision`, `Issue`, `Verification`, `Architecture`, `Debt`, `Conflict`). Relationships include structural code edges and explicit project effects such as `requires`, `targets`, `constrained-by`, `locks`, `verified-by`, `affects`, `supersedes`, and `conflicts-with`.

Opening a task materializes the task, its acceptance criteria as `Requirement` nodes, its constraints, and its target edges. A decision with a mutation effect creates enforceable graph locks. Verification, issues, criteria status, accepted debt, and ship status are also projected back into the graph instead of living only in command history.

## Portable and derived state

PSG deliberately separates durable collaboration state from a local query cache:

| Location | Purpose | Commit? |
| --- | --- | --- |
| `.psg/config.yaml` | Authority, guardrails, routing, review, dependency, and verification settings | Yes |
| `.psg/policies.yaml` | Repository mutation policies | Yes |
| `.psg/state/project.yaml` | Decisions, tasks, requirements, constraints, issues, verification, debt, conflicts, and their edges | Yes |
| `.psg/local/psg.db` | Derived SQLite graph and index | No |
| `.psg/local/events.jsonl` | Local append-only operational log | No |

On startup or `state_sync`, changed portable YAML is merged into SQLite. After durable mutations, the graph is exported back to YAML. Code-derived nodes are rebuilt from the repository, allowing a fresh clone to recover project intent without sharing a machine-specific database.

## Index and context freshness

The indexer hashes files and extracts Python symbols, signatures, imports, and calls. Non-Python files remain file-level nodes. Incremental refresh preserves policies and manually asserted or decision-derived edges while replacing stale code structure.

Every context build first synchronizes portable state and refreshes the index. The router follows targets, dependencies, constraints, and graph proximity within a token budget. Confidence combines freshness, language coverage, provenance, and dependency certainty. If confidence is below the configured threshold, routing expands once within the same call and immediately rebuilds the result; it never reports an expansion that will only take effect later.

## Enforcement boundary

PSG never applies patches. The authoritative `patch_validate` operation obtains the final change set directly from Git:

- tracked changes relative to `HEAD`, whether staged or unstaged;
- added, deleted, and binary changes;
- rename source and destination paths; and
- untracked files represented as additions.

Model-supplied diffs are accepted only by the separate `patch_validate_proposed` preflight operation and can never stand in for final validation.

The policy engine parses file headers and hunk line ranges. It checks:

- task `WRITE`, `READ_ONLY`, and `FORBIDDEN` scope;
- repository file policies;
- Python symbol policies intersected with actual changed lines;
- architecture or decision `locks` and `constrained-by` edges;
- interface changes in `interface_locked` files;
- dependency-manifest additions without task justification; and
- stale task baselines.

Unfreezing requires an explicit override and a recorded Decision. The new decision supersedes the previous lock; a reason string alone is insufficient.

## Evidence and ship gate

Every verification records its origin: `runtime_executed`, `external_tool`, `reviewer`, `user_asserted`, or `llm_reported`. Runtime commands are captured directly. External-tool passes require a reference. A model cannot label its own report as runtime-executed.

Acceptance passes require evidence kind, source, and reference. Model-reported evidence is not accepted as proof. Waivers require either explicit user authority or a Decision. All verification and acceptance evidence is bound to a worktree fingerprint; a subsequent code or governance change makes it stale.

The ship gate separately requires:

1. a passing policy validation of the current runtime-derived diff;
2. at least one trusted functional verification, not merely the policy pass;
3. passing or properly waived acceptance criteria;
4. no supported open blocking issues;
5. required independent review for high-risk work, with reviewer actor different from the recorded builder actor; and
6. convergence within the configured review/fix budgets.

Accepted debt records `what`, `why`, a permitted `ceiling`, and a `revisit_trigger`. Reviewers do not reopen it until evidence shows that trigger was met.

## Skill coexistence and authority

PSG does not claim exclusive control of a task. Other Skills may design, implement, test, or document. PSG resolves conflicts using the configured authority order:

1. mandatory host rules;
2. the user’s current instruction;
3. accepted PSG decisions and constraints;
4. repository-native rules;
5. task-specific Skills;
6. general Skills and preferences;
7. PSG heuristics; and
8. model preference.

Conflicts are recorded as graph nodes. A lower-authority Skill cannot widen scope, unlock frozen state, weaken required verification, or reopen accepted debt. A user override that changes durable project governance must be anchored to a Decision.

## Snapshot boundary

Snapshots serialize PSG graph state and bind it to Git revision. Restore creates a safety snapshot and restores graph state only. It never runs `git reset`, rewrites the working tree, or substitutes graph restoration for source recovery.
