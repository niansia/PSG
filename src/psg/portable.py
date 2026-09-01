from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .store import Store
from .util import atomic_write_text, sha256_text, utc_now


class PortableState:
    """Git-committable state projection with SQLite as the derived local index."""

    META_KEY = "portable_state_hash"

    def __init__(self, path: Path, store: Store):
        self.path = path
        self.store = store

    def sync_to_store(self) -> dict[str, Any]:
        if not self.path.exists():
            self.export_from_store()
            return {"created": True, "imported": False}
        text = self.path.read_text(encoding="utf-8")
        digest = sha256_text(text)
        if self.store.get_meta(self.META_KEY) == digest:
            return {"created": False, "imported": False}
        value = yaml.safe_load(text) or {}
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError(f"Unsupported PSG portable state: {self.path}")
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

    def export_from_store(self) -> dict[str, Any]:
        state = self.store.export_portable()
        state["generated_at"] = utc_now()
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
