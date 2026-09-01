# Sequential benchmark

This benchmark compares a disclosed all-source-files baseline with PSG's routed working set over 12 sequential changes in the same generated 38-file Python repository. Each task supplies its target path, so the benchmark measures routing efficiency after localization; it does not measure natural-language intent-to-target discovery.

It verifies the three MVP demo claims:

1. routed context reads fewer unrelated files and uses fewer estimated input tokens;
2. a mutation to a frozen core contract is rejected; and
3. all evidence-complete tasks become `SHIPPABLE`, while runtime-counted review budgets stop repeated review.

Run it reproducibly with:

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

The baseline is intentionally simple and disclosed. It is evidence for the MVP mechanism, not a claim that every external coding agent always reads the entire repository. Future comparative evaluation should add fixed repo-map and symbol-RAG baselines.

## Token accounting

The baseline token estimate counts the complete contents of every source file for every task. PSG's estimate counts both:

1. the full serialized `context_build` tool payload; and
2. the complete contents of every source file selected in that payload.

It does not count only file names, summaries, or graph-node labels. This accounting produces the current **32.41% context-token reduction** and **89.69% file-read reduction**. Per-task graph-context tokens, selected-source tokens, selected source count, gate summaries, and aggregate calculations are stored in `results/latest.json`.

## What the run also exercises

- initialization and first index;
- actual runtime verification with working-tree-bound evidence;
- acceptance criteria linked to verification records;
- final Git diff validation;
- all ship-gate requirements;
- rejection of an unauthorized frozen mutation; and
- runtime-derived issue changes and the configured review budget.
