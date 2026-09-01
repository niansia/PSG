from __future__ import annotations

from typing import Any

from .store import Store

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
    ) -> dict[str, Any]:
        task = self._task(task_id)
        rounds = task["review_rounds"] + 1
        no_new = task["no_new_blocking_rounds"] + 1 if new_blocking_issues == 0 else 0
        payload = task["payload"]
        payload.setdefault("review_history", []).append(
            {
                "round": rounds,
                "actor_id": (actor_id or "").strip(),
                "session_id": (session_id or "").strip(),
                "model_family": (model_family or "").strip(),
                "new_blocking_issues": new_blocking_issues,
            }
        )
        self.store.update_task(
            task_id,
            review_rounds=rounds,
            no_new_blocking_rounds=no_new,
            payload_json=payload,
        )
        stop = rounds >= task["review_budget"] or no_new >= int(
            self.config.get("review", {}).get("no_new_blocker_stop_rounds", 2)
        )
        result = {
            "task_id": task_id,
            "review_rounds_used": rounds,
            "review_budget": task["review_budget"],
            "no_new_blocking_rounds": no_new,
            "stop_general_review": stop,
            "reason": "budget_exhausted"
            if rounds >= task["review_budget"]
            else ("no_new_blocker_rule" if stop else None),
            "actor_id": (actor_id or "").strip(),
            "session_id": (session_id or "").strip(),
            "model_family": (model_family or "").strip(),
        }
        self.store.event("review.recorded", result)
        return result

    def fix_record(
        self, task_id: str, introduced: int, resolved: int
    ) -> dict[str, Any]:
        task = self._task(task_id)
        cycles = task["fix_cycles"] + 1
        churn = introduced / max(1, resolved)
        payload = task["payload"]
        history = payload.setdefault("churn_history", [])
        history.append(
            {
                "cycle": cycles,
                "introduced": introduced,
                "resolved": resolved,
                "ratio": churn,
            }
        )
        not_improving = (
            len(history) >= 2
            and history[-1]["ratio"] >= history[-2]["ratio"]
            and resolved <= introduced
        )
        stop = cycles >= task["fix_budget"] or not_improving
        self.store.update_task(task_id, fix_cycles=cycles, payload_json=payload)
        result = {
            "task_id": task_id,
            "fix_cycles_used": cycles,
            "fix_budget": task["fix_budget"],
            "churn": churn,
            "churn_trend": history,
            "stop_targeted_fixes": stop,
            "reason": "fix_budget_exhausted"
            if cycles >= task["fix_budget"]
            else ("churn_not_improving" if stop else None),
        }
        self.store.event("fix.recorded", result)
        return result

    def evaluate(
        self,
        task_id: str,
        *,
        graph_synchronized: bool,
        worktree_fingerprint: str,
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
        trusted_sources = {"runtime_executed", "external_tool"}
        functional_verifications = [
            item
            for item in required_verifications
            if item["kind"] != "policy"
            and item["evidence"].get("source") in trusted_sources
        ]
        untrusted_verifications = [
            item
            for item in required_verifications
            if item["kind"] != "policy"
            and item["evidence"].get("source") not in trusted_sources
        ]
        missing_verification = not functional_verifications
        issues = self.store.list_issues(task_id, status="open")
        blockers = [item for item in issues if item["severity"] == "blocker"]
        majors = [item for item in issues if item["severity"] == "major"]
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
        ]
        review_ok = not high_review_required or bool(independent_reviews)
        shippable = not (
            failed_criteria
            or stale_criteria
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
            self.store.update_task(task_id, status="shippable")
        else:
            status = "BLOCKED"
            budgets_exhausted = task["fix_cycles"] >= task["fix_budget"] and bool(
                blockers or majors
            )
            recommendation = (
                "HUMAN_DECISION_OR_RESTORE" if budgets_exhausted else "TARGETED_FIX"
            )
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
            "constraints_ok": constraints_ok,
            "graph_synchronized": graph_synchronized,
            "independent_review_required": high_review_required,
            "independent_review_satisfied": review_ok,
            "builder_actor": builder_actor or None,
            "independent_review_actors": [
                item["actor_id"] for item in independent_reviews
            ],
            "review_rounds_used": task["review_rounds"],
            "review_budget": task["review_budget"],
            "fix_cycles_used": task["fix_cycles"],
            "fix_budget": task["fix_budget"],
            "churn_trend": churn_history,
            "recommendation": recommendation,
        }
        self.store.event(
            "ship.evaluated",
            {"task_id": task_id, "status": status, "recommendation": recommendation},
        )
        return result

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        return task
