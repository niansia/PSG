# CLI and MCP reference

PSG exposes two interfaces over the same local runtime and project state:

- `psg` is the human-facing command-line interface, with `--json` for automation and advanced/debug operations.
- `psg-mcp` is the local MCP server used by supported execution hosts.

Most users need only `psg init`, `psg status`, `psg on`, and `psg off`. Coding Agents normally use MCP after the Skill activates.

## Everyday commands

| Command | Purpose |
| --- | --- |
| `psg init` | Initialize `.psg/`, create project configuration, and build the first index |
| `psg status` | Show project activation, state health, integrations, Git status, and current task |
| `psg on` | Enable PSG for the current project |
| `psg off` | Pause PSG for the current project |
| `psg on --global` | Enable automatic governance globally |
| `psg off --global` | Pause automatic governance globally |
| `psg handoff [TASK_ID]` | Build a read-only review contract for another model or teammate |

`psg handoff` defaults to ignored `.psg/local/handoffs/` storage. Use `--output PATH` or `--json` when another destination or machine-readable output is needed. A path inside the worktree may appear as a project change, so PSG warns about it.

## Installation lifecycle

| Command | Purpose |
| --- | --- |
| `psg setup` | Detect Codex, Claude Code, and Gemini CLI; install the Skill bundle and register MCP |
| `psg setup --all` | Explicitly set up every detected supported host |
| `psg doctor` | Check runtime, database, configuration, integrations, and Git health |
| `psg update` | Resolve the latest stable `vX.Y.Z` GitHub release, install that exact tag, and refresh integrations |
| `psg update --channel dev` | Explicitly follow `main` for development use |
| `psg update --source SOURCE` | Install an advanced custom source |
| `psg uninstall` | Remove runtime and host integrations while preserving every project `.psg/` directory |

Host destinations, fallbacks, and manual setup are documented in [installation](installation.md).

## Task and review workflow

The advanced CLI mirrors the governed lifecycle:

```text
task open → context build → edit → validate → verify
          → issue/review/fix → ship
```

| Command group | Purpose |
| --- | --- |
| `psg task open/list/show/criterion` | Create and inspect Task Contracts and acceptance criteria |
| `psg context build/expand` | Build minimum-sufficient context or add one evidence-justified read hop |
| `psg validate` | Validate the real final Git state against task and project policy |
| `psg verify` | Run deterministic checks; configured checks are preferred |
| `psg verification` | Record external or user-provided verification as a claim or explicit user approval |
| `psg issue report/update/list` | Manage evidence-backed findings and their relation to the task |
| `psg review` | Record one bounded review round |
| `psg fix` | Record one targeted correction cycle |
| `psg ship` | Evaluate acceptance, verification, policy, freshness, issues, and budgets |

`context expand` can widen what an Agent reads. It never changes the sealed mutation boundary. See [Task Contract](task-contract.md).

## User-owned approval commands

The following operations can mint `USER_APPROVED` authority and therefore require a real interactive terminal:

- `psg task approve-scope TASK_ID`
- accepting proposed Decisions or Debt through their CLI command groups;
- accepting untrusted portable-state changes;
- criterion waiver or user-approved verification;
- frozen-node override backed by an accepted Decision; and
- independent high-risk review attestation.

These actions are absent from ordinary MCP or cannot be promoted through MCP. They reject non-interactive and piped confirmation. An Agent must explain the proposal and let the user run the approval.

## Other advanced CLI groups

| Command group | Purpose |
| --- | --- |
| `psg guardrails` | Show effective authority, dependency discipline, and runtime guardrails |
| `psg state` | Synchronize clean portable state or explicitly accept an inspected change |
| `psg index` | Incrementally index files, Python symbols, imports, and supported debt annotations |
| `psg node` / `psg edge` | Inspect or maintain graph entities and relationships |
| `psg decision` | Propose, inspect, or explicitly approve engineering Decisions |
| `psg debt` | Propose, inspect, approve, or evaluate bounded Debt |
| `psg snapshot` | Create, list, or restore graph-state snapshots without modifying Git source files |

Run `psg COMMAND --help` for argument-level syntax. Place `--json` before the command for machine-readable results:

```text
psg --json status
psg --json task show T-0042
```

## MCP surface

The MCP server exposes bounded operations rather than the entire user CLI.

| Area | Tools |
| --- | --- |
| Project and graph | `project_status`, `guardrails_get`, `index_refresh`, `node_create`, `node_get`, `node_policy_set`, `edge_create`, `state_sync`, `snapshot_create` |
| Task and context | `task_open`, `context_build`, `context_expand`, `handoff_build` |
| Decisions and coordination | `decision_record`, `debt_record`, `debt_review`, `conflict_record` |
| Patch and evidence | `patch_validate_proposed`, `patch_validate`, `verification_run`, `verification_record`, `acceptance_record` |
| Review and convergence | `issue_report`, `issue_update`, `review_record`, `fix_record`, `ship_evaluate` |

Important MCP boundaries:

- A task opens as `DRAFT`; `context_build` seals its write boundary before editing.
- `context_expand` changes read context, not write authority.
- `patch_validate_proposed` is a preflight convenience; `patch_validate` against the runtime-read final Git state is required before shipping.
- `verification_run` accepts only names from `.psg/config.yaml`; MCP cannot send arbitrary shell commands.
- `verification_record`, reviewer identity, external-tool labels, Decisions, and Debt remain `CLAIMED` until a trusted channel attests or approves them.
- Agents report Issue severity, relation, and evidence. The runtime derives whether an Issue blocks the current task.
- `handoff_build` is read-only and does not change task status or the event log.

## Starting `psg-mcp`

Normal Codex, Claude Code, and Gemini CLI project sessions inherit the repository working directory. If a host launches MCP elsewhere, set `PSG_PROJECT_ROOT` to the absolute repository path before starting `psg-mcp`.

```text
PSG_PROJECT_ROOT=/absolute/path/to/repository
psg-mcp
```

The runtime is host-neutral. Setup adapters only install the same Skill bundle and register the same `psg-mcp` server using each host's native mechanism.

For security properties, see [trust and security](trust-and-security.md). For storage and component details, see [architecture](architecture.md).
