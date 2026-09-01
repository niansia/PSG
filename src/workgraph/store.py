from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .util import canonical_json, json_loads, utc_now

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    maturity TEXT NOT NULL DEFAULT 'accepted',
    policy TEXT NOT NULL DEFAULT 'mutable',
    source_json TEXT NOT NULL DEFAULT '{}',
    revision TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 1.0,
    provenance_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    src TEXT NOT NULL,
    type TEXT NOT NULL,
    dst TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    provenance TEXT NOT NULL DEFAULT 'repo_deterministic',
    revision TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (src, type, dst)
);
CREATE INDEX IF NOT EXISTS edges_src_idx ON edges(src);
CREATE INDEX IF NOT EXISTS edges_dst_idx ON edges(dst);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    risk TEXT NOT NULL,
    context_budget INTEGER NOT NULL,
    review_budget INTEGER NOT NULL,
    fix_budget INTEGER NOT NULL,
    review_rounds INTEGER NOT NULL DEFAULT 0,
    fix_cycles INTEGER NOT NULL DEFAULT 0,
    no_new_blocking_rounds INTEGER NOT NULL DEFAULT 0,
    baseline_snapshot TEXT,
    baseline_git_rev TEXT NOT NULL,
    graph_rev INTEGER NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS criteria (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    mandatory INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    evidence_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    claim TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    affected_json TEXT NOT NULL DEFAULT '[]',
    violates TEXT,
    introduced_by_patch TEXT,
    resolved_by_patch TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS issues_task_idx ON issues(task_id, status, severity);
CREATE TABLE IF NOT EXISTS verifications (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    command TEXT,
    result TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    revision TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    git_rev TEXT NOT NULL,
    graph_rev INTEGER NOT NULL,
    task_id TEXT,
    state_json TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    stable INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


class Store:
    def __init__(self, database: Path, event_log: Path):
        self.database = database
        self.event_log = event_log

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('graph_revision', '0')"
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '1')"
            )
        self.event_log.touch(exist_ok=True)

    def graph_revision(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='graph_revision'"
            ).fetchone()
        return int(row[0] if row else 0)

    def bump_graph_revision(self, connection: sqlite3.Connection | None = None) -> int:
        owns = connection is None
        connection = connection or self.connect()
        try:
            connection.execute(
                "UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key='graph_revision'"
            )
            row = connection.execute(
                "SELECT value FROM meta WHERE key='graph_revision'"
            ).fetchone()
            if owns:
                connection.commit()
            return int(row[0])
        finally:
            if owns:
                connection.close()

    def event(
        self, event_type: str, payload: dict[str, Any], actor: str = "runtime"
    ) -> int:
        ts = utc_now()
        encoded = canonical_json(payload)
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(ts, actor, type, payload_json) VALUES(?,?,?,?)",
                (ts, actor, event_type, encoded),
            )
            seq = int(cursor.lastrowid)
        record = canonical_json(
            {
                "seq": seq,
                "ts": ts,
                "actor": actor,
                "type": event_type,
                "payload": payload,
            }
        )
        with self.event_log.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(record + "\n")
        return seq

    def upsert_node(self, node: dict[str, Any], *, bump: bool = True) -> None:
        now = utc_now()
        fields = (
            node["id"],
            node["type"],
            node.get("title", node["id"]),
            node.get("status", "active"),
            node.get("maturity", "accepted"),
            node.get("policy", "mutable"),
            canonical_json(node.get("source", {})),
            node.get("revision", ""),
            float(node.get("confidence", 1.0)),
            canonical_json(node.get("provenance", [])),
            canonical_json(node.get("payload", {})),
            now,
        )
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO nodes(id,type,title,status,maturity,policy,source_json,revision,confidence,provenance_json,payload_json,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET type=excluded.type,title=excluded.title,status=excluded.status,
                maturity=excluded.maturity,policy=excluded.policy,source_json=excluded.source_json,
                revision=excluded.revision,confidence=excluded.confidence,provenance_json=excluded.provenance_json,
                payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
                fields,
            )
            if bump:
                self.bump_graph_revision(connection)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM nodes WHERE id=?", (node_id,)
            ).fetchone()
        return self._decode_node(row) if row else None

    def list_nodes(self, node_type: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if node_type:
                rows = connection.execute(
                    "SELECT * FROM nodes WHERE type=? ORDER BY id", (node_type,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM nodes ORDER BY type,id"
                ).fetchall()
        return [self._decode_node(row) for row in rows]

    def find_nodes_for_paths(self, paths: Iterable[str]) -> list[dict[str, Any]]:
        ids = [f"file:{path}" for path in paths]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM nodes WHERE id IN ({placeholders})", ids
            ).fetchall()
        return [self._decode_node(row) for row in rows]

    def delete_nodes_with_prefix(self, prefix: str, *, bump: bool = True) -> int:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM edges WHERE src LIKE ? OR dst LIKE ?",
                (prefix + "%", prefix + "%"),
            )
            cursor = connection.execute(
                "DELETE FROM nodes WHERE id LIKE ?", (prefix + "%",)
            )
            if cursor.rowcount and bump:
                self.bump_graph_revision(connection)
            return cursor.rowcount

    def set_policy(
        self, node_id: str, policy: str, maturity: str | None = None
    ) -> None:
        with self.connect() as connection:
            if maturity:
                cursor = connection.execute(
                    "UPDATE nodes SET policy=?, maturity=?, updated_at=? WHERE id=?",
                    (policy, maturity, utc_now(), node_id),
                )
            else:
                cursor = connection.execute(
                    "UPDATE nodes SET policy=?, updated_at=? WHERE id=?",
                    (policy, utc_now(), node_id),
                )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown node: {node_id}")
            self.bump_graph_revision(connection)
        self.event(
            "node.policy_set",
            {"node_id": node_id, "policy": policy, "maturity": maturity},
        )

    def upsert_edge(self, edge: dict[str, Any], *, bump: bool = True) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO edges(src,type,dst,confidence,provenance,revision,created_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(src,type,dst) DO UPDATE SET confidence=excluded.confidence,
                provenance=excluded.provenance,revision=excluded.revision""",
                (
                    edge["src"],
                    edge["type"],
                    edge["dst"],
                    float(edge.get("confidence", 1.0)),
                    edge.get("provenance", "repo_deterministic"),
                    edge.get("revision", ""),
                    utc_now(),
                ),
            )
            if bump:
                self.bump_graph_revision(connection)

    def replace_edges_for_source(self, src: str, edges: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM edges WHERE src=?", (src,))
            for edge in edges:
                connection.execute(
                    "INSERT OR REPLACE INTO edges(src,type,dst,confidence,provenance,revision,created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        edge["src"],
                        edge["type"],
                        edge["dst"],
                        float(edge.get("confidence", 1.0)),
                        edge.get("provenance", "repo_deterministic"),
                        edge.get("revision", ""),
                        utc_now(),
                    ),
                )
            self.bump_graph_revision(connection)

    def edges_for(
        self, node_ids: Iterable[str], both: bool = True
    ) -> list[dict[str, Any]]:
        ids = list(dict.fromkeys(node_ids))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        query = f"SELECT * FROM edges WHERE src IN ({placeholders})"
        params: list[str] = list(ids)
        if both:
            query += f" OR dst IN ({placeholders})"
            params.extend(ids)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def create_task(self, task: dict[str, Any], criteria: list[dict[str, Any]]) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO tasks(id,intent,status,risk,context_budget,review_budget,fix_budget,
                baseline_snapshot,baseline_git_rev,graph_rev,payload_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task["id"],
                    task["intent"],
                    task.get("status", "open"),
                    task.get("risk", "medium"),
                    task["context_budget"],
                    task["review_budget"],
                    task["fix_budget"],
                    task.get("baseline_snapshot"),
                    task["baseline_git_rev"],
                    task["graph_rev"],
                    canonical_json(task.get("payload", {})),
                    now,
                    now,
                ),
            )
            for criterion in criteria:
                connection.execute(
                    "INSERT INTO criteria(id,task_id,text,mandatory,status,evidence_json) VALUES(?,?,?,?,?,?)",
                    (
                        criterion["id"],
                        task["id"],
                        criterion["text"],
                        int(criterion.get("mandatory", True)),
                        criterion.get("status", "pending"),
                        canonical_json(criterion.get("evidence", {})),
                    ),
                )
        self.event("task.opened", {"task_id": task["id"], "intent": task["intent"]})

    def next_id(self, table: str, prefix: str) -> str:
        if table not in {"tasks", "issues", "verifications", "snapshots"}:
            raise ValueError("Unsupported ID table")
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT id FROM {table} WHERE id LIKE ?", (prefix + "-%",)
            ).fetchall()
        numbers = []
        for row in rows:
            try:
                numbers.append(int(row[0].split("-")[-1]))
            except ValueError:
                pass
        return f"{prefix}-{max(numbers, default=0) + 1:04d}"

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            criteria = connection.execute(
                "SELECT * FROM criteria WHERE task_id=? ORDER BY id", (task_id,)
            ).fetchall()
        if not row:
            return None
        task = self._decode_task(row)
        task["criteria"] = [self._decode_criterion(item) for item in criteria]
        return task

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks ORDER BY created_at,id"
            ).fetchall()
        return [self._decode_task(row) for row in rows]

    def update_task(self, task_id: str, **values: Any) -> None:
        allowed = {
            "status",
            "risk",
            "context_budget",
            "review_budget",
            "fix_budget",
            "review_rounds",
            "fix_cycles",
            "no_new_blocking_rounds",
            "baseline_snapshot",
            "baseline_git_rev",
            "graph_rev",
            "payload_json",
        }
        invalid = set(values) - allowed
        if invalid:
            raise ValueError(f"Unsupported task fields: {sorted(invalid)}")
        values["updated_at"] = utc_now()
        if "payload_json" in values and not isinstance(values["payload_json"], str):
            values["payload_json"] = canonical_json(values["payload_json"])
        columns = ",".join(f"{key}=?" for key in values)
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {columns} WHERE id=?", (*values.values(), task_id)
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown task: {task_id}")

    def set_criterion(
        self, task_id: str, criterion_id: str, status: str, evidence: dict[str, Any]
    ) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE criteria SET status=?, evidence_json=? WHERE task_id=? AND id=?",
                (status, canonical_json(evidence), task_id, criterion_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown acceptance criterion: {criterion_id}")
        self.event(
            "criterion.updated",
            {"task_id": task_id, "criterion_id": criterion_id, "status": status},
        )

    def create_issue(self, issue: dict[str, Any]) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO issues(id,task_id,severity,claim,evidence_json,affected_json,violates,
                introduced_by_patch,resolved_by_patch,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    issue["id"],
                    issue["task_id"],
                    issue["severity"],
                    issue["claim"],
                    canonical_json(issue.get("evidence", {})),
                    canonical_json(issue.get("affected_nodes", [])),
                    issue.get("violates"),
                    issue.get("introduced_by_patch"),
                    issue.get("resolved_by_patch"),
                    issue.get("status", "open"),
                    now,
                    now,
                ),
            )
        self.event(
            "issue.reported",
            {
                "issue_id": issue["id"],
                "task_id": issue["task_id"],
                "severity": issue["severity"],
            },
        )

    def update_issue(
        self, issue_id: str, status: str, resolved_by_patch: str | None = None
    ) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE issues SET status=?, resolved_by_patch=?, updated_at=? WHERE id=?",
                (status, resolved_by_patch, utc_now(), issue_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown issue: {issue_id}")
        self.event("issue.updated", {"issue_id": issue_id, "status": status})

    def list_issues(
        self, task_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM issues WHERE task_id=? AND status=? ORDER BY created_at,id",
                    (task_id, status),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM issues WHERE task_id=? ORDER BY created_at,id",
                    (task_id,),
                ).fetchall()
        return [self._decode_issue(row) for row in rows]

    def record_verification(self, verification: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO verifications(id,task_id,name,kind,command,result,required,evidence_json,revision,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    verification["id"],
                    verification["task_id"],
                    verification["name"],
                    verification.get("kind", "test"),
                    verification.get("command"),
                    verification["result"],
                    int(verification.get("required", True)),
                    canonical_json(verification.get("evidence", {})),
                    verification.get("revision", ""),
                    utc_now(),
                ),
            )
        self.event(
            "verification.recorded",
            {
                "verification_id": verification["id"],
                "task_id": verification["task_id"],
                "result": verification["result"],
            },
        )

    def latest_verifications(self, task_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT v.* FROM verifications v JOIN (
                SELECT name, MAX(created_at || id) marker FROM verifications WHERE task_id=? GROUP BY name
                ) latest ON v.name=latest.name AND (v.created_at || v.id)=latest.marker
                WHERE v.task_id=? ORDER BY v.name""",
                (task_id, task_id),
            ).fetchall()
        return [self._decode_verification(row) for row in rows]

    def create_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO snapshots(id,git_rev,graph_rev,task_id,state_json,summary_json,stable,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    snapshot["id"],
                    snapshot["git_rev"],
                    snapshot["graph_rev"],
                    snapshot.get("task_id"),
                    canonical_json(snapshot["state"]),
                    canonical_json(snapshot.get("summary", {})),
                    int(snapshot.get("stable", False)),
                    utc_now(),
                ),
            )
        self.event(
            "snapshot.created",
            {
                "snapshot_id": snapshot["id"],
                "task_id": snapshot.get("task_id"),
                "stable": bool(snapshot.get("stable")),
            },
        )

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
        return self._decode_snapshot(row) if row else None

    def list_snapshots(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM snapshots ORDER BY created_at,id"
            ).fetchall()
        return [self._decode_snapshot(row) for row in rows]

    def export_state(self) -> dict[str, Any]:
        with self.connect() as connection:
            tables = [
                "meta",
                "nodes",
                "edges",
                "tasks",
                "criteria",
                "issues",
                "verifications",
            ]
            return {
                table: [
                    dict(row)
                    for row in connection.execute(f"SELECT * FROM {table}").fetchall()
                ]
                for table in tables
            }

    def restore_state(self, state: dict[str, Any]) -> None:
        tables = [
            "verifications",
            "issues",
            "criteria",
            "tasks",
            "edges",
            "nodes",
            "meta",
        ]
        with self.connect() as connection:
            connection.execute("PRAGMA defer_foreign_keys = ON")
            for table in tables:
                connection.execute(f"DELETE FROM {table}")
            for table in reversed(tables):
                for row in state.get(table, []):
                    keys = list(row)
                    placeholders = ",".join("?" for _ in keys)
                    connection.execute(
                        f"INSERT INTO {table}({','.join(keys)}) VALUES({placeholders})",
                        [row[key] for key in keys],
                    )

    @staticmethod
    def _decode_node(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["source"] = json_loads(value.pop("source_json"), {})
        value["provenance"] = json_loads(value.pop("provenance_json"), [])
        value["payload"] = json_loads(value.pop("payload_json"), {})
        return value

    @staticmethod
    def _decode_task(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["payload"] = json_loads(value.pop("payload_json"), {})
        return value

    @staticmethod
    def _decode_criterion(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["mandatory"] = bool(value["mandatory"])
        value["evidence"] = json_loads(value.pop("evidence_json"), {})
        return value

    @staticmethod
    def _decode_issue(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["evidence"] = json_loads(value.pop("evidence_json"), {})
        value["affected_nodes"] = json_loads(value.pop("affected_json"), [])
        return value

    @staticmethod
    def _decode_verification(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["required"] = bool(value["required"])
        value["evidence"] = json_loads(value.pop("evidence_json"), {})
        return value

    @staticmethod
    def _decode_snapshot(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["stable"] = bool(value["stable"])
        value["state"] = json_loads(value.pop("state_json"), {})
        value["summary"] = json_loads(value.pop("summary_json"), {})
        return value
