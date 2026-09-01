# WorkGraph

WorkGraph is a local, model-independent project state and engineering-governance runtime for coding agents. It builds a small impact-aware context pack, enforces file mutation boundaries against the real Git diff, records deterministic evidence, and stops review when the task is safe to ship.

## What is included

- SQLite project-state graph plus append-only JSONL audit log
- Incremental Git/file index and Python AST symbol/dependency extraction
- Impact-aware context routing with token budgets and confidence reporting
- `mutable`, `read_only`, `interface_locked`, and `frozen` policies
- Pre/post-flight diff validation with stale-revision detection
- Acceptance criteria, verification evidence, evidence-backed issues, review/fix budgets, and ship gate
- Stable graph snapshots with recoverable state restore
- CLI, MCP server, and a reusable WorkGraph agent skill
- End-to-end tests and a reproducible 12-task benchmark

## Quick start

```powershell
python -m pip install -e ".[mcp,dev]"
git init
workgraph init
workgraph index
workgraph task open "Add a feature" --target src/example.py --ac "Behavior is covered by tests"
workgraph context T-0001
```

Use `workgraph --help` for all commands. The MCP server runs over stdio with `workgraph-mcp`; set `WORKGRAPH_PROJECT_ROOT` when its working directory is not the target repository.

The generated `.workgraph/` directory is repository-local state. Database/cache files are intentionally ignored; human-reviewed policies and configuration can be committed.

## Safety model

Source code and Git remain authoritative. WorkGraph does not apply patches and does not let review tools modify code. It only scopes, validates, records evidence, and evaluates convergence. Snapshot restore restores WorkGraph state; it never performs a destructive Git reset.
