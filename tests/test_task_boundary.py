from __future__ import annotations

import sqlite3

import pytest

from psg.cli import main
from psg.store import SCHEMA, Store
from psg.task_contract import MAX_FIX_CYCLES, MAX_REVIEW_ROUNDS, contract_hash
from psg.trust import USER_APPROVED


def make_ready(graph, task: dict) -> None:
    task_id = task["id"]
    verification = graph.verify_commands(
        task_id,
        [
            {
                "name": "unit:boundary",
                "command": "python -c \"print('ok')\"",
                "kind": "unit",
                "required": True,
            }
        ],
    )["results"][0]
    for criterion in graph.store.get_task(task_id)["criteria"]:
        graph.criterion_set(
            task_id,
            criterion["id"],
            "pass",
            {
                "kind": "test",
                "source": "runtime_executed",
                "reference": verification["id"],
            },
        )
    assert graph.patch_validate(task_id)["allowed"] is True


def test_task_contract_formalizes_every_boundary(graph, task) -> None:
    contract = graph.task_contract(task["id"])
    assert contract["contract_version"] == 1
    assert contract["goal_boundary"]["intent"] == task["intent"]
    assert contract["context_boundary"]["constraints"]
    assert contract["mutation_boundary"]["read_only"] == ["src/backend.py"]
    assert contract["review_boundary"]["no_scope_expansion_by_review"] is True
    assert contract["completion_boundary"]["current_task_blockers"] == 0
    assert graph.store.get_task(task["id"])["payload"]["contract_hash"].startswith(
        "sha256:"
    )


def test_patch_caused_blocker_blocks_current_task(graph, task) -> None:
    path = graph.root / "src" / "app.py"
    path.write_text(path.read_text(encoding="utf-8") + "\n# regression\n")
    issue = graph.issue_report(
        task_id=task["id"],
        severity="blocker",
        relation_to_task="caused_by_patch",
        claim="The current patch crashes",
        evidence={"kind": "diff_observation"},
        affected_nodes=["file:src/app.py"],
    )
    assert issue["evidence_sufficient"] is True
    assert issue["blocks_current_task"] is True


def test_acceptance_major_blocks_current_task(graph, task) -> None:
    issue = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="violates_acceptance",
        claim="Required behavior is missing",
        evidence={"kind": "acceptance_review", "path": "src/app.py"},
        violates=f"{task['id']}-AC1",
    )
    assert issue["evidence_sufficient"] is True
    assert issue["blocks_current_task"] is True


def test_project_constraint_major_blocks_current_task(graph, task) -> None:
    issue = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="violates_project_constraint",
        claim="The backend contract was changed",
        evidence={"kind": "constraint_review", "path": "src/backend.py"},
        affected_nodes=["file:src/backend.py"],
        violates=f"{task['id']}-C1",
    )
    assert issue["evidence_sufficient"] is True
    assert issue["blocks_current_task"] is True


@pytest.mark.parametrize(
    "relation",
    ["pre_existing", "unrelated", "future_improvement"],
)
def test_out_of_boundary_major_is_follow_up(graph, task, relation: str) -> None:
    issue = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task=relation,
        claim=f"A {relation} finding",
        evidence={"kind": "review_observation", "path": "src/backend.py"},
    )
    assert issue["severity"] == "major"
    assert issue["blocks_current_task"] is False


def test_unknown_issue_relation_is_rejected(graph, task) -> None:
    with pytest.raises(ValueError, match="relation_to_task"):
        graph.issue_report(
            task_id=task["id"],
            severity="major",
            relation_to_task="reviewer_invented",
            claim="Invented relation",
            evidence={"kind": "claim"},
        )


def test_review_cannot_expand_task_contract(graph, task) -> None:
    before = graph.task_contract(task["id"])
    stored_before = graph.store.get_task(task["id"])["payload"]["contract_hash"]
    result = graph.review_record(
        task["id"], 99, actor_id="reviewer", session_id="review-1"
    )
    after = graph.task_contract(task["id"])
    stored_after = graph.store.get_task(task["id"])["payload"]["contract_hash"]
    assert result["invariant"] == "NO_SCOPE_EXPANSION_BY_REVIEW"
    assert result["reported_metric_role"] == "advisory_only"
    assert before == after
    assert stored_before == stored_after


def test_follow_up_major_does_not_block_ship(graph, task) -> None:
    make_ready(graph, task)
    follow_up = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="pre_existing",
        claim="A serious pre-existing login bug",
        evidence={"kind": "reproduction", "reference": "follow-up:login"},
    )
    result = graph.ship_evaluate(task["id"])
    assert result["status"] == "SHIPPABLE"
    assert result["current_task_issue_summary"]["total"] == 0
    assert [item["id"] for item in result["follow_up_issues"]] == [follow_up["id"]]


