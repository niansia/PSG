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

Both conditions get identical sandbox permissions and an identical MCP configuration
(`--ignore-user-config`, with `PSG_PROJECT_ROOT` pinned to the worktree), so the only
difference between them is PSG itself.

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
- Raw traces in `results/agentic-ab-traces/` are published with local absolute paths
  redacted to `<WORKTREE>`, `<BENCHMARK_BASE>`, `<TMP>`, and `<USER_HOME>`.

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
