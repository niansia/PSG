from __future__ import annotations

from typing import Any

from .runtime import WorkGraph

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
except ImportError as exc:  # pragma: no cover - exercised by CLI installation guidance
    raise RuntimeError(
        "Install the MCP extra first: python -m pip install -e '.[mcp]'"
    ) from exc


mcp = FastMCP(
    "workgraph",
    instructions=(
        "Use WorkGraph before broad repository reading. Open/resume a task, build context, and treat WRITE, "
        "READ_ONLY, FORBIDDEN, frozen, and interface-locked boundaries as hard constraints. Validate the real "
        "diff, record deterministic evidence, report evidence-backed issues, and stop general review when the "
        "ship gate returns SHIPPABLE."
    ),
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
STATE_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
STATE_SET = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def _graph() -> WorkGraph:
    return WorkGraph()


@mcp.tool(title="Read project status", annotations=READ_ONLY)
def project_status() -> dict[str, Any]:
    """Read the current Git/graph revision, active tasks, and project status."""
    return _graph().status()


@mcp.tool(title="Open governed task", annotations=STATE_WRITE)
def task_open(
    intent: str,
    acceptance_criteria: list[str],
    constraints: list[str] | None = None,
    targets: list[str] | None = None,
    write: list[str] | None = None,
    read_only: list[str] | None = None,
    forbidden: list[str] | None = None,
    non_goals: list[str] | None = None,
    risk: str = "medium",
) -> dict[str, Any]:
    """Open a governed coding task with explicit acceptance criteria and boundaries."""
    return _graph().task_open(
        intent=intent,
        acceptance_criteria=acceptance_criteria,
        constraints=constraints,
        targets=targets,
        write=write,
        read_only=read_only,
        forbidden=forbidden,
        non_goals=non_goals,
        risk=risk,
    )


@mcp.tool(title="Build task context", annotations=STATE_WRITE)
def context_build(task_id: str, max_tokens: int | None = None) -> dict[str, Any]:
    """Build the minimum sufficient context pack and READ/WRITE working set for a task."""
    return _graph().context_build(task_id, max_tokens=max_tokens)


@mcp.tool(title="Expand task context", annotations=STATE_WRITE)
def context_expand(task_id: str, reason: str) -> dict[str, Any]:
    """Expand context by one evidence-justified hop when the existing pack is insufficient."""
    return _graph().context_expand(task_id, reason)


@mcp.tool(title="Read graph nodes", annotations=READ_ONLY)
def node_get(ids: list[str]) -> dict[str, Any]:
    """Read exact graph nodes and adjacent relationships by stable identifier."""
    return _graph().node_get(ids)


@mcp.tool(title="Record decision", annotations=STATE_WRITE)
def decision_record(
    decision_id: str,
    statement: str,
    rationale: list[str],
    alternatives_rejected: list[str] | None = None,
    scope: list[str] | None = None,
    mutation_effect: str | None = None,
) -> dict[str, Any]:
    """Persist a material engineering or product decision with rationale and rejected alternatives."""
    return _graph().decision_record(
        decision_id=decision_id,
        statement=statement,
        rationale=rationale,
        alternatives_rejected=alternatives_rejected,
        scope=scope,
        mutation_effect=mutation_effect,
    )


@mcp.tool(title="Set node policy", annotations=STATE_SET)
def node_policy_set(
    node_id: str,
    policy: str,
    reason: str,
    override: bool = False,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Set mutable/read-only/interface-locked/frozen policy; unfreezing needs explicit override."""
    return _graph().node_policy_set(
        node_id,
        policy,
        reason,
        override=override,
        decision_id=decision_id,
    )


@mcp.tool(title="Validate patch", annotations=STATE_WRITE)
def patch_validate(
    task_id: str, diff: str, phase: str = "postflight"
) -> dict[str, Any]:
    """Validate a proposed or actual unified Git diff against task scope and mutation policy."""
    return _graph().patch_validate(task_id, diff, phase=phase)


@mcp.tool(title="Record verification", annotations=STATE_WRITE)
def verification_record(
    task_id: str,
    name: str,
    result: str,
    kind: str = "test",
    command: str | None = None,
    required: bool = True,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record deterministic test, typecheck, lint, policy, or integration evidence."""
    return _graph().verification_record(
        task_id=task_id,
        name=name,
        result=result,
        kind=kind,
        command=command,
        required=required,
        evidence=evidence or {},
    )


@mcp.tool(title="Record acceptance evidence", annotations=STATE_SET)
def acceptance_record(
    task_id: str,
    criterion_id: str,
    status: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set one acceptance criterion to pending/pass/fail/waived with traceable evidence."""
    return _graph().criterion_set(task_id, criterion_id, status, evidence or {})


@mcp.tool(title="Report issue", annotations=STATE_WRITE)
def issue_report(
    task_id: str,
    severity: str,
    claim: str,
    evidence: dict[str, Any] | None = None,
    affected_nodes: list[str] | None = None,
    violates: str | None = None,
) -> dict[str, Any]:
    """Report a review finding; blocker/major claims without evidence become speculative."""
    return _graph().issue_report(
        task_id=task_id,
        severity=severity,
        claim=claim,
        evidence=evidence,
        affected_nodes=affected_nodes,
        violates=violates,
    )


@mcp.tool(title="Update issue", annotations=STATE_SET)
def issue_update(
    issue_id: str, status: str, resolved_by_patch: str | None = None
) -> dict[str, Any]:
    """Resolve, defer, reopen, or reject an issue after reviewing its evidence."""
    return _graph().issue_update(issue_id, status, resolved_by_patch)


@mcp.tool(title="Record review round", annotations=STATE_WRITE)
def review_record(task_id: str, new_blocking_issues: int = 0) -> dict[str, Any]:
    """Record one independent review round and enforce the no-new-blocker/review budget rules."""
    return _graph().review_record(task_id, new_blocking_issues)


@mcp.tool(title="Record targeted fix", annotations=STATE_WRITE)
def fix_record(task_id: str, introduced: int = 0, resolved: int = 0) -> dict[str, Any]:
    """Record one correction cycle and evaluate issue churn and the hard fix budget."""
    return _graph().fix_record(task_id, introduced, resolved)


@mcp.tool(title="Evaluate ship gate", annotations=STATE_WRITE)
def ship_evaluate(task_id: str) -> dict[str, Any]:
    """Evaluate acceptance, verification, issues, policy, revision sync, and review budgets."""
    return _graph().ship_evaluate(task_id)


@mcp.tool(title="Create graph snapshot", annotations=STATE_WRITE)
def snapshot_create(task_id: str | None = None, stable: bool = False) -> dict[str, Any]:
    """Create a traceable graph-state snapshot at the current Git revision."""
    return _graph().snapshot_create(task_id=task_id, stable=stable)


@mcp.resource("workgraph://project/summary")
def project_summary() -> dict[str, Any]:
    return _graph().status()


@mcp.resource("workgraph://task/{task_id}/brief")
def task_brief(task_id: str) -> dict[str, Any]:
    task = _graph().store.get_task(task_id)
    if not task:
        raise KeyError(f"Unknown task: {task_id}")
    return task


@mcp.resource("workgraph://task/{task_id}/context")
def task_context(task_id: str) -> dict[str, Any]:
    graph = _graph()
    task = graph.store.get_task(task_id)
    if not task:
        raise KeyError(f"Unknown task: {task_id}")
    ids = task["payload"].get("context_node_ids", [])
    return {
        "task_id": task_id,
        "graph_revision": task["graph_rev"],
        "confidence": task["payload"].get("context_confidence"),
        "working_set": task["payload"].get("working_set", {}),
        **graph.node_get(ids),
    }


@mcp.resource("workgraph://node/{node_id}")
def node_resource(node_id: str) -> dict[str, Any]:
    return _graph().node_get([node_id])


@mcp.resource("workgraph://snapshot/{snapshot_id}")
def snapshot_resource(snapshot_id: str) -> dict[str, Any]:
    snapshot = _graph().store.get_snapshot(snapshot_id)
    if not snapshot:
        raise KeyError(f"Unknown snapshot: {snapshot_id}")
    return {key: value for key, value in snapshot.items() if key != "state"}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
