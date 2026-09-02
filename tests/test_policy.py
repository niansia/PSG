from __future__ import annotations

import sys

from psg.runtime import PSG
from psg.trust import USER_APPROVED


def allow_operator_approval(monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda *_: "APPROVE")


def make_diff(path: str, old: str, new: str) -> str:
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"


def test_frozen_file_is_blocked(graph: PSG) -> None:
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
    graph: PSG,
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


def test_outside_write_scope_requests_expansion(task: dict, graph: PSG) -> None:
    result = graph.patch_validate(
        task["id"],
        make_diff(
            "tests/test_app.py", "assert feature(2) == 5", "assert feature(3) == 7"
        ),
    )
    assert result["allowed"] is False
    assert result["required_scope_expansion"] == ["tests/test_app.py"]


def test_stale_git_revision_is_rejected(graph: PSG, repo) -> None:
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


def test_untracked_files_are_included_in_actual_diff(task: dict, graph: PSG) -> None:
    (graph.root / "new_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = graph.patch_validate(task["id"])
    assert result["allowed"] is False
    assert "new_module.py" in result["required_scope_expansion"]


def test_unfreezing_requires_override_and_recorded_decision(
    graph: PSG, monkeypatch
) -> None:
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
    allow_operator_approval(monkeypatch)
    graph.decision_approve("D-unfreeze")
    updated = graph.node_policy_set(
        "file:src/backend.py",
        "mutable",
        "New requirement",
        override=True,
        decision_id="D-unfreeze",
        _trust_tier=USER_APPROVED,
    )
    assert updated["policy"] == "mutable"


def test_staged_change_cannot_bypass_final_policy(graph: PSG, repo) -> None:
    from conftest import run

    graph.node_policy_set("file:src/backend.py", "frozen", "Stable algorithm")
    opened = graph.task_open(
        intent="Change only the application",
        acceptance_criteria=[],
        targets=["src/app.py"],
        forbidden=["src/backend.py"],
    )
    graph.context_build(opened["id"])
    (repo / "src" / "backend.py").write_text(
        "def locked_api(value: int) -> int:\n    return value * 99\n",
        encoding="utf-8",
    )
    run(repo, "git", "add", "src/backend.py")
    result = graph.patch_validate(opened["id"])
    assert result["diff_source"] == "runtime_final_diff"
    assert result["allowed"] is False
    assert any(item["path"] == "src/backend.py" for item in result["violations"])


def test_frozen_python_symbol_blocks_only_its_hunk(graph: PSG, repo) -> None:
    graph.node_policy_set(
        "symbol:src/backend.py:locked_api", "frozen", "Approved algorithm"
    )
    opened = graph.task_open(
        intent="Revise backend internals",
        acceptance_criteria=[],
        targets=["src/backend.py"],
        write=["src/backend.py"],
    )
    graph.context_build(opened["id"])
    (repo / "src" / "backend.py").write_text(
        "def locked_api(value: int) -> int:\n    return value + value\n",
        encoding="utf-8",
    )
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is False
    violation = next(
        item
        for item in result["violations"]
        if item["kind"] == "symbol_policy_violation"
    )
    assert violation["symbols"][0]["id"] == "symbol:src/backend.py:locked_api"


def test_architecture_lock_edge_blocks_symbol_change(
    graph: PSG, repo, monkeypatch
) -> None:
    graph.decision_record(
        decision_id="ARCH-0001",
        statement="Stable backend algorithm",
        rationale=["Accepted architecture"],
        scope=["symbol:src/backend.py:locked_api"],
        mutation_effect="frozen",
    )
    allow_operator_approval(monkeypatch)
    graph.decision_approve("ARCH-0001")
    opened = graph.task_open(
        intent="Try to alter locked architecture",
        acceptance_criteria=[],
        targets=["src/backend.py"],
        write=["src/backend.py"],
    )
    graph.context_build(opened["id"])
    (repo / "src" / "backend.py").write_text(
        "def locked_api(value: int) -> int:\n    return value * 3\n",
        encoding="utf-8",
    )
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is False
    assert "symbol:src/backend.py:locked_api" in str(result["violations"])
    assert "frozen" in str(result["violations"])


def test_claimed_graph_lock_does_not_gain_policy_authority(graph: PSG, repo) -> None:
    graph.node_create(
        node_id="ARCH-CLAIMED",
        node_type="Architecture",
        title="Agent-claimed architecture",
        payload={"mutation_effect": "frozen"},
    )
    graph.edge_create("ARCH-CLAIMED", "locks", "symbol:src/backend.py:locked_api")
    policy, source = graph.policy.effective_node_policy(
        "symbol:src/backend.py:locked_api"
    )
    assert policy == "mutable"
    assert source != "edge:ARCH-CLAIMED:locks"


def test_claimed_decision_cannot_unlock_frozen_node(graph: PSG) -> None:
    graph.node_policy_set("file:src/backend.py", "frozen", "Stable boundary")
    proposed = graph.decision_record(
        decision_id="D-CLAIMED-UNLOCK",
        statement="Unlock it",
        rationale=["Agent wants to change it"],
        scope=["file:src/backend.py"],
        mutation_effect="mutable",
    )
    assert proposed["status"] == "proposed"
    assert graph.store.get_node("file:src/backend.py")["policy"] == "frozen"
    try:
        graph.node_policy_set(
            "file:src/backend.py",
            "mutable",
            "Claimed override",
            override=True,
            decision_id="D-CLAIMED-UNLOCK",
        )
    except PermissionError as exc:
        assert "USER_APPROVED" in str(exc)
    else:
        raise AssertionError("A claimed Decision must not weaken policy")


def test_decision_approval_validates_all_scope_before_acceptance(graph: PSG) -> None:
    graph.decision_record(
        decision_id="D-BAD-SCOPE",
        statement="Freeze unresolved scope",
        rationale=["test"],
        scope=["file:does-not-exist.py"],
        mutation_effect="frozen",
    )
    try:
        graph.decision_approve("D-BAD-SCOPE")
    except KeyError as exc:
        assert "does not resolve" in str(exc)
    else:
        raise AssertionError("Invalid scope must fail before Decision acceptance")
    decision = graph.store.get_node("D-BAD-SCOPE")
    assert decision["status"] == "proposed"
    assert decision["payload"]["approval_required"] is True


def test_staged_rename_keeps_source_policy(graph: PSG, repo) -> None:
    from conftest import run

    graph.node_policy_set("file:src/app.py", "frozen", "Stable file")
    opened = graph.task_open(
        intent="Rename another file",
        acceptance_criteria=[],
        targets=["src/backend.py"],
        write=["src/backend.py", "src/renamed.py"],
    )
    graph.context_build(opened["id"])
    run(repo, "git", "mv", "src/app.py", "src/renamed.py")
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is False
    assert any(item["kind"] == "forbidden_or_frozen" for item in result["violations"])


def test_new_dependency_requires_task_justification(graph: PSG, repo) -> None:
    opened = graph.task_open(
        intent="Add a runtime dependency",
        acceptance_criteria=[],
        targets=["requirements.txt"],
        write=["requirements.txt"],
    )
    graph.context_build(opened["id"])
    (repo / "requirements.txt").write_text("httpx>=0.28\n", encoding="utf-8")
    blocked = graph.patch_validate(opened["id"])
    assert any(
        item["kind"] == "new_dependency_requires_justification"
        for item in blocked["violations"]
    )

    justified = graph.task_open(
        intent="Add the approved HTTP client",
        acceptance_criteria=[],
        targets=["requirements.txt"],
        write=["requirements.txt"],
        dependency_justifications=[
            "The standard library lacks the required async transport API"
        ],
    )
    graph.context_build(justified["id"])
    allowed = graph.patch_validate(justified["id"])
    assert allowed["allowed"] is True


def test_governance_edit_is_not_hidden_as_runtime_state(graph: PSG, repo) -> None:
    opened = graph.task_open(
        intent="Change only application code",
        acceptance_criteria=[],
        targets=["src/app.py"],
        write=["src/app.py"],
    )
    graph.context_build(opened["id"])
    config = repo / ".psg" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "\n# unauthorized\n")
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is False
    assert any(
        item["kind"] == "outside_write_scope" and item["path"] == ".psg/config.yaml"
        for item in result["violations"]
    )


