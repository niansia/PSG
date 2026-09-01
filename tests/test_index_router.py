from __future__ import annotations

from workgraph.runtime import WorkGraph


def test_incremental_python_index_and_persistence(graph: WorkGraph) -> None:
    app = graph.store.get_node("file:src/app.py")
    symbol = graph.store.get_node("symbol:src/app.py:feature")
    assert app and app["payload"]["language"] == "python"
    assert symbol and symbol["payload"]["signature"].startswith("def feature")
    edges = graph.store.edges_for(["file:src/app.py"], both=False)
    assert any(
        edge["type"] == "depends-on" and edge["dst"] == "file:src/backend.py"
        for edge in edges
    )

    unchanged = graph.index()
    assert unchanged["indexed"] == 0
    assert unchanged["unchanged"] >= 3

    reloaded = WorkGraph(graph.root)
    assert reloaded.store.get_node("symbol:src/app.py:feature") is not None


def test_incremental_index_only_updates_changed_file(graph: WorkGraph) -> None:
    path = graph.root / "src" / "app.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nVALUE = 3\n", encoding="utf-8"
    )
    result = graph.index()
    assert result["indexed"] == 1
    assert result["unchanged"] >= 2


def test_router_builds_impact_aware_working_set(graph: WorkGraph) -> None:
    graph.node_policy_set("file:src/backend.py", "frozen", "Stable backend contract")
    opened = graph.task_open(
        intent="Adjust feature calculation",
        acceptance_criteria=["Calculation is correct"],
        targets=["src/app.py"],
        risk="medium",
    )
    context = graph.context_build(opened["id"])
    assert "src/app.py" in context["working_set"]["write"]
    assert "src/backend.py" in context["working_set"]["forbidden"]
    assert context["confidence"] >= 0.85
    assert context["token_estimate"] <= context["context_budget"]
    assert any(
        item["id"] == "symbol:src/app.py:feature" for item in context["context_items"]
    )


def test_context_expansion_requires_evidence(graph: WorkGraph) -> None:
    opened = graph.task_open(
        intent="Change feature", acceptance_criteria=[], targets=["src/app.py"]
    )
    graph.context_build(opened["id"])
    try:
        graph.context_expand(opened["id"], "  ")
    except ValueError as exc:
        assert "reason" in str(exc)
    else:
        raise AssertionError("Expected evidence requirement")
    expanded = graph.context_expand(
        opened["id"], "A failing test references the backend helper"
    )
    assert expanded["task_brief"]["id"] == opened["id"]


def test_independent_clients_share_project_state(graph: WorkGraph) -> None:
    builder = WorkGraph(graph.root)
    opened = builder.task_open(
        intent="Shared state task",
        acceptance_criteria=["Both clients observe the same task"],
        targets=["src/app.py"],
    )
    reviewer = WorkGraph(graph.root)
    assert reviewer.store.get_task(opened["id"])["intent"] == "Shared state task"
    reviewer.issue_report(
        task_id=opened["id"],
        severity="minor",
        claim="Reviewer-side observation",
        evidence={"kind": "cross_client_test"},
    )
    assert (
        builder.store.list_issues(opened["id"])[0]["claim"]
        == "Reviewer-side observation"
    )
