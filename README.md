<div align="center">

<img src="docs/assets/psg-concept.png" alt="PSG — project state graph" width="100%">

# PSG

### project state graph

**Install once. Initialize once. Then code normally.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-6EAEDB?style=flat-square)](https://www.python.org/)
[![CI](https://github.com/niansia/PSG/actions/workflows/ci.yml/badge.svg)](https://github.com/niansia/PSG/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v1.1.2-F3B557?style=flat-square)](https://github.com/niansia/PSG/releases/tag/v1.1.2)
[![Status](https://img.shields.io/badge/status-complete%20MVP-FF9364?style=flat-square)](docs/acceptance.md)

**English** · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

</div>

PSG is a Skill bundle and local runtime that gives your coding agent a durable memory of the project, a clear boundary for what it may change, and an evidence-based definition of "done." It works beside Git and your existing Skills; it does not replace your coding agent or edit source code by itself.

> You keep asking for changes in normal language. PSG quietly retrieves the relevant context, protects locked decisions and files, runs the checks you authorize, keeps review inside the task you actually asked for, and prevents stale or unsupported evidence from being called complete.

## Install

Install once. The command installs the runtime, the complete Skill bundle, and MCP integration for every detected Codex, Claude Code, or Gemini CLI host.

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2" && psg setup
```

Then opt a Git project in once:

```text
cd your-project
psg init
```

## Use normally

That's it. From then on, talk to your coding agent as usual:

```text
幫我在購物車是空的時候顯示一段友善提示，完成後幫我驗證。
```

When the PSG Skill is active, it opens and tracks the task, retrieves bounded context, validates the real final diff, records trusted verification, keeps review inside the task, and evaluates the ship gate. You do not have to manually operate its graph for everyday work.

The only everyday controls are:

```powershell
psg status       # See whether PSG is active and what it knows
psg off          # Temporarily disable automatic PSG governance
psg on           # Enable it again
psg handoff      # Write a review pack for another model or a teammate
```

`psg off --global` and `psg on --global` pause or resume automatic governance across all initialized projects. `psg update` installs the newest stable `vX.Y.Z` release; it never follows `main` unless you explicitly choose `psg update --channel dev`. `psg doctor` and `psg uninstall` manage health and removal; uninstall preserves every project's durable `.psg/` state.

### Two usage modes

| Mode | Hosts | What you get |
| --- | --- | --- |
| **Full execution** | Codex · Claude Code · Gemini CLI | The Skill plus the local runtime and MCP server. Boundaries are *enforced*: mutation policy runs against the real diff, verification is runtime-attested, and the ship gate is machine-evaluated. |
| **Review / handoff** | ChatGPT · Claude · Gemini | Upload the review pack `psg handoff` writes. The reviewer reads the same Task Contract and the same review boundary. |

All six share one Task Contract. Only the execution hosts carry runtime enforcement — a chat reviewer follows the contract, it does not enforce it.

```powershell
psg handoff
```

The review pack is written to `.psg/local/handoffs/<task>.md`, which Git ignores. That matters: a review file written into the worktree becomes an untracked project change and blocks the very ship gate it exists to inform. `--output` writes elsewhere, and warns if the path is inside the worktree.

`psg handoff` is strictly read-only: it never changes task status, and it never writes to the event log.

## Supported agents

| Agent | PSG Skill | PSG runtime | Automatic setup |
| --- | ---: | ---: | ---: |
| Codex | ✓ | ✓ | ✓ |
| Claude Code | ✓ | ✓ | ✓ |
| Gemini CLI | ✓ | ✓ | ✓ |
| Generic Agent Skills + MCP | ✓ | ✓ | Manual |

`psg setup` auto-detects installed hosts, copies the entire folder bundle, registers `psg-mcp` through each host's native CLI, and records integration status. `psg setup --all` is an explicit alias for installing into every detected host. See [installation and host setup](docs/installation.md) for wheel/source installs and the advanced fallback.

## Why PSG

PSG is for the ordinary problems that make agent-assisted coding frustrating:

- every new chat rereads the same repository;
- important constraints disappear between sessions;
- a small request changes unrelated files;
- "tests passed" refers to code that has since changed;
- a review of a two-line fix returns a list of everything wrong with the project;
- repeated reviews keep reopening accepted trade-offs; or
- nobody can explain why the work was considered finished.

PSG turns those problems into five concrete safeguards:

| You need | PSG provides |
| --- | --- |
| The right context | A token-budgeted working set built from files, Python symbols, dependencies, tasks, decisions, and constraints. |
| Safe changes | Policy checks against the final Git state, including staged, unstaged, renamed, deleted, and untracked files. |
| Trustworthy proof | Verification and acceptance evidence tied to the exact working tree and its real source. |
| A bounded review | A Task Contract that decides which findings belong to *this* task, and which are follow-up. |
| A real finish line | `SHIPPABLE` only when scope, checks, criteria, review, current code, and risk requirements agree. |

## Task Boundary

> **Severity is not task scope.**
> **More context is not more authority.**
> **Every task has a boundary. Every review stays inside it.**
> **Review the task, not the universe.**

A `blocker` is a statement about how bad something is. It is not a statement about whether that something belongs to the task you asked for. Treating the two as the same thing is how a one-line fix turns into a week.

`psg task open` records a formal **Task Contract**: goal, context, mutation, scope, review, completion, and risk boundaries. `review_record` verifies its hash, so a review round can never widen the task it is reviewing.

### More context is not more authority

A task opens as a **DRAFT**. It states intent and requests scope, but holds no write authority at all — try to change a file and the gate says the contract is unsealed.

Initial localization then **SEALS** it: the mutation boundary PSG derived becomes `authorized_write`, `authorized_read_only`, and `authorized_forbidden`, and *that* is what the contract hash commits to.

```text
user request → DRAFT (no write authority)
                 ↓  localization
              SEALED → authorized_write is hashed
                 ↓
              builder may now change files
```

The distinction this protects is easy to lose:

| | Grows as work proceeds | Enforced as authority |
| --- | ---: | ---: |
| **Working set** — what to read | Yes | No |
| **Task Contract** — what may change | No | Yes |

Context expansion, re-indexing, and re-routing may all widen what a task **reads**. None of them can widen what it may **write**. A file discovered after the seal becomes context, never permission. If the work genuinely needs a file outside the boundary, that is a new task — not a quiet edit to this one.

When a boundary was derived from bare intent rather than declared — a wildcard write scope, a high-risk task, or a sprawling write set — PSG marks it `requires_scope_approval` and the ship gate holds until a person runs `psg task approve-scope`. The approval is bound to the hash it approved, so it does not survive a different boundary. MCP cannot reach that command.

Every finding must declare exactly one relation to the task. The set is closed:

| Relation | Can it block this task? |
| --- | --- |
| `caused_by_patch` | Yes, with evidence |
| `violates_acceptance` | Yes, with evidence |
| `violates_project_constraint` | Yes, with evidence |
| `pre_existing` | No — follow-up |
| `unrelated` | No — follow-up |
| `future_improvement` | No — follow-up |

A finding blocks the current task **only** when all four hold: it is open, it is `blocker` or `major`, its relation is one of the first three, and its evidence is sufficient. "Sufficient" is checked by the runtime, not claimed by the agent:

- an acceptance violation must name a real acceptance-criterion ID;
- a project-constraint violation must identify a real Constraint, accepted Decision, policy reference, or affected frozen/locked node; and
- a patch-caused finding needs a changed node, concrete diff/runtime evidence, or a failing verification.

**An agent cannot set `blocks_current_task`.** It reports a claim with a relation and evidence; the runtime derives whether that claim blocks. Follow-up findings stay fully visible in the ship gate and the handoff pack — they are never dropped, they simply do not hold the task hostage. Review rounds and targeted fix cycles are hard-capped at 2.

### Does it actually classify correctly?

The deterministic Task-Boundary benchmark runs 10 seeded review scenarios against the real runtime:

| Metric | PSG v1.1 |
| --- | ---: |
| Correct classifications | **10 / 10** |
| Blocking precision | **1.0** |
| Blocking recall | **1.0** |
| False reopening rate | **0.0** |

```powershell
python benchmarks/task_boundary_benchmark.py --output benchmarks/results/task-boundary-latest.json
```

See the [raw result](benchmarks/results/task-boundary-latest.json) and the [review boundary reference](skills/psg/references/review-boundary.md).

## PSG OFF versus ON

The question that actually matters is whether a real coding agent does better work with PSG
on than off. `benchmarks/agentic_ab.py` answers it as directly as a controlled experiment can:

- 10 paired Python coding tasks;
- the **same** Codex CLI, model, and reasoning effort on both sides;
- the same prompt, the same baseline commit, and separate clean Git worktrees;
- identical sandbox permissions and identical MCP configuration;
- **OFF** = PSG installed but disabled; **ON** = PSG enabled;
- success decided by a **hidden test** the agent never sees, plus the existing visible suite
  to catch regressions.

Task success is the primary metric. Token and wall-time numbers mean nothing without it.

Both sides must know exactly as much as each other, so the benchmark runs in two explicit
modes:

| Mode | Who is told the target file | What it measures |
| --- | --- | --- |
| `end_to_end` **(headline)** | Neither side | Whether PSG helps on a plain request, localization included |
| `controlled_routing` | Both sides | Governance value with localization held constant |

Telling only the ON side where the change belongs would hand PSG the answer and make any
context saving meaningless, so the harness never does it.

```powershell
python benchmarks/agentic_ab.py --output benchmarks/results/agentic-ab-latest.json --traces benchmarks/results/agentic-ab-traces
```

### Result

> **This result is superseded and does not describe v1.1.2.** It is kept because the data is
> real and deleting inconvenient evidence is worse than labelling it. Two things invalidate it
> as a claim about the current version:
>
> 1. **The agent read a different PSG than the one under test.** The traces show Codex loading
>    the globally installed `~/.codex/skills/psg/SKILL.md`, which was still the pre-v1.1.1
>    bundle telling it that `context_expand` could widen write scope. The runtime enforced the
>    new rules while the agent was instructed by the old ones. The harness now refuses to start
>    unless the installed Skill hash matches this checkout, and records the commit, runtime
>    version, Skill SHA-256, and CLI version in every result.
> 2. **Localization has since changed.** At the time, a bare intent produced write authority
>    over 1–8 files (median 7) and 9 of 10 tasks needed manual scope approval. v1.1.2 separates
>    retrieval candidates from authority candidates: on these same ten intents it now seals
>    exactly the one correct target file in 10/10 cases, with no manual approval required. Any
>    token or scope number measured before that change describes different software.
>
> A re-run is required before PSG makes any OFF-versus-ON claim again. The numbers below are
> published as measured, and as superseded.

10 pairs, `end_to_end` mode, Codex CLI with `gpt-5.5` at low reasoning effort, 2026-09-01.
All 20 runs completed; none timed out.

| | PSG OFF | PSG ON |
| --- | ---: | ---: |
| **Task success** | 9 / 10 | **10 / 10** |
| Non-target edits | 10 | **2** |
| Regressions | 0 | 0 |
| False `SHIPPABLE` | 0 | 0 |
| Scope approval required | — | 9 / 10 |
| Sealed without manual approval | — | 1 / 10 |
| Input tokens | 1,984,624 | 3,543,483 |
| Output tokens | 17,840 | 24,627 |
| Wall time | 763 s | 1,084 s |
| Reported cost | not exposed by the CLI | not exposed by the CLI |

A **non-target edit** is any change outside the single reference target file. Editing the
shared test fixture is the ordinary way an agent finishes a task, so this is a diagnostic of
where the change landed, not by itself a scope violation — which is why it is not called
"out-of-scope". The two approval rows are in this table rather than in a footnote because they
are the cost of the guardrail, paid by the operator.

**PSG kept the agent inside the task, and spent 79% more input tokens doing it.** Both halves
of that sentence are the result.

The scope effect is the cleanest signal. Every one of OFF's ten non-target edits was the
same file: `tests/test_existing.py`. In all ten tasks the agent rewrote the shared, pre-existing
test suite to match its own change. PSG ON did that twice — and in both of those cases PSG had
itself sealed that test file into the write boundary.

The cost is not a rounding error: +79% input tokens, +38% output tokens, +42% wall time,
ranging from +14% to +198% across the ten pairs.

### What this result does not show

- **Ten pairs is a small sample.** These are counts, not statistically significant effects.
- **PSG's own localization is wide.** Sealed write boundaries held 1–8 files (median 7). All
  ten contained the correct target, so recall was perfect — but precision was not, and nine of
  the ten were flagged `requires_scope_approval`. That is PSG correctly reporting that it had
  derived a boundary too broad to seal silently, and it is also the mechanism that let the test
  file into scope in the two ON tasks that edited it.
- **`unique_file_reads` did not separate the conditions** — 4 on both sides. It is a lower
  bound inferred from paths named in command events, and on this repository it is uninformative.
- The repository is generated by the harness. This is a **matched controlled agentic benchmark**,
  not a real-world one, and calling it one would be false.

See the [raw result](benchmarks/results/agentic-ab-latest.json), the
[sanitized traces](benchmarks/results/agentic-ab-traces), and the
[benchmark method and limitations](benchmarks/README.md) — including why `reported_cost_usd` is
`null` rather than a price inferred from token counts.

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
 ├──bounded-by─────▶ Task Contract ──▶ review boundary ──▶ follow-up findings
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
- The Task Contract opens as a draft, is sealed by initial localization, and hashes the authority it sealed, so neither routing nor review can widen what may be written.
- The convergence engine derives blocking from Issue state and relation, enforces runtime-counted budgets, and rejects claimed high-risk self-review.
- The portable state layer synchronizes durable graph state through `.psg/state/project.yaml`; local SQLite is rebuilt as needed.

## Trust model

PSG v1 deliberately uses a small trust model:

| Tier | Meaning | Can ordinary MCP create it? |
| --- | --- | ---: |
| `CLAIMED` | Agent, reviewer label, external-tool label, proposal, or caller-supplied statement | ✓ |
| `RUNTIME_ATTESTED` | PSG executed the configured check itself | No |
| `USER_APPROVED` | A person used the separate local approval action | No |
| `EXTERNAL_ATTESTED` | Reserved for a future authenticated CI/connector adapter | No |

MCP `decision_record` and `debt_record` therefore create proposals. Frozen unlocks, waivers, accepted debt, governance-state acceptance, and high-risk independent review are intentionally not self-authorizable through ordinary MCP. The local CLI is the v1 explicit approval boundary; the Skill contract requires an Agent to present the proposal and wait for the user instead of invoking an approval command itself.

The same principle governs review: an agent supplies claims and evidence, and the runtime — not the agent — decides what blocks.

It also governs how a task is recorded. `task_open` normally runs through an agent relaying a request, so the resulting Task, Requirement, and Constraint nodes are marked `agent_interpreted_user_intent` — not `user_explicit`. That is an honest label for what actually happened, and it is why a boundary the agent derived rather than the user declared can require explicit approval before shipping.

## Included interfaces

- [`skills/psg/`](skills/psg/) — the complete Skill bundle: entry playbook, agent metadata, and supporting references.
- [`artifacts/psg-skill-v1.1.2.zip`](artifacts/psg-skill-v1.1.2.zip) — the distributable Skill bundle.
- `psg` — human-friendly product commands plus `--json` and advanced/debug APIs.
- `psg-mcp` — local MCP server exposing the same graph, index, validation, verification, handoff, debt, conflict, and ship operations.

If MCP starts outside the target repository, set `PSG_PROJECT_ROOT` to that repository before running `psg-mcp`.

## Mechanics regression benchmark

The synthetic benchmark runs 12 sequential tasks over a generated 38-file Python repository. Each task supplies its target path, so it measures routing efficiency **after** localization.

| Result | PSG |
| --- | ---: |
| Tasks reaching `SHIPPABLE` | **12 / 12** |
| File reads versus all-files baseline | **89.69% fewer** |
| Estimated context tokens versus all-files baseline | **32.41% fewer** |
| Unauthorized frozen mutation | **Blocked** |
| Review stopped at configured budget | **Yes** |

This is a **mechanics regression benchmark**. It proves the routing, policy, and gate machinery still behaves against a disclosed all-files baseline. It is *not* evidence that PSG makes a real coding agent more efficient — that question belongs to the OFF-versus-ON benchmark above.

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

See the [raw result](benchmarks/results/latest.json) and the [benchmark method](benchmarks/README.md).

## Research

- [Evaluation plan](research/evaluation-plan.md) — how PSG should be measured on held-out real repositories.
- [Literature map and citations](research/README.md).
- [Architecture](docs/architecture.md) and [acceptance traceability](docs/acceptance.md).
- [Runtime operations](skills/psg/references/runtime-operations.md) and the [review boundary](skills/psg/references/review-boundary.md).

## Project map

```text
PSG/
├── src/psg/          # Runtime, store, router, policy, verification, contract, ship gate
├── skills/psg/       # Installable Skill bundle and supporting resources
├── tests/            # Automated behavior, packaging, and adversarial tests
├── benchmarks/       # Agentic A/B, Task Boundary, and mechanics benchmarks
├── scripts/          # Release build, validation, and install smoke
├── research/         # Literature map, citations, and evaluation plan
├── docs/             # Architecture, acceptance report, visual identity
├── artifacts/        # Installable wheel and Skill archive
└── .psg/             # This repository's portable PSG configuration/state
```

## Current boundary

PSG v1.1 is a complete, Python-first research MVP:

- Python receives rich symbol extraction; other files are indexed at file level.
- Both benchmarks run on generated repositories and say so. Neither is a real-world benchmark.
- PSG governs and evaluates work; the active coding agent still makes the edits.
- Snapshot restore restores PSG graph state only. It never resets Git or overwrites source files.
- `EXTERNAL_ATTESTED` is reserved until an authenticated CI/connector adapter exists; `source="external_tool"` alone remains a claim.
- A chat reviewer consuming a handoff pack follows the Task Contract; it cannot enforce it.
- Widening a sealed boundary is deliberately not automated. PSG has no task-amendment engine in v1: the answer to "this needs one more file" is a new task.

The next meaningful step is held-out evaluation on real repositories—not adding a UI, vector database, or more languages before the governance contract is proven.
