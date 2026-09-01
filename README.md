<div align="center">

<img src="docs/assets/psg-concept.png" alt="PSG — project state graph" width="100%">

# PSG

### project state graph

**Install once. Initialize once. Then code normally.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-6EAEDB?style=flat-square)](https://www.python.org/)
[![CI](https://github.com/niansia/PSG/actions/workflows/ci.yml/badge.svg)](https://github.com/niansia/PSG/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v1.0.0-F3B557?style=flat-square)](artifacts/)
[![Status](https://img.shields.io/badge/status-complete%20MVP-FF9364?style=flat-square)](docs/acceptance.md)

</div>

PSG is a Skill bundle and local runtime that gives your coding agent a durable memory of the project, a clear boundary for what it may change, and an evidence-based definition of “done.” It works beside Git and your existing Skills; it does not replace your coding agent or edit source code by itself.

> You keep asking for changes in normal language. PSG quietly retrieves the relevant context, protects locked decisions and files, runs the checks you authorize, and prevents stale or unsupported evidence from being called complete.

## Install

Install once. The command installs the runtime, the complete Skill bundle, and MCP integration for every detected Codex, Claude Code, or Gemini CLI host.

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git" && psg setup
```

Then opt a Git project in once:

```text
cd your-project
psg init
```

That's it. From then on, talk to your coding agent as usual:

```text
幫我在購物車是空的時候顯示一段友善提示，完成後幫我驗證。
```

When the PSG Skill is active, it opens and tracks the task, retrieves bounded context, validates the real final diff, records trusted verification, and evaluates the ship gate. You do not have to manually operate its graph for everyday work.

The only everyday controls are:

```powershell
psg status       # See whether PSG is active and what it knows
psg off          # Temporarily disable automatic PSG governance
psg on           # Enable it again
```

`psg off --global` and `psg on --global` pause or resume automatic governance across all initialized projects. `psg update`, `psg doctor`, and `psg uninstall` manage the installation; uninstall preserves every project's durable `.psg/` state.

## Supported agents

| Agent | PSG Skill | PSG runtime | Automatic setup |
| --- | ---: | ---: | ---: |
| Codex | ✓ | ✓ | ✓ |
| Claude Code | ✓ | ✓ | ✓ |
| Gemini CLI | ✓ | ✓ | ✓ |
| Generic Agent Skills + MCP | ✓ | ✓ | Manual |

`psg setup` auto-detects installed hosts, copies the entire folder bundle, registers `psg-mcp` through each host's native CLI, and records integration status. `psg setup --all` is an explicit alias for installing into every detected host. See [installation and host setup](docs/installation.md) for wheel/source installs and the advanced fallback.

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

## What gets added to your project?

`psg init` creates a small `.psg/` folder and performs the first index:

```text
.psg/
├── config.yaml          # Committable project settings and real configuration knobs
├── policies.yaml        # Committable mutation policies
├── state/project.yaml   # Committable decisions, tasks, constraints, and evidence
└── local/               # Ignored SQLite, event log, cache, and raw check output
```

The YAML state is portable across clones and teammates. It stores compact evidence metadata and hashes, never full command output. Raw verification logs, SQLite, and events stay under ignored `.psg/local/`. Source code and Git remain authoritative.

On startup, PSG imports changed governance state only when it matches the last runtime export or Git reports it clean, which covers a pull or checkout to committed state. A dirty hash mismatch in `project.yaml` or `config.yaml` is blocked before config-defined commands can run, until a person reviews and explicitly accepts it.

## It works with your other Skills

PSG is a governance layer, not an exclusive workflow. A testing Skill can still test, a design Skill can still design, and a framework Skill can still implement. PSG supplies project context and enforces the accepted boundary around their work.

Its authority order is explicit: host rules and your current instruction come first; accepted project decisions and repository rules come before task-specific or general Skill preferences. Another Skill may propose a change, but it cannot silently unlock a frozen node, widen task scope, weaken required verification, or reopen accepted debt without its recorded trigger and approval.

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

- The indexer maps files, Python symbols, imports, and structured `psg-debt` annotations.
- The router selects a bounded working set and automatically expands it once when confidence is low.
- The policy engine checks actual Git hunks against file, symbol, decision, architecture, scope, and dependency rules.
- The verification engine accepts only configured check names over MCP and keeps raw output local.
- The trust layer separates Agent claims, runtime-attested evidence, and explicit user approval; a caller cannot promote its own strings into authority.
- The convergence engine derives blocker changes from Issue state, enforces runtime-counted budgets, and rejects claimed high-risk self-review.
- The portable state layer synchronizes durable graph state through `.psg/state/project.yaml`; local SQLite is rebuilt as needed.

## Trust boundary

PSG v1 deliberately uses a small trust model:

| Tier | Meaning | Can ordinary MCP create it? |
| --- | --- | ---: |
| `CLAIMED` | Agent, reviewer label, external-tool label, proposal, or caller-supplied statement | ✓ |
| `RUNTIME_ATTESTED` | PSG executed the configured check itself | No |
| `USER_APPROVED` | A person used the separate local approval action | No |
| `EXTERNAL_ATTESTED` | Reserved for a future authenticated CI/connector adapter | No |

MCP `decision_record` and `debt_record` therefore create proposals. Frozen unlocks, waivers, accepted debt, governance-state acceptance, and high-risk independent review are intentionally not self-authorizable through ordinary MCP. The local CLI is the v1 explicit approval boundary; the Skill contract requires an Agent to present the proposal and wait for the user instead of invoking an approval command itself.

## Included interfaces

- [`skills/psg/`](skills/psg/) — the complete Skill bundle: entry playbook, agent metadata, and supporting references.
- [`artifacts/psg-skill-v1.0.0.zip`](artifacts/psg-skill-v1.0.0.zip) — the distributable Skill bundle.
- `psg` — human-friendly product commands plus `--json` and advanced/debug APIs.
- `psg-mcp` — local MCP server exposing the same graph, index, validation, verification, debt, conflict, and ship operations.

If MCP starts outside the target repository, set `PSG_PROJECT_ROOT` to that repository before running `psg-mcp`.

## Reproducible benchmark

The included synthetic benchmark runs 12 sequential tasks over a generated 38-file Python repository. Its context estimate counts both the serialized PSG tool payload and the complete contents of every selected source file.

| Result | PSG v1.0 |
| --- | ---: |
| Tasks reaching `SHIPPABLE` | **12 / 12** |
| File reads versus all-files baseline | **89.69% fewer** |
| Estimated context tokens versus all-files baseline | **32.41% fewer** |
| Unauthorized frozen mutation | **Blocked** |
| Review stopped at configured budget | **Yes** |

These results validate context routing after the target path is supplied. They do not measure natural-language target localization and do not claim general performance across real repositories, languages, or agents. Reproduce them with:

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

See the [raw result](benchmarks/results/latest.json), [benchmark method](benchmarks/README.md), and [real-world evaluation plan](research/evaluation-plan.md).

## Project map

```text
PSG/
├── src/psg/          # Runtime, store, router, policy, verification, ship gate
├── skills/psg/       # Installable Skill bundle and supporting resources
├── tests/            # Automated behavior, packaging, and adversarial tests
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
- `EXTERNAL_ATTESTED` is reserved until an authenticated CI/connector adapter exists; `source="external_tool"` alone remains a claim.

The next meaningful step is held-out evaluation on real repositories—not adding a UI, vector database, or more languages before the governance contract is proven.
