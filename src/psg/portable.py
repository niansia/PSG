from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import git
from .store import Store
from .util import atomic_write_text, sha256_text, utc_now


class PortableStateTrustError(RuntimeError):
    pass


class PortableState:
    """Git-committable state projection with SQLite as the derived local index."""

    META_KEY = "portable_state_hash"

    def __init__(self, path: Path, store: Store):
        self.path = path
        self.store = store
        self.root = path.parents[2]

    def sync_to_store(self) -> dict[str, Any]:
        if not self.path.exists():
            self.export_from_store()
            return {"created": True, "imported": False}
        text = self.path.read_text(encoding="utf-8")
        digest = sha256_text(text)
        value = self._load(text)
        self._validate_config(value)
        if self.store.get_meta(self.META_KEY) == digest:
            return {"created": False, "imported": False}
        if self._git_dirty():
            raise PortableStateTrustError(
                "Portable PSG state changed outside the runtime while Git marks it "
                "dirty. It was not imported. Review the diff, then run "
                "'psg state accept --reason \"...\"' from an explicit user shell "
                "if the change is intended."
            )
        self.store.merge_portable(value)
        self.store.set_meta(self.META_KEY, digest)
        self.store.event(
            "portable_state.imported",
            {
                "path": str(self.path),
                "nodes": len(value.get("nodes", [])),
                "tasks": len(value.get("tasks", [])),
            },
        )
        return {"created": False, "imported": True}

    def accept_current(self, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("Accepting portable state requires an explicit reason.")
        if not self.path.exists():
            raise FileNotFoundError(f"Missing PSG portable state: {self.path}")
        text = self.path.read_text(encoding="utf-8")
        value = self._load(text)
        value["config_hash"] = self._config_hash()
        value["generated_at"] = utc_now()
        rendered = yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
        atomic_write_text(self.path, rendered)
        text = rendered
        digest = sha256_text(text)
        self.store.merge_portable(value)
        self.store.set_meta(self.META_KEY, digest)
        self.store.event(
            "portable_state.user_approved",
            {
                "path": str(self.path),
                "hash": digest,
                "reason": reason.strip(),
                "git_dirty": self._git_dirty(),
            },
        )
        return {
            "accepted": True,
            "path": str(self.path),
            "hash": digest,
            "reason": reason.strip(),
            "nodes": len(value.get("nodes", [])),
            "tasks": len(value.get("tasks", [])),
        }

    def export_from_store(self) -> dict[str, Any]:
        state = self.store.export_portable()
        state["generated_at"] = utc_now()
        state["config_hash"] = self._config_hash()
        rendered = yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
        atomic_write_text(self.path, rendered)
        digest = sha256_text(rendered)
        self.store.set_meta(self.META_KEY, digest)
        return {
            "path": str(self.path),
            "hash": digest,
            "nodes": len(state.get("nodes", [])),
            "tasks": len(state.get("tasks", [])),
        }

    def _git_dirty(self) -> bool:
        relative = self.path.relative_to(self.root).as_posix()
        return bool(
            git.run_git(
                self.root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                relative,
                check=False,
            ).strip()
        )

    def _config_hash(self) -> str:
        config = self.root / ".psg" / "config.yaml"
        return sha256_text(config.read_text(encoding="utf-8"))

    def _validate_config(self, state: dict[str, Any]) -> None:
        expected = state.get("config_hash")
        if expected == self._config_hash():
            return
        dirty = self._config_dirty()
        if not expected and not dirty:
            return
        if dirty:
            raise PortableStateTrustError(
                "PSG configuration changed outside the runtime while Git marks it "
                "dirty. Configured verification commands were not trusted. Review "
                "both .psg/config.yaml and .psg/state/project.yaml, then use the "
                "explicit 'psg state accept --reason \"...\"' user action if intended."
            )

    def _config_dirty(self) -> bool:
        return bool(
            git.run_git(
                self.root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                ".psg/config.yaml",
                check=False,
            ).strip()
        )

    def _load(self, text: str) -> dict[str, Any]:
        value = yaml.safe_load(text) or {}
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError(f"Unsupported PSG portable state: {self.path}")
        return value