def test_ship_after_current_blocker_fixed_keeps_follow_up_visible(graph, task) -> None:
    make_ready(graph, task)
    blocker = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="violates_acceptance",
        claim="AC1 is violated",
        evidence={"kind": "acceptance_review", "path": "src/app.py"},
        violates=f"{task['id']}-AC1",
    )
    follow_up = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="future_improvement",
        claim="Future architecture cleanup",
        evidence={"kind": "architecture_suggestion"},
    )
    blocked = graph.ship_evaluate(task["id"])
    assert blocked["status"] == "BLOCKED"
    graph.issue_update(blocker["id"], "fixed", "patch-1", _trust_tier=USER_APPROVED)
    shipped = graph.ship_evaluate(task["id"])
    assert shipped["status"] == "SHIPPABLE"
    assert shipped["current_task_issue_summary"]["total"] == 0
    assert follow_up["id"] in {item["id"] for item in shipped["follow_up_issues"]}


def test_handoff_is_read_only_and_contains_review_contract(graph, task) -> None:
    issue = graph.issue_report(
        task_id=task["id"],
        severity="major",
        relation_to_task="unrelated",
        claim="Unrelated review finding",
        evidence={"kind": "review_observation"},
    )
    before = graph.store.get_task(task["id"])
    event_count = len(graph.paths.events.read_text(encoding="utf-8").splitlines())
    pack = graph.handoff(task["id"])
    after = graph.store.get_task(task["id"])
    assert pack["state_mutated"] is False
    assert pack["review_instruction"] == "Review the task, not the entire project."
    assert "Review the task, not the entire project." in pack["markdown"]
    assert any(item["id"] == issue["id"] for item in pack["known_issues"])
    assert before == after
    assert (
        len(graph.paths.events.read_text(encoding="utf-8").splitlines()) == event_count
    )


