from __future__ import annotations

import asyncio
import json
import subprocess

from psg.cli import _console_safe, main
from psg.installer import setup_skill, uninstall_installation, update_installation
from psg.mcp_server import mcp


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


def test_cli_status_guides_uninitialized_project(repo, capsys) -> None:
    result = main(["--root", str(repo), "status"])
    captured = capsys.readouterr()
    assert result == 0
    assert "Run 'psg init'" in captured.out


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
