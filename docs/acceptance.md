# PSG v1.0 acceptance traceability

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
| Minimal CI | Python 3.10 install, Ruff format/lint, and Pytest on push/PR | `.github/workflows/ci.yml` |
| Reproducible benchmark | 12 tasks; full selected-file contents plus tool payload counted; frozen mutation blocked | `benchmarks/results/latest.json` |

## Verified release results

- Automated behavior, adversarial, packaging, and Skill archive tests: **64 passing locally**; CI repeats the suite on Python 3.10.
- Ruff lint and format checks: **passing**.
- Synthetic sequential benchmark: **12/12 SHIPPABLE**.
- Benchmark file-read reduction: **89.69%** versus disclosed all-files baseline.
- Benchmark context-token reduction: **32.41%**, counting the serialized context payload and actual contents of every selected source file.
- Unauthorized frozen mutation: **blocked**.
- Review stopping rule: **stopped at configured budget**.

## Deliberate v1 boundaries

- Rich symbol extraction is Python-first; other languages receive file-level indexing.
- The benchmark is synthetic. Generalization requires the held-out real-repository protocol in `research/evaluation-plan.md`.
- PSG governs and evaluates; the active agent performs source edits.
- Local SQLite is a cache, not a collaboration artifact or source of truth.
- No authenticated CI/connector adapter is included yet; `EXTERNAL_ATTESTED` is reserved and external-tool labels remain claims.
- No vector database, web UI, multi-language semantic parser, or autonomous patch application is included in v1.
