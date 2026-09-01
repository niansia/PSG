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
    return run_git(
        root, "status", "--porcelain=v1", "--untracked-files=all", check=False
    )


def worktree_fingerprint(root: Path) -> str:
    if not is_repository(root):
        return sha256_text("not-a-repository")
    pieces = [
        run_git(root, "rev-parse", "--verify", "HEAD", check=False),
        run_git(root, "diff", "--no-ext-diff", "--binary", check=False),
        run_git(root, "diff", "--no-ext-diff", "--binary", "--cached", check=False),
        status_porcelain(root),
    ]
    untracked = run_git(root, "ls-files", "--others", "--exclude-standard", check=False)
    for rel in (
        normalize_path(line) for line in untracked.splitlines() if line.strip()
    ):
        path = root / rel
        if path.is_file():
            try:
                pieces.append(f"{rel}:{sha256_bytes(path.read_bytes())}")
            except OSError:
                pieces.append(f"{rel}:unreadable")
    return sha256_text("\n".join(pieces))


def diff(root: Path, staged: bool = False) -> str:
    args = ["diff", "--no-ext-diff", "--binary"]
    if staged:
        args.append("--cached")
    rendered = run_git(root, *args, check=False)
    if staged:
        return rendered
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
    return "\n".join(part for part in [rendered, *additions] if part)