def test_legacy_database_migrates_and_defaults_findings_to_follow_up(
    tmp_path,
) -> None:
    """A schema-1 database must open, keep its issues, and never block by default."""
    database = tmp_path / "legacy.db"
    events = tmp_path / "legacy.jsonl"
    legacy_schema = SCHEMA.replace(
        "    relation_to_task TEXT NOT NULL DEFAULT 'unrelated',\n", ""
    ).replace("    evidence_sufficient INTEGER NOT NULL DEFAULT 0,\n", "")
    assert "relation_to_task" not in legacy_schema
    with sqlite3.connect(database) as connection:
        connection.executescript(legacy_schema)
        connection.execute("INSERT INTO meta(key, value) VALUES('schema_version', '1')")
        connection.execute("INSERT INTO meta(key, value) VALUES('graph_revision', '0')")
        connection.execute(
            """INSERT INTO tasks(id,intent,status,risk,context_budget,review_budget,
            fix_budget,baseline_git_rev,graph_rev,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "T-0001",
                "legacy task",
                "open",
                "medium",
                12000,
                2,
                2,
                "rev",
                0,
                "t",
                "t",
            ),
        )
        connection.execute(
            """INSERT INTO issues(id,task_id,severity,claim,evidence_json,affected_json,
            status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("I-0001", "T-0001", "blocker", "legacy", "{}", "[]", "open", "t", "t"),
        )

    store = Store(database, events)
    store.initialize()
    with store.connect() as connection:
        version = connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()["value"]
    assert version == "2"

    issue = store.get_issue("I-0001")
    assert issue["relation_to_task"] == "unrelated"
    assert issue["evidence_sufficient"] is False
    assert issue["blocks_current_task"] is False


def test_legacy_portable_issue_without_relation_is_follow_up(graph, task) -> None:
    graph.store.merge_portable(
        {
            "tasks": [
                {
                    **graph.store.get_task(task["id"]),
                    "issues": [
                        {
                            "id": "I-9001",
                            "task_id": task["id"],
                            "severity": "blocker",
                            "claim": "Imported from an older PSG state",
                            "status": "open",
                            "created_at": "t",
                            "updated_at": "t",
                        }
                    ],
                }
            ]
        }
    )
    imported = graph.store.get_issue("I-9001")
    assert imported["relation_to_task"] == "unrelated"
    assert imported["blocks_current_task"] is False


def test_imported_task_budget_is_clamped_in_the_contract(graph, task) -> None:
    """An older state may carry wider budgets than this runtime will honour."""
    graph.store.update_task(task["id"], review_budget=9, fix_budget=9)
    payload = graph.store.get_task(task["id"])["payload"]
    payload.pop("completion_boundary", None)
    graph.store.update_task(task["id"], payload_json=payload)

    contract = graph.task_contract(task["id"])
    assert contract["completion_boundary"]["review_budget"] == MAX_REVIEW_ROUNDS
    assert contract["completion_boundary"]["fix_budget"] == MAX_FIX_CYCLES

    evaluated = graph.ship_evaluate(task["id"])
    assert evaluated["review_budget"] == MAX_REVIEW_ROUNDS
    assert evaluated["fix_budget"] == MAX_FIX_CYCLES


def test_handoff_ignores_psg_managed_state_changes(graph, task) -> None:
    """PSG rewrites its own portable state constantly; that is not a reviewable change."""
    (graph.root / "src" / "app.py").write_text(
        "def feature(value: int) -> int:\n    return value\n", encoding="utf-8"
    )
    graph._persist()
    pack = graph.handoff(task["id"])
    changed = {item["path"] for item in pack["changed"]}
    assert "src/app.py" in changed
    assert not any(path.startswith((".psg/state/", ".psg/local/")) for path in changed)


def open_unscoped_task(graph) -> dict:
    """A task stated only as intent: exactly what an agent relays from a user."""
    return graph.task_open(
        intent="Update the feature helper in app",
        acceptance_criteria=["Feature behavior is verified"],
        risk="medium",
    )


def test_task_opens_as_a_draft_holding_no_write_authority(graph) -> None:
    payload = graph.store.get_task(open_unscoped_task(graph)["id"])["payload"]
    assert payload["contract_state"] == "draft"
    assert payload["authorized_write"] == []
    # A hash before the authority exists would protect nothing.
    assert "contract_hash" not in payload


def test_draft_contract_blocks_changes_until_localization_seals_it(graph) -> None:
    opened = open_unscoped_task(graph)
    (graph.root / "src" / "app.py").write_text(
        "def feature(value: int) -> int:\n    return value\n", encoding="utf-8"
    )
    result = graph.patch_validate(opened["id"])
    assert result["allowed"] is False
    assert any(item["kind"] == "unsealed_contract" for item in result["violations"])


def test_localization_derived_write_authority_is_sealed_into_the_hash(graph) -> None:
    """The router grants write scope task_open never stated; the hash must cover it."""
    opened = open_unscoped_task(graph)
    task_id = opened["id"]
    requested = graph.store.get_task(task_id)["payload"]["write"]
    assert requested == []

    seal = graph.context_build(task_id)["task_contract_seal"]
    assert seal["sealed_now"] is True

    payload = graph.store.get_task(task_id)["payload"]
    assert payload["contract_state"] == "sealed"
    # Localization really did manufacture authority out of a bare intent.
    assert payload["authorized_write"]
    assert payload["authorized_write"] != requested
    # And that authority is what the hash commits to.
    assert payload["contract_hash"] == contract_hash(graph.store.get_task(task_id))
    contract = graph.task_contract(task_id)
    assert contract["mutation_boundary"]["write"] == payload["authorized_write"]
    assert contract["requested_mutation_boundary"]["write"] == []


def test_contract_hash_changes_when_write_authority_changes(graph, task) -> None:
    """Hashing only the request would let authority drift invisibly."""
    stored = graph.store.get_task(task["id"])
    original = stored["payload"]["contract_hash"]
    stored["payload"]["authorized_write"] = [
        *stored["payload"]["authorized_write"],
        "src/backend.py",
    ]
    assert contract_hash(stored) != original


def test_context_expansion_widens_reading_never_writing(graph, task) -> None:
    """More context is not more authority."""
    task_id = task["id"]
    before = graph.store.get_task(task_id)["payload"]
    authority_before = list(before["authorized_write"])
    hash_before = before["contract_hash"]

    expanded = graph.context_expand(task_id, "needs the backend contract to reason")

    after = graph.store.get_task(task_id)["payload"]
    assert after["authorized_write"] == authority_before
    assert after["contract_hash"] == hash_before
    assert expanded["working_set"]["write"] == authority_before


def test_file_discovered_after_seal_never_gains_write_authority(graph) -> None:
    """Re-routing an intent-localized task must not enlarge its write authority."""
    task_id = open_unscoped_task(graph)["id"]
    graph.context_build(task_id)
    authority_before = list(
        graph.store.get_task(task_id)["payload"]["authorized_write"]
    )
    hash_before = graph.store.get_task(task_id)["payload"]["contract_hash"]

    # A new file the intent fallback would match and route straight into write.
    (graph.root / "src" / "app_feature_helper.py").write_text(
        "def feature_helper(value: int) -> int:\n    return value\n",
        encoding="utf-8",
    )
    graph.index(force=True)
    rebuilt = graph.context_build(task_id)

    payload = graph.store.get_task(task_id)["payload"]
    assert payload["authorized_write"] == authority_before
    assert "src/app_feature_helper.py" not in payload["authorized_write"]
    assert rebuilt["working_set"]["write"] == authority_before
    assert payload["contract_hash"] == hash_before
    # The new file is still reachable - as context, not as authority.
    assert "src/app_feature_helper.py" in rebuilt["working_set"]["read"]


def test_narrow_declared_scope_seals_without_asking_for_approval(graph, task) -> None:
    payload = graph.store.get_task(task["id"])["payload"]
    assert payload["authorized_write"] == ["src/app.py"]
    assert payload["requires_scope_approval"] is False


def test_broad_agent_derived_scope_needs_user_approval_before_ship(graph) -> None:
    opened = open_unscoped_task(graph)
    task_id = opened["id"]
    graph.context_build(task_id)
    payload = graph.store.get_task(task_id)["payload"]
    assert payload["requires_scope_approval"] is True
    assert payload["scope_approval_reasons"]

    make_ready(graph, {"id": task_id})
    blocked = graph.ship_evaluate(task_id)
    assert blocked["status"] == "BLOCKED"
    assert blocked["scope_approved"] is False

    graph.task_scope_approve(task_id, reason="Reviewed the derived boundary")
    assert graph.ship_evaluate(task_id)["status"] == "SHIPPABLE"


def test_scope_approval_does_not_survive_a_different_authority(graph) -> None:
    task_id = open_unscoped_task(graph)["id"]
    graph.context_build(task_id)
    graph.task_scope_approve(task_id, reason="Reviewed the derived boundary")
    stored = graph.store.get_task(task_id)
    payload = stored["payload"]
    # Someone widens the sealed authority after the approval was given.
    payload["authorized_write"] = [*payload["authorized_write"], "src/extra.py"]
    payload["contract_hash"] = contract_hash(stored)
    graph.store.update_task(task_id, payload_json=payload)

    make_ready(graph, {"id": task_id})
    assert graph.ship_evaluate(task_id)["scope_approved"] is False


def test_legacy_task_without_contract_state_keeps_its_working_set_authority(
    graph, task
) -> None:
    """A task opened before sealing existed must not be stranded without authority."""
    task_id = task["id"]
    payload = graph.store.get_task(task_id)["payload"]
    for key in (
        "contract_state",
        "authorized_write",
        "authorized_read_only",
        "authorized_forbidden",
        "requires_scope_approval",
    ):
        payload.pop(key, None)
    graph.store.update_task(task_id, payload_json=payload)

    (graph.root / "src" / "app.py").write_text(
        "from src.backend import locked_api\n\n\ndef feature(value: int) -> int:\n"
        "    return locked_api(value) + 2\n",
        encoding="utf-8",
    )
    result = graph.patch_validate(task_id)
    assert not any(item["kind"] == "unsealed_contract" for item in result["violations"])
    assert result["allowed"] is True


def test_handoff_defaults_to_ignored_local_state(graph, task, capsys) -> None:
    result = main(["--root", str(graph.root), "handoff", task["id"]])
    captured = capsys.readouterr()
    assert result == 0

    written = graph.paths.handoff_dir / f"{task['id']}.md"
    assert written.is_file()
    assert "Review the task, not the entire project." in written.read_text(
        encoding="utf-8"
    )
    assert "Review pack:" in captured.out
    assert "Warning" not in captured.out


def test_default_handoff_never_changes_the_ship_gate(graph, task) -> None:
    """The review pack must not become a project change that blocks its own ship."""
    task_id = task["id"]
    (graph.root / "src" / "app.py").write_text(
        "from src.backend import locked_api\n\n\ndef feature(value: int) -> int:\n"
        "    return locked_api(value) + 2\n",
        encoding="utf-8",
    )
    make_ready(graph, {"id": task_id})
    before = graph.ship_evaluate(task_id)
    assert before["status"] == "SHIPPABLE"

    assert main(["--root", str(graph.root), "handoff", task_id]) == 0

    validated = graph.patch_validate(task_id)
    assert validated["allowed"] is True
    assert not any(
        "handoff" in node or "PSG_REVIEW" in node for node in validated["touched_nodes"]
    )
    assert graph.ship_evaluate(task_id)["status"] == before["status"]


def test_handoff_written_into_the_worktree_warns(graph, task, capsys) -> None:
    result = main(
        [
            "--root",
            str(graph.root),
            "handoff",
            task["id"],
            "--output",
            str(graph.root / "PSG_REVIEW.md"),
        ]
    )
    captured = capsys.readouterr()
    assert result == 0
    assert "Warning" in captured.out
    assert "worktree" in captured.out
