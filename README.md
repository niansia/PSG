<div align="center">

<img src="docs/assets/psg-hero.svg" alt="PSG — project state graph" width="100%">

**English** · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

</div>

# PSG — Project State Graph

**Keep AI coding agents inside the task, preserve project decisions across sessions, and know when the work is done.**

PSG gives coding agents a persistent task boundary and project state instead of making every model rediscover the repository and redefine the scope from scratch.

## Install

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2" && psg setup
```

Then, inside a Git project:

```text
psg init
```

That's it. Use Codex, Claude Code, or Gemini CLI normally.

### Everyday controls

```text
psg status
psg on
psg off
```

## What PSG does

Without PSG, a coding agent can keep discovering more files, more refactors, and more review suggestions until a small task becomes a project-wide rewrite.

PSG gives every task a boundary:

- **Context boundary** — what the agent needs to read.
- **Mutation boundary** — what it may change.
- **Review boundary** — which findings may block this task.
- **Completion boundary** — when the task is done and review must stop.

A reviewer may still discover unrelated bugs or future improvements, but PSG records them as follow-up work instead of silently expanding the current task.

> **Review the task, not the universe.**

## Why use PSG?

### 1. Stop scope drift

A task that only needs to fix A does not automatically become A + B + C + D because another model noticed more things that could be improved.

### 2. Preserve project decisions

Accepted decisions, constraints, frozen boundaries, and known debt do not need to be explained again every time the agent or session changes.

### 3. Make reviews converge

Only a regression caused by the current patch, an acceptance-criterion violation, or a project-constraint violation can block the current task. Other findings remain visible as follow-up work without reopening it.

### 4. Know when to stop

When acceptance criteria, deterministic verification, guardrails, and current-task blockers all agree, the gate returns:

```text
SHIPPABLE
```

General review stops there.

## Measured result: PSG OFF vs ON

10 matched Codex CLI task pairs, using the same model, prompt, and repository baseline. This controlled run predates the latest localization changes, so it is evidence of the measured trade-off—not a prediction of current performance.

| Metric | PSG OFF | PSG ON |
| --- | ---: | ---: |
| **Task success** | 9 / 10 | **10 / 10** |
| Non-target edits | 10 | **2** |
| Regressions | 0 | 0 |
| False `SHIPPABLE` | 0 | 0 |
| Input tokens | 1.98M | 3.54M |
| Wall time | 763 s | 1,084 s |

**PSG kept the agent closer to the task boundary, but it did not save tokens in this benchmark. It used 79% more input tokens and 42% more wall time.**

### Why did PSG use more tokens?

This benchmark measures small, independent, cold-start coding tasks. Each pair starts from a fresh worktree, so PSG pays its task-contract, routing, verification, and ship-gate overhead every time.

That benchmark therefore measures the cost of PSG governance, but it does not measure one of PSG's main long-horizon benefits: reusing durable project state across many sequential tasks, model switches, and review cycles instead of repeatedly rebuilding project understanding from chat history.

PSG also localized natural-language requests too broadly in this measured run. Every correct target was found, but the median derived write boundary contained seven files, causing nine of ten ON tasks to require scope approval. This was a precision problem, not a reason to weaken the boundary; current localization separates retrieval relevance from write authority and requires a fresh A/B run.

The result should therefore be read as:

> **Better scope discipline, with measurable overhead.**

**PSG does not currently claim end-to-end token savings from this benchmark.**

### Evidence status

Demonstrated in the included controlled and deterministic runs:

- ✓ Task-boundary enforcement
- ✓ Fewer non-target edits in the measured A/B run
- ✓ No observed correctness regression in this small run
- ✓ Evidence-based ship gate

Not yet demonstrated:

- End-to-end token savings
- Real-world long-horizon savings
- Generalization across large repositories and models

See the [benchmark protocol, raw results, and disclosed limitations](benchmarks/README.md).

## How it works

```text
User request
     ↓
Task Contract
     ↓
Relevant project state
     ↓
Coding agent
     ↓
Git diff + deterministic verification
     ↓
Bounded review
     ↓
SHIPPABLE
```

Git remains the implementation source of truth. PSG stores durable decisions and task state instead of full conversations. Context may expand when needed; write authority does not silently expand with it.

## Where PSG works

| Mode | Hosts | Capability |
| --- | --- | --- |
| **Full execution** | Codex, Claude Code, Gemini CLI | Read, edit, verify, enforce, and ship |
| **Review / handoff** | ChatGPT, Claude, Gemini | Review against the same Task Contract |

All hosts can use the same Task Boundary; execution hosts additionally receive runtime enforcement. Use `psg handoff` to create a compact review pack for another model or teammate.

## Current limits

- Rich symbol indexing is Python-first; other languages receive file-level indexing.
- The included agentic benchmark uses a small generated repository, not production projects.
- A fresh matched A/B run is still required for the current localization behavior.
- PSG has no authenticated external CI attestation adapter yet.
- PSG governs and evaluates changes; the coding agent still performs the edits.

## Detailed documentation

- [Installation and host setup](docs/installation.md)
- [Task Contract and review boundary](docs/task-contract.md)
- [Trust and security model](docs/trust-and-security.md)
- [CLI and MCP reference](docs/cli-and-mcp.md)
- [Architecture](docs/architecture.md)
- [Acceptance and release evidence](docs/acceptance.md)
- [Benchmarks](benchmarks/README.md)
- [Research](research/README.md)

A separate [mechanics regression benchmark](benchmarks/README.md#3-mechanics-regression-benchmark) verifies that routing can reduce selected context when the relevant target is already known. It is not an end-to-end agent token-savings claim.

PSG is also being evaluated as a long-horizon software-agent research system. See the [evaluation plan](research/evaluation-plan.md).

## License

[MIT](LICENSE)
