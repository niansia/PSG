# PSG v1.1.x acceptance traceability

This document maps the reviewed completion requirements to implemented behavior and automated evidence. The release is a complete Python-first MVP, not a claim of production maturity across every language or repository.

| Requirement | Implemented behavior | Automated evidence |
| --- | --- | --- |
| Complete Skill bundle | `skills/psg/` contains `SKILL.md`, agent metadata, and conditional references | Skill validator and archive layout check |
| Low-friction activation | `psg setup` auto-installs the bundle/MCP for detected hosts; `psg init` creates and indexes project state; project/global on/off control activation | setup adapter, CLI initialization, and health tests |
| Non-exclusive Skill coexistence | Explicit authority order, conflict records, and compatibility contract | conflict override/Decision test |
| Trusted governance state | Clean Git state can import; dirty portable/config hash mismatches are rejected before config commands can run | fresh-clone, portable-tamper, and config-allowlist tamper tests |
| Project state graph | Tasks, requirements, constraints, decisions, issues, verification, debt, and conflicts are materialized with effect edges | task and graph-projection tests |
| Python code graph | Incremental file index, AST symbols, signatures, and imports | index/router tests |
| Fresh bounded context | Traversal follows `targets`/`requires`; lexical fallback scores File and Symbol metadata; low confidence expands and rebuilds | context refresh, graph-route, symbol-localization, and expansion tests |
| Final Git truth | Runtime diff includes staged, unstaged, additions, deletions, renames, binaries, and untracked files | staged bypass, rename, untracked, and final-diff tests |
| Python symbol locks | Diff hunks are intersected with symbol ranges; policy survives incremental reindex | frozen-symbol hunk test |
| Architecture/decision locks | Only approved Decision effects and attested lock edges affect mutation policy | architecture-lock and claimed-lock spoof tests |
| Scope and interface policy | `WRITE`/`READ_ONLY`/`FORBIDDEN`, file policy, and interface signature checks | policy regression tests |
| Dependency discipline | New manifest additions require task-level justification under conservative dependency policy | dependency-justification test |
| Trust tiers | MCP data remains `CLAIMED`; only runtime/user channels attest or approve; external and reviewer labels cannot self-promote | external-source, Decision unlock, and reviewer spoof tests |
| Verification command boundary | MCP selects configured check names and cannot provide arbitrary shell commands | allowlist and MCP schema tests |
| Compact portable evidence | Git state excludes raw stdout/stderr while local logs retain full output | compact-evidence and local-log test |
| Functional verification | A policy pass cannot substitute for a trusted functional check | policy-not-functional test |
| Strict acceptance/waiver | Passes require an attested Verification reference or user approval; waivers require user approval or accepted Decision | acceptance authority and trust-spoof tests |
| Fresh evidence | Verification and criteria evidence are bound to the current worktree fingerprint | time-of-check/time-of-use test |
| High-risk independent review | A distinct actor label remains claimed; high-risk work needs a distinct approved reviewer record | claimed/approved reviewer tests |
| Evidence-backed issues | Unsupported blocker/major claims are demoted; affected nodes and violated criteria are linked | issue evidence test |
| Accepted debt | Debt begins proposed, requires user approval, and cannot reopen from a claimed trigger | accepted-debt, trigger-spoof, and annotation tests |
| Bounded convergence | Runtime derives blocker changes from Issue state; only runtime-counted review/fix budgets hard-stop loops; caller counts/churn are advisory | convergence-budget and derived-blocker tests |
| Stable graph snapshots | Safety snapshot and graph-only restore, with no destructive Git action | snapshot restore test |
| Complete MCP surface | Index, graph, actual/proposed validation, verification, debt, conflict, status, and ship tools | MCP schema completeness test |
| Task Contract | Opening a task records goal, context, mutation, scope, review, completion, and risk boundaries | task-contract projection tests |
| Sealed write authority | A task opens as a DRAFT holding no write authority; initial localization seals the mutation boundary and the hash covers that sealed authority, not just the request | draft-blocks-changes, sealed-into-hash, and hash-sensitivity tests |
| Authority is not context | Context expansion and re-routing widen what a task READS and never what it may WRITE | expansion and post-seal discovery tests |
| Agent-derived breadth needs a person | A wildcard, high-risk, or sprawling boundary an agent derived from bare intent requires user approval, bound to the contract hash it approved | scope-approval and stale-approval tests |
| Handoff does not pollute the worktree | The review pack defaults to ignored local state and never becomes a project change | handoff-to-ship regression test |
| Review boundary | Findings carry one relation from a closed set; reviewers may classify but never redefine the task | relation-enum, unknown-relation, and no-scope-expansion tests |
| Runtime-derived blocking | `blocks_current_task` is derived from status, severity, relation, and runtime-checked evidence sufficiency | patch-caused, acceptance, constraint, pre-existing, unrelated, and future-improvement tests |
| Visible follow-up work | Out-of-boundary findings stay reported and never block the current task | follow-up visibility and ship-after-fix tests |
| Read-only handoff | `psg handoff` and `handoff_build` build a review pack without changing task status or the event log | handoff read-only test |
| Hard convergence budgets | Review and fix cycles cap at 2; imported wider budgets are clamped in enforcement and projection | budget-exhaustion and imported-budget clamp tests |
| Schema migration | A schema-1 database opens, keeps its issues, and defaults them to non-blocking follow-up | legacy-database and legacy-portable-state tests |
| Live MCP transport | Git-backed MCP tools answer over real stdio within a bounded time | live stdio MCP regression test |
| Cross-platform CI | Ubuntu/Windows/macOS on Python 3.10 and Ubuntu on Python 3.13 run tests, wheel build, and clean install smoke | `.github/workflows/ci.yml`, `scripts/build_release.py` |
| Task-Boundary benchmark | 10 seeded scenarios report blocking precision, recall, and false reopening rate | `benchmarks/results/task-boundary-latest.json` |
| Matched agentic benchmark | 10 paired tasks, one Codex CLI and model, same prompt and baseline commit, separate clean worktrees, hidden tests, symmetric target disclosure | Harness verified; the published run is **superseded** and is not evidence for this version — a re-run is required. That older result file predates two renames: its field is `out_of_scope_edits` (now `non_target_edits`) and it has no `provenance` block |
| Benchmark provenance | A run aborts unless the Skill the agent loads hashes equal to this checkout, and records commit, runtime version, Skill SHA-256, and CLI version | `_run_provenance()` abort path |
| Interactive approval | The gate lives in the runtime, below the CLI, so importing `psg.runtime` and calling an approval method directly hits the same terminal check. A non-interactive caller and a piped answer are both refused | all-approval-paths and piped-answer tests |
| Retrieval is not authority | A lexical match makes a file readable, not writable; an ambiguous or weak match grants no write authority at all | confident-match, ambiguous, and weak-match tests |
| Mechanics regression benchmark | 12 tasks; full selected-file contents plus tool payload counted; frozen mutation blocked | `benchmarks/results/latest.json` |

