from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .runtime import PSG
from .util import pretty_json


def _json(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    return json.loads(value)


def _checks(values: list[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for value in values:
        if "=" not in value:
            raise ValueError("Checks must use NAME=COMMAND")
        name, command = value.split("=", 1)
        checks.append(
            {"name": name.strip(), "command": command.strip(), "required": True}
        )
    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="psg", description="Graph-guided project state and ship governance"
    )
    parser.add_argument(
        "--root", type=Path, help="Repository root (defaults to the current project)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize PSG in a Git repository")
    init.add_argument("--project")

    sub.add_parser("status", help="Show project and task status")
    sub.add_parser("on", help="Enable automatic PSG governance")
    sub.add_parser("off", help="Disable automatic PSG governance")
    sub.add_parser("guardrails", help="Show authority, dependencies, and guardrails")
    state = sub.add_parser("state", help="Synchronize portable project state")
    state.add_argument("action", choices=["sync"])
    index = sub.add_parser(
        "index", help="Incrementally index repository files and Python symbols"
    )
    index.add_argument("--force", action="store_true")
    sub.add_parser("doctor", help="Check runtime, database, config, and Git health")

    node = sub.add_parser("node", help="Create, read, list, or govern nodes")
    node_sub = node.add_subparsers(dest="node_command", required=True)
    node_add = node_sub.add_parser("add")
    node_add.add_argument("id")
    node_add.add_argument("type")
    node_add.add_argument("title")
    node_add.add_argument("--payload", default="{}")
    node_add.add_argument("--policy", default="mutable")
    node_add.add_argument("--maturity", default="accepted")
    node_get = node_sub.add_parser("get")
    node_get.add_argument("ids", nargs="+")
    node_list = node_sub.add_parser("list")
    node_list.add_argument("--type")
    node_policy = node_sub.add_parser("policy")
    node_policy.add_argument("id")
    node_policy.add_argument("policy")
    node_policy.add_argument("--reason", required=True)
    node_policy.add_argument("--override", action="store_true")
    node_policy.add_argument("--decision")

    edge = sub.add_parser("edge", help="Create graph relationships")
    edge_sub = edge.add_subparsers(dest="edge_command", required=True)
    edge_add = edge_sub.add_parser("add")
    edge_add.add_argument("src")
    edge_add.add_argument("type")
    edge_add.add_argument("dst")
    edge_add.add_argument("--confidence", type=float, default=1.0)

    decision = sub.add_parser("decision", help="Record an engineering decision")
    decision_sub = decision.add_subparsers(dest="decision_command", required=True)
    decision_record = decision_sub.add_parser("record")
    decision_record.add_argument("id")
    decision_record.add_argument("statement")
    decision_record.add_argument("--rationale", action="append", required=True)
    decision_record.add_argument("--rejected", action="append", default=[])
    decision_record.add_argument("--scope", action="append", default=[])
    decision_record.add_argument("--mutation-effect")

    task = sub.add_parser("task", help="Open and manage tasks")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_open = task_sub.add_parser("open")
    task_open.add_argument("intent")
    task_open.add_argument("--ac", action="append", default=[])
    task_open.add_argument("--constraint", action="append", default=[])
    task_open.add_argument("--target", action="append", default=[])
    task_open.add_argument("--write", action="append", default=[])
    task_open.add_argument("--read-only", action="append", default=[])
    task_open.add_argument("--forbid", action="append", default=[])
    task_open.add_argument("--non-goal", action="append", default=[])
    task_open.add_argument(
        "--risk", choices=["low", "medium", "high"], default="medium"
    )
    task_open.add_argument("--context-budget", type=int)
    task_open.add_argument("--review-budget", type=int)
    task_open.add_argument("--fix-budget", type=int)
    task_open.add_argument("--builder-actor")
    task_open.add_argument("--dependency-justification", action="append", default=[])
    task_sub.add_parser("list")
    task_show = task_sub.add_parser("show")
    task_show.add_argument("id")
    criterion = task_sub.add_parser("criterion")
    criterion.add_argument("task_id")
    criterion.add_argument("criterion_id")
    criterion.add_argument("status", choices=["pending", "pass", "fail", "waived"])
    criterion.add_argument("--evidence", default="{}")

    context = sub.add_parser(
        "context", help="Build or expand minimum sufficient context"
    )
    context_sub = context.add_subparsers(dest="context_command", required=True)
    context_build = context_sub.add_parser("build")
    context_build.add_argument("task_id")
    context_build.add_argument("--max-tokens", type=int)
    context_expand = context_sub.add_parser("expand")
    context_expand.add_argument("task_id")
    context_expand.add_argument("--reason", required=True)

    validate = sub.add_parser(
        "validate", help="Validate the actual Git diff against task scope"
    )
    validate.add_argument("task_id")
    validate.add_argument("--diff-file", type=Path)
    validate.add_argument(
        "--phase", choices=["preflight", "postflight"], default="postflight"
    )

    verify = sub.add_parser(
        "verify", help="Run configured or explicit deterministic checks"
    )
    verify.add_argument("task_id")
    verify.add_argument("--check", action="append", default=[])

    record = sub.add_parser(
        "verification", help="Record externally executed verification evidence"
    )
    record.add_argument("task_id")
    record.add_argument("name")
    record.add_argument("result", choices=["pass", "fail", "error", "skipped"])
    record.add_argument("--kind", default="test")
    record.add_argument("--command")
    record.add_argument("--evidence", default="{}")
    record.add_argument("--optional", action="store_true")
    record.add_argument(
        "--source",
        choices=["external_tool", "llm_reported", "user_asserted", "reviewer"],
        default="llm_reported",
    )

    issue = sub.add_parser("issue", help="Report and update evidence-backed issues")
    issue_sub = issue.add_subparsers(dest="issue_command", required=True)
    issue_report = issue_sub.add_parser("report")
    issue_report.add_argument("task_id")
    issue_report.add_argument("severity")
    issue_report.add_argument("claim")
    issue_report.add_argument("--evidence", default="{}")
    issue_report.add_argument("--affected", action="append", default=[])
    issue_report.add_argument("--violates")
    issue_report.add_argument("--debt")
    issue_update = issue_sub.add_parser("update")
    issue_update.add_argument("id")
    issue_update.add_argument(
        "status", choices=["open", "fixed", "deferred", "rejected"]
    )
    issue_update.add_argument("--patch")
    issue_list = issue_sub.add_parser("list")
    issue_list.add_argument("task_id")
    issue_list.add_argument("--status")

    review = sub.add_parser("review", help="Record one independent review round")
    review.add_argument("task_id")
    review.add_argument("--new-blocking", type=int, default=0)
    review.add_argument("--actor")
    review.add_argument("--session")
    review.add_argument("--model-family")
    fix = sub.add_parser("fix", help="Record one targeted correction cycle")
    fix.add_argument("task_id")
    fix.add_argument("--introduced", type=int, default=0)
    fix.add_argument("--resolved", type=int, default=0)
    ship = sub.add_parser("ship", help="Evaluate the evidence-based ship gate")
    ship.add_argument("task_id")

    debt = sub.add_parser("debt", help="Record or evaluate accepted debt")
    debt_sub = debt.add_subparsers(dest="debt_command", required=True)
    debt_add = debt_sub.add_parser("record")
    debt_add.add_argument("task_id")
    debt_add.add_argument("what")
    debt_add.add_argument("--why", required=True)
    debt_add.add_argument("--ceiling", required=True)
    debt_add.add_argument("--revisit", required=True)
    debt_add.add_argument("--affected", action="append", default=[])
    debt_review = debt_sub.add_parser("review")
    debt_review.add_argument("debt_id")
    debt_review.add_argument("--trigger-met", action="store_true")
    debt_review.add_argument("--evidence", default="{}")

    snapshot = sub.add_parser(
        "snapshot", help="Create, list, or restore graph snapshots"
    )
    snapshot_sub = snapshot.add_subparsers(dest="snapshot_command", required=True)
    snapshot_sub.add_parser("list")
    snapshot_create = snapshot_sub.add_parser("create")
    snapshot_create.add_argument("--task")
    snapshot_create.add_argument("--stable", action="store_true")
    snapshot_restore = snapshot_sub.add_parser("restore")
    snapshot_restore.add_argument("id")
    snapshot_restore.add_argument("--allow-revision-mismatch", action="store_true")
    return parser


def dispatch(args: argparse.Namespace) -> Any:
    if args.command == "init":
        return PSG.initialize(args.root, project=args.project).status()
    graph = PSG(args.root)
    if args.command == "status":
        return graph.status()
    if args.command == "on":
        return graph.set_enabled(True)
    if args.command == "off":
        return graph.set_enabled(False)
    if args.command == "guardrails":
        return graph.guardrails_get()
    if args.command == "state":
        return graph.state_sync()
    if args.command == "index":
        return graph.index(force=args.force)
    if args.command == "doctor":
        return graph.doctor()
    if args.command == "node":
        if args.node_command == "add":
            return graph.node_create(
                node_id=args.id,
                node_type=args.type,
                title=args.title,
                payload=_json(args.payload, {}),
                policy=args.policy,
                maturity=args.maturity,
            )
        if args.node_command == "get":
            return graph.node_get(args.ids)
        if args.node_command == "list":
            return graph.store.list_nodes(args.type)
        return graph.node_policy_set(
            args.id,
            args.policy,
            args.reason,
            override=args.override,
            decision_id=args.decision,
        )
    if args.command == "edge":
        return graph.edge_create(
            args.src, args.type, args.dst, confidence=args.confidence
        )
    if args.command == "decision":
        return graph.decision_record(
            decision_id=args.id,
            statement=args.statement,
            rationale=args.rationale,
            alternatives_rejected=args.rejected,
            scope=args.scope,
            mutation_effect=args.mutation_effect,
        )
    if args.command == "task":
        if args.task_command == "open":
            return graph.task_open(
                intent=args.intent,
                acceptance_criteria=args.ac,
                constraints=args.constraint,
                targets=args.target,
                write=args.write,
                read_only=args.read_only,
                forbidden=args.forbid,
                non_goals=args.non_goal,
                risk=args.risk,
                context_budget=args.context_budget,
                review_budget=args.review_budget,
                fix_budget=args.fix_budget,
                builder_actor=args.builder_actor,
                dependency_justifications=args.dependency_justification,
            )
        if args.task_command == "list":
            return graph.store.list_tasks()
        if args.task_command == "show":
            value = graph.store.get_task(args.id)
            if not value:
                raise KeyError(f"Unknown task: {args.id}")
            return value
        return graph.criterion_set(
            args.task_id, args.criterion_id, args.status, _json(args.evidence, {})
        )
    if args.command == "context":
        if args.context_command == "build":
            return graph.context_build(args.task_id, max_tokens=args.max_tokens)
        return graph.context_expand(args.task_id, args.reason)
    if args.command == "validate":
        content = args.diff_file.read_text(encoding="utf-8") if args.diff_file else None
        if content is not None:
            return graph.patch_validate_proposed(
                args.task_id, content, phase=args.phase
            )
        return graph.patch_validate(args.task_id, phase=args.phase)
    if args.command == "verify":
        return graph.verify(args.task_id, _checks(args.check) if args.check else None)
    if args.command == "verification":
        return graph.verification_record(
            task_id=args.task_id,
            name=args.name,
            result=args.result,
            kind=args.kind,
            command=args.command,
            required=not args.optional,
            source=args.source,
            evidence=_json(args.evidence, {}),
        )
    if args.command == "issue":
        if args.issue_command == "report":
            return graph.issue_report(
                task_id=args.task_id,
                severity=args.severity,
                claim=args.claim,
                evidence=_json(args.evidence, {}),
                affected_nodes=args.affected,
                violates=args.violates,
                debt_id=args.debt,
            )
        if args.issue_command == "update":
            return graph.issue_update(args.id, args.status, args.patch)
        return graph.store.list_issues(args.task_id, status=args.status)
    if args.command == "review":
        return graph.review_record(
            args.task_id,
            args.new_blocking,
            actor_id=args.actor,
            session_id=args.session,
            model_family=args.model_family,
        )
    if args.command == "fix":
        return graph.fix_record(args.task_id, args.introduced, args.resolved)
    if args.command == "ship":
        return graph.ship_evaluate(args.task_id)
    if args.command == "debt":
        if args.debt_command == "record":
            return graph.debt_record(
                task_id=args.task_id,
                what=args.what,
                why=args.why,
                ceiling=args.ceiling,
                revisit_trigger=args.revisit,
                affected_nodes=args.affected,
            )
        return graph.debt_review(
            args.debt_id,
            trigger_met=args.trigger_met,
            evidence=_json(args.evidence, {}),
        )
    if args.command == "snapshot":
        if args.snapshot_command == "list":
            return [
                {key: value for key, value in item.items() if key != "state"}
                for item in graph.store.list_snapshots()
            ]
        if args.snapshot_command == "create":
            return graph.snapshot_create(task_id=args.task, stable=args.stable)
        return graph.snapshot_restore(
            args.id, allow_revision_mismatch=args.allow_revision_mismatch
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
        print(pretty_json(result))
        return 0
    except (
        FileNotFoundError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        PermissionError,
    ) as exc:
        print(
            pretty_json({"error": type(exc).__name__, "message": str(exc)}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
