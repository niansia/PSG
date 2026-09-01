# Runtime operations

Use this reference only for connection diagnostics or local CLI fallback.

## Required project state

- Work in the intended Git repository.
- `.psg/config.yaml`, `.psg/policies.yaml`, and `.psg/state/project.yaml` identify an initialized project.
- `.psg/local/` contains derived SQLite/events and raw verification logs and must be ignored. Run `state_sync` after pulling changed portable state.
- The MCP process must use that repository as its working directory or set `PSG_PROJECT_ROOT` to its absolute path.

Run `psg doctor` before attempting recovery when tools fail to load, the database cannot open, or the graph revision looks inconsistent. Do not initialize a different directory to silence a missing-project error.

## Product lifecycle

- `psg setup` auto-detects Codex, Claude Code, and Gemini CLI, installs the full Skill bundle, and registers `psg-mcp` through each host's native CLI.
- `psg init` opts the current Git project into governance and repairs missing host integration when possible.
- `psg status`, `psg on`, and `psg off` are the ordinary project controls. Add `--global` to `on` or `off` for the global automatic-governance switch.
- `psg handoff [TASK_ID]` builds a read-only review contract and writes it to ignored local state at `.psg/local/handoffs/<task>.md`. `--output` writes elsewhere; a path inside the Git worktree is reported as a warning because it would appear as a project change.
- `psg task approve-scope TASK_ID --reason "..."` is the user-owned approval for a broad sealed mutation boundary. It is deliberately absent from MCP.
- `psg update` resolves and installs the newest stable `vX.Y.Z` release tag, then refreshes the bundle and MCP registrations. `--channel dev` is an explicit opt-in to `main`; `--source` is an advanced override.
- `psg uninstall` removes installed integrations and runtime while preserving all project `.psg/` directories.

The advanced commands below are Agent/developer interfaces, not normal onboarding steps.

## CLI fallback mapping

Use the CLI only when the equivalent MCP tool is unavailable and shell access is already authorized.

| MCP operation | CLI equivalent |
| --- | --- |
| `project_status` | `psg status` |
| `guardrails_get` | `psg guardrails` |
| `index_refresh` | `psg index` |
| `state_sync` | `psg state sync` |
| `handoff_build` | `psg handoff TASK_ID` |
| `task_open` | `psg task open ...` |
| `context_build` | `psg context build TASK_ID` |
| `context_expand` | `psg context expand TASK_ID --reason "..."` |
| `patch_validate` | `psg validate TASK_ID` |
| `patch_validate_proposed` | `psg validate TASK_ID --diff-file PATCH` |
| `verification_run` | `psg verify TASK_ID --name CHECK_NAME` |
| external evidence | `psg verification TASK_ID NAME pass --evidence '{...}'` |
| `acceptance_record` | `psg task criterion TASK_ID CRITERION_ID pass --evidence '{...}'` |
| `issue_report` | `psg issue report ...` |
| `ship_evaluate` | `psg ship TASK_ID` |

Do not parse human-formatted terminal text when JSON tool output is available. Do not apply a patch merely because validation could not run.

`patch_validate` never accepts a model-supplied final diff. It reads staged, unstaged, renamed, deleted, and untracked state from Git. Only hypothetical preflight uses a supplied diff.

`verification_run` accepts only names from `verification.commands` in `.psg/config.yaml`. `psg verify TASK_ID --check NAME=COMMAND` is an advanced local CLI boundary for a person deliberately running a one-off command; never substitute it for the MCP allowlist.

Decision, debt, waiver, high-risk review, portable-state acceptance, and frozen-node override commands are user-owned approval actions. They are intentionally absent from the ordinary MCP surface. An Agent must not call them through a shell or add an approval flag for itself. If approval is needed, present the proposal and wait for the user.

The portable projection carries hashes for both its own export and `.psg/config.yaml`. PSG accepts a mismatch only when Git reports the corresponding governance file clean. A dirty mismatch is rejected before config-defined commands run. Do not work around it with `psg state accept`; that command is reserved for a user who reviewed both exact changes and supplies a reason.

`psg init` initializes portable state and performs the first index. `psg off` and `psg on` control project-level automatic governance; advanced task/context/verification commands are diagnostic interfaces, not the normal user workflow.

## Stale context

A `stale_working_set` result means Git HEAD moved after the task opened. Rebuild the task context; `context_build` performs the incremental index refresh. It is not permission to ignore the mismatch.
