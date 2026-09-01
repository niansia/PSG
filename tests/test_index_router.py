from __future__ import annotations

import yaml

from psg.portable import PortableStateTrustError
from psg.runtime import PSG


def test_incremental_python_index_and_persistence(graph: PSG) -> None:
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

    reloaded = PSG(graph.root)
    assert reloaded.store.get_node("symbol:src/app.py:feature") is not None


def test_incremental_index_only_updates_changed_file(graph: PSG) -> None:
    path = graph.root / "src" / "app.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nVALUE = 3\n", encoding="utf-8"
    )
    result = graph.index()
    assert result["indexed"] == 1
    assert result["unchanged"] >= 2


def test_router_builds_impact_aware_working_set(graph: PSG) -> None:
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


def test_context_expansion_requires_evidence(graph: PSG) -> None:
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


def test_independent_clients_share_project_state(graph: PSG) -> None:
    builder = PSG(graph.root)
    opened = builder.task_open(
        intent="Shared state task",
        acceptance_criteria=["Both clients observe the same task"],
        targets=["src/app.py"],
    )
    reviewer = PSG(graph.root)
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


def test_task_tables_are_projected_into_graph(graph: PSG) -> None:
    opened = graph.task_open(
        intent="Add projected behavior",
        acceptance_criteria=["The behavior is visible"],
        constraints=["Keep the backend stable"],
        targets=["src/app.py"],
    )
    task_node = graph.store.get_node(opened["id"])
    requirement = graph.store.get_node(f"{opened['id']}-AC1")
    constraint = graph.store.get_node(f"{opened['id']}-C1")
    assert task_node and task_node["type"] == "Task"
    assert requirement and requirement["type"] == "Requirement"
    assert constraint and constraint["type"] == "Constraint"
    edges = graph.store.edges_for([opened["id"], requirement["id"]])
    assert any(edge["type"] == "requires" for edge in edges)
    assert any(
        edge["type"] == "targets" and edge["dst"] == "file:src/app.py" for edge in edges
    )


def test_portable_state_rehydrates_a_fresh_checkout(graph: PSG, repo, tmp_path) -> None:
    from conftest import run

    graph.decision_record(
        decision_id="D-portable",
        statement="Freeze the backend algorithm",
        rationale=["It is externally verified"],
        scope=["symbol:src/backend.py:locked_api"],
        mutation_effect="frozen",
    )
    graph.decision_approve("D-portable")
    run(repo, "git", "add", ".psg")
    run(repo, "git", "commit", "-m", "persist PSG state")
    clone = tmp_path / "clone"
    run(tmp_path, "git", "clone", str(repo), str(clone))
    reloaded = PSG(clone)
    reloaded.index()
    assert reloaded.store.get_node("D-portable") is not None
    policy, source = reloaded.policy.effective_node_policy(
        "symbol:src/backend.py:locked_api"
    )
    assert policy == "frozen"
    assert "D-portable" in source


def test_structured_psg_debt_annotation_becomes_graph_node(graph: PSG, repo) -> None:
    path = repo / "src" / "app.py"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n# psg-debt: linear scan; why=small input; ceiling=50000; revisit=records > 30000\n",
        encoding="utf-8",
    )
    graph.index()
    debts = [
        node
        for node in graph.store.list_nodes("Debt")
        if node["source"].get("kind") == "psg_debt_annotation"
    ]
    assert len(debts) == 1
    assert debts[0]["payload"]["revisit_trigger"] == "records > 30000"
    assert debts[0]["status"] == "proposed"
    assert debts[0]["payload"]["trust_tier"] == "CLAIMED"
    portable = yaml.safe_load(graph.paths.portable_state.read_text(encoding="utf-8"))
    assert any(node["id"] == debts[0]["id"] for node in portable["nodes"])


def test_psg_debt_marker_inside_python_string_is_not_an_annotation(
    graph: PSG, repo
) -> None:
    path = repo / "src" / "app.py"
    path.write_text(
        path.read_text(encoding="utf-8")
        + '\nEXAMPLE = "psg-debt: fake; why=fixture; ceiling=1; revisit=never"\n',
        encoding="utf-8",
    )
    graph.index()
    assert not any(node["title"] == "fake" for node in graph.store.list_nodes("Debt"))


def test_router_uses_task_edges_and_symbol_lexical_fallback(graph: PSG) -> None:
    opened = graph.task_open(
        intent="Revise locked_api behavior",
        acceptance_criteria=["Locked API behavior is verified"],
        constraints=["Keep the public signature stable"],
        targets=[],
    )
    context = graph.context_build(opened["id"])
    ids = {item["id"] for item in context["context_items"]}
    assert "symbol:src/backend.py:locked_api" in ids
    assert opened["id"] in ids
    assert f"{opened['id']}-AC1" in ids
    assert f"{opened['id']}-C1" in ids
    assert "src/backend.py" in context["working_set"]["write"]


def test_dirty_portable_state_is_rejected_until_explicit_acceptance(
    graph: PSG, repo
) -> None:
    opened = graph.task_open(
        intent="Portable tamper boundary",
        acceptance_criteria=[],
        targets=["src/app.py"],
        write=["src/app.py"],
    )
    graph.context_build(opened["id"])
    state = yaml.safe_load(graph.paths.portable_state.read_text(encoding="utf-8"))
    task = next(item for item in state["tasks"] if item["id"] == opened["id"])
    task["payload"]["working_set"]["write"].append("src/backend.py")
    graph.paths.portable_state.write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    try:
        PSG(repo)
    except PortableStateTrustError as exc:
        assert "not imported" in str(exc)
    else:
        raise AssertionError("Dirty portable state must not auto-import")

    accepted = PSG.accept_portable_state(repo, reason="Reviewed test state change")
    assert accepted["accepted"] is True
    reloaded = PSG(repo)
    assert (
        "src/backend.py"
        in reloaded.store.get_task(opened["id"])["payload"]["working_set"]["write"]
    )


def test_dirty_config_cannot_replace_verification_allowlist(graph: PSG, repo) -> None:
    config = yaml.safe_load(graph.paths.config.read_text(encoding="utf-8"))
    config["verification"]["commands"]["agent-command"] = {
        "command": "python -c \"raise SystemExit('must-not-run')\"",
        "kind": "test",
        "required": True,
    }
    graph.paths.config.write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    try:
        PSG(repo)
    except PortableStateTrustError as exc:
        assert "verification commands were not trusted" in str(exc)
    else:
        raise AssertionError("Dirty config must not become a trusted command allowlist")
