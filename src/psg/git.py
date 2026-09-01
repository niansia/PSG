from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from .util import normalize_path, sha256_bytes, sha256_text


class GitError(RuntimeError):
    pass


def run_git(root: Path, *args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        # Never inherit the host stdin: under an MCP stdio server that handle is the
        # JSON-RPC pipe with a blocking read pending, and an inheriting child stalls
        # until the next client message arrives.
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise GitError(process.stderr.strip() or f"git {' '.join(args)} failed")
    return process.stdout.strip()


def is_repository(root: Path) -> bool:
    return run_git(root, "rev-parse", "--is-inside-work-tree", check=False) == "true"


def revision(root: Path) -> str:
    value = run_git(root, "rev-parse", "--verify", "HEAD", check=False)
    if value:
        return value
    return f"unborn:{worktree_fingerprint(root)[:16]}"


def branch(root: Path) -> str:
    return (
        run_git(root, "branch", "--show-current", check=False) or "detached-or-unborn"
    )


def tracked_and_untracked_files(root: Path) -> list[str]:
    output = run_git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    return sorted(
        {normalize_path(line) for line in output.splitlines() if line.strip()}
    )


def status_porcelain(root: Path) -> str:
    value = run_git(
        root, "status", "--porcelain=v1", "--untracked-files=all", check=False
    )
    return "\n".join(
        line
        for line in value.splitlines()
        if not is_managed_state_path(normalize_path(line[3:].split(" -> ")[-1]))
    )


def is_managed_state_path(path: str) -> bool:
    """PSG's own derived/portable state is bookkeeping, never a reviewable change."""
    return path.startswith((".psg/local/", ".psg/state/"))


def worktree_fingerprint(root: Path) -> str:
    if not is_repository(root):
        return sha256_text("not-a-repository")
    pieces = [
        run_git(root, "rev-parse", "--verify", "HEAD", check=False),
        run_git(
            root,
            "diff",
            "--no-ext-diff",
            "--binary",
            "--",
            ".",
            ":(exclude).psg/local/**",
            ":(exclude).psg/state/**",
            check=False,
        ),
        run_git(
            root,
            "diff",
            "--no-ext-diff",
            "--binary",
            "--cached",
            "--",
            ".",
            ":(exclude).psg/local/**",
            ":(exclude).psg/state/**",
            check=False,
        ),
        status_porcelain(root),
    ]
    untracked = run_git(root, "ls-files", "--others", "--exclude-standard", check=False)
    for rel in (
        normalize_path(line) for line in untracked.splitlines() if line.strip()
    ):
        if is_managed_state_path(rel):
            continue
        path = root / rel
        if path.is_file():
            try:
                pieces.append(f"{rel}:{sha256_bytes(path.read_bytes())}")
            except OSError:
                pieces.append(f"{rel}:unreadable")
    return sha256_text("\n".join(pieces))


def _untracked_diffs(root: Path) -> list[str]:
    untracked = run_git(
        root, "ls-files", "--others", "--exclude-standard", check=False
    ).splitlines()
    additions: list[str] = []
    for item in untracked:
        rel = normalize_path(item)
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            additions.append(
                f"diff --git a/{rel} b/{rel}\nnew file mode 100644\nBinary files /dev/null and b/{rel} differ"
            )
            continue
        body = "".join(
            difflib.unified_diff(
                [],
                text.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=f"b/{rel}",
                lineterm="\n",
            )
        )
        additions.append(
            f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n{body}".rstrip()
        )
    return additions


def final_diff(root: Path) -> str:
    """Return HEAD -> current state, including staged, unstaged, and untracked files."""
    head = run_git(root, "rev-parse", "--verify", "HEAD", check=False)
    if head:
        rendered = run_git(
            root,
            "diff",
            "HEAD",
            "--no-ext-diff",
            "--binary",
            "--find-renames",
            check=False,
        )
        parts = [rendered, *_untracked_diffs(root)]
    else:
        staged = run_git(
            root,
            "diff",
            "--cached",
            "--no-ext-diff",
            "--binary",
            "--find-renames",
            check=False,
        )
        unstaged = run_git(
            root,
            "diff",
            "--no-ext-diff",
            "--binary",
            "--find-renames",
            check=False,
        )
        parts = [staged, unstaged, *_untracked_diffs(root)]
    return "\n".join(part for part in parts if part)


def diff(root: Path, staged: bool = False) -> str:
    """Advanced/debug diff view. Ship and actual validation use final_diff()."""
    args = ["diff", "--no-ext-diff", "--binary"]
    if staged:
        args.append("--cached")
    rendered = run_git(root, *args, check=False)
    if staged:
        return rendered
    return "\n".join(part for part in [rendered, *_untracked_diffs(root)] if part)
