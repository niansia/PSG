from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest

from psg.cli import _console_safe, main
from psg.config import discover_root
from psg.installer import setup_skill, uninstall_installation, update_installation
from psg.mcp_server import mcp
from psg.runtime import PSG
from psg.trust import (
    EXTERNAL_ATTESTED,
    RUNTIME_ATTESTED,
    USER_APPROVED,
    ApprovalRefused,
)


def test_cli_status_is_json(graph, capsys) -> None:
    result = main(["--root", str(graph.root), "--json", "status"])
    captured = capsys.readouterr()
    assert result == 0
    value = json.loads(captured.out)
    assert value["project"] == "sample"


def test_cli_status_is_human_readable_by_default(graph, capsys) -> None:
    result = main(["--root", str(graph.root), "status"])
    captured = capsys.readouterr()
    assert result == 0
    assert "PSG " in captured.out
    assert "Project" in captured.out
    assert "Agents" in captured.out
    assert "Current task" in captured.out


def test_project_root_discovery_stops_at_the_git_worktree(graph, tmp_path) -> None:
    # ~/.psg/config.yaml is the global home, not a project: an unbounded upward scan
    # resolves every repository under $HOME to the home directory once setup has run.
    outer_state = tmp_path / ".psg"
    outer_state.mkdir(parents=True, exist_ok=True)
    (outer_state / "config.yaml").write_text("version: 1", encoding="utf-8")

    assert discover_root(graph.root / "src") == graph.root
    assert discover_root(graph.root) == graph.root

    plain = tmp_path / "plain"
    (plain / ".git").mkdir(parents=True)
    assert discover_root(plain) == plain.resolve()


def test_cli_status_guides_uninitialized_project(repo, capsys) -> None:
    result = main(["--root", str(repo), "status"])
    captured = capsys.readouterr()
    assert result == 0
    assert "Run 'psg init'" in captured.out


