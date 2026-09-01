<div align="center">

<img src="docs/assets/psg-concept.png" alt="PSG — project state graph" width="100%">

# PSG

### project state graph

**Install once. Initialize once. Then code normally.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-6EAEDB?style=flat-square)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-38%20passing-79B9A4?style=flat-square)](tests/)
[![Release](https://img.shields.io/badge/release-v1.0.0-F3B557?style=flat-square)](artifacts/)
[![Status](https://img.shields.io/badge/status-complete%20MVP-FF9364?style=flat-square)](docs/acceptance.md)

</div>

PSG is a Skill bundle and local runtime that gives your coding agent a durable memory of the project, a clear boundary for what it may change, and an evidence-based definition of “done.” It works beside Git and your existing Skills; it does not replace your coding agent or edit source code by itself.

> You keep asking for changes in normal language. PSG quietly retrieves the relevant context, protects locked decisions and files, runs the checks you authorize, and prevents stale or unsupported evidence from being called complete.

## Why use it?

PSG is for the ordinary problems that make agent-assisted coding frustrating:

- every new chat rereads the same repository;
- important constraints disappear between sessions;
- a small request changes unrelated files;
- “tests passed” refers to code that has since changed;
- repeated reviews keep reopening accepted trade-offs; or
- nobody can explain why the work was considered finished.

PSG turns those problems into four concrete safeguards:

| You need | PSG provides |
| --- | --- |
| The right context | A token-budgeted working set built from files, Python symbols, dependencies, tasks, decisions, and constraints. |
| Safe changes | Policy checks against the final Git state, including staged, unstaged, renamed, deleted, and untracked files. |
| Trustworthy proof | Verification and acceptance evidence tied to the exact working tree and its real source. |
| A real finish line | `SHIPPABLE` only when scope, checks, criteria, review, current code, and risk requirements agree. |

## Get started

You need Python 3.10+ and a Git repository. Clone PSG once, install its runtime, and copy the complete Skill folder—not only `SKILL.md`.

```powershell
git clone https://github.com/niansia/PSG.git
cd PSG
python -m pip install ".[mcp]"
Copy-Item -Recurse .\skills\psg "$env:USERPROFILE\.codex\skills\psg"
```

In the project where you want PSG:

```powershell
cd C:\path\to\your\project
psg init
```

That is the normal setup. From then on, talk to your coding agent as usual:

```text
幫我在購物車是空的時候顯示一段友善提示，完成後幫我驗證。
```

When the PSG Skill is active, it opens and tracks the task, retrieves bounded context, validates the real final diff, records trusted verification, and evaluates the ship gate. You do not have to manually operate its graph for everyday work.

Useful controls:

```powershell
psg status       # See whether PSG is active and what it knows
psg guardrails   # See current authority, dependency, and safety rules
psg off          # Temporarily disable automatic PSG governance
psg on           # Enable it again
```

## What gets added to your project?

`psg init` creates a small `.psg/` folder and performs the first index:

```text
.psg/
├── config.yaml          # Committable project settings and guardrails
├── policies.yaml        # Committable mutation policies
├── state/project.yaml   # Committable decisions, tasks, constraints, and evidence
└── local/               # Ignored derived SQLite index and event log
```

The YAML state is portable across clones and teammates. The SQLite database is a disposable local cache and is never meant to be committed. Source code and Git remain authoritative.

## It works with your other Skills

PSG is a governance layer, not an exclusive workflow. A testing Skill can still test, a design Skill can still design, and a framework Skill can still implement. PSG supplies project context and enforces the accepted boundary around their work.

Its authority order is explicit: host rules and your current instruction come first; accepted project decisions and repository rules come before task-specific or general Skill preferences. Another Skill may propose a change, but it cannot silently unlock a frozen node, widen task scope, weaken required verification, or reopen accepted debt without its recorded trigger.

See the [compatibility contract](skills/psg/references/compatibility-contract.md) for the exact rules.

## How it works

```text
ordinary request
      │
      ▼
Task ──requires──▶ Requirement
 │                    │
 ├──targets────────▶ code graph ◀──constrained-by── Decision / Constraint
 │                    │
 └──verified-by────▶ Verification
                           │
                           ▼
                    evidence-aware ship gate
```

- The indexer maps files, Python symbols, imports, calls, and structured `psg-debt` annotations.
- The router selects a bounded working set and automatically expands it once when confidence is low.
- The policy engine checks actual Git hunks against file, symbol, decision, architecture, scope, and dependency rules.
- The verification engine distinguishes runtime-executed, external-tool, reviewer, user-asserted, and model-reported evidence.
- The convergence engine prevents stale evidence, unsupported blockers, endless review loops, and high-risk self-review.
- The portable state layer synchronizes durable graph state through `.psg/state/project.yaml`; local SQLite is rebuilt as needed.

## Included interfaces

- [`skills/psg/`](skills/psg/) — the complete Skill bundle: entry playbook, agent metadata, and supporting references.
- [`artifacts/psg-skill-v1.0.0.zip`](artifacts/psg-skill-v1.0.0.zip) — the distributable Skill bundle.
- `psg` — JSON CLI used for setup, diagnostics, and automation.
- `psg-mcp` — local MCP server exposing the same graph, index, validation, verification, debt, conflict, and ship operations.

If MCP starts outside the target repository, set `PSG_PROJECT_ROOT` to that repository before running `psg-mcp`.

## Reproducible benchmark

The included synthetic benchmark runs 12 sequential tasks over a generated 38-file Python repository. Its context estimate counts both the serialized PSG tool payload and the complete contents of every selected source file.

| Result | PSG v1.0 |
| --- | ---: |
| Tasks reaching `SHIPPABLE` | **12 / 12** |
| File reads versus all-files baseline | **89.69% fewer** |
| Estimated context tokens versus all-files baseline | **22.4% fewer** |
| Unauthorized frozen mutation | **Blocked** |
| Review stopped at configured budget | **Yes** |

These results validate this implementation’s mechanics; they do not claim general performance across real repositories, languages, or agents. Reproduce them with:

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

See the [raw result](benchmarks/results/latest.json), [benchmark method](benchmarks/README.md), and [real-world evaluation plan](research/evaluation-plan.md).

## Project map

```text
PSG/
├── src/psg/          # Runtime, store, router, policy, verification, ship gate
├── skills/psg/       # Installable Skill bundle and supporting resources
├── tests/            # 38 automated behavior and adversarial tests
├── benchmarks/       # Reproducible 12-task benchmark
├── research/         # Literature map, citations, and evaluation plan
├── docs/             # Architecture, acceptance report, visual identity
├── artifacts/        # Installable wheel and Skill archive
└── .psg/             # This repository's portable PSG configuration/state
```

For technical details, read the [architecture](docs/architecture.md), [acceptance traceability](docs/acceptance.md), [runtime operations](skills/psg/references/runtime-operations.md), and [research map](research/README.md).

## Current boundary

PSG v1.0 is a complete, Python-first research MVP:

- Python receives rich symbol extraction; other files are indexed at file level.
- The benchmark is synthetic and deliberately reports that limitation.
- PSG governs and evaluates work; the active coding agent still makes the edits.
- Snapshot restore restores PSG graph state only. It never resets Git or overwrites source files.

The next meaningful step is held-out evaluation on real repositories—not adding a UI, vector database, or more languages before the governance contract is proven.
