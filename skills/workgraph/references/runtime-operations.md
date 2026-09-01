# Runtime operations

Use this reference only for connection diagnostics or local CLI fallback.

## Required project state

- Work in the intended Git repository.
- `.workgraph/config.yaml` and `.workgraph/policies.yaml` identify an initialized project.
- The MCP process must use that repository as its working directory or set `WORKGRAPH_PROJECT_ROOT` to its absolute path.

Run `workgraph doctor` before attempting recovery when tools fail to load, the database cannot open, or the graph revision looks inconsistent. Do not initialize a different directory to silence a missing-project error.

## CLI fallback mapping

Use the CLI only when the equivalent MCP tool is unavailable and shell access is already authorized.

| MCP operation | CLI equivalent |
| --- | --- |
| `project_status` | `workgraph status` |
| `task_open` | `workgraph task open ...` |
| `context_build` | `workgraph context build TASK_ID` |
| `context_expand` | `workgraph context expand TASK_ID --reason "..."` |
| `patch_validate` | `workgraph validate TASK_ID` |
| deterministic checks | `workgraph verify TASK_ID --check NAME=COMMAND` |
| external evidence | `workgraph verification TASK_ID NAME pass --evidence '{...}'` |
| `acceptance_record` | `workgraph task criterion TASK_ID CRITERION_ID pass --evidence '{...}'` |
| `issue_report` | `workgraph issue report ...` |
| `ship_evaluate` | `workgraph ship TASK_ID` |

Do not parse human-formatted terminal text when JSON tool output is available. Do not apply a patch merely because validation could not run.

## Stale context

A `stale_working_set` result means Git HEAD moved after the task opened. Re-index and rebuild the task context against the current revision. It is not permission to ignore the mismatch.
