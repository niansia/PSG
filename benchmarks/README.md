# Benchmarks

PSG ships three benchmarks. They answer different questions, and only one of them is
evidence about an agent doing real work.

| Benchmark | Question it answers | Kind |
| --- | --- | --- |
| `agentic_ab.py` | Does a real coding agent do better work with PSG on than off? | Matched controlled agentic benchmark |
| `task_boundary_benchmark.py` | Does the runtime block exactly the findings that belong to the task? | Deterministic unit-level benchmark |
| `sequential_benchmark.py` | Do the routing, policy, and gate mechanics still behave? | Mechanics regression benchmark |

## 1. Matched controlled agentic benchmark

`agentic_ab.py` runs 10 paired Python coding tasks through the **same** Codex CLI, the
same model, and the same reasoning effort. Each pair uses the same prompt, the same
baseline commit, and two separate clean Git worktrees:

- **OFF** — PSG is installed but disabled for the project.
- **ON** — PSG is enabled with a predeclared Task Contract and runtime enforcement.

Both conditions received identical sandbox permissions and an identical MCP configuration
(`--ignore-user-config`, with `PSG_PROJECT_ROOT` pinned to the worktree). That comparison
isolated project-level enablement, but it was not a clean no-PSG tooling baseline: the OFF
condition still had the PSG MCP server registered and exposed to the agent.

Success is decided by a **hidden test** the agent never sees, plus the pre-existing
visible test suite to catch regressions. Task success is the primary metric; token and
wall-time numbers are secondary and are only meaningful next to it.

```powershell
python benchmarks/agentic_ab.py --output benchmarks/results/agentic-ab-latest.json --traces benchmarks/results/agentic-ab-traces
```

Validate the harness on one pair first with `--smoke`. A smoke result is never published
evidence.

### What this benchmark is not

It runs on a **generated** repository built by the harness, not on real-world projects.
Calling it a real-world benchmark would be false. It is a *matched controlled* benchmark:
strong internal validity about the PSG-versus-no-PSG contrast, limited external validity
about any particular codebase.

Other disclosed limits:

- Ten task pairs is a small sample, and the results are reported as counts, not as
  statistically significant effects.
- `unique_file_reads` is a **lower bound**, inferred from repository paths explicitly
  named in Codex command events. It undercounts reads the agent performs another way.
- The Codex CLI does not expose a per-run dollar charge, so `reported_cost_usd` is
  `null`. Tokens and wall time are reported; a price is not invented from them.
- Raw traces are written to `results/agentic-ab-traces/` with local absolute paths redacted
  to `<WORKTREE>`, `<BENCHMARK_BASE>`, `<TMP>`, and `<USER_HOME>`.

**The published run in `results/agentic-ab-latest.json` is superseded.** It was measured while
Codex loaded a globally installed pre-v1.1.1 Skill rather than the one in the checkout under
test, and localization has since been rewritten, so its numbers describe different software.
The data and traces are kept and labelled rather than deleted; see the README for the full
explanation. A re-run is required before PSG makes any OFF-versus-ON claim.

### Superseded raw result

These measurements remain here and in `results/agentic-ab-latest.json` for transparency.
They are historical observations, not current-version performance evidence.

| Metric | PSG OFF | PSG ON |
| --- | ---: | ---: |
| Task success | 9 / 10 | 10 / 10 |
| Non-target edits | 10 | 2 |
| Regressions | 0 | 0 |
| False `SHIPPABLE` | 0 | 0 |
| Raw input tokens | 1,984,624 | 3,543,483 |
| Cached input tokens | 1,786,112 | 3,274,112 |
| Output tokens | 17,840 | 24,627 |
| Wall time | 762.558 s | 1,083.603 s |

The raw input-token difference rounds to **+79%**, and the wall-time difference rounds to
**+42%**. Those ratios are retained as part of the superseded record, not as claims about
the current release.

