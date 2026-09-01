from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import git
from .store import Store


class VerificationEngine:
    def __init__(self, root: Path, store: Store):
        self.root = root
        self.store = store

    def record(
        self,
        task_id: str,
        *,
        name: str,
        result: str,
        kind: str = "test",
        command: str | None = None,
        required: bool = True,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = result.lower()
        if normalized not in {"pass", "fail", "error", "skipped"}:
            raise ValueError(
                "Verification result must be pass, fail, error, or skipped"
            )
        recorded_evidence = dict(evidence or {})
        recorded_evidence.setdefault(
            "worktree_fingerprint", git.worktree_fingerprint(self.root)
        )
        verification = {
            "id": self.store.next_id("verifications", "V"),
            "task_id": task_id,
            "name": name,
            "kind": kind,
            "command": command,
            "result": normalized,
            "required": required,
            "evidence": recorded_evidence,
            "revision": git.revision(self.root),
        }
        self.store.record_verification(verification)
        return verification

    def run(self, task_id: str, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for check in checks:
            name = str(check["name"])
            command = str(check["command"])
            required = bool(check.get("required", True))
            timeout = int(check.get("timeout_seconds", 300))
            started = time.monotonic()
            try:
                process = subprocess.run(
                    command,
                    cwd=self.root,
                    shell=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
                result = "pass" if process.returncode == 0 else "fail"
                evidence = {
                    "kind": "command_result",
                    "exit_code": process.returncode,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "output": process.stdout[-12000:],
                }
            except subprocess.TimeoutExpired as exc:
                result = "error"
                evidence = {
                    "kind": "timeout",
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "timeout_seconds": timeout,
                    "output": (exc.stdout or "")[-12000:]
                    if isinstance(exc.stdout, str)
                    else "",
                }
            results.append(
                self.record(
                    task_id,
                    name=name,
                    result=result,
                    kind=str(check.get("kind", "test")),
                    command=command,
                    required=required,
                    evidence=evidence,
                )
            )
        return results


IssueReporter = Callable[..., dict[str, Any]]


def report_failed_checks(
    results: list[dict[str, Any]], report_issue: IssueReporter
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for result in results:
        if result["required"] and result["result"] in {"fail", "error"}:
            issues.append(
                report_issue(
                    task_id=result["task_id"],
                    severity="major",
                    claim=f"Required verification '{result['name']}' did not pass",
                    evidence={
                        "kind": "verification_failure",
                        "verification_id": result["id"],
                        "result": result["result"],
                    },
                    affected_nodes=[],
                    violates=None,
                )
            )
    return issues
