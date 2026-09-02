# Changelog

All notable changes to PSG are recorded here. Versions follow [semantic versioning](https://semver.org/).

## [1.1.3] — 2026-09-02

The release-identity correction and runtime approval hardening release. The existing v1.1.2
tag and Release remain immutable; v1.1.3 is the first release to include every hardening and
documentation change made after that tag under a new version identity.

### Security

- **`USER_APPROVED` is enforced at the Runtime boundary.** Direct Python callers can no
  longer bypass the interactive operator gate used by the CLI. Runtime approval operations
  fail closed without an interactive terminal and the literal operator confirmation.

### Fixed

- **Release identity is one-to-one again.** The tracked v1.1.2 wheel and Skill archive are
  restored to the exact bytes published by the immutable v1.1.2 Release. New v1.1.3 artifacts
  are validated against the v1.1.3 source, clean-installed, checksummed, and published only
  under the v1.1.3 tag.
- **The historical agentic A/B table is unmistakably marked superseded** in all four README
  translations. It remains available for transparency, but is not presented as evidence for
  the current release because the run loaded an older installed Skill than the Runtime under
  test and predates the current localization behavior.

### Changed

- The README product surface is shorter and task-boundary-first, with a shared branded SVG
  workflow diagram and a compact dark-canvas PSG identity.
- Release tests now compare every Python file inside the tracked wheel with `src/psg` byte for
  byte, in addition to validating the complete Skill bundle and clean-install behavior.

## [1.1.2] — 2026-09-02

The enforcement release. v1.1.1 sealed the write boundary but still trusted a prompt to stop
an agent from approving its own work, and still treated every lexical match as a candidate to
write. Both are now enforced by the runtime.

### Fixed

- **`USER_APPROVED` is no longer reachable by an agent.** MCP could not mint it, but coding
  agents run shell commands, so "do not approve your own work" was a Skill instruction rather
  than an enforced rule: `psg task approve-scope`, `psg decision approve`, `psg debt approve`,
  `psg state accept`, and every `--user-approved` flag executed straight through. All ten
  paths now require a real terminal on stdin and stdout, print the authority being granted,
  and demand the literal word `APPROVE`. A captured subprocess fails closed, and
  `echo APPROVE | psg ...` fails with it. This is not cryptographic proof that a human pressed
  the key — an agent given a PTY under the same OS identity is the host's trust boundary, not
  PSG's — so `USER_APPROVED` is now defined as *interactive local operator approval under the
  host permission boundary*, and the documentation says exactly that.
- **A lexical match no longer grants write authority.** The intent fallback took its top eight
  scored nodes and handed every one of their files write scope, so "might be relevant" and
  "may be modified" were the same thing. Retrieval candidates and authority candidates are now
  separate: symbol scores collapse onto their file, and only a single match that beats the
  runner-up by a clear margin becomes the write target. An ambiguous match or a merely
  incidental substring hit grants **no** write authority and asks the operator which file the
  request means. On the ten benchmark intents this moves localization from 1–8 files (median
  7, nine of ten needing manual approval) to exactly the one correct file in 10/10 cases with
  no approval needed.
- **`psg verification` was unreachable.** Its `--command` option shared argparse's `dest` with
  the top-level subparser, overwriting the subcommand name, so the command always failed with
  "Unsupported command: None". Found by a test that exercises every approval path.

### Changed

- **The agentic benchmark verifies its own provenance and aborts if it cannot.** The published
  v1.1.1 run was measured while Codex loaded a globally installed pre-v1.1.1 Skill instead of
  the checkout under test — the runtime enforced one set of rules while the agent was
  instructed by another. A run now refuses to start unless the importable `psg` is this
  checkout and the Skill installed for Codex hashes equal to `skills/psg`, and records commit,
  runtime version, Skill SHA-256, worktree cleanliness, and CLI version in the result.
- **That published run is marked superseded** in all four README translations rather than
  deleted. Its numbers describe different software, and a re-run is required before PSG makes
  any OFF-versus-ON claim.
- `out_of_scope_edits` is renamed `non_target_edits`. Editing the shared test fixture is the
  ordinary way an agent finishes a task; the metric is diagnostic, and the old name asserted a
  violation the benchmark protocol had not defined in advance.
- The benchmark's headline table now carries scope-approval counts instead of burying them in
  the limitations, because they are the cost of the guardrail.

## [1.1.1] — 2026-09-01

### Added

- **The matched agentic OFF/ON benchmark now has a measured 10-pair result**, run in
  `end_to_end` mode where neither condition is told which file to change. All 20 runs
  completed. PSG ON reached 10/10 task success against 9/10 for OFF and cut out-of-scope
  edits from 10 to 2 — every one of OFF's was the same shared test file — while spending
  79% more input tokens and 42% more wall time. The cost is published as prominently as
  the benefit, along with the finding that PSG's own localization sealed boundaries wider
  than needed in nine of ten tasks.

### Fixed

- **Trace sanitization missed two spellings of a local path.** Codex writes paths into
  traces singly, doubly, and quadruply escaped (JSON nested in JSON), and the terminal
  wraps long command lines, splitting a path across a newline mid-word. Plain string
  replacement caught neither, so `~/.codex/...` and temp paths survived into supposedly
  redacted traces. Redaction now matches any escaping depth and tolerates a path broken by
  a wrapped line. The published traces were re-redacted with the fixed matcher and verified
  clean.

## [1.1.1] — 2026-09-01

The sealing release. v1.1.0 shipped a Task Contract whose hash covered the scope a task
*asked for* rather than the scope the runtime actually *enforced*. This closes that gap.

**More context is not more authority.**

### Fixed

- **A sealed Task Contract now covers the write authority actually enforced.** The
  contract hashed the scope a task *requested*, but the policy engine enforced the
  scope the context router *derived* — and the router runs after the hash is taken.
  A task opened with no declared scope could therefore be granted write access to
  several files by lexical localization, with the hash none the wiser, so
  `NO_SCOPE_EXPANSION_BY_REVIEW` protected a boundary that was not the one in force.

  A task now opens as a **DRAFT** holding no write authority; initial localization
  **SEALS** `authorized_write`, `authorized_read_only`, and `authorized_forbidden`,
  and the hash commits to those. The policy engine reads the sealed authority, never
  the working set. Re-routing and context expansion may widen what a task reads and
  can no longer widen what it may write — a file discovered after the seal becomes
  context, not permission. Tasks written before sealing existed keep honouring their
  working set so they are not stranded.

- **A boundary an agent derived now needs a person.** A wildcard write scope, a
  high-risk task, or a sprawling write set is marked `requires_scope_approval` and
  holds the ship gate until `psg task approve-scope` is run. The approval is bound to
  the contract hash it approved, so it does not carry over to a different boundary.
  MCP cannot reach the command.

- **`task_open` no longer claims `user_explicit` provenance.** It normally runs
  through an agent relaying a request, so Task, Requirement, and Constraint nodes are
  marked `agent_interpreted_user_intent`, which is what actually happened.

- **`psg handoff` no longer pollutes the worktree it is reviewing.** The review pack
  defaulted to a path the caller chose, and `PSG_REVIEW.md` written at the repo root
  became an untracked project change that could block the very ship gate the pack
  exists to inform. It now defaults to ignored `.psg/local/handoffs/<task>.md`, and
  `--output` warns when the destination is inside the worktree.

### Changed

- The agentic A/B benchmark had an oracle asymmetry: the ON condition was handed the
  correct target path while the OFF condition had to find it. It now runs in two
  explicit modes. `end_to_end` (the default, and the headline) tells neither side
  where the change belongs, so PSG must localize the request itself;
  `controlled_routing` tells both sides the same target, isolating governance value
  from localization value. Results record which mode produced them.
- `docs/acceptance.md` no longer hard-codes a test count, and no longer lists a
  result file for a benchmark that has not been run.

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

[1.1.3]: https://github.com/niansia/PSG/releases/tag/v1.1.3
[1.1.2]: https://github.com/niansia/PSG/releases/tag/v1.1.2
[1.1.1]: https://github.com/niansia/PSG/releases/tag/v1.1.1
[1.1.0]: https://github.com/niansia/PSG/releases/tag/v1.1.0
[1.0.1]: https://github.com/niansia/PSG/releases/tag/v1.0.1
[1.0.0]: https://github.com/niansia/PSG/releases/tag/v1.0.0
