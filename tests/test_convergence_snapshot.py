from __future__ import annotations


def runtime_pass(graph, task_id: str):
    result = graph.verify(
        task_id,
        [
            {
                "name": "unit:feature",
                "command": "python -c \"print('ok')\"",
                "kind": "unit",
                "required": True,
            }
        ],
    )
    return result["results"][0]


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
    verification = runtime_pass(graph, task_id)
    graph.criterion_set(
        task_id,
        f"{task_id}-AC1",
        "pass",
        {
            "kind": "test",
            "source": "runtime_executed",
            "reference": verification["id"],
        },
    )
    policy = graph.patch_validate(task_id, "")
    assert policy["allowed"]
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
    graph.verify(
        task_id,
        [
            {
                "name": "unit:feature",
                "command": 'python -c "raise SystemExit(1)"',
                "kind": "unit",
            }
        ],
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
    verification = runtime_pass(graph, task_id)
    graph.criterion_set(
        task_id,
        f"{task_id}-AC1",
        "pass",
        {
            "kind": "test",
            "source": "runtime_executed",
            "reference": verification["id"],
        },
    )
    (graph.root / "src" / "backend.py").write_text(
        "def locked_api(value: int) -> int:\n    return value * 99\n",
        encoding="utf-8",
    )
    result = graph.ship_evaluate(task_id)
    assert result["status"] == "BLOCKED"
    assert result["final_policy_validation"]["allowed"] is False
    assert result["verification_summary"]["stale"]


def test_policy_pass_does_not_replace_functional_verification(graph, task) -> None:
    task_id = task["id"]
    graph.criterion_set(
        task_id,
        f"{task_id}-AC1",
        "pass",
        {"kind": "user_check", "source": "user_asserted", "reference": "user-1"},
    )
    graph.patch_validate(task_id, "")
    result = graph.ship_evaluate(task_id)
    assert result["status"] == "BLOCKED"
    assert result["verification_summary"]["missing"] is True


def test_llm_reported_pass_is_not_trusted_by_ship_gate(graph, task) -> None:
    task_id = task["id"]
    graph.verification_record(
        task_id=task_id,
        name="claimed:test",
        result="pass",
        kind="test",
        evidence={"kind": "claim"},
    )
    graph.criterion_set(
        task_id,
        f"{task_id}-AC1",
        "pass",
        {"kind": "user_check", "source": "user_asserted", "reference": "user-1"},
    )
    result = graph.ship_evaluate(task_id)
    assert result["status"] == "BLOCKED"
    assert result["verification_summary"]["untrusted"]


def test_acceptance_pass_and_waiver_require_authority(graph, task) -> None:
    criterion = f"{task['id']}-AC1"
    try:
        graph.criterion_set(task["id"], criterion, "pass", {"kind": "test"})
    except ValueError as exc:
        assert "reference" in str(exc)
    else:
        raise AssertionError("Expected acceptance evidence validation")
    try:
        graph.criterion_set(task["id"], criterion, "waived", {})
    except PermissionError as exc:
        assert "Decision" in str(exc)
    else:
        raise AssertionError("Expected waiver authority validation")


def test_high_risk_review_requires_a_different_actor(graph) -> None:
    opened = graph.task_open(
        intent="High-risk change",
        acceptance_criteria=[],
        targets=["src/app.py"],
        risk="high",
        builder_actor="builder-1",
    )
    task_id = opened["id"]
    runtime_pass(graph, task_id)
    graph.review_record(task_id, 0, actor_id="builder-1", session_id="build")
    same_actor = graph.ship_evaluate(task_id)
    assert same_actor["independent_review_satisfied"] is False
    graph.review_record(task_id, 0, actor_id="reviewer-2", session_id="review")
    independent = graph.ship_evaluate(task_id)
    assert independent["independent_review_satisfied"] is True


def test_accepted_debt_is_not_reopened_before_trigger(graph, task) -> None:
    debt = graph.debt_record(
        task_id=task["id"],
        what="Keep a linear scan for v1",
        why="The dataset is small",
        ceiling="50000 records",
        revisit_trigger="records exceed 30000",
        affected_nodes=["symbol:src/app.py:feature"],
    )
    issue = graph.issue_report(
        task_id=task["id"],
        severity="major",
        claim="Replace the linear scan now",
        evidence={"kind": "performance_suggestion"},
        affected_nodes=["symbol:src/app.py:feature"],
        debt_id=debt["id"],
    )
    assert issue["status"] == "deferred"
    assert issue["severity"] == "optional"
    review = graph.debt_review(debt["id"], trigger_met=False, evidence={})
    assert review["review_action"] == "DO_NOT_REOPEN"


def test_skill_conflict_cannot_override_guardrail_without_decision(graph, task) -> None:
    deferred = graph.conflict_record(
        task_id=task["id"],
        source="simplicity-skill",
        domain="architecture",
        recommendation="Delete the locked adapter",
        guardrail="ARCH-14 frozen",
    )
    assert deferred["payload"]["resolution"] == "deferred"
    try:
        graph.conflict_record(
            task_id=task["id"],
            source="simplicity-skill",
            domain="architecture",
            recommendation="Delete the locked adapter",
            guardrail="ARCH-14 frozen",
            resolution="user_override",
        )
    except PermissionError as exc:
        assert "Decision" in str(exc)
    else:
        raise AssertionError("Expected a Decision requirement")
