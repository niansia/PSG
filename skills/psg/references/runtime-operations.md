# Runtime operations

Use this reference only for connection diagnostics or local CLI fallback.

## Required project state

- Work in the intended Git repository.
- `.psg/config.yaml`, `.psg/policies.yaml`, and `.psg/state/project.yaml` identify an initialized project.
- `.psg/local/` contains derived SQLite/events and must be ignored. Run `state_sync` after pulling changed portable state.
- The MCP process must use that repository as its working directory or set `PSG_PROJECT_ROOT` to its absolute path.

Run `psg doctor` before attempting recovery when tools fail to load, the database cannot open, or the graph revision looks inconsistent. Do not initialize a different directory to silence a missing-project error.

## CLI fallback mapping

Use the CLI only when the equivalent MCP tool is unavailable and shell access is already authorized.

| MCP operation | CLI equivalent |
| --- | --- |
| `project_status` | `psg status` |
| `guardrails_get` | `psg guardrails` |
| `index_refresh` | `psg index` |
| `state_sync` | `psg state sync` |
| `task_open` | `psg task open ...` |
| `context_build` | `psg context build TASK_ID` |
| `context_expand` | `psg context expand TASK_ID --reason "..."` |
| `patch_validate` | `psg validate TASK_ID` |
| `patch_validate_proposed` | `psg validate TASK_ID --diff-file PATCH` |
| `verification_run` | `psg verify TASK_ID --check NAME=COMMAND` |
| external evidence | `psg verification TASK_ID NAME pass --evidence '{...}'` |
| `acceptance_record` | `psg task criterion TASK_ID CRITERION_ID pass --evidence '{...}'` |
| `issue_report` | `psg issue report ...` |
| `ship_evaluate` | `psg ship TASK_ID` |

Do not parse human-formatted terminal text when JSON tool output is available. Do not apply a patch merely because validation could not run.

`patch_validate` never accepts a model-supplied final diff. It reads staged, unstaged, renamed, deleted, and untracked state from Git. Only hypothetical preflight uses a supplied diff.

`psg init` initializes portable state and performs the first index. `psg off` and `psg on` control project-level automatic governance; advanced task/context/verification commands are diagnostic interfaces, not the normal user workflow.

## Stale context

A `stale_working_set` result means Git HEAD moved after the task opened. Rebuild the task context; `context_build` performs the incremental index refresh. It is not permission to ignore the mismatch.
