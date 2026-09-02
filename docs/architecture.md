# PSG v1.1 architecture

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

Opening a task materializes the task, its acceptance criteria as `Requirement` nodes, its constraints, and its target edges. An approved Decision with a mutation effect creates enforceable graph locks; an MCP-recorded Decision remains a proposal. Verification, issues, criteria status, accepted debt, and ship status are also projected back into the graph instead of living only in command history.

## Distribution layer

The runtime remains host-neutral. A small installer maps the same Skill bundle and `psg-mcp` command into Codex, Claude Code, and Gemini CLI using each host's native Skill location and MCP management command. `psg setup` auto-detects hosts, `psg update` resolves the highest stable `vX.Y.Z` tag before refreshing the runtime/bundle/registrations, and `psg uninstall` removes integrations without touching project `.psg/` directories. Following `main` requires the explicit `--channel dev` option. No host-specific PSG runtime is created.

Global installation makes PSG available; `.psg/config.yaml` opts a repository into governance. Project and global `on`/`off` switches are independent, so a globally installed Skill does not govern repositories that have not run `psg init`.

## Portable and derived state

PSG deliberately separates durable collaboration state from a local query cache:

| Location | Purpose | Commit? |
| --- | --- | --- |
| `.psg/config.yaml` | Authority order plus routing, review, dependency, and verification knobs | Yes |
| `.psg/policies.yaml` | Repository mutation policies | Yes |
| `.psg/state/project.yaml` | Decisions, tasks, requirements, constraints, issues, verification, debt, conflicts, and their edges | Yes |
| `.psg/local/psg.db` | Derived SQLite graph and index | No |
| `.psg/local/events.jsonl` | Local append-only operational log | No |

On startup or `state_sync`, changed portable YAML is merged into SQLite only when it is trusted. The portable projection also carries the runtime-known hash of `.psg/config.yaml`. Matching runtime exports are accepted; different hashes are accepted when Git reports the corresponding file clean, covering pull/checkout to committed state. A dirty state or config mismatch is blocked before config-defined verification commands can run and requires a separate user-owned acceptance action. After durable mutations, the graph is exported back to YAML. Code-derived nodes are rebuilt from the repository, allowing a fresh clone to recover project intent without sharing a machine-specific database.

Portable verification entries contain compact fields such as result, kind, check name, fingerprint, evidence hash, reference, exit code, and timestamp. Raw stdout/stderr is written under `.psg/local/verification/` and never exported to the committable YAML.

## Index and context freshness

The indexer hashes files and extracts Python symbols, signatures, and imports. Non-Python files remain file-level nodes. Incremental refresh preserves policies and attested decision-derived edges while replacing stale code structure. PSG v1 does not build a call graph.

Every context build first synchronizes portable state and refreshes the index. The router follows `targets`, `requires`, dependencies, constraints, and graph proximity within a token budget. Its lexical fallback scores both File and Symbol names, paths, qualified names, and signatures; it intentionally does not require a vector database. Confidence combines freshness, language coverage, provenance, and dependency certainty. If confidence is below the configured threshold, routing expands once within the same call and immediately rebuilds the result; it never reports an expansion that will only take effect later.

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

Unfreezing requires an explicit override and an accepted, user-approved Decision. An MCP caller can create only a proposed Decision; it cannot apply the mutation effect. The approved decision supersedes the previous lock, and a reason string alone is insufficient.

## Trust, evidence, and ship gate

PSG normalizes authority into four tiers: `CLAIMED`, `RUNTIME_ATTESTED`, `USER_APPROVED`, and reserved `EXTERNAL_ATTESTED`. Ordinary MCP input is always `CLAIMED`, regardless of a caller-supplied source or actor label. Runtime checks can create `RUNTIME_ATTESTED`; separate interactive local user actions can create `USER_APPROVED`. The operator gate lives in the runtime boundary rather than only in `cli.py`, so a direct Python call and the CLI reach the same TTY and exact-`APPROVE` check. Caller-supplied trust-tier strings cannot mint authority. No authenticated external attestation adapter ships in v1, so an `external_tool` string remains claimed.

MCP verification accepts only check names defined in `verification.commands`. The Agent chooses which approved check to run; the runtime chooses the command. Arbitrary `command` text is unavailable on the MCP surface. Advanced one-off commands remain a deliberate local CLI operation.

Acceptance passes require evidence kind, source, and reference. A claimed pass cannot self-assert user or external authority: it must reference a passing attested Verification ID or use the user-owned approval channel. Waivers require explicit user approval or an accepted user-approved Decision. All verification and acceptance evidence is bound to a worktree fingerprint; a subsequent code or governance change makes it stale.

The ship gate separately requires:

