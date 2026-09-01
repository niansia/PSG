from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from psg.runtime import PSG

SCENARIOS = [
    {
        "name": "patch-caused blocker",
        "severity": "blocker",
        "relation": "caused_by_patch",
        "evidence": {"kind": "diff_observation", "path": "src/cart.py"},
        "affected_nodes": ["file:src/cart.py"],
        "expected_block": True,
    },
    {
        "name": "patch-caused major",
        "severity": "major",
        "relation": "caused_by_patch",
        "evidence": {"kind": "runtime_failure", "path": "src/cart.py"},
        "affected_nodes": ["file:src/cart.py"],
        "expected_block": True,
    },
    {
        "name": "acceptance major",
        "severity": "major",
        "relation": "violates_acceptance",
        "evidence": {"kind": "acceptance_review", "path": "src/cart.py"},
        "violates": "AC1",
        "expected_block": True,
    },
    {
        "name": "constraint blocker",
        "severity": "blocker",
        "relation": "violates_project_constraint",
        "evidence": {"kind": "constraint_review", "path": "src/api.py"},
        "affected_nodes": ["file:src/api.py"],
        "violates": "C1",
        "expected_block": True,
    },
    {
        "name": "pre-existing major",
        "severity": "major",
        "relation": "pre_existing",
        "evidence": {"kind": "reproduction", "path": "src/login.py"},
        "expected_block": False,
    },
    {
        "name": "unrelated blocker",
        "severity": "blocker",
        "relation": "unrelated",
        "evidence": {"kind": "review_observation", "path": "src/search.py"},
        "expected_block": False,
    },
    {
        "name": "future architecture major",
        "severity": "major",
        "relation": "future_improvement",
        "evidence": {"kind": "architecture_suggestion"},
        "expected_block": False,
    },
    {
        "name": "patch-caused minor",
        "severity": "minor",
        "relation": "caused_by_patch",
        "evidence": {"kind": "diff_observation", "path": "src/cart.py"},
        "affected_nodes": ["file:src/cart.py"],
        "expected_block": False,
    },
    {
        "name": "unsupported acceptance claim",
        "severity": "major",
        "relation": "violates_acceptance",
        "evidence": {"kind": "opinion"},
        "violates": "UNKNOWN-AC",
        "expected_block": False,
    },
    {
        "name": "unsupported patch claim",
        "severity": "major",
        "relation": "caused_by_patch",
        "evidence": {"kind": "opinion"},
        "expected_block": False,
    },
]


def _run(root: Path, *args: str) -> None:
    subprocess.run(
        list(args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _create_repository(root: Path) -> None:
    source = root / "src"
    source.mkdir(parents=True)
    for name in ("cart", "api", "login", "search"):
        (source / f"{name}.py").write_text(
            f'def {name}_status() -> str:\n    return "ok"\n', encoding="utf-8"
        )
    _run(root, "git", "init", "-b", "main")
    _run(root, "git", "config", "user.email", "benchmark@example.invalid")
    _run(root, "git", "config", "user.name", "PSG Benchmark")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "task-boundary baseline")


def run_benchmark() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="psg-task-boundary-") as directory:
        root = Path(directory)
        _create_repository(root)
        graph = PSG.initialize(root, project="task-boundary-benchmark")
        graph.index(force=True)
        cart = root / "src" / "cart.py"
        cart.write_text(
            cart.read_text(encoding="utf-8") + "\n# current patch\n",
            encoding="utf-8",
        )
        results: list[dict[str, Any]] = []
        for scenario in SCENARIOS:
            task = graph.task_open(
                intent="Add an empty-cart message",
                acceptance_criteria=["Empty carts show a helpful message"],
                constraints=["The public API remains unchanged"],
                targets=["src/cart.py"],
                write=["src/cart.py"],
                read_only=["src/api.py"],
                non_goals=["Login, search, and architecture cleanup"],
                risk="medium",
            )
            violates = scenario.get("violates")
            if violates == "AC1":
                violates = f"{task['id']}-AC1"
            elif violates == "C1":
                violates = f"{task['id']}-C1"
            issue = graph.issue_report(
                task_id=task["id"],
                severity=str(scenario["severity"]),
                relation_to_task=str(scenario["relation"]),
                claim=str(scenario["name"]),
                evidence=dict(scenario["evidence"]),
                affected_nodes=list(scenario.get("affected_nodes", [])),
                violates=violates,
            )
            actual = bool(issue["blocks_current_task"])
            results.append(
                {
                    **scenario,
                    "task_id": task["id"],
                    "issue_id": issue["id"],
                    "actual_block": actual,
                    "evidence_sufficient": issue["evidence_sufficient"],
                    "correct": actual == scenario["expected_block"],
                }
            )
        expected_positive = sum(item["expected_block"] for item in results)
        expected_negative = len(results) - expected_positive
        true_positive = sum(
            item["expected_block"] and item["actual_block"] for item in results
        )
        false_positive = sum(
            not item["expected_block"] and item["actual_block"] for item in results
        )
        return {
            "benchmark": "psg-task-boundary-v1",
            "scenario_count": len(results),
            "summary": {
                "correct": sum(item["correct"] for item in results),
                "blocking_recall": round(true_positive / expected_positive, 4),
                "blocking_precision": round(
                    true_positive / max(1, true_positive + false_positive), 4
                ),
                "false_reopening_rate": round(
                    false_positive / max(1, expected_negative), 4
                ),
                "all_passed": all(item["correct"] for item in results),
            },
            "scenarios": results,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic PSG Task Boundary scenarios"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
