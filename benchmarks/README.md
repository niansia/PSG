# Sequential benchmark

This benchmark compares a conservative baseline that reads every source file on each task with WorkGraph's routed working set over 12 sequential changes in the same repository.

It verifies the three MVP demo claims:

1. routed context reads fewer unrelated files and estimates fewer input tokens;
2. a mutation to a frozen core contract is rejected; and
3. all evidence-complete tasks become `SHIPPABLE`, while two no-new-blocker reviews trigger the stopping rule.

Run it reproducibly with:

```powershell
python benchmarks/sequential_benchmark.py --output benchmarks/results/latest.json
```

The baseline is intentionally simple and disclosed. It is evidence for the MVP mechanism, not a claim that every external coding agent always reads the entire repository. Future comparative evaluation should add fixed repo-map and symbol-RAG baselines.
