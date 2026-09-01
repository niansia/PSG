from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from .indexer import Indexer
from .policy import PolicyEngine
from .store import Store
from .util import canonical_json, normalize_path


class ContextRouter:
    def __init__(
        self,
        root: Path,
        store: Store,
        indexer: Indexer,
        policy: PolicyEngine,
        config: dict[str, Any],
    ):
        self.root = root
        self.store = store
        self.indexer = indexer
        self.policy = policy
        self.config = config

    def build(
        self,
        task_id: str,
        max_tokens: int | None = None,
        *,
        _auto_expand: bool = True,
    ) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        payload = task["payload"]
        targets = payload.get("targets", [])
        start_nodes = self._resolve_targets(targets)
        if not start_nodes:
            start_nodes = self._intent_fallback(task["intent"])
        hops = (
            1
            + int(payload.get("expansion_hops", 0))
            + (1 if task["risk"] == "high" else 0)
        )
        selected_ids, distance = self._traverse(
            [node["id"] for node in start_nodes], min(hops, 4)
        )
        selected_nodes = [
            node for node_id in selected_ids if (node := self.store.get_node(node_id))
        ]

        file_nodes: dict[str, dict[str, Any]] = {}
        for node in selected_nodes:
            path = node.get("source", {}).get("path")
            if path:
                file_node = self.store.get_node(f"file:{normalize_path(path)}")
                if file_node:
                    file_nodes[normalize_path(path)] = file_node
        for node in start_nodes:
            path = node.get("source", {}).get("path")
            if path and node["type"] == "File":
                file_nodes[normalize_path(path)] = node

        explicit_write = {normalize_path(item) for item in payload.get("write", [])}
        explicit_read_only = {
            normalize_path(item) for item in payload.get("read_only", [])
        }
        explicit_forbidden = {
            normalize_path(item) for item in payload.get("forbidden", [])
        }
        target_paths = {
            normalize_path(node["source"]["path"])
            for node in start_nodes
            if node.get("source", {}).get("path")
        }
        read: list[str] = []
        write: list[str] = []
        read_only: list[str] = []
        forbidden: list[str] = []
        rationale: dict[str, str] = {}
        for path, node in sorted(file_nodes.items()):
            effective, source = self.policy.effective_policy(path)
            if path in explicit_forbidden or effective == "frozen":
                forbidden.append(path)
                rationale[path] = f"{effective} boundary ({source})"
            elif path in explicit_read_only or effective == "read_only":
                read_only.append(path)
                rationale[path] = f"read-only boundary ({source})"
            elif path in explicit_write or path in target_paths:
                write.append(path)
                rationale[path] = "explicit/target write scope"
            else:
                read.append(path)
                rationale[path] = (
                    "dependency, reverse dependency, contract, or verification context"
                )

        for path in sorted(explicit_forbidden - set(forbidden)):
            forbidden.append(path)
            rationale[path] = "explicit forbidden scope"
        for path in sorted(explicit_read_only - set(read_only) - set(forbidden)):
            read_only.append(path)
            rationale[path] = "explicit read-only scope"
        for path in sorted(
            explicit_write - set(write) - set(read_only) - set(forbidden)
        ):
            write.append(path)
            rationale[path] = "explicit write scope"

        confidence = self._confidence(file_nodes.values())
        if confidence < 0.60 and hops < 3 and _auto_expand:
            payload["expansion_hops"] = min(
                int(payload.get("expansion_hops", 0)) + 1, 3
            )
            payload.setdefault("expansion_reasons", []).append(
                "automatic bounded expansion after low-confidence routing"
            )
            self.store.update_task(task_id, payload_json=payload)
            self.store.event(
                "context.auto_expanded",
                {"task_id": task_id, "initial_confidence": confidence, "hops": 1},
            )
            return self.build(task_id, max_tokens=max_tokens, _auto_expand=False)
        items = self._pack_context(
            selected_nodes, distance, max_tokens or task["context_budget"]
        )
        working_set = {
            "read": sorted(set(read)),
            "write": sorted(set(write)),
            "read_only": sorted(set(read_only)),
            "forbidden": sorted(set(forbidden)),
            "rationale": rationale,
        }
        payload["working_set"] = working_set
        payload["context_confidence"] = confidence
        payload["context_node_ids"] = [item["id"] for item in items]
        self.store.update_task(
            task_id,
            payload_json=payload,
            graph_rev=self.store.graph_revision(),
        )
        result = {
            "git_revision": task["baseline_git_rev"],
            "graph_revision": self.store.graph_revision(),
            "confidence": confidence,
            "task_brief": {
                "id": task_id,
                "intent": task["intent"],
                "risk": task["risk"],
                "acceptance_criteria": task["criteria"],
                "constraints": payload.get("constraints", []),
                "non_goals": payload.get("non_goals", []),
            },
            "working_set": working_set,
            "context_items": items,
            "token_estimate": sum(item["token_estimate"] for item in items),
            "context_budget": max_tokens or task["context_budget"],
        }
        self.store.event(
            "context.built",
            {
                "task_id": task_id,
                "confidence": confidence,
                "working_set": working_set,
                "token_estimate": result["token_estimate"],
            },
        )
        return result

    def expand(self, task_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError(
                "Context expansion requires a concrete reason or evidence."
            )
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        payload = task["payload"]
        payload["expansion_hops"] = min(int(payload.get("expansion_hops", 0)) + 1, 3)
        payload.setdefault("expansion_reasons", []).append(reason.strip())
        self.store.update_task(task_id, payload_json=payload)
        self.store.event(
            "context.expanded",
            {"task_id": task_id, "reason": reason, "hops": payload["expansion_hops"]},
        )
        return self.build(task_id)

    def _resolve_targets(self, targets: list[str]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for target in targets:
            normalized = normalize_path(target)
            candidates = [target, f"file:{normalized}"]
            for candidate in candidates:
                node = self.store.get_node(candidate)
                if node:
                    nodes.append(node)
                    break
        return list({node["id"]: node for node in nodes}.values())

    def _intent_fallback(self, intent: str) -> list[dict[str, Any]]:
        words = {
            word.lower()
            for word in intent.replace("_", " ").replace("-", " ").split()
            if len(word) >= 3
        }
        scored: list[tuple[int, dict[str, Any]]] = []
        for node in self.store.list_nodes("File"):
            title = node["title"].lower()
            score = sum(word in title for word in words)
            if score:
                scored.append((score, node))
        return [
            node
            for _, node in sorted(scored, key=lambda pair: (-pair[0], pair[1]["id"]))[
                :5
            ]
        ]

    def _traverse(
        self, starts: list[str], max_hops: int
    ) -> tuple[list[str], dict[str, int]]:
        queue = deque((node_id, 0) for node_id in starts)
        distance: dict[str, int] = {node_id: 0 for node_id in starts}
        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for edge in self.store.edges_for([node_id], both=True):
                if edge["type"] not in {
                    "depends-on",
                    "consumed-by",
                    "constrained-by",
                    "verified-by",
                    "locks",
                    "contains",
                }:
                    continue
                other = edge["dst"] if edge["src"] == node_id else edge["src"]
                if other not in distance:
                    distance[other] = depth + 1
                    queue.append((other, depth + 1))
        return list(distance), distance

    def _confidence(self, nodes: Any) -> float:
        nodes = list(nodes)
        if not nodes:
            return 0.0
        freshness = sum(self.indexer.freshness(node) for node in nodes) / len(nodes)
        coverage = sum(
            1.0 if node["payload"].get("language") == "python" else 0.7
            for node in nodes
        ) / len(nodes)
        provenance = sum(float(node.get("confidence", 0.5)) for node in nodes) / len(
            nodes
        )
        dependency_certainty = (
            0.95 if self.store.edges_for([node["id"] for node in nodes]) else 0.65
        )
        return round(freshness * coverage * provenance * dependency_certainty, 3)

    @staticmethod
    def _pack_context(
        nodes: list[dict[str, Any]], distance: dict[str, int], budget: int
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for node in nodes:
            compact = {
                "id": node["id"],
                "type": node["type"],
                "title": node["title"],
                "policy": node["policy"],
                "maturity": node["maturity"],
                "source": node["source"],
                "revision": node["revision"],
                "confidence": node["confidence"],
                "summary": node["payload"],
            }
            estimate = max(1, len(canonical_json(compact)) // 4)
            relevance = 1.0 / (1 + distance.get(node["id"], 3))
            criticality = (
                1.0
                if node["policy"] in {"frozen", "interface_locked", "read_only"}
                else 0.5
            )
            score = round(
                4 * relevance
                + 2 * criticality
                + float(node["confidence"])
                - estimate / max(budget, 1),
                4,
            )
            compact["token_estimate"] = estimate
            compact["score"] = score
            candidates.append(compact)
        candidates.sort(key=lambda item: (-item["score"], item["id"]))
        packed: list[dict[str, Any]] = []
        used = 0
        for item in candidates:
            mandatory = distance.get(item["id"], 9) == 0 or item["policy"] in {
                "frozen",
                "interface_locked",
                "read_only",
            }
            if mandatory or used + item["token_estimate"] <= budget:
                packed.append(item)
                used += item["token_estimate"]
        return packed