## Verified release results

- Automated behavior, adversarial, packaging, and Skill archive suite: **PASS on current CI** across Ubuntu, Windows, and macOS. A hard-coded test count goes stale every time a test is added, so the CI badge is the live answer.
- Ruff lint and format checks: **passing**.
- Task-Boundary benchmark: **10/10 correct**, blocking precision **1.0**, blocking recall **1.0**, false reopening rate **0.0**.
- Mechanics regression benchmark: **12/12 SHIPPABLE**.
- Matched agentic OFF/ON benchmark: **superseded, not current evidence.** The published run was measured while the agent loaded a pre-v1.1.1 global Skill, and localization has since changed, so its numbers describe different software. The data is kept and labelled rather than deleted. A re-run is required before any OFF/ON claim.
- Localization precision on the same ten benchmark intents after the retrieval/authority split: **10/10 seal exactly the correct single target file**, **0/10 need manual scope approval** (previously 1-8 files, median 7, with 9/10 needing approval).
- Benchmark file-read reduction: **89.69%** versus disclosed all-files baseline.
- Benchmark context-token reduction: **32.41%**, counting the serialized context payload and actual contents of every selected source file.
- Unauthorized frozen mutation: **blocked**.
- Review stopping rule: **stopped at configured budget**.

## Deliberate v1 boundaries

- Rich symbol extraction is Python-first; other languages receive file-level indexing.
- Both benchmarks run on generated repositories. The agentic A/B is a *matched controlled* benchmark with strong internal validity about the PSG contrast and limited external validity; generalization still requires the held-out real-repository protocol in `research/evaluation-plan.md`.
- The Codex CLI exposes no per-run dollar charge, so the agentic benchmark reports `reported_cost_usd: null` rather than inferring a price.
- PSG governs and evaluates; the active agent performs source edits.
- Local SQLite is a cache, not a collaboration artifact or source of truth.
- No authenticated CI/connector adapter is included yet; `EXTERNAL_ATTESTED` is reserved and external-tool labels remain claims.
- No vector database, web UI, multi-language semantic parser, or autonomous patch application is included in v1.
