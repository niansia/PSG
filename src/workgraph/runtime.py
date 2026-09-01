from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import git
from .config import ProjectPaths, discover_root, initialize_config, load_yaml
from .convergence import ConvergenceEngine
from .indexer import Indexer
from .policy import VALID_POLICIES, PolicyEngine
from .router import ContextRouter
from .store import Store
from .verification import VerificationEngine, report_failed_checks

VALID_NODE_TYPES = {
    "Requirement",
    "Decision",
    "Constraint",
    "File",
    "Symbol",
    "Test",
    "Issue",
    "Task",
    "Snapshot",
}
VALID_EDGE_TYPES = {
    "depends-on",
    "constrained-by",
    "verified-by",
    "introduced-by",
    "resolved-by",
    "locks",
    "contains",
    "consumed-by",
}
VALID_SEVERITIES = {"blocker", "major", "minor", "optional", "speculative"}


class WorkGraph:
    def __init__(self, root: str | Path | None = None):
        requested = Path(root or os.environ.get("WORKGRAPH_PROJECT_ROOT", Path.cwd()))
        self.root = discover_root(requested)
        self.paths = ProjectPaths(self.root)
        if not self.paths.config.exists():
            raise FileNotFoundError(
                f"WorkGraph is not initialized in {self.root}. Run 'workgraph init'."
            )
        self.config = load_yaml(self.paths.config)
        self.policies = load_yaml(self.paths.policies)
        self.store = Store(self.paths.database, self.paths.events)
        self.store.initialize()
        self.indexer = Indexer(self.root, self.store, self.config)
        self.policy = PolicyEngine(self.root, self.store, self.config, self.policies)
        self.router = ContextRouter(
            self.root, self.store, self.indexer, self.policy, self.config
        )
        self.verifier = VerificationEngine(self.root, self.store)
        self.convergence = ConvergenceEngine(self.store, self.config)

    @classmethod
    def initialize(
        cls, root: str | Path | None = None, project: str | None = None
    ) -> WorkGraph:
        selected = Path(root or Path.cwd()).resolve()
        if not git.is_repository(selected):
            raise git.GitError(
                "WorkGraph requires a Git repository. Run 'git init' first."
            )
        paths = initialize_config(selected, project)
        store = Store(paths.database, paths.events)
        store.initialize()
        store.event(
            "project.initialized",
            {
                "project": project or selected.name,
                "root": str(selected),
                "git_revision": git.revision(selected),
            },
        )
        return cls(selected)

    def status(self) -> dict[str, Any]:
        tasks = self.store.list_tasks()
        active = [task for task in tasks if task["status"] in {"open", "blocked"}]
        return {
            "project": self.config.get("project", self.root.name),
            "root": str(self.root),
            "git_revision": git.revision(self.root),
            "git_branch": git.branch(self.root),
            "graph_revision": self.store.graph_revision(),
            "active_tasks": [
                {"id": task["id"], "intent": task["intent"], "status": task["status"]}
                for task in active
            ],
            "node_count": len(self.store.list_nodes()),
            "snapshot_count": len(self.store.list_snapshots()),
        }

    def doctor(self) -> dict[str, Any]:
        problems: list[str] = []
        if not git.is_repository(self.root):
            problems.append("not_a_git_repository")
        if self.config.get("version") != 1:
            problems.append("unsupported_config_version")
        policies = [node["policy"] for node in self.store.list_nodes()]
        invalid = sorted(set(policies) - VALID_POLICIES)
        if invalid:
            problems.append(f"invalid_node_policies:{','.join(invalid)}")
        event_lines = 0
        if self.paths.events.exists():
            with self.paths.events.open(encoding="utf-8") as stream:
                event_lines = sum(1 for _ in stream)
        return {
            "healthy": not problems,
            "problems": problems,
            "database": str(self.paths.database),
            "event_log": str(self.paths.events),
            "event_count": event_lines,
            "git_revision": git.revision(self.root),
            "graph_revision": self.store.graph_revision(),
        }

    def index(self, force: bool = False) -> dict[str, Any]:
        return self.indexer.index(force=force).as_dict()

    def node_create(
        self,
        *,
        node_id: str,
        node_type: str,
        title: str,
        payload: dict[str, Any],
        policy: str = "mutable",
        maturity: str = "accepted",
        provenance: list[str] | None = None,
    ) -> dict[str, Any]:
        if node_type not in VALID_NODE_TYPES:
            raise ValueError(f"Unsupported node type: {node_type}")
        if policy not in VALID_POLICIES:
            raise ValueError(f"Unsupported policy: {policy}")
        node = {
            "id": node_id,
            "type": node_type,
            "title": title,
            "status": "active",
            "maturity": maturity,
            "policy": policy,
            "source": {"kind": "user_explicit"},
            "revision": git.revision(self.root),
            "confidence": 1.0,
            "provenance": provenance or ["user_explicit"],
            "payload": payload,
        }
        self.store.upsert_node(node)
        self.store.event("node.created", {"node_id": node_id, "node_type": node_type})
        return self.store.get_node(node_id) or node

    def node_get(self, ids: list[str]) -> dict[str, Any]:
        nodes = [node for node_id in ids if (node := self.store.get_node(node_id))]
        return {
            "nodes": nodes,
            "edges": self.store.edges_for([node["id"] for node in nodes]),
        }

    def edge_create(
        self,
        src: str,
        edge_type: str,
        dst: str,
        confidence: float = 1.0,
        provenance: str = "user_explicit",
    ) -> dict[str, Any]:
        if edge_type not in VALID_EDGE_TYPES:
            raise ValueError(f"Unsupported edge type: {edge_type}")
        if not self.store.get_node(src) or not self.store.get_node(dst):
            raise KeyError("Both edge endpoints must exist")
        edge = {
            "src": src,
            "type": edge_type,
            "dst": dst,
            "confidence": confidence,
            "provenance": provenance,
            "revision": git.revision(self.root),
        }
        self.store.upsert_edge(edge)
        self.store.event("edge.created", edge)
        return edge

    def decision_record(
        self,
        *,
        decision_id: str,
        statement: str,
        rationale: list[str],
        alternatives_rejected: list[str] | None = None,
        scope: list[str] | None = None,
        mutation_effect: str | None = None,
    ) -> dict[str, Any]:
        return self.node_create(
            node_id=decision_id,
            node_type="Decision",
            title=statement,
            payload={
                "statement": statement,
                "rationale": rationale,
                "alternatives_rejected": alternatives_rejected or [],
                "scope": scope or [],
                "mutation_effect": mutation_effect,
            },
            maturity="accepted",
            provenance=["user_explicit", "documented_decision"],
        )

    def node_policy_set(
        self,
        node_id: str,
        policy: str,
        reason: str,
        override: bool = False,
        decision_id: str | None = None,
    ) -> dict[str, Any]:
        if policy not in VALID_POLICIES:
            raise ValueError(f"Unsupported policy: {policy}")
        node = self.store.get_node(node_id)
        if not node:
            raise KeyError(f"Unknown node: {node_id}")
        if node["policy"] == "frozen" and policy != "frozen":
            decision = self.store.get_node(decision_id) if decision_id else None
            if not override or not decision or decision["type"] != "Decision":
                raise PermissionError(
                    "Unfreezing requires an explicit override and an existing Decision node."
                )
        maturity = "frozen" if policy == "frozen" else node["maturity"]
        self.store.set_policy(node_id, policy, maturity)
        self.store.event(
            "policy.override" if override else "policy.changed",
            {
                "node_id": node_id,
                "policy": policy,
                "reason": reason,
                "decision_id": decision_id,
            },
        )
        return self.store.get_node(node_id) or node

    def task_open(
        self,
        *,
        intent: str,
        acceptance_criteria: list[str],
        constraints: list[str] | None = None,
        targets: list[str] | None = None,
        write: list[str] | None = None,
        read_only: list[str] | None = None,
        forbidden: list[str] | None = None,
        non_goals: list[str] | None = None,
        risk: str = "medium",
        context_budget: int | None = None,
        review_budget: int | None = None,
        fix_budget: int | None = None,
    ) -> dict[str, Any]:
        if risk not in {"low", "medium", "high"}:
            raise ValueError("Risk must be low, medium, or high")
        task_id = self.store.next_id("tasks", "T")
        review = self.config.get("review", {})
        task = {
            "id": task_id,
            "intent": intent.strip(),
            "status": "open",
            "risk": risk,
            "context_budget": context_budget
            if context_budget is not None
            else int(self.config.get("context", {}).get("default_token_budget", 12000)),
            "review_budget": review_budget
            if review_budget is not None
            else int(review.get("general_round_limit", 2)),
            "fix_budget": fix_budget
            if fix_budget is not None
            else int(review.get("targeted_fix_limit", 2)),
            "baseline_git_rev": git.revision(self.root),
            "graph_rev": self.store.graph_revision(),
            "payload": {
                "constraints": constraints or [],
                "targets": targets or [],
                "write": [str(item).replace("\\", "/") for item in (write or [])],
                "read_only": [
                    str(item).replace("\\", "/") for item in (read_only or [])
                ],
                "forbidden": [
                    str(item).replace("\\", "/") for item in (forbidden or [])
                ],
                "non_goals": non_goals or [],
            },
        }
        criteria = [
            {
                "id": f"{task_id}-AC{index}",
                "text": text,
                "mandatory": True,
                "status": "pending",
            }
            for index, text in enumerate(acceptance_criteria, 1)
        ]
        self.store.create_task(task, criteria)
        snapshot = self.snapshot_create(
            task_id=task_id,
            stable=False,
            summary={"kind": "baseline", "intent": intent},
        )
        self.store.update_task(task_id, baseline_snapshot=snapshot["id"])
        return self.store.get_task(task_id) or task

    def context_build(
        self, task_id: str, max_tokens: int | None = None
    ) -> dict[str, Any]:
        return self.router.build(task_id, max_tokens=max_tokens)

    def context_expand(self, task_id: str, reason: str) -> dict[str, Any]:
        return self.router.expand(task_id, reason)

    def patch_validate(
        self,
        task_id: str,
        diff_text: str | None = None,
        *,
        staged: bool = False,
        phase: str = "postflight",
    ) -> dict[str, Any]:
        selected = (
            diff_text if diff_text is not None else git.diff(self.root, staged=staged)
        )
        result = self.policy.validate(task_id, selected, phase=phase)
        self.verifier.record(
            task_id,
            name="policy:mutation-boundary",
            result="pass" if result["allowed"] else "fail",
            kind="policy",
            required=True,
            evidence={
                "violations": result["violations"],
                "touched_nodes": result["touched_nodes"],
                "phase": phase,
            },
        )
        return result

    def verification_record(self, **kwargs: Any) -> dict[str, Any]:
        return self.verifier.record(**kwargs)

    def verify(
        self, task_id: str, checks: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        selected = (
            checks
            if checks is not None
            else list(self.config.get("verification", {}).get("commands", []))
        )
        results = self.verifier.run(task_id, selected)
        issues = report_failed_checks(results, self.issue_report)
        return {"task_id": task_id, "results": results, "issues_created": issues}

    def criterion_set(
        self,
        task_id: str,
        criterion_id: str,
        status: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"pending", "pass", "fail", "waived"}:
            raise ValueError("Criterion status must be pending, pass, fail, or waived")
        recorded_evidence = dict(evidence or {})
        recorded_evidence.setdefault(
            "worktree_fingerprint", git.worktree_fingerprint(self.root)
        )
        self.store.set_criterion(task_id, criterion_id, status, recorded_evidence)
        return self.store.get_task(task_id) or {}

    def issue_report(
        self,
        *,
        task_id: str,
        severity: str,
        claim: str,
        evidence: dict[str, Any] | None,
        affected_nodes: list[str] | None = None,
        violates: str | None = None,
        introduced_by_patch: str | None = None,
    ) -> dict[str, Any]:
        normalized = severity.lower()
        if normalized not in VALID_SEVERITIES:
            raise ValueError(f"Unsupported severity: {severity}")
        provided = evidence or {}
        if normalized in {"blocker", "major"} and not provided:
            provided = {"kind": "unsupported_claim", "requested_severity": normalized}
            normalized = "speculative"
        issue = {
            "id": self.store.next_id("issues", "I"),
            "task_id": task_id,
            "severity": normalized,
            "claim": claim,
            "evidence": provided,
            "affected_nodes": affected_nodes or [],
            "violates": violates,
            "introduced_by_patch": introduced_by_patch,
            "status": "open",
        }
        self.store.create_issue(issue)
        return issue

    def issue_update(
        self, issue_id: str, status: str, resolved_by_patch: str | None = None
    ) -> dict[str, Any]:
        if status not in {"open", "fixed", "deferred", "rejected"}:
            raise ValueError("Issue status must be open, fixed, deferred, or rejected")
        self.store.update_issue(issue_id, status, resolved_by_patch)
        return {
            "issue_id": issue_id,
            "status": status,
            "resolved_by_patch": resolved_by_patch,
        }

    def review_record(self, task_id: str, new_blocking_issues: int) -> dict[str, Any]:
        return self.convergence.review_record(task_id, new_blocking_issues)

    def fix_record(
        self, task_id: str, introduced: int, resolved: int
    ) -> dict[str, Any]:
        return self.convergence.fix_record(task_id, introduced, resolved)

    def ship_evaluate(self, task_id: str) -> dict[str, Any]:
        final_policy = self.patch_validate(task_id, phase="ship_gate")
        self.indexer.index(force=False)
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        working_paths = set()
        for values in task["payload"].get("working_set", {}).values():
            if isinstance(values, list):
                working_paths.update(values)
        nodes = self.store.find_nodes_for_paths(working_paths)
        graph_synchronized = all(self.indexer.freshness(node) == 1.0 for node in nodes)
        self.store.update_task(task_id, graph_rev=self.store.graph_revision())
        result = self.convergence.evaluate(
            task_id,
            graph_synchronized=graph_synchronized,
            worktree_fingerprint=git.worktree_fingerprint(self.root),
        )
        result["final_policy_validation"] = final_policy
        if result["status"] == "SHIPPABLE":
            snapshot = self.snapshot_create(
                task_id=task_id, stable=True, summary={"ship_gate": result}
            )
            result["stable_snapshot"] = snapshot["id"]
        return result

    def snapshot_create(
        self,
        task_id: str | None = None,
        stable: bool = False,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        snapshot = {
            "id": self.store.next_id("snapshots", "S"),
            "git_rev": git.revision(self.root),
            "graph_rev": self.store.graph_revision(),
            "task_id": task_id,
            "state": self.store.export_state(),
            "summary": summary or {},
            "stable": stable,
        }
        self.store.create_snapshot(snapshot)
        return {key: value for key, value in snapshot.items() if key != "state"}

    def snapshot_restore(
        self, snapshot_id: str, *, allow_revision_mismatch: bool = False
    ) -> dict[str, Any]:
        snapshot = self.store.get_snapshot(snapshot_id)
        if not snapshot:
            raise KeyError(f"Unknown snapshot: {snapshot_id}")
        current = git.revision(self.root)
        if current != snapshot["git_rev"] and not allow_revision_mismatch:
            raise RuntimeError(
                "Snapshot Git revision does not match the current repository. Use an explicit override to restore graph state only."
            )
        safety = self.snapshot_create(
            stable=False, summary={"kind": "pre_restore_safety", "target": snapshot_id}
        )
        self.store.restore_state(snapshot["state"])
        self.store.event(
            "snapshot.restored",
            {
                "snapshot_id": snapshot_id,
                "safety_snapshot": safety["id"],
                "git_revision_unchanged": current,
            },
        )
        return {
            "restored": snapshot_id,
            "safety_snapshot": safety["id"],
            "git_revision": current,
            "source_code_changed": False,
        }
