from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from . import git
from .config import (
    ProjectPaths,
    discover_root,
    initialize_config,
    load_yaml,
    save_yaml,
)
from .convergence import ConvergenceEngine
from .indexer import Indexer
from .installer import global_settings
from .policy import POLICY_RANK, VALID_POLICIES, PolicyEngine, parse_diff
from .portable import PortableState
from .router import ContextRouter
from .store import Store
from .task_contract import (
    CONTRACT_STATE_DRAFT,
    CONTRACT_STATE_SEALED,
    CONTRACT_VERSION,
    MAX_FIX_CYCLES,
    MAX_REVIEW_ROUNDS,
    RELATIONS_TO_TASK,
    contract_hash,
    default_completion_boundary,
    default_review_boundary,
    is_sealed,
    render_handoff,
    requires_scope_approval,
    task_contract,
)
from .trust import (
    APPROVAL_TRUST_TIERS,
    CLAIMED,
    EXTERNAL_ATTESTED,
    RUNTIME_ATTESTED,
    USER_APPROVED,
    OperatorApproval,
    evidence_trust,
    is_user_approved,
    require_interactive_user_approval,
    require_runtime_user_approval,
)
from .util import sha256_bytes, utc_now
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
    "Architecture",
    "Verification",
    "Debt",
    "Conflict",
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
    "requires",
    "targets",
    "affects",
    "supersedes",
    "conflicts-with",
}
VALID_SEVERITIES = {"blocker", "major", "minor", "optional", "speculative"}