def test_cli_handoff_writes_markdown(graph, task, tmp_path, capsys) -> None:
    output = tmp_path / "PSG_REVIEW.md"
    result = main(
        [
            "--root",
            str(graph.root),
            "handoff",
            task["id"],
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert result == 0
    assert str(output) in captured.out
    assert "Review the task, not the entire project." in output.read_text(
        encoding="utf-8"
    )


# Every live MCP call is bounded: a stalled stdio server must fail the suite fast
# instead of hanging it. PSG tools that shell out to Git regressed exactly this way
# when their child processes inherited the JSON-RPC stdin handle.
LIVE_MCP_CALL_TIMEOUT_SECONDS = 30.0


def test_live_mcp_git_backed_tools_answer_over_stdio(graph, task) -> None:
    mcp_module = pytest.importorskip("mcp")
    stdio_module = pytest.importorskip("mcp.client.stdio")

    async def exercise() -> None:
        parameters = mcp_module.StdioServerParameters(
            command=sys.executable,
            args=["-m", "psg.mcp_server"],
            env={**os.environ, "PSG_PROJECT_ROOT": str(graph.root)},
        )
        async with (
            stdio_module.stdio_client(parameters) as streams,
            mcp_module.ClientSession(*streams) as session,
        ):
            await asyncio.wait_for(session.initialize(), LIVE_MCP_CALL_TIMEOUT_SECONDS)
            status = await asyncio.wait_for(
                session.call_tool("project_status", {}),
                LIVE_MCP_CALL_TIMEOUT_SECONDS,
            )
            assert status.structuredContent["root"] == str(graph.root)
            context = await asyncio.wait_for(
                session.call_tool(
                    "context_build", {"task_id": task["id"], "max_tokens": 12000}
                ),
                LIVE_MCP_CALL_TIMEOUT_SECONDS,
            )
            assert context.isError is False
            assert context.structuredContent["task_brief"]["id"] == task["id"]
            handoff = await asyncio.wait_for(
                session.call_tool("handoff_build", {"task_id": task["id"]}),
                LIVE_MCP_CALL_TIMEOUT_SECONDS,
            )
            assert handoff.isError is False
            # A second Git-backed call proves the transport is still healthy.
            again = await asyncio.wait_for(
                session.call_tool("project_status", {}),
                LIVE_MCP_CALL_TIMEOUT_SECONDS,
            )
            assert again.isError is False

    asyncio.run(exercise())


def test_human_output_falls_back_for_legacy_windows_console() -> None:
    rendered = _console_safe("✓ Codex → ready · now\n○ Gemini", "cp950")
    rendered.encode("cp950")
    assert rendered == "[ok] Codex -> ready - now\n[--] Gemini"


def test_cli_global_on_off_controls_runtime(graph, capsys) -> None:
    assert main(["off", "--global"]) == 0
    capsys.readouterr()
    value = graph.status()
    assert value["global_enabled"] is False
    assert value["enabled"] is False
    assert main(["on", "--global"]) == 0
    capsys.readouterr()
    assert graph.status()["enabled"] is True


def test_mcp_exposes_complete_tool_surface() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "project_status",
        "index_refresh",
        "state_sync",
        "guardrails_get",
        "task_open",
        "context_build",
        "context_expand",
        "node_get",
        "node_create",
        "edge_create",
        "decision_record",
        "node_policy_set",
        "patch_validate",
        "patch_validate_proposed",
        "verification_run",
        "verification_record",
        "acceptance_record",
        "issue_report",
        "issue_update",
        "review_record",
        "fix_record",
        "ship_evaluate",
        "snapshot_create",
        "handoff_build",
        "debt_record",
        "debt_review",
        "conflict_record",
    } <= names
    for tool in tools:
        assert tool.description
        assert tool.inputSchema["type"] == "object"
    actual_validation = next(tool for tool in tools if tool.name == "patch_validate")
    assert "diff" not in actual_validation.inputSchema.get("properties", {})
    proposed = next(tool for tool in tools if tool.name == "patch_validate_proposed")
    assert "diff" in proposed.inputSchema.get("properties", {})
    verification_run = next(tool for tool in tools if tool.name == "verification_run")
    run_properties = verification_run.inputSchema.get("properties", {})
    assert "check_names" in run_properties
    assert "checks" not in run_properties
    verification_record = next(
        tool for tool in tools if tool.name == "verification_record"
    )
    record_properties = verification_record.inputSchema.get("properties", {})
    assert "source" not in record_properties
    assert "command" not in record_properties
    node_policy = next(tool for tool in tools if tool.name == "node_policy_set")
    policy_properties = node_policy.inputSchema.get("properties", {})
    assert "override" not in policy_properties
    assert "decision_id" not in policy_properties
    handoff = next(tool for tool in tools if tool.name == "handoff_build")
    assert handoff.annotations is not None
    assert handoff.annotations.readOnlyHint is True
    issue = next(tool for tool in tools if tool.name == "issue_report")
    assert "relation_to_task" in issue.inputSchema.get("required", [])


def test_mcp_instructions_state_the_review_boundary() -> None:
    """A host reading only the server instructions must still learn the boundary."""
    instructions = mcp.instructions or ""
    assert "Task Contract" in instructions
    assert "relation_to_task" in instructions
    for relation in (
        "caused_by_patch",
        "violates_acceptance",
        "violates_project_constraint",
        "pre_existing",
        "unrelated",
        "future_improvement",
    ):
        assert relation in instructions
    assert "follow-up" in instructions
    assert "handoff_build" in instructions
    assert "Review the task, not the entire project." in instructions


def test_mcp_resources_are_discoverable() -> None:
    resources = asyncio.run(mcp.list_resources())
    templates = asyncio.run(mcp.list_resource_templates())
    assert any(str(resource.uri) == "psg://project/summary" for resource in resources)
    assert any(
        str(resource.uri) == "psg://project/guardrails" for resource in resources
    )
    uris = {template.uriTemplate for template in templates}
    assert "psg://task/{task_id}/brief" in uris
    assert "psg://task/{task_id}/context" in uris
    assert "psg://node/{node_id}" in uris
    assert "psg://snapshot/{snapshot_id}" in uris


def test_mcp_tool_call_reads_shared_project_state(graph, monkeypatch) -> None:
    monkeypatch.setenv("PSG_PROJECT_ROOT", str(graph.root))
    _, structured = asyncio.run(mcp.call_tool("project_status", {}))
    assert structured["project"] == "sample"


def test_cli_setup_installs_complete_skill_bundle(tmp_path, capsys) -> None:
    destination = tmp_path / "skills"
    result = main(["--json", "setup", "codex", "--skill-dir", str(destination)])
    captured = capsys.readouterr()
    assert result == 0
    value = json.loads(captured.out)
    installed = destination / "psg"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "agents" / "openai.yaml").is_file()
    assert (installed / "references" / "compatibility-contract.md").is_file()
    assert value["installed"][0]["path"] == str(installed)


