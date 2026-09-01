from __future__ import annotations

from workgraph.runtime import WorkGraph


def make_diff(path: str, old: str, new: str) -> str:
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"


def test_frozen_file_is_blocked(graph: WorkGraph) -> None:
    graph.node_policy_set("file:src/backend.py", "frozen", "Approved architecture")
    opened = graph.task_open(
        intent="Change application",
        acceptance_criteria=[],
        targets=["src/app.py"],
        forbidden=["src/backend.py"],
    )
    graph.context_build(opened["id"])
    result = graph.patch_validate(
        opened["id"],
        make_diff("src/backend.py", "return value * 2", "return value * 3"),
    )
    assert result["allowed"] is False
    assert result["violations"][0]["kind"] == "forbidden_or_frozen"


def test_interface_lock_allows_internals_but_blocks_public_signature(
    graph: WorkGraph,
) -> None:
    graph.node_policy_set(
        "file:src/backend.py", "interface_locked", "Public consumers depend on it"
    )
    opened = graph.task_open(
        intent="Optimize backend internals",
        acceptance_criteria=[],
        targets=["src/backend.py"],
        write=["src/backend.py"],
    )
    graph.context_build(opened["id"])
    internal = graph.patch_validate(
        opened["id"],
        make_diff("src/backend.py", "return value * 2", "return value + value"),
    )
    assert internal["allowed"] is True
    contract = graph.patch_validate(
        opened["id"],
        make_diff(
            "src/backend.py",
            "def locked_api(value: int) -> int:",
            "def locked_api(value: int, scale: int = 2) -> int:",
        ),
    )
    assert contract["allowed"] is False
    assert any(item["kind"] == "interface_locked" for item in contract["violations"])


def test_outside_write_scope_requests_expansion(task: dict, graph: WorkGraph) -> None:
    result = graph.patch_validate(
        task["id"],
        make_diff(
            "tests/test_app.py", "assert feature(2) == 5", "assert feature(3) == 7"
        ),
    )
    assert result["allowed"] is False
    assert result["required_scope_expansion"] == ["tests/test_app.py"]


def test_stale_git_revision_is_rejected(graph: WorkGraph, repo) -> None:
    opened = graph.task_open(
        intent="Change feature", acceptance_criteria=[], targets=["src/app.py"]
    )
    graph.context_build(opened["id"])
    (repo / "README.md").write_text("new head\n", encoding="utf-8")
    from conftest import run

    run(repo, "git", "add", "README.md")
    run(repo, "git", "commit", "-m", "move head")
    result = graph.patch_validate(opened["id"], "")
    assert result["allowed"] is False
    assert result["violations"][0]["kind"] == "stale_working_set"


def test_untracked_files_are_included_in_actual_diff(
    task: dict, graph: WorkGraph
) -> None:
    (graph.root / "new_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = graph.patch_validate(task["id"])
    assert result["allowed"] is False
    assert "new_module.py" in result["required_scope_expansion"]


def test_unfreezing_requires_override_and_recorded_decision(graph: WorkGraph) -> None:
    graph.node_policy_set("file:src/backend.py", "frozen", "Approved architecture")
    try:
        graph.node_policy_set(
            "file:src/backend.py", "mutable", "New requirement", override=True
        )
    except PermissionError as exc:
        assert "Decision" in str(exc)
    else:
        raise AssertionError("Expected a recorded-decision requirement")
    graph.decision_record(
        decision_id="D-unfreeze",
        statement="Allow backend revision",
        rationale=["A new requirement needs it"],
    )
    updated = graph.node_policy_set(
        "file:src/backend.py",
        "mutable",
        "New requirement",
        override=True,
        decision_id="D-unfreeze",
    )
    assert updated["policy"] == "mutable"