class PSG:
    def __init__(self, root: str | Path | None = None):
        requested = Path(root or os.environ.get("PSG_PROJECT_ROOT", Path.cwd()))
        self.root = discover_root(requested)
        self.paths = ProjectPaths(self.root)
        if not self.paths.config.exists():
            raise FileNotFoundError(
                f"PSG is not initialized in {self.root}. Run 'psg init'."
            )
        self.config = load_yaml(self.paths.config)
        self.policies = load_yaml(self.paths.policies)
        self.store = Store(self.paths.database, self.paths.events)
        self.store.initialize()
        self.portable = PortableState(self.paths.portable_state, self.store)
        self.portable.sync_to_store()
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
    ) -> PSG:
        selected = Path(root or Path.cwd()).resolve()
        if not git.is_repository(selected):
            raise git.GitError("PSG requires a Git repository. Run 'git init' first.")
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
        instance = cls(selected)
        instance.index(force=False)
        instance._persist()
        return instance

    @classmethod
    def accept_portable_state(
        cls, root: str | Path | None, *, reason: str
    ) -> dict[str, Any]:
        selected = discover_root(Path(root or Path.cwd()))
        paths = ProjectPaths(selected)
        if not paths.config.exists():
            raise FileNotFoundError(
                f"PSG is not initialized in {selected}. Run 'psg init'."
            )
        if not reason.strip():
            raise ValueError("Accepting portable state requires an explicit reason.")
        require_interactive_user_approval(
            "Accept externally modified PSG governance state",
            {"Project": str(selected), "Reason": reason.strip()},
        )
        store = Store(paths.database, paths.events)
        store.initialize()
        return PortableState(paths.portable_state, store).accept_current(reason.strip())

    def _persist(self) -> dict[str, Any]:
        return self.portable.export_from_store()

    def state_sync(self) -> dict[str, Any]:
        imported = self.portable.sync_to_store()
        return {**imported, "path": str(self.paths.portable_state)}

    def status(self) -> dict[str, Any]:
        tasks = self.store.list_tasks()
        active = [task for task in tasks if task["status"] in {"open", "blocked"}]
        project_enabled = bool(self.config.get("enabled", True))
        global_enabled = bool(global_settings().get("enabled", True))
        return {
            "enabled": project_enabled and global_enabled,
            "project_enabled": project_enabled,
            "global_enabled": global_enabled,
            "project": self.config.get("project", self.root.name),
            "root": str(self.root),
            "git_revision": git.revision(self.root),
            "git_branch": git.branch(self.root),
            "git_clean": not bool(git.status_porcelain(self.root)),
            "graph_revision": self.store.graph_revision(),
            "active_tasks": [
                {"id": task["id"], "intent": task["intent"], "status": task["status"]}
                for task in active
            ],
            "node_count": len(self.store.list_nodes()),
            "snapshot_count": len(self.store.list_snapshots()),
            "portable_state": str(self.paths.portable_state),
            "guardrails": self.guardrails_get()["effective"],
        }

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        self.config["enabled"] = bool(enabled)
        save_yaml(self.paths.config, self.config)
        self.store.event("project.enabled" if enabled else "project.disabled", {})
        self._persist()
        return {
            "scope": "project",
            "enabled": bool(enabled),
            "project": self.config.get("project"),
        }

    def doctor(self) -> dict[str, Any]:
        problems: list[str] = []
        if not git.is_repository(self.root):
            problems.append("not_a_git_repository")
        if self.config.get("version") != 1:
            problems.append("unsupported_config_version")
        if not self.paths.portable_state.exists():
            problems.append("missing_portable_state")
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
            "portable_state": str(self.paths.portable_state),
            "project_enabled": bool(self.config.get("enabled", True)),
            "global_enabled": bool(global_settings().get("enabled", True)),
        }

    def index(self, force: bool = False) -> dict[str, Any]:
        self.portable.sync_to_store()
        result = self.indexer.index(force=force).as_dict()
        self._persist()
        return result

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
        _trust_tier: str = CLAIMED,
        _operator_approval: OperatorApproval | None = None,
    ) -> dict[str, Any]:
        if node_type not in VALID_NODE_TYPES:
            raise ValueError(f"Unsupported node type: {node_type}")
        if policy not in VALID_POLICIES:
            raise ValueError(f"Unsupported policy: {policy}")
        if self.store.get_node(node_id):
            raise PermissionError(
                f"Node already exists and cannot be overwritten through node_create: {node_id}"
            )
        require_runtime_user_approval(
            _trust_tier,
            "Create a graph node on user authority",
            {"Node": node_id, "Type": node_type, "Policy": policy},
            approval=_operator_approval,
        )
        protected = node_type in {"Decision", "Debt"}
        claimed_protected = protected and _trust_tier == CLAIMED
        recorded_payload = dict(payload)
        recorded_payload["trust_tier"] = _trust_tier
        node = {
            "id": node_id,
            "type": node_type,
            "title": title,
            "status": "proposed" if claimed_protected else "active",
            "maturity": "proposed" if claimed_protected else maturity,
            "policy": policy,
            "source": {
                "kind": "user_approved"
                if _trust_tier == USER_APPROVED
                else "agent_claim"
            },
            "revision": git.revision(self.root),
            "confidence": 1.0,
            "provenance": provenance or [_trust_tier.lower()],
            "payload": recorded_payload,
        }
        self.store.upsert_node(node)
        self.store.event("node.created", {"node_id": node_id, "node_type": node_type})
        self._persist()
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
        provenance: str = "claimed",
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
        existing = next(
            (
                item
                for item in self.store.edges_for([src], both=False)
                if item["type"] == edge_type and item["dst"] == dst
            ),
            None,
        )
        if existing and existing.get("provenance") in {
            "user_approved",
            "external_attested",
        }:
            raise PermissionError("A claimed edge cannot replace an attested edge.")
        self.store.upsert_edge(edge)
        self.store.event("edge.created", edge)
        self._persist()
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
        normalized_effect = {
            None: None,
            "freeze": "frozen",
            "frozen": "frozen",
            "read_only": "read_only",
            "interface_locked": "interface_locked",
            "mutable": "mutable",
        }.get(mutation_effect)
        if mutation_effect is not None and normalized_effect is None:
            raise ValueError(f"Unsupported decision mutation effect: {mutation_effect}")
        if normalized_effect and not scope:
            raise ValueError(
                "A decision mutation effect requires at least one scope node."
            )
        decision = self.node_create(
            node_id=decision_id,
            node_type="Decision",
            title=statement,
            payload={
                "statement": statement,
                "rationale": rationale,
                "alternatives_rejected": alternatives_rejected or [],
                "scope": scope or [],
                "mutation_effect": normalized_effect,
                "applied_effects": [],
                "approval_required": True,
            },
            maturity="proposed",
            provenance=["claimed", "proposed_decision"],
        )
        decision["applied_effects"] = []
        decision["approval_required"] = True
        return decision

    def decision_approve(self, decision_id: str) -> dict[str, Any]:
        decision = self.store.get_node(decision_id)
        if not decision or decision["type"] != "Decision":
            raise KeyError(f"Unknown decision: {decision_id}")
        scope = list(decision["payload"].get("scope", []))
        resolved_scope: list[tuple[str, dict[str, Any]]] = []
        if scope:
            self.indexer.index(force=False)
            for value in scope:
                normalized = str(value).replace("\\", "/")
                target_id = (
                    normalized
                    if self.store.get_node(normalized)
                    else f"file:{normalized}"
                )
                target = self.store.get_node(target_id)
                if not target:
                    raise KeyError(
                        f"Decision scope does not resolve to a graph node: {value}"
                    )
                resolved_scope.append((target_id, target))
        operator_approval = require_interactive_user_approval(
            "Approve a Decision and apply its mutation effect",
            {
                "Decision": decision_id,
                "Statement": decision.get("title", "(unknown)"),
                "Scope": scope,
            },
        )
        decision["status"] = "accepted"
        decision["maturity"] = "accepted"
        decision["source"] = {"kind": "user_approved"}
        decision["confidence"] = 1.0
        decision["provenance"] = ["user_approved", "documented_decision"]
        decision["payload"]["trust_tier"] = USER_APPROVED
        self.store.upsert_node(decision)
        applied: list[dict[str, str]] = []
        normalized_effect = decision["payload"].get("mutation_effect")
        if resolved_scope:
            for target_id, target in resolved_scope:
                if normalized_effect == "mutable":
                    self.node_policy_set(
                        target_id,
                        "mutable",
                        f"Superseded by {decision_id}",
                        override=True,
                        decision_id=decision_id,
                        _trust_tier=USER_APPROVED,
                        _operator_approval=operator_approval,
                    )
                elif normalized_effect:
                    self.store.set_policy(
                        target_id,
                        normalized_effect,
                        "frozen"
                        if normalized_effect == "frozen"
                        else target["maturity"],
                    )
                edge_type = (
                    "locks" if normalized_effect == "frozen" else "constrained-by"
                )
                edge = {
                    "src": decision_id,
                    "type": edge_type,
                    "dst": target_id,
                    "confidence": 1.0,
                    "provenance": "user_approved",
                    "revision": git.revision(self.root),
                }
                self.store.upsert_edge(edge)
                applied.append(
                    {"target": target_id, "policy": normalized_effect or "unchanged"}
                )
        decision["payload"]["applied_effects"] = applied
        decision["payload"]["approval_required"] = False
        self.store.upsert_node(decision)
        self._persist()
        decision["applied_effects"] = applied
        decision["approval_required"] = False
        return decision

    def node_policy_set(
        self,
        node_id: str,
        policy: str,
        reason: str,
        override: bool = False,
        decision_id: str | None = None,
        _trust_tier: str = CLAIMED,
        _operator_approval: OperatorApproval | None = None,
    ) -> dict[str, Any]:
        if policy not in VALID_POLICIES:
            raise ValueError(f"Unsupported policy: {policy}")
        node = self.store.get_node(node_id)
        if not node:
            raise KeyError(f"Unknown node: {node_id}")
        require_runtime_user_approval(
            _trust_tier,
            "Override a node policy boundary",
            {
                "Node": node_id,
                "New policy": policy,
                "Decision": decision_id or "(none)",
                "Reason": reason,
            },
            approval=_operator_approval,
        )
        effective_policy, _ = self.policy.effective_node_policy(node_id)
        weakening = POLICY_RANK[policy] < POLICY_RANK[effective_policy]
        if weakening:
            decision = self.store.get_node(decision_id) if decision_id else None
            if (
                not override
                or _trust_tier not in APPROVAL_TRUST_TIERS
                or not decision
                or decision["type"] != "Decision"
                or not is_user_approved(decision)
            ):
                raise PermissionError(
                    "Weakening a node policy requires an explicit CLI user approval "
                    "and an accepted USER_APPROVED Decision."
                )
            removed = [
                *self.store.delete_incoming_edges(node_id, "locks"),
                *self.store.delete_incoming_edges(node_id, "constrained-by"),
            ]
            for edge in removed:
                source_node = self.store.get_node(edge["src"])
                effect = (source_node or {}).get("payload", {}).get("mutation_effect")
                if not effect:
                    self.store.upsert_edge(edge)
                elif edge["src"] != decision_id and source_node:
                    self.store.upsert_edge(
                        {
                            "src": decision_id,
                            "type": "supersedes",
                            "dst": edge["src"],
                            "confidence": 1.0,
                            "provenance": "user_approved",
                            "revision": git.revision(self.root),
                        }
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
                "trust_tier": _trust_tier,
            },
        )
        self._persist()
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
        builder_actor: str | None = None,
        dependency_justifications: list[str] | None = None,
    ) -> dict[str, Any]:
        if risk not in {"low", "medium", "high"}:
            raise ValueError("Risk must be low, medium, or high")
        self.portable.sync_to_store()
        self.indexer.index(force=False)
        task_id = self.store.next_id("tasks", "T")
        review = self.config.get("review", {})
        selected_review_budget = (
            review_budget
            if review_budget is not None
            else int(review.get("general_round_limit", 2))
        )
        selected_fix_budget = (
            fix_budget
            if fix_budget is not None
            else int(review.get("targeted_fix_limit", 2))
        )
        if not 1 <= selected_review_budget <= MAX_REVIEW_ROUNDS:
            raise ValueError(f"review_budget must be between 1 and {MAX_REVIEW_ROUNDS}")
        if not 1 <= selected_fix_budget <= MAX_FIX_CYCLES:
            raise ValueError(f"fix_budget must be between 1 and {MAX_FIX_CYCLES}")
        governance_baseline = {}
        for relative in (
            ".psg/.gitignore",
            ".psg/config.yaml",
            ".psg/policies.yaml",
        ):
            path = self.root / relative
            governance_baseline[relative] = (
                sha256_bytes(path.read_bytes()) if path.is_file() else None
            )
        task = {
            "id": task_id,
            "intent": intent.strip(),
            "status": "open",
            "risk": risk,
            "context_budget": context_budget
            if context_budget is not None
            else int(self.config.get("context", {}).get("default_token_budget", 12000)),
            "review_budget": selected_review_budget,
            "fix_budget": selected_fix_budget,
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
                "builder_actor": (builder_actor or "").strip(),
                "dependency_justifications": dependency_justifications or [],
                "governance_baseline": governance_baseline,
                "contract_version": CONTRACT_VERSION,
                # A task opens as a DRAFT: it states intent and requests scope, but
                # holds no write authority until localization seals a concrete
                # mutation boundary. More context must never mean more authority.
                "contract_state": CONTRACT_STATE_DRAFT,
                "authorized_write": [],
                "authorized_read_only": [],
                "authorized_forbidden": [],
                "review_boundary": default_review_boundary(),
                "completion_boundary": default_completion_boundary(
                    review_budget=selected_review_budget,
                    fix_budget=selected_fix_budget,
                    risk=risk,
                ),
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
        # The contract hash is only meaningful once the authority it protects exists,
        # so it is written by the seal in context_build, not here.
        revision = git.revision(self.root)
        self.store.upsert_node(
            {
                "id": task_id,
                "type": "Task",
                "title": intent.strip(),
                "status": "active",
                "maturity": "working",
                "policy": "mutable",
                "source": {"kind": "psg_runtime"},
                "revision": revision,
                "confidence": 1.0,
                "provenance": ["agent_interpreted_user_intent", "psg_runtime"],
                "payload": {
                    "intent": intent.strip(),
                    "risk": risk,
                    "builder_actor": (builder_actor or "").strip(),
                    "contract_version": CONTRACT_VERSION,
                },
            },
            bump=False,
        )
        target_ids: list[str] = []
        for value in targets or []:
            normalized = str(value).replace("\\", "/")
            target_id = (
                normalized if self.store.get_node(normalized) else f"file:{normalized}"
            )
            if self.store.get_node(target_id):
                target_ids.append(target_id)
        for criterion in criteria:
            requirement = {
                "id": criterion["id"],
                "type": "Requirement",
                "title": criterion["text"],
                "status": criterion["status"],
                "maturity": "proposed",
                "policy": "mutable",
                "source": {"kind": "task_acceptance", "task_id": task_id},
                "revision": revision,
                "confidence": 1.0,
                "provenance": ["agent_interpreted_user_intent", "task_projection"],
                "payload": {"mandatory": criterion["mandatory"], "evidence": {}},
            }
            self.store.upsert_node(requirement, bump=False)
            self.store.upsert_edge(
                {
                    "src": task_id,
                    "type": "requires",
                    "dst": criterion["id"],
                    "confidence": 1.0,
                    "provenance": "task_projection",
                    "revision": revision,
                },
                bump=False,
            )
            for target_id in target_ids:
                self.store.upsert_edge(
                    {
                        "src": criterion["id"],
                        "type": "targets",
                        "dst": target_id,
                        "confidence": 1.0,
                        "provenance": "task_projection",
                        "revision": revision,
                    },
                    bump=False,
                )
        for index, text in enumerate(constraints or [], 1):
            constraint_id = f"{task_id}-C{index}"
            self.store.upsert_node(
                {
                    "id": constraint_id,
                    "type": "Constraint",
                    "title": text,
                    "status": "active",
                    "maturity": "accepted",
                    "policy": "mutable",
                    "source": {"kind": "task_constraint", "task_id": task_id},
                    "revision": revision,
                    "confidence": 1.0,
                    "provenance": ["agent_interpreted_user_intent", "task_projection"],
                    "payload": {"text": text},
                },
                bump=False,
            )
            self.store.upsert_edge(
                {
                    "src": task_id,
                    "type": "constrained-by",
                    "dst": constraint_id,
                    "confidence": 1.0,
                    "provenance": "task_projection",
                    "revision": revision,
                },
                bump=False,
            )
        self.store.bump_graph_revision()
        snapshot = self.snapshot_create(
            task_id=task_id,
            stable=False,
            summary={"kind": "baseline", "intent": intent},
        )
        self.store.update_task(task_id, baseline_snapshot=snapshot["id"])
        self._persist()
        return self.store.get_task(task_id) or task

    def context_build(
        self, task_id: str, max_tokens: int | None = None
    ) -> dict[str, Any]:
        if not self.config.get("enabled", True) or not global_settings().get(
            "enabled", True
        ):
            raise RuntimeError(
                "PSG governance is disabled. Run 'psg on' for this project or "
                "'psg on --global' for the global switch."
            )
        self.portable.sync_to_store()
        index = self.indexer.index(force=False).as_dict()
        result = self.router.build(task_id, max_tokens=max_tokens)
        result["task_contract_seal"] = self._seal_contract(task_id)
        result["index_refresh"] = index
        self._persist()
        return result

    def _seal_contract(self, task_id: str) -> dict[str, Any]:
        """Freeze the mutation authority produced by initial localization.

        Everything before this point is a proposal. Everything after it may widen
        what the task READS and never what it may WRITE, which is the property the
        contract hash exists to protect.
        """
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        payload = task["payload"]
        if is_sealed(payload):
            return {
                "contract_state": CONTRACT_STATE_SEALED,
                "sealed_now": False,
                "contract_hash": payload.get("contract_hash"),
                "authorized_write": list(payload.get("authorized_write", [])),
                "requires_scope_approval": bool(
                    payload.get("requires_scope_approval", False)
                ),
            }
        working_set = payload.get("working_set", {})
        authorized_write = sorted(set(working_set.get("write", [])))
        authorized_read_only = sorted(set(working_set.get("read_only", [])))
        authorized_forbidden = sorted(set(working_set.get("forbidden", [])))
        localization = payload.get("localization", {})
        needs_approval, reasons = requires_scope_approval(
            write=authorized_write,
            read_only=authorized_read_only,
            forbidden=authorized_forbidden,
            risk=str(task["risk"]),
            localization=localization,
        )
        payload["authorized_write"] = authorized_write
        payload["authorized_read_only"] = authorized_read_only
        payload["authorized_forbidden"] = authorized_forbidden
        payload["contract_state"] = CONTRACT_STATE_SEALED
        payload["requires_scope_approval"] = needs_approval
        payload["scope_approval_reasons"] = reasons
        payload["localization"] = localization
        task["payload"] = payload
        payload["contract_hash"] = contract_hash(task)
        self.store.update_task(task_id, payload_json=payload)
        self.store.event(
            "task.contract_sealed",
            {
                "task_id": task_id,
                "contract_hash": payload["contract_hash"],
                "authorized_write": authorized_write,
                "requires_scope_approval": needs_approval,
                "scope_approval_reasons": reasons,
            },
        )
        return {
            "contract_state": CONTRACT_STATE_SEALED,
            "sealed_now": True,
            "contract_hash": payload["contract_hash"],
            "authorized_write": authorized_write,
            "requires_scope_approval": needs_approval,
            "scope_approval_reasons": reasons,
        }

    def context_expand(self, task_id: str, reason: str) -> dict[str, Any]:
        self.portable.sync_to_store()
        self.indexer.index(force=False)
        result = self.router.expand(task_id, reason)
        self._persist()
        return result

    def patch_validate(
        self,
        task_id: str,
        diff_text: str | None = None,
        *,
        phase: str = "postflight",
    ) -> dict[str, Any]:
        selected = diff_text if diff_text is not None else git.final_diff(self.root)
        result = self.policy.validate(task_id, selected, phase=phase)
        result["diff_source"] = (
            "proposed" if diff_text is not None else "runtime_final_diff"
        )
        policy_verification = self.verifier.record(
            task_id,
            name="policy:mutation-boundary",
            result="pass" if result["allowed"] else "fail",
            kind="policy",
            required=True,
            source="runtime_executed",
            trust_tier=RUNTIME_ATTESTED,
            evidence={
                "violations": result["violations"],
                "touched_nodes": result["touched_nodes"],
                "phase": phase,
            },
        )
        self._project_verification(policy_verification)
        self._persist()
        return result

    def patch_validate_proposed(
        self, task_id: str, diff_text: str, *, phase: str = "preflight"
    ) -> dict[str, Any]:
        if not diff_text.strip():
            raise ValueError("Proposed diff validation requires a unified diff.")
        return self.patch_validate(task_id, diff_text, phase=phase)

    def verification_record(
        self, *, _trust_tier: str = CLAIMED, **kwargs: Any
    ) -> dict[str, Any]:
        require_runtime_user_approval(
            _trust_tier,
            "Record a verification result on user authority",
            {
                "Task": kwargs.get("task_id", "(unknown)"),
                "Check": kwargs.get("name", "(unknown)"),
                "Result": kwargs.get("result", "(unknown)"),
            },
        )
        reported_source = str(kwargs.pop("source", "llm_reported"))
        evidence = dict(kwargs.pop("evidence", {}) or {})
        if _trust_tier == CLAIMED:
            evidence["reported_source"] = reported_source
            kwargs["source"] = "agent_claim"
        elif _trust_tier == USER_APPROVED:
            kwargs["source"] = "user_asserted"
        else:
            raise PermissionError("Unsupported verification approval channel.")
        kwargs["trust_tier"] = _trust_tier
        kwargs["evidence"] = evidence
        result = self.verifier.record(**kwargs)
        self._project_verification(result)
        self._persist()
        return result

    def verify(
        self, task_id: str, check_names: list[str] | None = None
    ) -> dict[str, Any]:
        configured = self._configured_checks()
        selected_names = check_names if check_names is not None else list(configured)
        unknown = sorted(set(selected_names) - set(configured))
        if unknown:
            raise PermissionError(
                "MCP verification may run only configured check names. Unknown: "
                + ", ".join(unknown)
            )
        selected = [configured[name] for name in selected_names]
        return self._run_checks(task_id, selected)

    def verify_commands(
        self, task_id: str, checks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Advanced CLI boundary: execute explicit commands authorized by the shell user."""
        return self._run_checks(task_id, checks)

    def _run_checks(
        self, task_id: str, selected: list[dict[str, Any]]
    ) -> dict[str, Any]:
        results = self.verifier.run(task_id, selected)
        for result in results:
            self._project_verification(result)
        issues = report_failed_checks(results, self.issue_report)
        self._persist()
        return {"task_id": task_id, "results": results, "issues_created": issues}

    def _configured_checks(self) -> dict[str, dict[str, Any]]:
        raw = self.config.get("verification", {}).get("commands", {})
        if isinstance(raw, list):
            return {str(item["name"]): dict(item) for item in raw}
        if not isinstance(raw, dict):
            raise TypeError("verification.commands must be a mapping of check names")
        configured: dict[str, dict[str, Any]] = {}
        for name, value in raw.items():
            if isinstance(value, str):
                configured[str(name)] = {
                    "name": str(name),
                    "command": value,
                    "kind": "test",
                    "required": True,
                }
            elif isinstance(value, dict) and value.get("command"):
                configured[str(name)] = {"name": str(name), **value}
            else:
                raise ValueError(f"Invalid configured verification check: {name}")
        return configured

    def _project_verification(self, verification: dict[str, Any]) -> None:
        revision = git.revision(self.root)
        self.store.upsert_node(
            {
                "id": verification["id"],
                "type": "Verification",
                "title": verification["name"],
                "status": verification["result"],
                "maturity": "accepted"
                if verification["result"] == "pass"
                else "working",
                "policy": "mutable",
                "source": {
                    "kind": verification["evidence"].get("source", "unknown"),
                    "task_id": verification["task_id"],
                },
                "revision": revision,
                "confidence": 1.0
                if evidence_trust(verification["evidence"]) == RUNTIME_ATTESTED
                else 0.6,
                "provenance": [evidence_trust(verification["evidence"]).lower()],
                "payload": verification,
            },
            bump=False,
        )
        if self.store.get_node(verification["task_id"]):
            self.store.upsert_edge(
                {
                    "src": verification["task_id"],
                    "type": "verified-by",
                    "dst": verification["id"],
                    "confidence": 1.0,
                    "provenance": "runtime_projection",
                    "revision": revision,
                },
                bump=False,
            )
        self.store.bump_graph_revision()

    def criterion_set(
        self,
        task_id: str,
        criterion_id: str,
        status: str,
        evidence: dict[str, Any] | None = None,
        *,
        _trust_tier: str = CLAIMED,
    ) -> dict[str, Any]:
        if status not in {"pending", "pass", "fail", "waived"}:
            raise ValueError("Criterion status must be pending, pass, fail, or waived")
        recorded_evidence = dict(evidence or {})
        if status == "pass":
            required = {"kind", "source", "reference"}
            missing = sorted(key for key in required if not recorded_evidence.get(key))
            if missing:
                raise ValueError(
                    f"Passing acceptance evidence requires: {', '.join(missing)}"
                )
            reference = str(recorded_evidence["reference"])
            verification = self.store.get_verification(reference)
            if verification and verification["task_id"] == task_id:
                if verification["result"] != "pass" or evidence_trust(
                    verification["evidence"]
                ) not in {RUNTIME_ATTESTED, EXTERNAL_ATTESTED}:
                    raise PermissionError(
                        "Acceptance requires a passing runtime/external attested verification."
                    )
                recorded_evidence["source"] = verification["evidence"].get(
                    "source", "runtime_executed"
                )
                recorded_evidence["trust_tier"] = evidence_trust(
                    verification["evidence"]
                )
            elif _trust_tier == USER_APPROVED:
                recorded_evidence["source"] = "user_asserted"
                recorded_evidence["trust_tier"] = USER_APPROVED
            else:
                raise PermissionError(
                    "Claimed acceptance cannot self-assert user or external authority; "
                    "reference a trusted Verification ID or use the explicit CLI approval channel."
                )
        if status == "waived":
            decision_id = recorded_evidence.get("decision_id")
            decision = self.store.get_node(str(decision_id)) if decision_id else None
            approved_decision = (
                decision
                and decision["type"] == "Decision"
                and is_user_approved(decision)
                and decision["status"] == "accepted"
            )
            if _trust_tier != USER_APPROVED and not approved_decision:
                raise PermissionError(
                    "Waiving acceptance requires an explicit CLI user approval or an "
                    "accepted USER_APPROVED Decision."
                )
            recorded_evidence["source"] = "user_asserted"
            recorded_evidence["trust_tier"] = USER_APPROVED
        require_runtime_user_approval(
            _trust_tier,
            "Set an acceptance criterion on user authority",
            {"Task": task_id, "Criterion": criterion_id, "Status": status},
        )
        recorded_evidence.setdefault("trust_tier", _trust_tier)
        recorded_evidence.setdefault(
            "worktree_fingerprint", git.worktree_fingerprint(self.root)
        )
        self.store.set_criterion(task_id, criterion_id, status, recorded_evidence)
        node = self.store.get_node(criterion_id)
        if node:
            node["status"] = status
            node["maturity"] = (
                "accepted" if status in {"pass", "waived"} else "proposed"
            )
            node["payload"]["evidence"] = recorded_evidence
            self.store.upsert_node(node)
        self._persist()
        return self.store.get_task(task_id) or {}

    def issue_report(
        self,
        *,
        task_id: str,
        severity: str,
        relation_to_task: str,
        claim: str,
        evidence: dict[str, Any] | None,
        affected_nodes: list[str] | None = None,
        violates: str | None = None,
        introduced_by_patch: str | None = None,
        debt_id: str | None = None,
    ) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        normalized = severity.lower()
        if normalized not in VALID_SEVERITIES:
            raise ValueError(f"Unsupported severity: {severity}")
        relation = relation_to_task.lower().strip()
        if relation not in RELATIONS_TO_TASK:
            raise ValueError(f"Unsupported relation_to_task: {relation_to_task}")
        provided = evidence or {}
        status = "open"
        debt = self.store.get_node(debt_id) if debt_id else None
        if debt:
            if debt["type"] != "Debt":
                raise ValueError(f"Node is not accepted debt: {debt_id}")
            if (
                debt["status"] == "accepted"
                and is_user_approved(debt)
                and not debt["payload"].get("trigger_met")
            ):
                normalized = "optional"
                status = "deferred"
                provided = {
                    **provided,
                    "kind": "accepted_debt_not_due",
                    "debt_id": debt_id,
                }
        evidence_sufficient = self._issue_evidence_sufficient(
            task=task,
            relation_to_task=relation,
            evidence=provided,
            affected_nodes=affected_nodes or [],
            violates=violates,
        )
        issue = {
            "id": self.store.next_id("issues", "I"),
            "task_id": task_id,
            "severity": normalized,
            "relation_to_task": relation,
            "evidence_sufficient": evidence_sufficient,
            "claim": claim,
            "evidence": provided,
            "affected_nodes": affected_nodes or [],
            "violates": violates,
            "introduced_by_patch": introduced_by_patch,
            "status": status,
        }
        self.store.create_issue(issue)
        revision = git.revision(self.root)
        self.store.upsert_node(
            {
                "id": issue["id"],
                "type": "Issue",
                "title": claim,
                "status": status,
                "maturity": "working",
                "policy": "mutable",
                "source": {"kind": "review", "task_id": task_id},
                "revision": revision,
                "confidence": 1.0 if provided else 0.4,
                "provenance": [str(provided.get("source", "review"))],
                "payload": {
                    "severity": normalized,
                    "relation_to_task": relation,
                    "evidence_sufficient": evidence_sufficient,
                    "evidence": provided,
                    "violates": violates,
                    "debt_id": debt_id,
                },
            },
            bump=False,
        )
        self.store.upsert_edge(
            {
                "src": issue["id"],
                "type": "introduced-by",
                "dst": task_id,
                "confidence": 1.0,
                "provenance": "runtime_projection",
                "revision": revision,
            },
            bump=False,
        )
        for node_id in affected_nodes or []:
            if self.store.get_node(node_id):
                self.store.upsert_edge(
                    {
                        "src": issue["id"],
                        "type": "affects",
                        "dst": node_id,
                        "confidence": 1.0,
                        "provenance": "review_evidence",
                        "revision": revision,
                    },
                    bump=False,
                )
        self.store.bump_graph_revision()
        self._persist()
        return self.store.get_issue(issue["id"]) or issue

    def _issue_evidence_sufficient(
        self,
        *,
        task: dict[str, Any],
        relation_to_task: str,
        evidence: dict[str, Any],
        affected_nodes: list[str],
        violates: str | None,
    ) -> bool:
        if relation_to_task in {"pre_existing", "unrelated", "future_improvement"}:
            return bool(evidence)
        if relation_to_task == "violates_acceptance":
            criterion_ids = {item["id"] for item in task.get("criteria", [])}
            return bool(violates in criterion_ids and evidence)
        if relation_to_task == "violates_project_constraint":
            pointer = self.store.get_node(violates) if violates else None
            valid_pointer = bool(
                pointer
                and (
                    (
                        pointer["type"] == "Constraint"
                        and pointer.get("source", {}).get("task_id") == task["id"]
                    )
                    or (
                        pointer["type"] == "Decision"
                        and pointer.get("status") == "accepted"
                    )
                )
            )
            restricted_node = any(
                self.store.get_node(node_id)
                and self.policy.effective_node_policy(node_id)[0]
                in {"frozen", "read_only", "interface_locked"}
                for node_id in affected_nodes
            )
            policy_reference = bool(
                violates
                and violates.startswith("policy:")
                and evidence.get("reference")
            )
            return bool(
                evidence and (valid_pointer or restricted_node or policy_reference)
            )
        if relation_to_task == "caused_by_patch":
            changes = parse_diff(git.final_diff(self.root))
            changed_nodes: set[str] = set()
            changed_paths: set[str] = set()
            for change in changes:
                changed_paths.update(change.scope_paths)
                changed_nodes.add(f"file:{change.path}")
                changed_nodes.update(
                    node["id"] for node in self.policy.affected_symbols(change)
                )
            affected_change = bool(set(affected_nodes) & changed_nodes)
            evidence_path = str(evidence.get("path", "")).replace("\\", "/")
            diff_reference = bool(
                evidence_path in changed_paths
                and (evidence.get("diff_hunk") or evidence.get("runtime_error"))
            )
            verification_id = str(
                evidence.get("verification_id") or evidence.get("reference") or ""
            )
            verification = (
                self.store.get_verification(verification_id)
                if verification_id
                else None
            )
            failing_verification = bool(
                verification
                and verification["task_id"] == task["id"]
                and verification["result"] != "pass"
            )
            return affected_change or diff_reference or failing_verification
        return False

    def task_contract(self, task_id: str) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        return task_contract(task)

    def handoff(self, task_id: str | None = None) -> dict[str, Any]:
        selected_id = task_id
        if not selected_id:
            active = [
                task
                for task in self.store.list_tasks()
                if task["status"] in {"open", "blocked"}
            ]
            if len(active) != 1:
                raise ValueError(
                    "Specify TASK_ID when there is not exactly one active task."
                )
            selected_id = active[0]["id"]
        task = self.store.get_task(selected_id)
        if not task:
            raise KeyError(f"Unknown task: {selected_id}")
        contract = task_contract(task)
        changes = []
        relevant_ids = {selected_id}
        for change in parse_diff(git.final_diff(self.root)):
            # PSG's own portable state is rewritten by every mutation; it is
            # bookkeeping, not a change the reviewer should read.
            if git.is_managed_state_path(change.path):
                continue
            symbols = [node["id"] for node in self.policy.affected_symbols(change)]
            relevant_ids.add(f"file:{change.path}")
            relevant_ids.update(symbols)
            changes.append({"path": change.path, "symbols": symbols})
        for values in contract["mutation_boundary"].values():
            for entry in values:
                relevant_ids.update(self._boundary_node_ids(entry))
        relevant_ids.update(
            node["id"]
            for node in self.store.list_nodes("Constraint")
            if node.get("source", {}).get("task_id") == selected_id
        )
        decisions = []
        for node in self.store.list_nodes("Decision"):
            if node["status"] != "accepted" or not is_user_approved(node):
                continue
            scope = set(node.get("payload", {}).get("scope", []))
            normalized_scope = {
                value if self.store.get_node(value) else f"file:{value}"
                for value in scope
            }
            if normalized_scope and not normalized_scope.intersection(relevant_ids):
                continue
            decisions.append(
                {
                    "id": node["id"],
                    "title": node["title"],
                    "scope": sorted(scope),
                }
            )
        accepted_debt = []
        for node in self.store.list_nodes("Debt"):
            if node["status"] != "accepted" or not is_user_approved(node):
                continue
            affects = {
                edge["dst"]
                for edge in self.store.edges_for([node["id"]], both=False)
                if edge["type"] == "affects"
            }
            same_task = node.get("source", {}).get("task_id") == selected_id
            if not same_task and affects and not affects.intersection(relevant_ids):
                continue
            accepted_debt.append({"id": node["id"], "title": node["title"]})
        trusted_verification = []
        for item in self.store.latest_verifications(selected_id):
            if evidence_trust(item["evidence"]) not in {
                RUNTIME_ATTESTED,
                EXTERNAL_ATTESTED,
            }:
                continue
            trusted_verification.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "kind": item["kind"],
                    "result": item["result"],
                    "revision": item["revision"],
                    "reference": item["evidence"].get("reference"),
                }
            )
        issues = [
            {
                key: item.get(key)
                for key in (
                    "id",
                    "severity",
                    "relation_to_task",
                    "blocks_current_task",
                    "claim",
                    "violates",
                    "status",
                )
            }
            for item in self.store.list_issues(selected_id)
        ]
        working_paths = {
            path
            for values in task["payload"].get("working_set", {}).values()
            if isinstance(values, list)
            for path in values
        }
        graph_synchronized = all(
            self.indexer.freshness(node) == 1.0
            for node in self.store.find_nodes_for_paths(working_paths)
        )
        ship_state = self.convergence.evaluate(
            selected_id,
            graph_synchronized=graph_synchronized,
            worktree_fingerprint=git.worktree_fingerprint(self.root),
            persist=False,
        )
        frozen = sorted(
            node_id
            for node_id in relevant_ids
            if self.store.get_node(node_id)
            and self.policy.effective_node_policy(node_id)[0]
            in {"frozen", "read_only", "interface_locked"}
        )
        pack = {
            "task_contract": contract,
            "contract_hash": task["payload"].get("contract_hash"),
            "changed": changes,
            "frozen": frozen,
            "relevant_decisions": decisions,
            "trusted_verification": trusted_verification,
            "accepted_debt": accepted_debt,
            "known_issues": issues,
            "current_ship_state": {
                "status": ship_state["status"],
                "recommendation": ship_state["recommendation"],
                "current_task_issues": ship_state["current_task_issue_summary"],
                "follow_up_issues": ship_state["follow_up_issue_summary"],
            },
            "review_instruction": "Review the task, not the entire project.",
            "state_mutated": False,
        }
        pack["markdown"] = render_handoff(pack)
        return pack

    def _boundary_node_ids(self, entry: str) -> set[str]:
        """Resolve one mutation-boundary entry to the graph node ids it covers.

        Entries are node ids, plain paths, or path globs, so a glob must expand
        against indexed File nodes to stay comparable with decision scopes.
        """
        if self.store.get_node(entry):
            return {entry}
        resolved = {f"file:{entry}"}
        if any(character in entry for character in "*?["):
            resolved.update(
                node["id"]
                for node in self.store.list_nodes("File")
                if fnmatch.fnmatch(node["id"].removeprefix("file:"), entry)
            )
        return resolved

    def issue_update(
        self,
        issue_id: str,
        status: str,
        resolved_by_patch: str | None = None,
        *,
        _trust_tier: str = CLAIMED,
    ) -> dict[str, Any]:
        if status not in {"open", "fixed", "deferred", "rejected"}:
            raise ValueError("Issue status must be open, fixed, deferred, or rejected")
        issue = self.store.get_issue(issue_id)
        if not issue:
            raise KeyError(f"Unknown issue: {issue_id}")
        require_runtime_user_approval(
            _trust_tier,
            "Resolve an issue on user authority",
            {"Issue": issue_id, "New status": status},
        )
        if (
            issue["severity"] in {"blocker", "major"}
            and status != "open"
            and _trust_tier not in APPROVAL_TRUST_TIERS
        ):
            self.store.event(
                "issue.resolution_claimed",
                {
                    "issue_id": issue_id,
                    "status": status,
                    "resolved_by_patch": resolved_by_patch,
                },
            )
            return {
                "issue_id": issue_id,
                "status": issue["status"],
                "claimed_status": status,
                "approval_required": True,
            }
        self.store.update_issue(issue_id, status, resolved_by_patch)
        node = self.store.get_node(issue_id)
        if node:
            node["status"] = status
            node["payload"]["resolved_by_patch"] = resolved_by_patch
            self.store.upsert_node(node)
        self._persist()
        return {
            "issue_id": issue_id,
            "status": status,
            "resolved_by_patch": resolved_by_patch,
        }

    def guardrails_get(self) -> dict[str, Any]:
        review = self.config.get("review", {})
        return {
            "authority": self.config.get("authority", {}),
            "dependencies": self.config.get("dependencies", {}),
            "effective": {
                "frozen_mutation": {
                    "mode": "ENFORCED",
                    "configurable": False,
                },
                "out_of_scope_write": {
                    "mode": "BLOCKED",
                    "configurable": False,
                },
                "dirty_portable_state": {
                    "mode": "REJECTED_UNTIL_USER_APPROVED",
                    "configurable": False,
                },
                "stale_evidence": {
                    "mode": "REJECTED",
                    "configurable": False,
                },
                "mcp_verification_commands": {
                    "mode": "ALLOWLIST_ONLY",
                    "configurable": False,
                },
                "accepted_debt": {
                    "mode": "REOPEN_ON_APPROVED_TRIGGER_ONLY",
                    "configurable": False,
                },
                "high_risk_review": {
                    "mode": "USER_OR_EXTERNAL_APPROVAL_REQUIRED"
                    if self.config.get("risk", {}).get(
                        "high_requires_independent_review", True
                    )
                    else "NOT_REQUIRED",
                    "configurable": True,
                },
                "review_round_limit": {
                    "mode": int(review.get("general_round_limit", 2)),
                    "configurable": True,
                },
                "fix_round_limit": {
                    "mode": int(review.get("targeted_fix_limit", 2)),
                    "configurable": True,
                },
            },
        }

    def debt_record(
        self,
        *,
        task_id: str,
        what: str,
        why: str,
        ceiling: str,
        revisit_trigger: str,
        affected_nodes: list[str] | None = None,
    ) -> dict[str, Any]:
        if not all(value.strip() for value in (what, why, ceiling, revisit_trigger)):
            raise ValueError("Debt requires what, why, ceiling, and revisit_trigger.")
        if not self.store.get_task(task_id):
            raise KeyError(f"Unknown task: {task_id}")
        debt_id = self.store.next_node_id("DEBT")
        node = {
            "id": debt_id,
            "type": "Debt",
            "title": what.strip(),
            "status": "proposed",
            "maturity": "proposed",
            "policy": "mutable",
            "source": {"kind": "agent_claim", "task_id": task_id},
            "revision": git.revision(self.root),
            "confidence": 0.6,
            "provenance": ["claimed", "proposed_debt"],
            "payload": {
                "what": what.strip(),
                "why": why.strip(),
                "ceiling": ceiling.strip(),
                "revisit_trigger": revisit_trigger.strip(),
                "trigger_met": False,
                "trust_tier": CLAIMED,
                "approval_required": True,
            },
        }
        self.store.upsert_node(node, bump=False)
        self.store.upsert_edge(
            {
                "src": debt_id,
                "type": "introduced-by",
                "dst": task_id,
                "confidence": 1.0,
                "provenance": "proposed_debt",
                "revision": git.revision(self.root),
            },
            bump=False,
        )
        for affected in affected_nodes or []:
            if not self.store.get_node(affected):
                raise KeyError(f"Unknown affected node: {affected}")
            self.store.upsert_edge(
                {
                    "src": debt_id,
                    "type": "affects",
                    "dst": affected,
                    "confidence": 1.0,
                    "provenance": "proposed_debt",
                    "revision": git.revision(self.root),
                },
                bump=False,
            )
        self.store.bump_graph_revision()
        self.store.event("debt.proposed", {"debt_id": debt_id, "task_id": task_id})
        self._persist()
        return self.store.get_node(debt_id) or node

    def task_scope_approve(self, task_id: str, reason: str) -> dict[str, Any]:
        """Approve a broad mutation boundary. Deliberately unreachable from MCP.

        The approval is bound to the contract hash it approved, so it cannot carry
        over to a different authority than the one a person actually read.
        """
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        payload = task["payload"]
        if not is_sealed(payload):
            raise ValueError(
                "Seal the contract with context_build before approving its scope."
            )
        if not reason.strip():
            raise ValueError(
                "Approving a broad mutation boundary requires an explicit reason."
            )
        require_interactive_user_approval(
            "Approve a broad sealed mutation boundary",
            {
                "Task": task_id,
                "Contract": payload.get("contract_hash", "(unsealed)"),
                "Flagged because": payload.get("scope_approval_reasons", []),
                "Write authority": payload.get("authorized_write", []),
            },
        )
        payload["scope_approval"] = {
            "trust_tier": USER_APPROVED,
            "reason": reason.strip(),
            "approved_at": utc_now(),
            "contract_hash": payload.get("contract_hash"),
            "authorized_write": list(payload.get("authorized_write", [])),
        }
        self.store.update_task(task_id, payload_json=payload)
        self.store.event(
            "task.scope_approved",
            {
                "task_id": task_id,
                "contract_hash": payload.get("contract_hash"),
                "reason": reason.strip(),
            },
        )
        self._persist()
        return {
            "task_id": task_id,
            "scope_approved": True,
            "contract_hash": payload.get("contract_hash"),
            "authorized_write": list(payload.get("authorized_write", [])),
        }

    def debt_approve(self, debt_id: str) -> dict[str, Any]:
        node = self.store.get_node(debt_id)
        if not node or node["type"] != "Debt":
            raise KeyError(f"Unknown debt: {debt_id}")
        require_interactive_user_approval(
            "Accept bounded technical debt",
            {
                "Debt": debt_id,
                "What": node.get("title", "(unknown)"),
                "Ceiling": node.get("payload", {}).get("ceiling", ""),
                "Revisit trigger": node.get("payload", {}).get(
                    "revisit_trigger", ""
                ),
            },
        )
        node["status"] = "accepted"
        node["maturity"] = "accepted"
        node["source"] = {
            "kind": "user_approved",
            "task_id": node.get("source", {}).get("task_id"),
        }
        node["confidence"] = 1.0
        node["provenance"] = ["user_approved", "accepted_debt"]
        node["payload"]["trust_tier"] = USER_APPROVED
        node["payload"]["approval_required"] = False
        self.store.upsert_node(node)
        self.store.event("debt.accepted", {"debt_id": debt_id})
        self._persist()
        return self.store.get_node(debt_id) or node

    def debt_review(
        self,
        debt_id: str,
        *,
        trigger_met: bool,
        evidence: dict[str, Any],
        _trust_tier: str = CLAIMED,
    ) -> dict[str, Any]:
        node = self.store.get_node(debt_id)
        if not node or node["type"] != "Debt":
            raise KeyError(f"Unknown debt: {debt_id}")
        if not is_user_approved(node) or node["status"] not in {"accepted", "due"}:
            return {
                "debt_id": debt_id,
                "trigger_met": False,
                "review_action": "DEBT_APPROVAL_REQUIRED",
                "trust_tier": CLAIMED,
            }
        if trigger_met and not evidence:
            raise ValueError("Marking a debt trigger as met requires evidence.")
        require_runtime_user_approval(
            _trust_tier,
            "Attest a debt revisit trigger on user authority",
            {"Debt": debt_id, "Trigger met": bool(trigger_met)},
        )
        if _trust_tier not in APPROVAL_TRUST_TIERS:
            self.store.event(
                "debt.trigger_claimed",
                {
                    "debt_id": debt_id,
                    "claimed_trigger_met": bool(trigger_met),
                    "evidence": evidence,
                },
            )
            currently_due = bool(node["payload"].get("trigger_met"))
            return {
                "debt_id": debt_id,
                "trigger_met": currently_due,
                "claimed_trigger_met": bool(trigger_met),
                "review_action": "USER_APPROVAL_REQUIRED"
                if trigger_met or currently_due
                else "DO_NOT_REOPEN",
                "trust_tier": CLAIMED,
            }
        node["payload"]["trigger_met"] = bool(trigger_met)
        node["payload"]["trigger_evidence"] = evidence
        node["payload"]["trigger_trust_tier"] = _trust_tier
        node["status"] = "due" if trigger_met else "accepted"
        self.store.upsert_node(node)
        self.store.event(
            "debt.reviewed", {"debt_id": debt_id, "trigger_met": bool(trigger_met)}
        )
        self._persist()
        return {
            "debt_id": debt_id,
            "trigger_met": bool(trigger_met),
            "review_action": "REOPEN" if trigger_met else "DO_NOT_REOPEN",
        }

    def conflict_record(
        self,
        *,
        task_id: str,
        source: str,
        domain: str,
        recommendation: str,
        guardrail: str,
        resolution: str = "deferred",
        decision_id: str | None = None,
    ) -> dict[str, Any]:
        if resolution not in {"deferred", "reported", "user_override"}:
            raise ValueError(
                "Conflict resolution must be deferred, reported, or user_override"
            )
        if resolution == "user_override":
            decision = self.store.get_node(decision_id) if decision_id else None
            if (
                not decision
                or decision["type"] != "Decision"
                or not is_user_approved(decision)
            ):
                raise PermissionError(
                    "A user override conflict requires an accepted USER_APPROVED Decision."
                )
        conflict_id = self.store.next_node_id("CONFLICT")
        node = self.node_create(
            node_id=conflict_id,
            node_type="Conflict",
            title=f"{source}: {recommendation}",
            payload={
                "task_id": task_id,
                "source": source,
                "domain": domain,
                "recommendation": recommendation,
                "guardrail": guardrail,
                "resolution": resolution,
                "decision_id": decision_id,
            },
            maturity="accepted",
            provenance=["skill_conflict", source],
        )
        if self.store.get_node(task_id):
            self.edge_create(
                conflict_id, "introduced-by", task_id, provenance="skill_conflict"
            )
        if decision_id:
            self.edge_create(
                conflict_id, "resolved-by", decision_id, provenance="skill_conflict"
            )
        self.store.event("skill.conflict", node["payload"])
        return node

    def review_record(
        self,
        task_id: str,
        new_blocking_issues: int,
        *,
        actor_id: str | None = None,
        session_id: str | None = None,
        model_family: str | None = None,
        _trust_tier: str = CLAIMED,
    ) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        expected_contract_hash = task["payload"].get("contract_hash")
        actual_contract_hash = contract_hash(task)
        if expected_contract_hash and expected_contract_hash != actual_contract_hash:
            raise PermissionError(
                "NO_SCOPE_EXPANSION_BY_REVIEW: the Task Contract changed outside a new user task."
            )
        require_runtime_user_approval(
            _trust_tier,
            "Attest an independent review on user authority",
            {
                "Task": task_id,
                "Reviewer actor": actor_id or "(unnamed)",
                "Model family": model_family or "(unnamed)",
            },
        )
        result = self.convergence.review_record(
            task_id,
            new_blocking_issues,
            actor_id=actor_id,
            session_id=session_id,
            model_family=model_family,
            trust_tier=_trust_tier,
        )
        result["invariant"] = "NO_SCOPE_EXPANSION_BY_REVIEW"
        result["contract_hash"] = actual_contract_hash
        self._persist()
        return result

    def fix_record(
        self, task_id: str, introduced: int, resolved: int
    ) -> dict[str, Any]:
        result = self.convergence.fix_record(task_id, introduced, resolved)
        self._persist()
        return result

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
        task_node = self.store.get_node(task_id)
        if task_node:
            task_node["status"] = result["status"].lower()
            task_node["maturity"] = (
                "accepted" if result["status"] == "SHIPPABLE" else "working"
            )
            task_node["payload"]["ship_gate"] = {
                "status": result["status"],
                "recommendation": result["recommendation"],
            }
            self.store.upsert_node(task_node)
        self._persist()
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
        self._persist()
        return {
            "restored": snapshot_id,
            "safety_snapshot": safety["id"],
            "git_revision": current,
            "source_code_changed": False,
        }