def test_setup_autodetects_hosts_and_registers_native_mcp(
    tmp_path, monkeypatch
) -> None:
    commands: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name in {"codex", "claude", "gemini", "psg", "psg-mcp"}:
            return str(tmp_path / "bin" / f"{name}.exe")
        return None

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("psg.installer.shutil.which", fake_which)
    result = setup_skill(runner=runner)
    assert result["ready"] is True
    assert {item["host"] for item in result["installed"]} == {
        "codex",
        "claude",
        "gemini",
    }
    assert all(item["mcp_registered"] for item in result["integrations"])
    assert any(command[1:4] == ["mcp", "add", "psg"] for command in commands)
    assert any("--scope" in command and "user" in command for command in commands)
    for item in result["installed"]:
        path = tmp_path / "user-home" / f".{item['host']}" / "skills" / "psg"
        assert (path / "SKILL.md").is_file()
        assert (path / "references" / "runtime-operations.md").is_file()

    removed = uninstall_installation(remove_runtime=False, runner=runner)
    assert removed["uninstalled"] is True
    assert removed["project_state"] == "preserved"
    assert all(
        not (tmp_path / "user-home" / f".{name}" / "skills" / "psg").exists()
        for name in ("codex", "claude", "gemini")
    )


def test_setup_is_idempotent_and_replaces_a_stale_bundle(tmp_path) -> None:
    """Re-running setup must converge, not accumulate files from older bundles."""
    destination = tmp_path / "skills"
    first = setup_skill(skill_dir=str(destination))
    installed = destination / "psg"
    stale = installed / "references" / "removed-in-a-later-version.md"
    stale.write_text("stale", encoding="utf-8")

    second = setup_skill(skill_dir=str(destination))
    assert second["installed"] == first["installed"]
    assert not stale.exists()
    assert (installed / "SKILL.md").is_file()
    assert (installed / "agents" / "openai.yaml").is_file()
    assert (installed / "references" / "review-boundary.md").is_file()


def test_update_refreshes_runtime_then_integrations() -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "psg.cli" in command:
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"ready": True}), ""
            )
        return subprocess.CompletedProcess(command, 0, "updated", "")

    result = update_installation("git+https://example.invalid/psg.git", runner=runner)
    assert result["updated"] is True
    assert commands[0][2:5] == ["pip", "install", "--upgrade"]
    assert commands[1][-2:] == ["--json", "setup"]


def test_update_defaults_to_latest_stable_release() -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:3] == ["git", "ls-remote", "--tags"]:
            output = (
                "aaa\trefs/tags/v1.0.0\n"
                "bbb\trefs/tags/v1.2.0\n"
                "ccc\trefs/tags/v2.0.0-rc.1"
            )
            return subprocess.CompletedProcess(command, 0, output, "")
        if "psg.cli" in command:
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"ready": True}), ""
            )
        return subprocess.CompletedProcess(command, 0, "updated", "")

    result = update_installation(runner=runner)
    assert result["channel"] == "stable"
    assert result["release"] == "v1.2.0"
    assert result["source"].endswith("PSG.git@v1.2.0")
    assert commands[0][:4] == ["git", "ls-remote", "--tags", "--refs"]


def test_dev_update_explicitly_tracks_main() -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "psg.cli" in command:
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"ready": True}), ""
            )
        return subprocess.CompletedProcess(command, 0, "updated", "")

    result = update_installation(channel="dev", runner=runner)
    assert result["channel"] == "dev"
    assert result["release"] == "main"
    assert result["source"].endswith("PSG.git@main")
    assert not any(command[:2] == ["git", "ls-remote"] for command in commands)


