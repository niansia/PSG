from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .util import atomic_write_text

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "project": "project",
    "source_of_truth": "git",
    "index": {
        "mode": "incremental",
        "languages": ["python"],
        "exclude": [
            ".git/**",
            ".workgraph/**",
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
        "no_new_blocker_stop_rounds": 2,
        "targeted_fix_limit": 2,
    },
    "risk": {"high_requires_independent_review": True},
    "policies": {"default": "mutable"},
    "verification": {"commands": []},
}

DEFAULT_POLICIES: dict[str, Any] = {
    "version": 1,
    "rules": [
        {
            "pattern": ".workgraph/**",
            "policy": "frozen",
            "reason": "WorkGraph runtime state",
        }
    ],
}


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def state_dir(self) -> Path:
        return self.root / ".workgraph"

    @property
    def config(self) -> Path:
        return self.state_dir / "config.yaml"

    @property
    def policies(self) -> Path:
        return self.state_dir / "policies.yaml"

    @property
    def database(self) -> Path:
        return self.state_dir / "workgraph.db"

    @property
    def events(self) -> Path:
        return self.state_dir / "events.jsonl"


def discover_root(start: str | Path | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".workgraph" / "config.yaml").exists():
            return candidate
    return current


def initialize_config(root: Path, project: str | None = None) -> ProjectPaths:
    paths = ProjectPaths(root.resolve())
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    (paths.state_dir / "cache").mkdir(exist_ok=True)
    (paths.state_dir / "exports").mkdir(exist_ok=True)
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


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing WorkGraph file: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise TypeError(f"Expected a YAML mapping in {path}")
    return value