### Additional limitations identified from the preserved traces

- The OFF condition still had the PSG MCP server registered, so it was not a clean no-PSG
  tooling baseline.
- Trace accounting suggests repeated Skill instructions and MCP tool definitions across
  agent turns were a major contributor to raw input-token volume.
- PSG ON introduced more interaction rounds, multiplying this fixed per-turn context cost.
- This interpretation is a trace-based estimate, not a re-measured causal result.
- Most input tokens in both conditions were cached. Raw input-token ratios therefore must
  not be interpreted directly as monetary-cost ratios.
- The retrieval integration has changed since this run, but its token and latency impact
  has not been re-measured.

Reducing repeated tool-surface definitions and unnecessary interaction round trips is a
**future optimization only**. It has not been implemented or measured by this result; PSG
makes no current claim of token, latency, or monetary-cost savings.

Every run now begins by verifying its own provenance and aborts if it cannot:

- the importable `psg` package must be this checkout;
- the Skill installed for Codex must hash equal to `skills/psg` here — otherwise it stops and
  tells you to run `psg setup codex`;
- the commit, runtime version, Skill SHA-256, worktree cleanliness, and Codex CLI version are
  recorded in the result under `provenance`.

These checks postdate the superseded result, so `results/agentic-ab-latest.json` has no
`provenance` block, and its per-run field is still named `out_of_scope_edits` rather than
`non_target_edits`. Both are expected for a file produced by the older harness.

This is PSG's own rule applied to PSG: evidence must be bound to the thing it claims to verify.

A **non-target edit** is any change outside the single reference target file. Editing the shared
test fixture is the ordinary way an agent finishes a task, so the metric is diagnostic, not by
itself a scope violation — which is why it is not named "out-of-scope".

## 2. Deterministic Task-Boundary benchmark

`task_boundary_benchmark.py` runs 10 seeded review scenarios against the real runtime and
checks that `blocks_current_task` is derived correctly: a finding blocks only when it is
open, `blocker`/`major`, evidence-backed, and related to the task by `caused_by_patch`,
`violates_acceptance`, or `violates_project_constraint`.

It reports blocking precision, blocking recall, and false reopening rate.

```powershell
python benchmarks/task_boundary_benchmark.py --output benchmarks/results/task-boundary-latest.json
```

The same scenarios run in CI on every supported platform through
`tests/test_task_boundary_benchmark.py`.

## 3. Mechanics regression benchmark

`sequential_benchmark.py` compares a disclosed all-source-files baseline with PSG's routed
working set over 12 sequential changes in a generated 38-file Python repository. Each task
supplies its target path, so it measures routing efficiency **after** localization; it does
not measure natural-language intent-to-target discovery.

It exists to catch mechanical regressions in:

1. routed context reading fewer unrelated files and using fewer estimated input tokens;
2. rejection of a mutation to a frozen core contract; and
3. evidence-complete tasks reaching `SHIPPABLE` while runtime-counted review budgets stop
   repeated review.

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

Its baseline is intentionally simple and disclosed. **It is not evidence that PSG makes a
real agent more efficient** — that question belongs to the agentic A/B benchmark above.
Future comparative evaluation should add fixed repo-map and symbol-RAG baselines.

### Token accounting

The baseline token estimate counts the complete contents of every source file for every
task. PSG's estimate counts both:

1. the full serialized `context_build` tool payload; and
2. the complete contents of every source file selected in that payload.

It does not count only file names, summaries, or graph-node labels. Per-task graph-context
tokens, selected-source tokens, selected source count, gate summaries, and aggregate
calculations are stored in `results/latest.json`.

### What the run also exercises

- initialization and first index;
- actual runtime verification with working-tree-bound evidence;
- acceptance criteria linked to verification records;
- final Git diff validation;
- all ship-gate requirements;
- rejection of an unauthorized frozen mutation; and
- runtime-derived issue changes and the configured review budget.