def test_cli_update_requires_explicit_dev_channel(monkeypatch, capsys) -> None:
    calls: list[tuple[str | None, str]] = []

    def update(*, source: str | None, channel: str) -> dict[str, object]:
        calls.append((source, channel))
        return {"updated": True, "message": "updated"}

    monkeypatch.setattr("psg.cli.update_installation", update)
    assert main(["--json", "update"]) == 0
    capsys.readouterr()
    assert main(["--json", "update", "--channel", "dev"]) == 0
    capsys.readouterr()
    assert calls == [(None, "stable"), (None, "dev")]


def test_init_repairs_missing_host_integration(repo, monkeypatch, capsys) -> None:
    calls: list[str] = []
    fake_status = {
        "version": "1.0.0",
        "global_enabled": True,
        "agents": [
            {
                "id": "codex",
                "name": "Codex",
                "detected": True,
                "skill_installed": False,
                "mcp_registered": False,
            }
        ],
    }
    monkeypatch.setattr("psg.cli.installation_status", lambda: fake_status)
    monkeypatch.setattr(
        "psg.cli.setup_skill",
        lambda: calls.append("setup") or {"ready": True},
    )
    result = main(["--root", str(repo), "--json", "init"])
    capsys.readouterr()
    assert result == 0
    assert calls == ["setup"]
    assert (repo / ".psg" / "config.yaml").is_file()


def test_mcp_decision_is_proposed_and_does_not_apply_policy(graph, monkeypatch) -> None:
    monkeypatch.setenv("PSG_PROJECT_ROOT", str(graph.root))
    _, structured = asyncio.run(
        mcp.call_tool(
            "decision_record",
            {
                "decision_id": "D-MCP-CLAIM",
                "statement": "Unlock backend",
                "rationale": ["Agent claim"],
                "scope": ["file:src/backend.py"],
                "mutation_effect": "mutable",
            },
        )
    )
    assert structured["status"] == "proposed"
    assert structured["approval_required"] is True


def _seed_approval_targets(graph, task: dict) -> dict[str, str]:
    graph.decision_record(
        decision_id="D-APPROVAL",
        statement="Keep the application boundary stable",
        rationale=["Approval test fixture"],
        scope=["file:src/app.py"],
        mutation_effect="frozen",
    )
    debt = graph.debt_record(
        task_id=task["id"],
        what="Bounded fixture debt",
        why="Exercise the approval path",
        ceiling="One fixture",
        revisit_trigger="Fixture review",
    )
    review_debt = graph.debt_record(
        task_id=task["id"],
        what="Accepted fixture debt",
        why="Exercise the debt-review path",
        ceiling="One fixture",
        revisit_trigger="Fixture review",
    )
    accepted = graph.store.get_node(review_debt["id"])
    assert accepted is not None
    accepted["status"] = "accepted"
    accepted["maturity"] = "accepted"
    accepted["payload"]["trust_tier"] = USER_APPROVED
    graph.store.upsert_node(accepted)
    issue = graph.issue_report(
        task_id=task["id"],
        severity="minor",
        relation_to_task="future_improvement",
        claim="Fixture follow-up",
        evidence={"kind": "test", "reference": "fixture"},
    )
    graph._persist()
    return {
        "decision": "D-APPROVAL",
        "debt": debt["id"],
        "review_debt": review_debt["id"],
        "issue": issue["id"],
    }


def _approval_commands(
    root: str, task_id: str, targets: dict[str, str]
) -> list[tuple[str, list[str]]]:
    """Every CLI entry point that can mint USER_APPROVED authority."""
    return [
        ("state accept", ["--root", root, "state", "accept", "--reason", "r"]),
        (
            "decision approve",
            ["--root", root, "decision", "approve", targets["decision"]],
        ),
        (
            "task approve-scope",
            ["--root", root, "task", "approve-scope", task_id, "--reason", "r"],
        ),
        (
            "debt approve",
            ["--root", root, "debt", "approve", targets["debt"]],
        ),
        (
            "task criterion",
            [
                "--root",
                root,
                "task",
                "criterion",
                task_id,
                f"{task_id}-AC1",
                "fail",
                "--user-approved",
            ],
        ),
        ("review record", ["--root", root, "review", task_id, "--user-approved"]),
        (
            "node policy set",
            [
                "--root",
                root,
                "node",
                "policy",
                "file:src/app.py",
                "frozen",
                "--reason",
                "r",
                "--override",
            ],
        ),
        (
            "verification record",
            [
                "--root",
                root,
                "verification",
                task_id,
                "unit",
                "pass",
                "--user-approved",
            ],
        ),
        (
            "issue update",
            [
                "--root",
                root,
                "issue",
                "update",
                targets["issue"],
                "fixed",
                "--user-approved",
            ],
        ),
        (
            "debt review",
            [
                "--root",
                root,
                "debt",
                "review",
                targets["review_debt"],
                "--user-approved",
            ],
        ),
    ]


