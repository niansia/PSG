from __future__ import annotations

import asyncio
import json

from psg.cli import main
from psg.mcp_server import mcp


def test_cli_status_is_json(graph, capsys) -> None:
    result = main(["--root", str(graph.root), "status"])
    captured = capsys.readouterr()
    assert result == 0
    value = json.loads(captured.out)
    assert value["project"] == "sample"


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
