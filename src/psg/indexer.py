from __future__ import annotations

import ast
import fnmatch
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import git
from .store import Store
from .util import sha256_bytes

_DEBT_MARKER = re.compile(r"psg-debt:\s*(.+)$", re.IGNORECASE)


@dataclass
class IndexResult:
    revision: str
    scanned: int
    indexed: int
    unchanged: int
    removed: int
    symbols: int
    dependencies: int
    unsupported: int
    errors: list[dict[str, str]]

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.symbols: list[dict[str, Any]] = []
        self.imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.update(alias.name for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.add(node.module)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_symbol(node, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_symbol(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_symbol(node, "async_function")

    def _visit_symbol(self, node: ast.AST, kind: str) -> None:
        name = node.name
        qualified = ".".join([*self.stack, name])
        signature = self._signature(node, name, kind)
        self.symbols.append(
            {
                "name": name,
                "qualname": qualified,
                "kind": kind,
                "signature": signature,
                "line_start": getattr(node, "lineno", 1),
                "line_end": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                "public": not name.startswith("_"),
            }
        )
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    @staticmethod
    def _signature(node: ast.AST, name: str, kind: str) -> str:
        if kind == "class":
            bases = [ast.unparse(base) for base in getattr(node, "bases", [])]
            return f"class {name}({', '.join(bases)})" if bases else f"class {name}"
        arguments = ast.unparse(node.args)
        prefix = "async def" if kind == "async_function" else "def"
        returns = getattr(node, "returns", None)
        suffix = f" -> {ast.unparse(returns)}" if returns else ""
        return f"{prefix} {name}({arguments}){suffix}"


class Indexer:
    def __init__(self, root: Path, store: Store, config: dict[str, Any]):
        self.root = root
        self.store = store
        self.config = config

    def index(self, force: bool = False) -> IndexResult:
        if not git.is_repository(self.root):
            raise git.GitError("PSG requires a Git repository. Run 'git init' first.")
        revision = git.revision(self.root)
        files = [
            item
            for item in git.tracked_and_untracked_files(self.root)
            if not self._excluded(item)
        ]
        current = set(files)
        existing_files = {
            node["source"].get("path", ""): node
            for node in self.store.list_nodes("File")
        }
        removed = 0
        for path in set(existing_files) - current:
            self._delete_file(path)
            removed += 1

        indexed = unchanged = symbols = dependencies = unsupported = 0
        errors: list[dict[str, str]] = []
        module_map = self._module_map(files)
        for rel in files:
            absolute = self.root / rel
            if not absolute.is_file():
                continue
            try:
                raw = absolute.read_bytes()
            except OSError as exc:
                errors.append({"path": rel, "error": str(exc)})
                continue
            digest = sha256_bytes(raw)
            previous = existing_files.get(rel)
            if (
                previous
                and previous["payload"].get("content_hash") == digest
                and not force
            ):
                unchanged += 1
                continue
            try:
                result = self._index_file(rel, raw, digest, module_map)
                indexed += 1
                symbols += result[0]
                dependencies += result[1]
                unsupported += int(result[2])
            except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
                errors.append({"path": rel, "error": str(exc)})
                self._index_file_metadata(
                    rel, digest, len(raw), language="unknown", confidence=0.45
                )

        output = IndexResult(
            revision=revision,
            scanned=len(files),
            indexed=indexed,
            unchanged=unchanged,
            removed=removed,
            symbols=symbols,
            dependencies=dependencies,
            unsupported=unsupported,
            errors=errors,
        )
        self.store.event("index.completed", output.as_dict())
        return output

    def freshness(self, node: dict[str, Any]) -> float:
        path = node.get("source", {}).get("path")
        expected = node.get("payload", {}).get("content_hash")
        if not path or not expected:
            return 0.5
        absolute = self.root / path
        if not absolute.is_file():
            return 0.0
        try:
            return 1.0 if sha256_bytes(absolute.read_bytes()) == expected else 0.0
        except OSError:
            return 0.0

    def _index_file(
        self, rel: str, raw: bytes, digest: str, module_map: dict[str, str]
    ) -> tuple[int, int, bool]:
        suffix = Path(rel).suffix.lower()
        if suffix != ".py":
            self._index_file_metadata(
                rel, digest, len(raw), language=self._language(suffix), confidence=0.7
            )
            self.store.replace_edges_for_source(f"file:{rel}", [])
            return 0, 0, True

        text = raw.decode("utf-8")
        tree = ast.parse(text, filename=rel)
        visitor = _PythonVisitor()
        visitor.visit(tree)
        existing_symbols = {
            node["id"]: node
            for node in self.store.list_nodes("Symbol")
            if node.get("source", {}).get("path") == rel
        }
        preserved_edges = [
            edge
            for edge in self.store.edges_with_endpoint_prefix(f"symbol:{rel}:")
            if edge.get("provenance") not in {"python_ast", "psg-debt"}
        ]
        self._delete_symbols(rel)
        self.store.delete_nodes_with_prefix(f"debt:{rel}:", bump=False)
        self._index_file_metadata(
            rel,
            digest,
            len(raw),
            language="python",
            confidence=1.0,
            extra={"line_count": text.count("\n") + 1},
        )
        edges: list[dict[str, Any]] = []
        file_id = f"file:{rel}"
        for symbol in visitor.symbols:
            symbol_id = f"symbol:{rel}:{symbol['qualname']}"
            previous_symbol = existing_symbols.get(symbol_id)
            self.store.upsert_node(
                {
                    "id": symbol_id,
                    "type": "Symbol",
                    "title": symbol["qualname"],
                    "status": "active",
                    "maturity": previous_symbol["maturity"]
                    if previous_symbol
                    else "accepted",
                    "policy": previous_symbol["policy"]
                    if previous_symbol
                    else "mutable",
                    "source": {
                        "kind": "file",
                        "path": rel,
                        "line": symbol["line_start"],
                    },
                    "revision": f"sha256:{digest}",
                    "confidence": 1.0,
                    "provenance": ["repo_deterministic", "python_ast"],
                    "payload": symbol,
                },
                bump=False,
            )
            edges.append(
                {
                    "src": file_id,
                    "type": "contains",
                    "dst": symbol_id,
                    "confidence": 1.0,
                    "provenance": "python_ast",
                    "revision": f"sha256:{digest}",
                }
            )
        edges.extend(self._debt_annotations(rel, text, visitor.symbols, digest))
        live_symbol_ids = {
            f"symbol:{rel}:{symbol['qualname']}" for symbol in visitor.symbols
        }
        edges.extend(
            edge
            for edge in preserved_edges
            if (
                not edge["src"].startswith(f"symbol:{rel}:")
                or edge["src"] in live_symbol_ids
            )
            and (
                not edge["dst"].startswith(f"symbol:{rel}:")
                or edge["dst"] in live_symbol_ids
            )
        )
        for imported in visitor.imports:
            target = self._resolve_import(imported, module_map)
            if target and target != rel:
                edges.append(
                    {
                        "src": file_id,
                        "type": "depends-on",
                        "dst": f"file:{target}",
                        "confidence": 0.95,
                        "provenance": "python_ast",
                        "revision": f"sha256:{digest}",
                    }
                )
        self.store.replace_edges_for_source(file_id, edges)
        return (
            len(visitor.symbols),
            sum(1 for edge in edges if edge["type"] == "depends-on"),
            False,
        )

    def _index_file_metadata(
        self,
        rel: str,
        digest: str,
        size: int,
        *,
        language: str,
        confidence: float,
        extra: dict[str, Any] | None = None,
    ) -> None:
        previous = self.store.get_node(f"file:{rel}")
        policy = previous["policy"] if previous else "mutable"
        maturity = previous["maturity"] if previous else "accepted"
        payload = {
            "path": rel,
            "language": language,
            "content_hash": digest,
            "bytes": size,
            **(extra or {}),
        }
        self.store.upsert_node(
            {
                "id": f"file:{rel}",
                "type": "File",
                "title": rel,
                "status": "active",
                "maturity": maturity,
                "policy": policy,
                "source": {"kind": "file", "path": rel},
                "revision": f"sha256:{digest}",
                "confidence": confidence,
                "provenance": ["repo_deterministic", "git_worktree"],
                "payload": payload,
            },
            bump=False,
        )

    def _delete_file(self, rel: str) -> None:
        self._delete_symbols(rel)
        self.store.delete_nodes_with_prefix(f"debt:{rel}:", bump=False)
        self.store.delete_nodes_with_prefix(f"file:{rel}")

    def _delete_symbols(self, rel: str) -> None:
        self.store.delete_nodes_with_prefix(f"symbol:{rel}:", bump=False)

    def _debt_annotations(
        self,
        rel: str,
        text: str,
        symbols: list[dict[str, Any]],
        digest: str,
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            match = _DEBT_MARKER.search(line)
            if not match:
                continue
            parts = [part.strip() for part in match.group(1).split(";") if part.strip()]
            values: dict[str, str] = {}
            for index, part in enumerate(parts):
                if "=" in part:
                    key, value = part.split("=", 1)
                    values[key.strip().lower()] = value.strip()
                elif index == 0:
                    values["what"] = part
            revisit = values.get("revisit") or values.get("revisit_trigger")
            if not all(
                (values.get("what"), values.get("why"), values.get("ceiling"), revisit)
            ):
                self.store.event(
                    "debt.annotation_rejected",
                    {
                        "path": rel,
                        "line": line_number,
                        "reason": "what, why, ceiling, and revisit are required",
                    },
                )
                continue
            debt_id = f"debt:{rel}:{line_number}"
            self.store.upsert_node(
                {
                    "id": debt_id,
                    "type": "Debt",
                    "title": values["what"],
                    "status": "accepted",
                    "maturity": "accepted",
                    "policy": "mutable",
                    "source": {
                        "kind": "psg_debt_annotation",
                        "path": rel,
                        "line": line_number,
                    },
                    "revision": f"sha256:{digest}",
                    "confidence": 1.0,
                    "provenance": ["repo_deterministic", "psg-debt"],
                    "payload": {
                        "what": values["what"],
                        "why": values["why"],
                        "ceiling": values["ceiling"],
                        "revisit_trigger": revisit,
                        "trigger_met": False,
                    },
                },
                bump=False,
            )
            containing = next(
                (
                    symbol
                    for symbol in symbols
                    if int(symbol["line_start"])
                    <= line_number
                    <= int(symbol["line_end"])
                ),
                None,
            )
            target = (
                f"symbol:{rel}:{containing['qualname']}"
                if containing
                else f"file:{rel}"
            )
            edges.append(
                {
                    "src": debt_id,
                    "type": "affects",
                    "dst": target,
                    "confidence": 1.0,
                    "provenance": "psg-debt",
                    "revision": f"sha256:{digest}",
                }
            )
        return edges

    def _excluded(self, rel: str) -> bool:
        patterns = self.config.get("index", {}).get("exclude", [])
        return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)

    @staticmethod
    def _module_map(files: Iterable[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for rel in files:
            if not rel.endswith(".py"):
                continue
            without_suffix = rel[:-3]
            module = without_suffix.replace("/", ".")
            module = module.removesuffix(".__init__")
            mapping[module] = rel
            if module.startswith("src."):
                mapping[module[4:]] = rel
        return mapping

    @staticmethod
    def _resolve_import(imported: str, module_map: dict[str, str]) -> str | None:
        candidate = imported
        while candidate:
            if candidate in module_map:
                return module_map[candidate]
            candidate = candidate.rpartition(".")[0]
        return None

    @staticmethod
    def _language(suffix: str) -> str:
        return {
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".cs": "csharp",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
        }.get(suffix, "text")
