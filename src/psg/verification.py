from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import git
from .store import Store
from .trust import CLAIMED, RUNTIME_ATTESTED, VALID_TRUST_TIERS
from .util import atomic_write_text, sha256_text


class VerificationEngine:
    def __init__(self, root: Path, store: Store):
        self.root = root
        self.store = store
        self.log_dir = store.event_log.parent / "verification"

    def record(
        self,
        task_id: str,
        *,
        name: str,
        result: str,
        kind: str = "test",
        command: str | None = None,
        required: bool = True,
        source: str = "agent_claim",
        trust_tier: str = CLAIMED,
        evidence: dict[str, Any] | None = None,
        verification_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = result.lower()
        if normalized not in {"pass", "fail", "error", "skipped"}:
            raise ValueError(
                "Verification result must be pass, fail, error, or skipped"
            )
        if trust_tier not in VALID_TRUST_TIERS:
            raise ValueError(f"Unsupported verification trust tier: {trust_tier}")
        if source not in {
            "runtime_executed",
            "external_tool",
            "llm_reported",
            "user_asserted",
            "reviewer",
            "agent_claim",
        }:
            raise ValueError(f"Unsupported verification source: {source}")
        if trust_tier == RUNTIME_ATTESTED and source != "runtime_executed":
            raise ValueError("Runtime attestation requires runtime-executed evidence.")
        recorded_evidence = {
            key: value
            for key, value in dict(evidence or {}).items()
            if key not in {"output", "stdout", "stderr", "trust_tier"}
        }
        recorded_evidence["source"] = source
        recorded_evidence["trust_tier"] = trust_tier
        recorded_evidence.setdefault(
            "worktree_fingerprint", git.worktree_fingerprint(self.root)
        )
        verification = {
            "id": verification_id or self.store.next_id("verifications", "V"),
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
            verification_id = self.store.next_id("verifications", "V")
            started = time.monotonic()
            output = ""
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
                }
                output = process.stdout
            except subprocess.TimeoutExpired as exc:
                result = "error"
                evidence = {
                    "kind": "timeout",
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "timeout_seconds": timeout,
                }
                output = exc.stdout or "" if isinstance(exc.stdout, str) else ""
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self.log_dir / f"{verification_id}.log"
            log_content = f"check: {name}\ncommand: {command}\n\n{output}"
            atomic_write_text(log_path, log_content)
            evidence.update(
                {
                    "check_name": name,
                    "output_hash": f"sha256:{sha256_text(output)}",
                    "reference": f"local:verification/{verification_id}.log",
                }
            )
            results.append(
                self.record(
                    task_id,
                    name=name,
                    result=result,
                    kind=str(check.get("kind", "test")),
                    command=name,
                    required=required,
                    source="runtime_executed",
                    trust_tier=RUNTIME_ATTESTED,
                    evidence=evidence,
                    verification_id=verification_id,
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
