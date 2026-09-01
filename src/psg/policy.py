from __future__ import annotations

import fnmatch
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import git
from .store import Store
from .trust import is_user_approved
from .util import normalize_path, sha256_bytes

VALID_POLICIES = {"mutable", "read_only", "interface_locked", "frozen"}
POLICY_RANK = {"mutable": 0, "interface_locked": 1, "read_only": 2, "frozen": 3}
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_PYTHON_CONTRACT = re.compile(r"^[+-]\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")
_OTHER_CONTRACT = re.compile(
    r"^[+-].*\b(?:export|public|interface|type|schema)\b", re.IGNORECASE
)
_DEPENDENCY_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "Pipfile",
    "Cargo.toml",
    "go.mod",
}
_MANAGED_STATE_PREFIXES = (".psg/local/", ".psg/state/")
_GOVERNANCE_PATHS = {
    ".psg/.gitignore",
    ".psg/config.yaml",
    ".psg/policies.yaml",
}


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int


@dataclass
class FileChange:
    old_path: str
    new_path: str
    lines: list[str] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path if self.new_path != "/dev/null" else self.old_path

    @property
    def scope_paths(self) -> list[str]:
        return list(
            dict.fromkeys(
                path for path in (self.old_path, self.new_path) if path != "/dev/null"
            )
        )


def _diff_path(value: str) -> str:
    if value == "/dev/null":
        return value
    return normalize_path(value[2:] if value.startswith(("a/", "b/")) else value)


def parse_diff(diff_text: str) -> list[FileChange]:
    changes: list[FileChange] = []
    current: FileChange | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            try:
                parts = shlex.split(line[len("diff --git ") :])
            except ValueError:
                parts = []
            if len(parts) >= 2:
                current = FileChange(_diff_path(parts[0]), _diff_path(parts[1]))
                changes.append(current)
            else:
                current = None
            continue
        if current is None:
            continue
        current.lines.append(line)
        match = _HUNK.match(line)
        if match:
            current.hunks.append(
                Hunk(
                    old_start=int(match.group(1)),
                    old_count=int(match.group(2) or 1),
                    new_start=int(match.group(3)),
                    new_count=int(match.group(4) or 1),
                )
            )
    return changes


def changed_paths(diff_text: str) -> list[str]:
    return [change.path for change in parse_diff(diff_text)]


def _intersects(start: int, count: int, line_start: int, line_end: int) -> bool:
    if count == 0:
        return line_start <= start <= line_end + 1
    return max(start, line_start) <= min(start + count - 1, line_end)


def _toml_section_values(text: str, section: str) -> set[str]:
    values: set[str] = set()
    active = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("[") and line.endswith("]"):
            active = line[1:-1].strip() == section
            continue
        if active and "=" in line:
            values.add(line.split("=", 1)[0].strip().strip('"').lower())
    return values


def _pyproject_dependencies(text: str) -> set[str]:
    values: set[str] = set()
    in_project = False
    in_dependencies = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            in_dependencies = False
            continue
        if (
            in_project
            and not in_dependencies
            and re.match(r"^dependencies\s*=\s*\[", line)
        ):
            in_dependencies = True
            line = line.split("[", 1)[1]
        if in_dependencies:
            for value in re.findall(r'["\']([^"\']+)["\']', line):
                values.add(value.strip().lower())
            if "]" in line:
                in_dependencies = False
    return values


def _go_dependencies(text: str) -> set[str]:
    values: set[str] = set()
    in_block = False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if line == "require (":
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        match = re.match(r"(?:require\s+)?([^\s]+)\s+(v[^\s]+)", line)
        if match and (in_block or line.startswith("require ")):
            values.add(f"{match.group(1).lower()}@{match.group(2)}")
    return values


