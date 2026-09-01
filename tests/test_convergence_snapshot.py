from __future__ import annotations

from psg.trust import USER_APPROVED


def runtime_pass(graph, task_id: str):
    result = graph.verify_commands(
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
    graph.verify_commands(
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


def test_no_new_blocker_metric_is_derived_but_budget_is_the_hard_stop(graph) -> None:
    opened = graph.task_open(
        intent="Review-budget boundary",
        acceptance_criteria=[],
        targets=["src/app.py"],
        review_budget=3,
    )
    first = graph.review_record(opened["id"], 99)
    second = graph.review_record(opened["id"], 99)
    third = graph.review_record(opened["id"], 99)
    assert first["derived_new_blocking_issues"] == 0
    assert second["no_new_blocking_rounds"] == 2
    assert second["stop_general_review"] is False
    assert third["stop_general_review"] is True
    assert third["reason"] == "budget_exhausted"


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
        _trust_tier=USER_APPROVED,
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
        _trust_tier=USER_APPROVED,
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
        graph.criterion_set(
            task["id"],
            criterion,
            "pass",
            {
                "kind": "user_check",
                "source": "user_asserted",
                "reference": "trust-me",
            },
        )
    except PermissionError as exc:
        assert "cannot self-assert" in str(exc)
    else:
        raise AssertionError("A claimed user_asserted label must not pass acceptance")
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
    declared = graph.ship_evaluate(task_id)
    assert declared["independent_review_satisfied"] is False
    graph.review_record(
        task_id,
        0,
        actor_id="reviewer-2",
        session_id="review-approved",
        _trust_tier=USER_APPROVED,
    )
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
    debt = graph.debt_approve(debt["id"])
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


def test_claimed_debt_trigger_cannot_reopen_accepted_debt(graph, task) -> None:
    proposed = graph.debt_record(
        task_id=task["id"],
        what="Keep a linear scan for v1",
        why="The dataset is small",
        ceiling="50000 records",
        revisit_trigger="records exceed 30000",
    )
    debt = graph.debt_approve(proposed["id"])
    claimed = graph.debt_review(
        debt["id"],
        trigger_met=True,
        evidence={"kind": "metric_claim", "value": 40000},
    )
    assert claimed["review_action"] == "USER_APPROVAL_REQUIRED"
    assert claimed["trigger_met"] is False
    assert graph.store.get_node(debt["id"])["status"] == "accepted"

    approved = graph.debt_review(
        debt["id"],
        trigger_met=True,
        evidence={"kind": "measured_metric", "value": 40000},
        _trust_tier=USER_APPROVED,
    )
    assert approved["review_action"] == "REOPEN"
    reset_claim = graph.debt_review(debt["id"], trigger_met=False, evidence={})
    assert reset_claim["review_action"] == "USER_APPROVAL_REQUIRED"
    assert reset_claim["trigger_met"] is True
    assert graph.store.get_node(debt["id"])["status"] == "due"


def test_external_tool_label_from_agent_remains_claimed(graph, task) -> None:
    task_id = task["id"]
    claimed = graph.verification_record(
        task_id=task_id,
        name="external:claimed",
        result="pass",
        kind="integration",
        source="external_tool",
        evidence={"reference": "trust-me"},
    )
    assert claimed["evidence"]["trust_tier"] == "CLAIMED"
    assert claimed["evidence"]["reported_source"] == "external_tool"
    result = graph.ship_evaluate(task_id)
    assert claimed["id"] in result["verification_summary"]["untrusted"]


def test_runtime_output_is_local_and_portable_evidence_is_compact(graph, task) -> None:
    marker = "PSG_PRIVATE_LOG_MARKER"
    result = graph.verify_commands(
        task["id"],
        [
            {
                "name": "compact-log",
                "command": f"python -c \"print('{marker}')\"",
                "kind": "test",
            }
        ],
    )["results"][0]
    portable = graph.paths.portable_state.read_text(encoding="utf-8")
    assert marker not in portable
    assert result["evidence"]["output_hash"].startswith("sha256:")
    local_log = graph.paths.local_dir / "verification" / f"{result['id']}.log"
    assert marker in local_log.read_text(encoding="utf-8")


def test_verification_allowlist_does_not_execute_agent_command(graph, task) -> None:
    marker = graph.root / "must-not-exist.txt"
    injected = f"python -c \"open(r'{marker}', 'w').write('bad')\""
    try:
        graph.verify(task["id"], [injected])
    except PermissionError as exc:
        assert "configured check names" in str(exc)
    else:
        raise AssertionError("Unconfigured MCP check name must be rejected")
    assert not marker.exists()

    graph.config["verification"] = {"commands": {"safe": "python -c \"print('safe')\""}}
    result = graph.verify(task["id"], ["safe"])
    assert result["results"][0]["result"] == "pass"


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