def test_every_user_approved_cli_path_refuses_a_non_interactive_caller(
    graph, task, capsys, monkeypatch
) -> None:
    """A coding agent runs PSG as a captured subprocess; that must never mint authority."""
    targets = _seed_approval_targets(graph, task)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    for label, argv in _approval_commands(str(graph.root), task["id"], targets):
        assert main(argv) == 2, f"{label} was not refused"
        captured = capsys.readouterr()
        assert "interactive terminal" in captured.err, label


def test_approval_refuses_a_piped_answer(graph, task, capsys, monkeypatch) -> None:
    """`echo APPROVE | psg task approve-scope ...` must not work."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda *_: "APPROVE")

    assert (
        main(
            [
                "--root",
                str(graph.root),
                "task",
                "approve-scope",
                task["id"],
                "--reason",
                "r",
            ]
        )
        == 2
    )
    assert graph.store.get_task(task["id"])["payload"].get("scope_approval") is None


def test_approval_requires_the_exact_word(graph, task, capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda *_: "y")

    assert (
        main(
            [
                "--root",
                str(graph.root),
                "task",
                "approve-scope",
                task["id"],
                "--reason",
                "r",
            ]
        )
        == 2
    )
    assert graph.store.get_task(task["id"])["payload"].get("scope_approval") is None


def test_interactive_approval_shows_the_authority_it_grants(
    graph, task, capsys, monkeypatch
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda *_: "APPROVE")

    assert (
        main(
            [
                "--root",
                str(graph.root),
                "task",
                "approve-scope",
                task["id"],
                "--reason",
                "r",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "PSG USER APPROVAL" in captured.out
    # The operator must see the authority they are granting, not just a yes/no prompt.
    assert "Write authority" in captured.out
    assert "src/app.py" in captured.out
    assert (
        graph.store.get_task(task["id"])["payload"]["scope_approval"]["reason"] == "r"
    )


def test_direct_runtime_approval_paths_refuse_non_tty(graph, task, monkeypatch) -> None:
    targets = _seed_approval_targets(graph, task)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)

    calls = [
        lambda: graph.task_scope_approve(task["id"], "Reviewed boundary"),
        lambda: graph.decision_approve(targets["decision"]),
        lambda: graph.debt_approve(targets["debt"]),
        lambda: PSG.accept_portable_state(graph.root, reason="Reviewed state"),
    ]
    for call in calls:
        with pytest.raises(ApprovalRefused, match="interactive terminal"):
            call()


def test_runtime_rejects_caller_supplied_user_approved(
    graph, task, monkeypatch
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)

    with pytest.raises(ApprovalRefused, match="interactive terminal"):
        graph.verification_record(
            task_id=task["id"],
            name="claimed-pass",
            result="pass",
            kind="test",
            command="claimed",
            required=True,
            source="user_asserted",
            evidence={"reference": "trust-me"},
            _trust_tier=USER_APPROVED,
        )
    assert not graph.store.list_verifications(task["id"])


@pytest.mark.parametrize("trust_tier", [RUNTIME_ATTESTED, EXTERNAL_ATTESTED])
def test_runtime_rejects_caller_supplied_attestation(graph, trust_tier) -> None:
    with pytest.raises(ApprovalRefused, match="cannot be supplied"):
        graph.node_create(
            node_id=f"claimed:{trust_tier}",
            node_type="Constraint",
            title="Caller-supplied authority",
            payload={},
            _trust_tier=trust_tier,
        )
    assert graph.store.get_node(f"claimed:{trust_tier}") is None


def test_direct_runtime_interactive_approval_succeeds(
    graph, task, capsys, monkeypatch
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda *_: "APPROVE")

    approved = graph.task_scope_approve(task["id"], "Reviewed boundary")

    assert approved["scope_approved"] is True
    assert "Write authority" in capsys.readouterr().out
