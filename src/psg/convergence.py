from __future__ import annotations

from typing import Any

from .store import Store
from .task_contract import (
    MAX_FIX_CYCLES,
    MAX_REVIEW_ROUNDS,
    blocks_current_task,
    task_contract,
)
from .trust import (
    APPROVAL_TRUST_TIERS,
    FUNCTIONAL_TRUST_TIERS,
    evidence_trust,
)

BLOCKING = {"blocker", "major"}
NON_BLOCKING = {"minor", "optional", "speculative"}


class ConvergenceEngine:
    def __init__(self, store: Store, config: dict[str, Any]):
        self.store = store
        self.config = config

    def review_record(
        self,
        task_id: str,
        new_blocking_issues: int,
        *,
        actor_id: str | None = None,
        session_id: str | None = None,
        model_family: str | None = None,
        trust_tier: str = "CLAIMED",
    ) -> dict[str, Any]:
        task = self._task(task_id)
        review_budget = min(int(task["review_budget"]), MAX_REVIEW_ROUNDS)
        if task["review_rounds"] >= review_budget:
            return {
                "task_id": task_id,
                "review_rounds_used": task["review_rounds"],
                "review_budget": review_budget,
                "stop_general_review": True,
                "reason": "budget_exhausted",
                "recorded": False,
            }
        rounds = task["review_rounds"] + 1
        payload = task["payload"]
        blocking_ids = {
            item["id"]
            for item in self.store.list_issues(task_id, status="open")
            if blocks_current_task(item)
        }
        previously_seen = set(payload.get("review_seen_blocking_ids", []))
        derived_new = len(blocking_ids - previously_seen)
        payload["review_seen_blocking_ids"] = sorted(blocking_ids)
        no_new = task["no_new_blocking_rounds"] + 1 if derived_new == 0 else 0
        payload.setdefault("review_history", []).append(
            {
                "round": rounds,
                "actor_id": (actor_id or "").strip(),
                "session_id": (session_id or "").strip(),
                "model_family": (model_family or "").strip(),
                "derived_new_blocking_issues": derived_new,
                "reported_new_blocking_issues": new_blocking_issues,
                "trust_tier": trust_tier,
            }
        )
        self.store.update_task(
            task_id,
            review_rounds=rounds,
            no_new_blocking_rounds=no_new,
            payload_json=payload,
        )
        stop = rounds >= review_budget
        result = {
            "task_id": task_id,
            "review_rounds_used": rounds,
            "review_budget": review_budget,
            "no_new_blocking_rounds": no_new,
            "stop_general_review": stop,
            "reason": "budget_exhausted" if stop else None,
            "actor_id": (actor_id or "").strip(),
            "session_id": (session_id or "").strip(),
            "model_family": (model_family or "").strip(),
            "derived_new_blocking_issues": derived_new,
            "reported_new_blocking_issues": new_blocking_issues,
            "reported_metric_role": "advisory_only",
            "trust_tier": trust_tier,
        }
        self.store.event("review.recorded", result)
        return result

    def fix_record(
        self, task_id: str, introduced: int, resolved: int
    ) -> dict[str, Any]:
        task = self._task(task_id)
        fix_budget = min(int(task["fix_budget"]), MAX_FIX_CYCLES)
        if task["fix_cycles"] >= fix_budget:
            return {
                "task_id": task_id,
                "fix_cycles_used": task["fix_cycles"],
                "fix_budget": fix_budget,
                "stop_targeted_fixes": True,
                "reason": "fix_budget_exhausted",
                "recorded": False,
            }
        cycles = task["fix_cycles"] + 1
        payload = task["payload"]
        current_open = {
            item["id"]
            for item in self.store.list_issues(task_id, status="open")
            if blocks_current_task(item)
        }
        previous_open = set(payload.get("fix_seen_open_issue_ids", current_open))
        derived_introduced = len(current_open - previous_open)
        derived_resolved = len(previous_open - current_open)
        payload["fix_seen_open_issue_ids"] = sorted(current_open)
        churn = derived_introduced / max(1, derived_resolved)
        history = payload.setdefault("churn_history", [])
        history.append(
            {
                "cycle": cycles,
                "derived_introduced": derived_introduced,
                "derived_resolved": derived_resolved,
                "reported_introduced": introduced,
                "reported_resolved": resolved,
                "ratio": churn,
                "role": "advisory",
            }
        )
        stop = cycles >= fix_budget
        self.store.update_task(task_id, fix_cycles=cycles, payload_json=payload)
        result = {
            "task_id": task_id,
            "fix_cycles_used": cycles,
            "fix_budget": fix_budget,
            "churn": churn,
            "churn_trend": history,
            "stop_targeted_fixes": stop,
            "reason": "fix_budget_exhausted" if stop else None,
            "reported_metric_role": "advisory_only",
        }
        self.store.event("fix.recorded", result)
        return result

    def evaluate(
        self,
        task_id: str,
        *,
        graph_synchronized: bool,
        worktree_fingerprint: str,
        persist: bool = True,
    ) -> dict[str, Any]:
        task = self._task(task_id)
        criteria = task["criteria"]
        mandatory = [item for item in criteria if item["mandatory"]]
        failed_criteria = [
            item for item in mandatory if item["status"] not in {"pass", "waived"}
        ]
        stale_criteria = [
            item
            for item in mandatory
            if item["status"] == "pass"
            and item["evidence"].get("worktree_fingerprint") != worktree_fingerprint
        ]
        untrusted_criteria = [
            item
            for item in mandatory
            if item["status"] in {"pass", "waived"}
            and evidence_trust(item["evidence"])
            not in FUNCTIONAL_TRUST_TIERS | APPROVAL_TRUST_TIERS
        ]
        verifications = self.store.latest_verifications(task_id)
        required_verifications = [item for item in verifications if item["required"]]
        failed_verifications = [
            item for item in required_verifications if item["result"] != "pass"
        ]
        stale_verifications = [
            item
            for item in required_verifications
            if item["evidence"].get("worktree_fingerprint") != worktree_fingerprint
        ]
        functional_verifications = [
            item
            for item in required_verifications
            if item["kind"] != "policy"
            and evidence_trust(item["evidence"]) in FUNCTIONAL_TRUST_TIERS
        ]
        untrusted_verifications = [
            item
            for item in required_verifications
            if item["kind"] != "policy"
            and evidence_trust(item["evidence"]) not in FUNCTIONAL_TRUST_TIERS
        ]
        missing_verification = not functional_verifications
        issues = self.store.list_issues(task_id, status="open")
        current_task_issues = [item for item in issues if blocks_current_task(item)]
        blockers = [
            item for item in current_task_issues if item["severity"] == "blocker"
        ]
        majors = [item for item in current_task_issues if item["severity"] == "major"]
        follow_up = [item for item in issues if not blocks_current_task(item)]
        deferred = [item for item in issues if item["severity"] in NON_BLOCKING]
        policy_checks = [
            item for item in required_verifications if item["kind"] == "policy"
        ]
        constraints_ok = bool(policy_checks) and all(
            item["result"] == "pass" for item in policy_checks
        )
        high_review_required = task["risk"] == "high" and bool(
            self.config.get("risk", {}).get("high_requires_independent_review", True)
        )
        builder_actor = str(task["payload"].get("builder_actor", "")).strip()
        independent_reviews = [
            item
            for item in task["payload"].get("review_history", [])
            if item.get("actor_id")
            and builder_actor
            and item["actor_id"] != builder_actor
            and item.get("trust_tier") in APPROVAL_TRUST_TIERS
        ]
        review_ok = not high_review_required or bool(independent_reviews)
        shippable = not (
            failed_criteria
            or stale_criteria
            or untrusted_criteria
            or failed_verifications
            or stale_verifications
            or untrusted_verifications
            or missing_verification
            or blockers
            or majors
            or not constraints_ok
            or not graph_synchronized
            or not review_ok
        )
        if shippable:
            status = "SHIPPABLE"
            recommendation = "SHIP"
            if persist:
                self.store.update_task(task_id, status="shippable")
        else:
            status = "BLOCKED"
            effective_fix_budget = min(int(task["fix_budget"]), MAX_FIX_CYCLES)
            budgets_exhausted = task["fix_cycles"] >= effective_fix_budget and bool(
                blockers or majors
            )
            recommendation = (
                "HUMAN_DECISION_OR_RESTORE" if budgets_exhausted else "TARGETED_FIX"
            )
            if persist:
                self.store.update_task(task_id, status="blocked")
        churn_history = task["payload"].get("churn_history", [])
        result = {
            "status": status,
            "task_id": task_id,
            "acceptance_summary": {
                "mandatory_total": len(mandatory),
                "passed": len(mandatory) - len(failed_criteria),
                "waived": [
                    item["id"] for item in mandatory if item["status"] == "waived"
                ],
                "failed_or_pending": [item["id"] for item in failed_criteria],
                "stale": [item["id"] for item in stale_criteria],
                "untrusted": [item["id"] for item in untrusted_criteria],
            },
            "verification_summary": {
                "required_total": len(required_verifications),
                "failed": [item["id"] for item in failed_verifications],
                "stale": [item["id"] for item in stale_verifications],
                "missing": missing_verification,
                "functional_trusted": [item["id"] for item in functional_verifications],
                "untrusted": [item["id"] for item in untrusted_verifications],
            },
            "unresolved_blockers": blockers,
            "unresolved_majors": majors,
            "deferred_minors": deferred,
            "follow_up_issues": follow_up,
            "current_task_issue_summary": {
                "blockers": len(blockers),
                "majors": len(majors),
                "total": len(current_task_issues),
            },
            "follow_up_issue_summary": {
                "total": len(follow_up),
                "major": sum(item["severity"] == "major" for item in follow_up),
                "blocker": sum(item["severity"] == "blocker" for item in follow_up),
            },
            "constraints_ok": constraints_ok,
            "graph_synchronized": graph_synchronized,
            "independent_review_required": high_review_required,
            "independent_review_satisfied": review_ok,
            "builder_actor": builder_actor or None,
            "independent_review_actors": [
                item["actor_id"] for item in independent_reviews
            ],
            "declared_review_actors": [
                item.get("actor_id")
                for item in task["payload"].get("review_history", [])
                if item.get("actor_id")
            ],
            "review_rounds_used": task["review_rounds"],
            "review_budget": min(int(task["review_budget"]), MAX_REVIEW_ROUNDS),
            "fix_cycles_used": task["fix_cycles"],
            "fix_budget": min(int(task["fix_budget"]), MAX_FIX_CYCLES),
            "churn_trend": churn_history,
            "recommendation": recommendation,
            "task_contract": task_contract(task),
        }
        if persist:
            self.store.event(
                "ship.evaluated",
                {
                    "task_id": task_id,
                    "status": status,
                    "recommendation": recommendation,
                },
            )
        return result

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        return task