def test_rename_into_managed_state_cannot_hide_frozen_source(graph: PSG, repo) -> None:
    from conftest import run

    graph.node_policy_set("file:src/app.py", "frozen", "Stable application entry")
    opened = graph.task_open(
        intent="Change a different file",
        acceptance_criteria=[],
        targets=["src/backend.py"],
        write=["src/backend.py"],
    )
    graph.context_build(opened["id"])
    run(repo, "git", "mv", "src/app.py", ".psg/state/hidden.py")
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is False
    assert any(item["kind"] == "forbidden_or_frozen" for item in result["violations"])


def test_non_dependency_manifest_edit_does_not_require_justification(
    graph: PSG, repo
) -> None:
    from conftest import run

    manifest = repo / "pyproject.toml"
    manifest.write_text(
        '[project]\nname = "sample"\ndescription = "before"\n'
        'dependencies = ["PyYAML>=6"]\n',
        encoding="utf-8",
    )
    run(repo, "git", "add", "pyproject.toml")
    run(repo, "git", "commit", "-m", "add manifest")
    opened = graph.task_open(
        intent="Clarify package metadata",
        acceptance_criteria=[],
        targets=["pyproject.toml"],
        write=["pyproject.toml"],
    )
    graph.context_build(opened["id"])
    manifest.write_text(
        '[project]\nname = "sample"\ndescription = "after"\n'
        'dependencies = ["PyYAML>=6"]\n',
        encoding="utf-8",
    )
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is True