1. a passing policy validation of the current runtime-derived diff;
2. at least one trusted functional verification, not merely the policy pass;
3. passing or properly waived acceptance criteria;
4. no open issue that blocks the current task, as derived by the Task Contract;
5. required independent review for high-risk work, with reviewer actor different from the recorded builder actor and an approved review record; and
6. convergence within the configured review/fix budgets.

Debt starts as a claimed proposal and becomes accepted only through the user-owned approval action. Accepted debt records `what`, `why`, a permitted `ceiling`, and a `revisit_trigger`. A claimed trigger cannot reopen it; reviewers do not reopen it until trigger evidence is explicitly approved.

The runtime derives new blocker counts from stored Issue state rather than trusting numbers supplied to `review_record` or `fix_record`. Review and fix budgets are hard runtime-counted stops capped at 2, and imported state carrying a wider budget is clamped in both enforcement and the contract projection. Caller counts and churn remain advisory metrics.

## Task Contract and review boundary

Opening a task materializes a versioned **Task Contract**: goal boundary (intent and acceptance criteria), context boundary (targets, read set, constraints), mutation boundary (`WRITE`/`READ_ONLY`/`FORBIDDEN`), scope boundary (non-goals), review boundary, completion boundary, and risk boundary.

The contract has two states. A task opens as a **draft**: it records intent and requests scope, but holds no write authority, and the policy engine rejects any change against it. Initial context routing then **seals** it, freezing the derived mutation boundary into `authorized_write`, `authorized_read_only`, and `authorized_forbidden`. Only then is the contract hashed, and the hash covers that sealed authority.

The separation is deliberate. The routed working set is *context* and may grow with every expansion or reindex; the sealed boundary is *authority* and cannot. The policy engine reads only the sealed authority, so a file the router discovers after the seal becomes something to read, never something to write. Widening authority requires a new task; v1 has no task-amendment engine on purpose. A boundary the runtime derived from bare intent rather than an explicit declaration — a wildcard scope, high risk, or a sprawling write set — is marked `requires_scope_approval` and holds the ship gate until a user-owned interactive approval bound to that exact contract hash is recorded. `review_record` verifies that hash, which is the mechanical form of `NO_SCOPE_EXPANSION_BY_REVIEW`: a review round cannot redefine the task it is reviewing.

Severity and task scope are separate axes. Every Issue therefore carries a `relation_to_task` drawn from a closed set:

| Relation | Meaning | Blocks the current task |
| --- | --- | ---: |
| `caused_by_patch` | Introduced by the change under review | With evidence |
| `violates_acceptance` | Breaks a declared acceptance criterion | With evidence |
| `violates_project_constraint` | Breaks an accepted Constraint, Decision, policy, or locked node | With evidence |
| `pre_existing` | Already true before this task | No |
| `unrelated` | Outside this task's boundary | No |
| `future_improvement` | Desirable later work | No |

`blocks_current_task` is **derived**, never supplied. It is true only when the issue is open, its severity is `blocker` or `major`, its relation is one of the first three, and the runtime judged its evidence sufficient. Sufficiency is checked against real graph state: an acceptance violation must name an existing acceptance-criterion ID; a project-constraint violation must identify an existing Constraint, accepted Decision, policy reference, or restricted node; a patch-caused finding needs an affected changed node, concrete diff/runtime evidence, or a failing Verification.

Follow-up relations are retained and reported — the ship gate returns `current_task_issue_summary`, `follow_up_issue_summary`, and the follow-up issues themselves — so nothing is lost by classifying a finding out of scope.

`handoff` projects the contract, the changed files and symbols, relevant constraints and decisions, trusted verification, accepted debt, known issues with their relations, the current ship preview, and follow-up findings into a minimum-sufficient review pack. It evaluates convergence with persistence disabled, so reading a handoff never changes task status or appends to the event log. PSG's own `.psg/state/**` and `.psg/local/**` churn is excluded from the reviewer's changed-file list.

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

Conflicts are recorded as graph nodes. A lower-authority Skill cannot widen scope, unlock frozen state, weaken required verification, or reopen accepted debt. A user override that changes durable project governance must be anchored to an accepted user-approved Decision.

## Effective guardrails

`guardrails_get` reports the enforcement actually active in the runtime: frozen mutation enforcement, governance-state tamper rejection, out-of-scope blocking, stale-evidence rejection, verification allowlisting, accepted-debt behavior, independent-review requirements, and configured budgets. PSG v1 does not treat arbitrary YAML values as a generic rule-engine DSL. Only documented knobs such as budgets, dependency policy, risk review, and verification commands are configurable.

## Snapshot boundary

Snapshots serialize PSG graph state and bind it to Git revision. Restore creates a safety snapshot and restores graph state only. It never runs `git reset`, rewrites the working tree, or substitutes graph restoration for source recovery.
