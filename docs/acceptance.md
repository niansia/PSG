# MVP acceptance traceability

| Architecture requirement | Implementation | Verification |
| --- | --- | --- |
| Single Git repository | `workgraph.git`, project discovery | temporary Git repositories in tests |
| SQLite store + event log | `Store`, WAL database, JSONL events | persistence and doctor tests |
| Nine core node types | runtime node registry and typed tables | node/index/task/snapshot tests |
| Six required edge types | runtime edge registry plus `contains`/`consumed-by` | index dependency tests |
| One language symbol extraction | Python `ast` indexer | signature and dependency tests |
| Minimum working set | impact-aware `ContextRouter` | write/frozen/dependency assertions |
| Four mutation policies | `PolicyEngine` | frozen and interface-lock tests |
| Actual diff enforcement | unified Git diff parser and stale check | scope, frozen, signature, stale tests |
| Final-state evidence binding | ship-time diff validation and worktree fingerprints | time-of-check/time-of-use regression test |
| Deterministic verification | registry, command runner, evidence records | pass/fail ship-gate tests |
| Evidence-backed issues | severity lifecycle and demotion | unsupported blocker demotion test |
| Convergence + hard budgets | `ConvergenceEngine` | review/fix stopping tests |
| MCP + Skill | FastMCP tools/resources, `skills/workgraph` bundle | MCP schema and skill validation |
| Cross-client state | repository-local SQLite and revision binding | independent builder/reviewer runtime sessions |
| Stable snapshot + restore | graph-only snapshot manager | restore/safety-snapshot test |
| 10+ task benchmark | 12-task synthetic Git history | `benchmarks/results/latest.json` |

The benchmark's all-files baseline is deliberately conservative. The next research phase should compare against fixed repo maps and symbol-only retrieval on real long-horizon repositories.