def _runtime_dependencies(path: str, text: str) -> set[str]:
    name = Path(path).name
    if name == "requirements.txt":
        return {
            line.split("#", 1)[0].strip().lower()
            for line in text.splitlines()
            if line.split("#", 1)[0].strip()
        }
    if name == "pyproject.toml":
        return _pyproject_dependencies(text)
    if name == "package.json":
        try:
            dependencies = json.loads(text or "{}").get("dependencies", {})
            return {f"{key.lower()}@{value}" for key, value in dependencies.items()}
        except (AttributeError, json.JSONDecodeError):
            return set()
    if name == "Cargo.toml":
        return _toml_section_values(text, "dependencies")
    if name == "Pipfile":
        return _toml_section_values(text, "packages")
    if name == "go.mod":
        return _go_dependencies(text)
    return set()


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
        candidates: list[tuple[str, str]] = []
        node = self.store.get_node(f"file:{normalized}")
        if node:
            candidates.append(
                (str(node.get("policy", "mutable")), f"node:{node['id']}")
            )
            candidates.extend(self._edge_policies(node["id"]))
        for rule in self.policies.get("rules", []):
            if fnmatch.fnmatch(normalized, str(rule.get("pattern", ""))):
                candidates.append(
                    (
                        str(rule.get("policy", "mutable")),
                        str(rule.get("reason", "policy rule")),
                    )
                )
        if not candidates:
            candidates.append(
                (
                    str(self.config.get("policies", {}).get("default", "mutable")),
                    "default",
                )
            )
        return max(candidates, key=lambda item: POLICY_RANK.get(item[0], 0))

    def effective_node_policy(self, node_id: str) -> tuple[str, str]:
        node = self.store.get_node(node_id)
        if not node:
            return "mutable", "missing_node"
        candidates = [(str(node.get("policy", "mutable")), f"node:{node_id}")]
        candidates.extend(self._edge_policies(node_id))
        return max(candidates, key=lambda item: POLICY_RANK.get(item[0], 0))

    def _edge_policies(self, node_id: str) -> list[tuple[str, str]]:
        values: list[tuple[str, str]] = []
        for edge in self.store.edges_for([node_id], both=True):
            if edge["dst"] != node_id:
                continue
            if edge.get("provenance") not in {
                "user_approved",
                "external_attested",
            }:
                continue
            source = self.store.get_node(edge["src"])
            if not is_user_approved(source):
                continue
            if edge["type"] == "locks":
                values.append(("frozen", f"edge:{edge['src']}:locks"))
            elif edge["type"] == "constrained-by":
                effect = (source or {}).get("payload", {}).get("mutation_effect")
                normalized = {
                    "freeze": "frozen",
                    "frozen": "frozen",
                    "read_only": "read_only",
                    "interface_locked": "interface_locked",
                }.get(str(effect))
                if normalized:
                    values.append((normalized, f"edge:{edge['src']}:constrained-by"))
        return values

    def affected_symbols(self, change: FileChange) -> list[dict[str, Any]]:
        paths = set(change.scope_paths)
        symbols = [
            node
            for node in self.store.list_nodes("Symbol")
            if normalize_path(str(node.get("source", {}).get("path", ""))) in paths
        ]
        if not change.hunks:
            return symbols
        affected: list[dict[str, Any]] = []
        for symbol in symbols:
            payload = symbol.get("payload", {})
            line_start = int(payload.get("line_start", 1))
            line_end = int(payload.get("line_end", line_start))
            if any(
                _intersects(hunk.old_start, hunk.old_count, line_start, line_end)
                or _intersects(hunk.new_start, hunk.new_count, line_start, line_end)
                for hunk in change.hunks
            ):
                affected.append(symbol)
        return affected

    def validate(
        self, task_id: str, diff_text: str, *, phase: str = "postflight"
    ) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        changes = parse_diff(diff_text)
        managed_state: list[str] = []
        product_changes: list[FileChange] = []
        for change in changes:
            scope_paths = change.scope_paths
            runtime_managed = bool(scope_paths) and all(
                path.startswith(_MANAGED_STATE_PREFIXES) for path in scope_paths
            )
            unchanged_setup = self._unchanged_governance(task, change)
            if runtime_managed or unchanged_setup:
                managed_state.extend(scope_paths)
            else:
                product_changes.append(change)
        changes = product_changes
        working_set = task.get("payload", {}).get("working_set", {})
        write = set(working_set.get("write", []))
        read_only = set(working_set.get("read_only", []))
        forbidden = set(working_set.get("forbidden", []))
        violations: list[dict[str, Any]] = []
        contract_changes: list[dict[str, Any]] = []
        scope_expansion: list[str] = []
        touched_nodes: list[str] = []

        current_revision = git.revision(self.root)
        if task["baseline_git_rev"] != current_revision:
            violations.append(
                {
                    "kind": "stale_working_set",
                    "path": None,
                    "message": "Git HEAD changed after task context creation; rebuild context before applying.",
                    "expected": task["baseline_git_rev"],
                    "actual": current_revision,
                }
            )

        for change in changes:
            path = change.path
            touched_nodes.append(f"file:{path}")
            file_policies = [
                self.effective_policy(candidate) for candidate in change.scope_paths
            ]
            policy, source = max(
                file_policies or [("mutable", "default")],
                key=lambda item: POLICY_RANK.get(item[0], 0),
            )
            symbols = self.affected_symbols(change)
            symbol_policies = [
                (symbol, *self.effective_node_policy(symbol["id"]))
                for symbol in symbols
            ]
            touched_nodes.extend(symbol["id"] for symbol in symbols)
            strict_symbols = [
                {"id": symbol["id"], "policy": node_policy, "source": node_source}
                for symbol, node_policy, node_source in symbol_policies
                if node_policy in {"frozen", "read_only"}
            ]
            if strict_symbols:
                violations.append(
                    {
                        "kind": "symbol_policy_violation",
                        "path": path,
                        "symbols": strict_symbols,
                    }
                )
                continue
            if (
                any(candidate in forbidden for candidate in change.scope_paths)
                or policy == "frozen"
            ):
                violations.append(
                    {
                        "kind": "forbidden_or_frozen",
                        "path": path,
                        "policy": policy,
                        "source": source,
                    }
                )
                continue
            if (
                any(candidate in read_only for candidate in change.scope_paths)
                or policy == "read_only"
            ):
                violations.append(
                    {
                        "kind": "read_only",
                        "path": path,
                        "policy": policy,
                        "source": source,
                    }
                )
                continue
            outside = [
                candidate for candidate in change.scope_paths if candidate not in write
            ]
            if outside:
                scope_expansion.extend(outside)
                violations.append(
                    {
                        "kind": "outside_write_scope",
                        "path": path,
                        "paths": outside,
                        "message": "Request context expansion before modifying this path.",
                    }
                )
                continue

            interface_sources = [
                node_source
                for _symbol, node_policy, node_source in symbol_policies
                if node_policy == "interface_locked"
            ]
            if policy == "interface_locked" or interface_sources:
                contract = self._contract_changes(change)
                contract_changes.extend(
                    {"path": path, "line": line} for line in contract
                )
                if contract:
                    violations.append(
                        {
                            "kind": "interface_locked",
                            "path": path,
                            "changes": contract,
                            "source": interface_sources or [source],
                        }
                    )

            if self._dependency_change(change) and not task.get("payload", {}).get(
                "dependency_justifications"
            ):
                dependency = self.config.get("dependencies", {})
                if dependency.get(
                    "new_runtime_dependency_requires_justification", True
                ):
                    violations.append(
                        {
                            "kind": "new_dependency_requires_justification",
                            "path": path,
                            "policy": dependency.get("policy", "conservative"),
                        }
                    )

        result = {
            "allowed": not violations,
            "phase": phase,
            "task_id": task_id,
            "git_revision": current_revision,
            "graph_revision": self.store.graph_revision(),
            "violations": violations,
            "touched_nodes": list(dict.fromkeys(touched_nodes)),
            "managed_state_paths": managed_state,
            "contract_changes": contract_changes,
            "required_scope_expansion": list(dict.fromkeys(scope_expansion)),
        }
        self.store.event("patch.validated", result)
        return result

    def _unchanged_governance(self, task: dict[str, Any], change: FileChange) -> bool:
        paths = change.scope_paths
        if not paths or not all(path in _GOVERNANCE_PATHS for path in paths):
            return False
        baseline = task.get("payload", {}).get("governance_baseline", {})
        for relative in paths:
            path = self.root / relative
            current = sha256_bytes(path.read_bytes()) if path.is_file() else None
            if baseline.get(relative) != current:
                return False
        return True

    @staticmethod
    def _contract_changes(change: FileChange) -> list[str]:
        values: list[str] = []
        for line in change.lines:
            if line.startswith(("+++", "---")):
                continue
            python_match = _PYTHON_CONTRACT.match(line)
            if (
                python_match
                and not python_match.group(1).startswith("_")
                or _OTHER_CONTRACT.match(line)
            ):
                values.append(line[:300])
        return values

    def _dependency_change(self, change: FileChange) -> bool:
        old_name = Path(change.old_path).name
        new_name = Path(change.new_path).name
        if old_name not in _DEPENDENCY_FILES and new_name not in _DEPENDENCY_FILES:
            return False
        old_text = (
            git.run_git(self.root, "show", f"HEAD:{change.old_path}", check=False)
            if change.old_path != "/dev/null"
            else ""
        )
        current_path = self.root / change.new_path
        try:
            new_text = (
                current_path.read_text(encoding="utf-8")
                if change.new_path != "/dev/null" and current_path.is_file()
                else ""
            )
        except (OSError, UnicodeDecodeError):
            return True
        old_dependencies = _runtime_dependencies(change.old_path, old_text)
        new_dependencies = _runtime_dependencies(change.new_path, new_text)
        return bool(new_dependencies - old_dependencies)
