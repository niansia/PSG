from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from . import git
from .store import Store
from .util import normalize_path

VALID_POLICIES = {"mutable", "read_only", "interface_locked", "frozen"}
_DIFF_FILE = re.compile(r"^diff --git a/(.+?) b/(.+?)$")
_PYTHON_CONTRACT = re.compile(r"^[+-]\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")
_OTHER_CONTRACT = re.compile(
    r"^[+-].*\b(?:export|public|interface|type|schema)\b", re.IGNORECASE
)


def changed_paths(diff_text: str) -> list[str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        match = _DIFF_FILE.match(line)
        if match:
            old, new = match.groups()
            selected = new if new != "/dev/null" else old
            paths.append(normalize_path(selected))
    return list(dict.fromkeys(paths))


class PolicyEngine:
    def __init__(
        self,
        root: Path,
        store: Store,
        config: dict[str, Any],
        policies: dict[str, Any],
    ):
        self.root = root
        self.store = store
        self.config = config
        self.policies = policies

    def effective_policy(self, path: str) -> tuple[str, str]:
        normalized = normalize_path(path)
        node = self.store.get_node(f"file:{normalized}")
        explicit = node.get("policy") if node else None
        if explicit and explicit != "mutable":
            return explicit, f"node:{node['id']}"
        for rule in self.policies.get("rules", []):
            if fnmatch.fnmatch(normalized, str(rule.get("pattern", ""))):
                return str(rule.get("policy", "mutable")), str(
                    rule.get("reason", "policy rule")
                )
        return str(
            explicit or self.config.get("policies", {}).get("default", "mutable")
        ), "default"

    def validate(
        self, task_id: str, diff_text: str, *, phase: str = "postflight"
    ) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        touched = changed_paths(diff_text)
        working_set = task.get("payload", {}).get("working_set", {})
        write = set(working_set.get("write", []))
        read_only = set(working_set.get("read_only", []))
        forbidden = set(working_set.get("forbidden", []))
        violations: list[dict[str, Any]] = []
        contract_changes: list[dict[str, Any]] = []
        scope_expansion: list[str] = []

        current_revision = git.revision(self.root)
        if task["baseline_git_rev"] != current_revision:
            violations.append(
                {
                    "kind": "stale_working_set",
                    "path": None,
                    "message": "Git HEAD changed after the task context was created; rebuild context before applying.",
                    "expected": task["baseline_git_rev"],
                    "actual": current_revision,
                }
            )

        for path in touched:
            policy, source = self.effective_policy(path)
            if path in forbidden or policy == "frozen":
                violations.append(
                    {
                        "kind": "forbidden_or_frozen",
                        "path": path,
                        "policy": policy,
                        "source": source,
                    }
                )
                continue
            if path in read_only or policy == "read_only":
                violations.append(
                    {
                        "kind": "read_only",
                        "path": path,
                        "policy": policy,
                        "source": source,
                    }
                )
                continue
            if path not in write:
                scope_expansion.append(path)
                violations.append(
                    {
                        "kind": "outside_write_scope",
                        "path": path,
                        "message": "Request context expansion before modifying this file.",
                    }
                )
                continue
            if policy == "interface_locked":
                changes = self._contract_changes(diff_text, path)
                contract_changes.extend(
                    {"path": path, "line": line} for line in changes
                )
                if changes:
                    violations.append(
                        {
                            "kind": "interface_locked",
                            "path": path,
                            "changes": changes,
                            "source": source,
                        }
                    )

        result = {
            "allowed": not violations,
            "phase": phase,
            "task_id": task_id,
            "git_revision": current_revision,
            "graph_revision": self.store.graph_revision(),
            "violations": violations,
            "touched_nodes": [f"file:{path}" for path in touched],
            "contract_changes": contract_changes,
            "required_scope_expansion": scope_expansion,
        }
        self.store.event("patch.validated", result)
        return result

    @staticmethod
    def _contract_changes(diff_text: str, path: str) -> list[str]:
        active = False
        changes: list[str] = []
        for line in diff_text.splitlines():
            match = _DIFF_FILE.match(line)
            if match:
                old, new = match.groups()
                active = path in {normalize_path(old), normalize_path(new)}
                continue
            if not active or line.startswith(("+++", "---")):
                continue
            python_match = _PYTHON_CONTRACT.match(line)
            if (
                python_match
                and not python_match.group(1).startswith("_")
                or _OTHER_CONTRACT.match(line)
            ):
                changes.append(line[:300])
        return changes
