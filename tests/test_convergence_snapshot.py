from __future__ import annotations


def test_unsupported_blocking_claim_is_demoted(graph, task) -> None:
    issue = graph.issue_report(
        task_id=task["id"],
        severity="blocker",
        claim="This might someday be slow",
        evidence={},
    )
    assert issue["severity"] == "speculative"
    assert issue["evidence"]["requested_severity"] == "blocker"


def test_ship_gate_accepts_evidence_and_defers_minor(graph, task) -> None:
    task_id = task["id"]
    graph.criterion_set(
        task_id, f"{task_id}-AC1", "pass", {"kind": "test", "name": "unit"}
    )
    policy = graph.patch_validate(task_id, "")
    assert policy["allowed"]
    graph.verification_record(
        task_id=task_id,
        name="unit:feature",
        result="pass",
        kind="unit",
        required=True,
        evidence={"tests": 1},
    )
    graph.issue_report(
        task_id=task_id,
        severity="minor",
        claim="Message wording could be more consistent",
        evidence={"kind": "review_observation", "path": "src/app.py"},
    )
    result = graph.ship_evaluate(task_id)
    assert result["status"] == "SHIPPABLE"
    assert result["recommendation"] == "SHIP"
    assert len(result["deferred_minors"]) == 1
    assert result["stable_snapshot"].startswith("S-")


def test_ship_gate_blocks_pending_acceptance_and_failed_test(graph, task) -> None:
    task_id = task["id"]
    graph.patch_validate(task_id, "")
    graph.verification_record(
        task_id=task_id,
        name="unit:feature",
        result="fail",
        evidence={"kind": "test_failure"},
    )
    result = graph.ship_evaluate(task_id)
    assert result["status"] == "BLOCKED"
    assert result["acceptance_summary"]["failed_or_pending"]
    assert result["verification_summary"]["failed"]


def test_review_and_fix_budgets_stop_churn(graph, task) -> None:
    first = graph.review_record(task["id"], 0)
    second = graph.review_record(task["id"], 0)
    assert first["stop_general_review"] is False
    assert second["stop_general_review"] is True
    assert second["reason"] == "budget_exhausted"

    fix1 = graph.fix_record(task["id"], introduced=1, resolved=1)
    fix2 = graph.fix_record(task["id"], introduced=1, resolved=1)
    assert fix1["stop_targeted_fixes"] is False
    assert fix2["stop_targeted_fixes"] is True


def test_snapshot_restore_is_graph_only_and_creates_safety_snapshot(graph) -> None:
    snapshot = graph.snapshot_create(stable=True, summary={"test": True})
    graph.decision_record(
        decision_id="D-restore",
        statement="Temporary decision",
        rationale=["test"],
    )
    assert graph.store.get_node("D-restore") is not None
    restored = graph.snapshot_restore(snapshot["id"])
    assert restored["source_code_changed"] is False
    assert graph.store.get_node("D-restore") is None
    assert graph.store.get_snapshot(restored["safety_snapshot"]) is not None


def test_ship_gate_revalidates_current_diff_and_rejects_stale_tests(
    graph, task
) -> None:
    task_id = task["id"]
    graph.criterion_set(task_id, f"{task_id}-AC1", "pass", {"kind": "test"})
    graph.verification_record(
        task_id=task_id,
        name="unit:feature",
        result="pass",
        evidence={"kind": "test_result"},
    )
    (graph.root / "src" / "backend.py").write_text(
        "def locked_api(value: int) -> int:\n    return value * 99\n",
        encoding="utf-8",
    )
    result = graph.ship_evaluate(task_id)
    assert result["status"] == "BLOCKED"
    assert result["final_policy_validation"]["allowed"] is False
    assert result["verification_summary"]["stale"]
