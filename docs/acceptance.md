# PSG v1.0 acceptance traceability

This document maps the reviewed completion requirements to implemented behavior and automated evidence. The release is a complete Python-first MVP, not a claim of production maturity across every language or repository.

| Requirement | Implemented behavior | Automated evidence |
| --- | --- | --- |
| Complete Skill bundle | `skills/psg/` contains `SKILL.md`, agent metadata, and conditional references | Skill validator and archive layout check |
| Low-friction activation | `psg init` creates portable/local state and performs the first index; `on`/`off` controls automatic governance | CLI initialization and health tests |
| Non-exclusive Skill coexistence | Explicit authority order, conflict records, and compatibility contract | conflict override/Decision test |
| Portable project state | Committable `.psg/state/project.yaml`; ignored SQLite/events are derived locally | fresh-clone portable-state test |
| Project state graph | Tasks, requirements, constraints, decisions, issues, verification, debt, and conflicts are materialized with effect edges | task and graph-projection tests |
| Python code graph | Incremental file index, AST symbols, signatures, imports, and calls | index/router tests |
| Fresh bounded context | State sync and index refresh happen before routing; low confidence expands once and rebuilds immediately | context refresh/expansion tests |
| Final Git truth | Runtime diff includes staged, unstaged, additions, deletions, renames, binaries, and untracked files | staged bypass, rename, untracked, and final-diff tests |
| Python symbol locks | Diff hunks are intersected with symbol ranges; policy survives incremental reindex | frozen-symbol hunk test |
| Architecture/decision locks | `locks` and `constrained-by` graph edges affect effective mutation policy | architecture-lock test |
| Scope and interface policy | `WRITE`/`READ_ONLY`/`FORBIDDEN`, file policy, and interface signature checks | policy regression tests |
| Dependency discipline | New manifest additions require task-level justification under conservative dependency policy | dependency-justification test |
| Provenance-aware evidence | Runtime, external-tool, reviewer, user, and model sources are distinct; models cannot self-assert runtime evidence | untrusted-model evidence test |
| Functional verification | A policy pass cannot substitute for a trusted functional check | policy-not-functional test |
| Strict acceptance/waiver | Passes require kind/source/reference; waivers require user assertion or Decision | acceptance authority test |
| Fresh evidence | Verification and criteria evidence are bound to the current worktree fingerprint | time-of-check/time-of-use test |
| High-risk independent review | Reviewer actor must differ from the stored builder actor | distinct-actor test |
| Evidence-backed issues | Unsupported blocker/major claims are demoted; affected nodes and violated criteria are linked | issue evidence test |
| Accepted debt | Debt records what/why/ceiling/revisit trigger; reviewers do not reopen before the trigger | accepted-debt test and annotation test |
| Bounded convergence | Review and fix budgets plus no-new-blocker stopping prevent infinite loops | convergence-budget tests |
| Stable graph snapshots | Safety snapshot and graph-only restore, with no destructive Git action | snapshot restore test |
| Complete MCP surface | Index, graph, actual/proposed validation, verification, debt, conflict, status, and ship tools | MCP schema completeness test |
| Minimal CI | Python 3.10 install, Ruff format/lint, and Pytest on push/PR | `.github/workflows/ci.yml` |
| Reproducible benchmark | 12 tasks; full selected-file contents plus tool payload counted; frozen mutation blocked | `benchmarks/results/latest.json` |

## Verified release results

- Automated tests: **38 passing**.
- Ruff lint and format checks: **passing**.
- Synthetic sequential benchmark: **12/12 SHIPPABLE**.
- Benchmark file-read reduction: **89.69%** versus disclosed all-files baseline.
- Benchmark context-token reduction: **22.4%**, counting the serialized context payload and actual contents of every selected source file.
- Unauthorized frozen mutation: **blocked**.
- Review stopping rule: **stopped at configured budget**.

## Deliberate v1 boundaries

- Rich symbol extraction is Python-first; other languages receive file-level indexing.
- The benchmark is synthetic. Generalization requires the held-out real-repository protocol in `research/evaluation-plan.md`.
- PSG governs and evaluates; the active agent performs source edits.
- Local SQLite is a cache, not a collaboration artifact or source of truth.
- No vector database, web UI, multi-language semantic parser, or autonomous patch application is included in v1.
