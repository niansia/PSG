from __future__ import annotations

import asyncio
import json

from workgraph.cli import main
from workgraph.mcp_server import mcp


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
        "task_open",
        "context_build",
        "context_expand",
        "node_get",
        "decision_record",
        "node_policy_set",
        "patch_validate",
        "verification_record",
        "acceptance_record",
        "issue_report",
        "issue_update",
        "review_record",
        "fix_record",
        "ship_evaluate",
        "snapshot_create",
    } <= names
    for tool in tools:
        assert tool.description
        assert tool.inputSchema["type"] == "object"


def test_mcp_resources_are_discoverable() -> None:
    resources = asyncio.run(mcp.list_resources())
    templates = asyncio.run(mcp.list_resource_templates())
    assert any(
        str(resource.uri) == "workgraph://project/summary" for resource in resources
    )
    uris = {template.uriTemplate for template in templates}
    assert "workgraph://task/{task_id}/brief" in uris
    assert "workgraph://task/{task_id}/context" in uris
    assert "workgraph://node/{node_id}" in uris
    assert "workgraph://snapshot/{snapshot_id}" in uris


def test_mcp_tool_call_reads_shared_project_state(graph, monkeypatch) -> None:
    monkeypatch.setenv("WORKGRAPH_PROJECT_ROOT", str(graph.root))
    _, structured = asyncio.run(mcp.call_tool("project_status", {}))
    assert structured["project"] == "sample"
