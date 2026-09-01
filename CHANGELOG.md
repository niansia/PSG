# Changelog

All notable changes to PSG are recorded here. Versions follow [semantic versioning](https://semver.org/).

## [1.1.0] — 2026-09-01

The Task Boundary release. v1.0 could tell you whether the evidence was real; it could
not tell you whether a finding belonged to the task you asked for. A reviewer could
report a pre-existing problem as a blocker and quietly turn a small change into an open-
ended project. v1.1 makes the boundary of a task explicit, machine-checked, and immune
to expansion by review.

**Severity is not task scope. Every task has a boundary. Every review stays inside it.**

### Added

- **Task Contract.** `psg task open` now records a formal, versioned contract: goal,
  context, mutation, scope, review, completion, and risk boundaries. The contract is
  hashed at creation (`contract_hash`) and that hash is immutable for the task's life.
- **Review Boundary with a fixed relation enum.** Every finding must declare exactly one
  `relation_to_task`: `caused_by_patch`, `violates_acceptance`,
  `violates_project_constraint`, `pre_existing`, `unrelated`, or `future_improvement`.
  The set is closed; unknown relations are rejected.
- **Runtime-derived blocking.** An Agent can no longer assert that a finding blocks the
  task. `blocks_current_task` is derived by the runtime and is true only when the issue
  is open, `blocker`/`major`, related by one of the first three relations, and backed by
  sufficient evidence. Acceptance violations must name a real acceptance-criterion ID;
  constraint violations must name a real Constraint, Decision, Policy, or restricted
  node; patch-caused claims need a changed node, diff/runtime evidence, or a failing
  verification.
- **Follow-up issues.** `pre_existing`, `unrelated`, and `future_improvement` findings
  stay fully visible and are never silently dropped — they simply do not block the
  current task. The ship gate reports `current_task_issue_summary`,
  `follow_up_issue_summary`, and `follow_up_issues` separately.
- **Read-only handoff.** `psg handoff [TASK_ID]` and MCP `handoff_build` build a
  minimum-sufficient review pack — Task Contract, changed files and symbols, relevant
  constraints and decisions, trusted verification, accepted debt, known issues, current
  ship preview, and follow-up findings — without mutating task status or the event log.
  `psg handoff --output PSG_REVIEW.md` writes it as Markdown for a chat reviewer.
- **`NO_SCOPE_EXPANSION_BY_REVIEW`.** `review_record` verifies the contract hash, so a
  review round cannot widen the task it is reviewing.
- **Hard review and fix budgets.** Review rounds and targeted fix cycles are capped at 2
  by the runtime. Once a budget is exhausted no further round is recorded, and imported
  state carrying a wider budget is clamped in both enforcement and the contract
  projection.
- **Deterministic Task-Boundary benchmark.** `benchmarks/task_boundary_benchmark.py`
  runs 10 seeded scenarios and reports blocking precision, blocking recall, and false
  reopening rate. It runs in CI on every platform.
- **Matched controlled agentic benchmark.** `benchmarks/agentic_ab.py` runs 10 paired
  coding tasks through the same Codex CLI and model, with the same prompt, the same
  baseline commit, and separate clean worktrees — PSG disabled versus PSG enabled with a
  predeclared Task Contract. Hidden tests decide task success. Raw traces are published
  with local absolute paths redacted.
- **Cross-platform CI.** Ubuntu, Windows, and macOS on Python 3.10, plus Ubuntu on
  Python 3.13. Every platform runs the tests, builds the wheel and Skill archive, and
  smoke-installs the wheel into a clean environment. Host-integration tests use fake
  Codex/Claude/Gemini executables; no real agent client is installed in CI.
- **`scripts/build_release.py`.** One entry point builds, validates, and smoke-installs
  the release artifacts and writes `SHA256SUMS`, so what CI proves is what ships.
- **`skills/psg/references/review-boundary.md`.** Loaded conditionally for review,
  handoff, and cross-model audit only, keeping the ordinary path small.

### Fixed

- **MCP tools that shell out to Git no longer hang.** PSG's subprocesses inherited the
  host's stdin. Under an MCP stdio server that handle is the JSON-RPC pipe with a
  blocking read pending, so every Git child stalled until the next client message
  arrived — `context_build`, `project_status`, and `patch_validate` appeared to hang
  indefinitely while the same calls took milliseconds in-process. All PSG subprocesses
  now run with `stdin=DEVNULL`, and a live stdio MCP regression test with per-call
  timeouts guards it.
- **Project root discovery no longer escapes the Git worktree.** The global PSG home
  (`~/.psg`) also contains a `config.yaml`, so after `psg setup` an unbounded upward
  scan resolved every repository under `$HOME` to the home directory. Discovery now
  stops at the enclosing Git worktree and never treats the global home as a project.
- **`psg setup` replaces a stale Skill bundle instead of merging into it.** Reference
  files removed in a newer version no longer linger in an installed bundle.
- **Handoff ignores PSG's own bookkeeping.** `.psg/state/**` and `.psg/local/**` are
  excluded from the reviewer's changed-file list, and mutation-boundary globs now
  resolve to real graph nodes.

### Changed

- The synthetic 12-task benchmark is now presented as a **mechanics regression
  benchmark**, not evidence of end-to-end efficiency.
- SQLite schema version 2 adds `relation_to_task` and `evidence_sufficient` to issues.
  Migration is additive and idempotent, and every added column carries a default, so an
  older runtime can still open a newer database. Portable state written before v1.1
  imports with findings defaulted to `unrelated` and non-blocking.

### Unchanged

- `psg update` still installs the newest stable `vX.Y.Z` tag and never follows `main`
  unless you explicitly pass `--channel dev`.
- The trust model is unchanged: `CLAIMED`, `RUNTIME_ATTESTED`, `USER_APPROVED`, and the
  reserved `EXTERNAL_ATTESTED`. Frozen unlocks, waivers, accepted debt, governance-state
  acceptance, and high-risk independent review remain non-self-authorizable over MCP.

## [1.0.1] — 2026-09-01

- Made stable releases the default `psg update` channel; `main` requires an explicit
  `--channel dev`.

## [1.0.0] — 2026-09-01

- First complete PSG release: portable project state graph, context router, mutation
  policy engine, verification and trust tiers, convergence and ship gate, installable
  Skill bundle, and the `psg` CLI plus `psg-mcp` server.

[1.1.0]: https://github.com/niansia/PSG/releases/tag/v1.1.0
[1.0.1]: https://github.com/niansia/PSG/releases/tag/v1.0.1
[1.0.0]: https://github.com/niansia/PSG/releases/tag/v1.0.0
