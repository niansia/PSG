from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from psg.runtime import PSG


def is_open(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False
    return True


def test_every_connection_is_closed_when_its_operation_ends(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No connection may wait for the garbage collector to be closed.

    An open handle keeps the database locked on Windows, which broke temporary
    directory cleanup in the benchmarks on Python 3.13.
    """
    opened: list[sqlite3.Connection] = []
    connect = sqlite3.connect

    def tracking_connect(*args, **kwargs) -> sqlite3.Connection:
        connection = connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)

    graph = PSG.initialize(repo, project="sample")
    graph.index(force=True)
    task = graph.task_open(
        intent="Change the feature without changing the backend contract",
        acceptance_criteria=["Feature behavior is verified"],
        constraints=["Backend API remains unchanged"],
        targets=["src/app.py"],
        read_only=["src/backend.py"],
        risk="medium",
    )
    graph.context_build(task["id"])
    graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="caused_by_patch",
        claim="Feature output changed",
        evidence={"kind": "diff_observation", "path": "src/app.py"},
        affected_nodes=["file:src/app.py"],
    )
    snapshot = graph.snapshot_create(stable=True)
    graph.snapshot_restore(snapshot["id"])
    graph.ship_evaluate(task["id"])
    with pytest.raises(KeyError):
        graph.store.update_task("T-9999", status="closed")

    assert opened
    assert [connection for connection in opened if is_open(connection)] == []
    shutil.rmtree(graph.paths.database.parent)
