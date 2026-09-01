# Review boundary

Read this reference only when reviewing an existing implementation, consuming a handoff pack, performing a cross-model review, or auditing the current task.

Review only against the sealed Task Contract. Its mutation boundary is the authority the runtime enforces, not whatever the working set happens to list: more context never means more write authority.

Review only against the current Task Contract. Reviewers may read, analyze, report, classify, and provide evidence. They may not change the task goal or acceptance criteria, widen WRITE, unlock a node, supersede a Decision, or turn follow-up work into current work.

Classify every finding with one allowed `relation_to_task`:

- `caused_by_patch`
- `violates_acceptance`
- `violates_project_constraint`
- `pre_existing`
- `unrelated`
- `future_improvement`

Only an evidence-backed BLOCKER or MAJOR in the first three relations may block the current task. Acceptance violations must name the acceptance-criterion ID. Project-constraint violations must identify a Constraint, accepted Decision, policy reference, or affected frozen/locked node. Patch-caused findings need an affected changed node, a failing Verification, or concrete diff/runtime evidence.

Pre-existing bugs, unrelated findings, and future improvements remain visible as follow-up findings. Do not investigate unrelated areas without evidence of current-task impact. Do not reopen accepted debt before its approved trigger. Do not present speculative refactors as blockers.

When the Task Contract is satisfied and the ship gate returns `SHIPPABLE`, stop. **Review the task, not the entire project.**
