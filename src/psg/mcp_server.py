from __future__ import annotations

from typing import Any

from .runtime import PSG

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
except ImportError as exc:  # pragma: no cover - exercised by CLI installation guidance
    raise RuntimeError(
        "Install the MCP extra first: python -m pip install -e '.[mcp]'"
    ) from exc


mcp = FastMCP(
    "psg",
    instructions=(
        "PSG is a non-exclusive governance layer. Respect host and user authority, then repository rules and "
        "accepted PSG decisions. Open/resume a task, build context, and treat WRITE, "
        "READ_ONLY, FORBIDDEN, frozen, and interface-locked boundaries as hard constraints. Validate the real "
        "runtime-read final diff, run deterministic evidence, defer known debt until its trigger, and stop when the "
        "ship gate returns SHIPPABLE. "
        "A task opens as a DRAFT with no write authority. context_build seals its mutation "
        "boundary and hashes it; only then may files change. More context is never more "
        "authority: later routing widens what you READ, never what you may WRITE. If the work "
        "needs a file outside the sealed boundary, report it and open a new task - do not "
        "expand scope. "
        "Every task carries a hashed Task Contract; review classifies findings against it and never widens it. "
        "Each reported issue must declare one relation_to_task: caused_by_patch, violates_acceptance, "
        "violates_project_constraint, pre_existing, unrelated, or future_improvement. Only an evidence-backed "
        "blocker/major in the first three blocks the current task; the runtime derives that, callers cannot assert "
        "it. Pre-existing, unrelated, and future-improvement findings stay visible as follow-up work and must not "
        "expand the task. Use handoff_build for a read-only review pack. Review the task, not the entire project."
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


def _graph() -> PSG:
    return PSG()


@mcp.tool(title="Read project status", annotations=READ_ONLY)
def project_status() -> dict[str, Any]:
    """Read the current Git/graph revision, active tasks, and project status."""
    return _graph().status()


@mcp.tool(title="Refresh repository index", annotations=STATE_WRITE)
def index_refresh(force: bool = False) -> dict[str, Any]:
    """Incrementally refresh files, Python symbols, dependencies, and debt annotations."""
    return _graph().index(force=force)


@mcp.tool(title="Sync portable project state", annotations=STATE_WRITE)
def state_sync() -> dict[str, Any]:
    """Import changed Git-committable PSG state into the local derived SQLite index."""
    return _graph().state_sync()


@mcp.tool(title="Read authority and guardrails", annotations=READ_ONLY)
def guardrails_get() -> dict[str, Any]:
    """Read authority order, dependency discipline, and active project guardrails."""
    return _graph().guardrails_get()


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
    builder_actor: str | None = None,
    dependency_justifications: list[str] | None = None,
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
        builder_actor=builder_actor,
        dependency_justifications=dependency_justifications,
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


@mcp.tool(title="Create graph node", annotations=STATE_WRITE)
def node_create(
    node_id: str,
    node_type: str,
    title: str,
    payload: dict[str, Any],
    policy: str = "mutable",
    maturity: str = "accepted",
) -> dict[str, Any]:
    """Create an explicit Requirement, Constraint, Architecture, Test, or other PSG node."""
    return _graph().node_create(
        node_id=node_id,
        node_type=node_type,
        title=title,
        payload=payload,
        policy=policy,
        maturity=maturity,
    )


@mcp.tool(title="Link graph nodes", annotations=STATE_WRITE)
def edge_create(
    src: str,
    edge_type: str,
    dst: str,
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Create a typed relationship between two existing PSG nodes."""
    return _graph().edge_create(src, edge_type, dst, confidence=confidence)


@mcp.tool(title="Record decision", annotations=STATE_WRITE)
def decision_record(
    decision_id: str,
    statement: str,
    rationale: list[str],
    alternatives_rejected: list[str] | None = None,
    scope: list[str] | None = None,
    mutation_effect: str | None = None,
) -> dict[str, Any]:
    """Propose a decision; MCP claims never apply mutation effects until CLI user approval."""
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
) -> dict[str, Any]:
    """Maintain or tighten policy; MCP cannot weaken an existing boundary."""
    return _graph().node_policy_set(node_id, policy, reason)


@mcp.tool(title="Validate patch", annotations=STATE_WRITE)
def patch_validate(task_id: str) -> dict[str, Any]:
    """Validate HEAD to the complete current state, including staged, unstaged, renamed, deleted, and untracked files."""
    return _graph().patch_validate(task_id)


@mcp.tool(title="Validate proposed patch", annotations=STATE_WRITE)
def patch_validate_proposed(task_id: str, diff: str) -> dict[str, Any]:
    """Preflight a hypothetical unified diff; never use this in place of final runtime validation."""
    return _graph().patch_validate_proposed(task_id, diff)


@mcp.tool(title="Run verification", annotations=STATE_WRITE)
def verification_run(
    task_id: str, check_names: list[str] | None = None
) -> dict[str, Any]:
    """Run only check names allowlisted in .psg/config.yaml; commands never come from MCP."""
    return _graph().verify(task_id, check_names)


@mcp.tool(title="Record verification", annotations=STATE_WRITE)
def verification_record(
    task_id: str,
    name: str,
    result: str,
    kind: str = "test",
    required: bool = True,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a CLAIMED result; MCP cannot assert user, runtime, reviewer, or external authority."""
    return _graph().verification_record(
        task_id=task_id,
        name=name,
        result=result,
        kind=kind,
        required=required,
        source="llm_reported",
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
    relation_to_task: str,
    claim: str,
    evidence: dict[str, Any] | None = None,
    affected_nodes: list[str] | None = None,
    violates: str | None = None,
    debt_id: str | None = None,
) -> dict[str, Any]:
    """Report a review finding; blocker/major claims without evidence become speculative."""
    return _graph().issue_report(
        task_id=task_id,
        severity=severity,
        relation_to_task=relation_to_task,
        claim=claim,
        evidence=evidence,
        affected_nodes=affected_nodes,
        violates=violates,
        debt_id=debt_id,
    )


@mcp.tool(title="Update issue", annotations=STATE_SET)
def issue_update(
    issue_id: str, status: str, resolved_by_patch: str | None = None
) -> dict[str, Any]:
    """Resolve, defer, reopen, or reject an issue after reviewing its evidence."""
    return _graph().issue_update(issue_id, status, resolved_by_patch)


@mcp.tool(title="Record review round", annotations=STATE_WRITE)
def review_record(
    task_id: str,
    new_blocking_issues: int = 0,
    actor_id: str | None = None,
    session_id: str | None = None,
    model_family: str | None = None,
) -> dict[str, Any]:
    """Record a declared review; actor labels are CLAIMED and cannot satisfy high-risk independence."""
    return _graph().review_record(
        task_id,
        new_blocking_issues,
        actor_id=actor_id,
        session_id=session_id,
        model_family=model_family,
    )


@mcp.tool(title="Accept bounded debt", annotations=STATE_WRITE)
def debt_record(
    task_id: str,
    what: str,
    why: str,
    ceiling: str,
    revisit_trigger: str,
    affected_nodes: list[str] | None = None,
) -> dict[str, Any]:
    """Propose bounded debt; only explicit CLI user approval can accept it."""
    return _graph().debt_record(
        task_id=task_id,
        what=what,
        why=why,
        ceiling=ceiling,
        revisit_trigger=revisit_trigger,
        affected_nodes=affected_nodes,
    )


@mcp.tool(title="Review debt trigger", annotations=STATE_SET)
def debt_review(
    debt_id: str, trigger_met: bool, evidence: dict[str, Any]
) -> dict[str, Any]:
    """Report trigger evidence; MCP claims cannot reopen accepted debt."""
    return _graph().debt_review(debt_id, trigger_met=trigger_met, evidence=evidence)


@mcp.tool(title="Record skill conflict", annotations=STATE_WRITE)
def conflict_record(
    task_id: str,
    source: str,
    domain: str,
    recommendation: str,
    guardrail: str,
    resolution: str = "deferred",
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Record and defer another skill's recommendation when it conflicts with a PSG guardrail."""
    return _graph().conflict_record(
        task_id=task_id,
        source=source,
        domain=domain,
        recommendation=recommendation,
        guardrail=guardrail,
        resolution=resolution,
        decision_id=decision_id,
    )


@mcp.tool(title="Record targeted fix", annotations=STATE_WRITE)
def fix_record(task_id: str, introduced: int = 0, resolved: int = 0) -> dict[str, Any]:
    """Record one correction cycle and evaluate issue churn and the hard fix budget."""
    return _graph().fix_record(task_id, introduced, resolved)


@mcp.tool(title="Evaluate ship gate", annotations=STATE_WRITE)
def ship_evaluate(task_id: str) -> dict[str, Any]:
    """Evaluate acceptance, verification, issues, policy, revision sync, and review budgets."""
    return _graph().ship_evaluate(task_id)


@mcp.tool(title="Build review handoff", annotations=READ_ONLY)
def handoff_build(task_id: str | None = None) -> dict[str, Any]:
    """Build a read-only minimum-sufficient Task Contract and review pack."""
    return _graph().handoff(task_id)


@mcp.tool(title="Create graph snapshot", annotations=STATE_WRITE)
def snapshot_create(task_id: str | None = None, stable: bool = False) -> dict[str, Any]:
    """Create a traceable graph-state snapshot at the current Git revision."""
    return _graph().snapshot_create(task_id=task_id, stable=stable)


@mcp.resource("psg://project/summary")
def project_summary() -> dict[str, Any]:
    return _graph().status()


@mcp.resource("psg://project/guardrails")
def project_guardrails() -> dict[str, Any]:
    return _graph().guardrails_get()


@mcp.resource("psg://task/{task_id}/brief")
def task_brief(task_id: str) -> dict[str, Any]:
    task = _graph().store.get_task(task_id)
    if not task:
        raise KeyError(f"Unknown task: {task_id}")
    return task


@mcp.resource("psg://task/{task_id}/context")
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


@mcp.resource("psg://node/{node_id}")
def node_resource(node_id: str) -> dict[str, Any]:
    return _graph().node_get([node_id])


@mcp.resource("psg://snapshot/{snapshot_id}")
def snapshot_resource(snapshot_id: str) -> dict[str, Any]:
    snapshot = _graph().store.get_snapshot(snapshot_id)
    if not snapshot:
        raise KeyError(f"Unknown snapshot: {snapshot_id}")
    return {key: value for key, value in snapshot.items() if key != "state"}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
