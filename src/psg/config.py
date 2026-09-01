from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .util import atomic_write_text

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "enabled": True,
    "project": "project",
    "source_of_truth": "git",
    "authority": {
        "order": [
            "host_mandatory_rules",
            "current_user_instruction",
            "accepted_psg_decisions_and_constraints",
            "repository_native_rules",
            "task_specific_skills",
            "general_skills_and_preferences",
            "psg_heuristics",
            "model_preference",
        ]
    },
    "index": {
        "mode": "incremental",
        "languages": ["python"],
        "exclude": [
            ".git/**",
            ".psg/**",
            ".venv/**",
            "venv/**",
            "node_modules/**",
            "dist/**",
            "build/**",
            "tmp/**",
        ],
    },
    "context": {"default_token_budget": 12000},
    "review": {
        "general_round_limit": 2,
        "targeted_fix_limit": 2,
    },
    "risk": {"high_requires_independent_review": True},
    "policies": {"default": "mutable"},
    "dependencies": {
        "policy": "conservative",
        "prefer": ["standard_library", "native_platform", "existing_dependencies"],
        "new_runtime_dependency_requires_justification": True,
    },
    "verification": {"commands": {}},
}

DEFAULT_POLICIES: dict[str, Any] = {
    "version": 1,
    "rules": [
        {
            "pattern": ".psg/local/**",
            "policy": "frozen",
            "reason": "PSG derived local state",
        }
    ],
}


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def state_dir(self) -> Path:
        return self.root / ".psg"

    @property
    def config(self) -> Path:
        return self.state_dir / "config.yaml"

    @property
    def policies(self) -> Path:
        return self.state_dir / "policies.yaml"

    @property
    def portable_state(self) -> Path:
        return self.state_dir / "state" / "project.yaml"

    @property
    def local_dir(self) -> Path:
        return self.state_dir / "local"

    @property
    def database(self) -> Path:
        return self.local_dir / "psg.db"

    @property
    def events(self) -> Path:
        return self.local_dir / "events.jsonl"


def discover_root(start: str | Path | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".psg" / "config.yaml").exists():
            return candidate
    return current


def initialize_config(root: Path, project: str | None = None) -> ProjectPaths:
    paths = ProjectPaths(root.resolve())
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    paths.local_dir.mkdir(parents=True, exist_ok=True)
    (paths.local_dir / "cache").mkdir(exist_ok=True)
    paths.portable_state.parent.mkdir(parents=True, exist_ok=True)
    local_ignore = paths.state_dir / ".gitignore"
    if not local_ignore.exists():
        atomic_write_text(local_ignore, "local/\n")
    config = yaml.safe_load(yaml.safe_dump(DEFAULT_CONFIG))
    config["project"] = project or root.name
    if not paths.config.exists():
        atomic_write_text(
            paths.config, yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
        )
    if not paths.policies.exists():
        atomic_write_text(
            paths.policies,
            yaml.safe_dump(DEFAULT_POLICIES, sort_keys=False, allow_unicode=True),
        )
    return paths


def save_yaml(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, yaml.safe_dump(value, sort_keys=False, allow_unicode=True))


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing PSG file: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise TypeError(f"Expected a YAML mapping in {path}")
    return value
