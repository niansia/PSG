from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from psg.runtime import PSG


def command(root: Path, *args: str) -> str:
    process = subprocess.run(
        list(args),
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(process.stderr)
    return process.stdout.strip()


def create_repository(root: Path, module_count: int = 36) -> None:
    package = root / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "core.py").write_text(
        "def stable_contract(value: int) -> int:\n    return value * 10\n",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.psg/local/\n", encoding="utf-8"
    )
    for index in range(module_count):
        dependency = "from pkg.core import stable_contract\n"
        if index:
            dependency += f"from pkg.feature_{index - 1} import feature_{index - 1}\n"
        body = (
            f"{dependency}\n"
            f"def feature_{index}(value: int) -> int:\n"
            f"    return stable_contract(value) + {index}\n"
        )
        (package / f"feature_{index}.py").write_text(body, encoding="utf-8")
    command(root, "git", "init", "-b", "main")
    command(root, "git", "config", "user.email", "benchmark@example.invalid")
    command(root, "git", "config", "user.name", "PSG Benchmark")
    command(root, "git", "add", ".")
    command(root, "git", "commit", "-m", "benchmark baseline")


def source_metrics(root: Path) -> tuple[int, int]:
    files = list((root / "pkg").glob("*.py"))
    tokens = sum(max(1, len(path.read_text(encoding="utf-8")) // 4) for path in files)
    return len(files), tokens


def selected_context_tokens(
    root: Path, context: dict[str, Any], selected_files: set[str]
) -> int:
    tool_payload = max(
        1,
        len(json.dumps(context, ensure_ascii=False, sort_keys=True)) // 4,
    )
    source_content = sum(
        max(1, len(path.read_text(encoding="utf-8")) // 4)
        for rel in selected_files
        if (path := root / rel).is_file()
    )
    return tool_payload + source_content


def run_benchmark(task_count: int = 12) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="psg-benchmark-") as directory:
        root = Path(directory)
        create_repository(root)
        graph = PSG.initialize(root, project="sequential-benchmark")
        index_result = graph.index(force=True)
        graph.node_policy_set("file:pkg/core.py", "frozen", "Public benchmark baseline")
        baseline_files, baseline_tokens = source_metrics(root)
        task_results: list[dict[str, Any]] = []
        for index in range(task_count):
            path = f"pkg/feature_{index}.py"
            opened = graph.task_open(
                intent=f"Adjust feature {index} while preserving the stable core contract",
                acceptance_criteria=[
                    f"feature_{index} returns the updated deterministic result"
                ],
                constraints=["pkg/core.py must not change"],
                targets=[path],
                forbidden=["pkg/core.py"],
                risk="low",
            )
            context = graph.context_build(opened["id"])
            absolute = root / path
            old = absolute.read_text(encoding="utf-8")
            new = old.replace(f"+ {index}\n", f"+ {index + 100}\n")
            absolute.write_text(new, encoding="utf-8")
            validation = graph.patch_validate(opened["id"])
            verified = graph.verify(
                opened["id"],
                [
                    {
                        "name": f"deterministic:feature-{index}",
                        "kind": "unit",
                        "required": True,
                        "command": (
                            f'"{sys.executable}" -c "from pkg.feature_{index} import '
                            f"feature_{index}; assert feature_{index}(2) == {20 + index + 100}"
                        ),
                    }
                ],
            )
            verification = verified["results"][0]
            graph.criterion_set(
                opened["id"],
                f"{opened['id']}-AC1",
                "pass",
                {
                    "kind": "deterministic_assertion",
                    "source": "runtime_executed",
                    "reference": verification["id"],
                },
            )
            if index % 3 == 0:
                graph.issue_report(
                    task_id=opened["id"],
                    severity="optional",
                    claim="The feature modules could share a generated helper",
                    evidence={"kind": "architecture_preference"},
                )
            shipped = graph.ship_evaluate(opened["id"])
            command(root, "git", "add", path)
            command(root, "git", "commit", "-m", f"task {index + 1}")
            working = context["working_set"]
            selected_files = set(
                working["read"]
                + working["write"]
                + working["read_only"]
                + working["forbidden"]
            )
            psg_tokens = selected_context_tokens(root, context, selected_files)
            task_results.append(
                {
                    "task_id": opened["id"],
                    "target": path,
                    "baseline_file_reads": baseline_files,
                    "psg_file_reads": len(selected_files),
                    "baseline_token_estimate": baseline_tokens,
                    "psg_token_estimate": psg_tokens,
                    "psg_graph_context_tokens": context["token_estimate"],
                    "psg_selected_source_tokens": psg_tokens
                    - max(
                        1,
                        len(json.dumps(context, ensure_ascii=False, sort_keys=True))
                        // 4,
                    ),
                    "context_confidence": context["confidence"],
                    "policy_allowed": validation["allowed"],
                    "ship_status": shipped["status"],
                    "ship_verification_summary": shipped["verification_summary"],
                    "ship_acceptance_summary": shipped["acceptance_summary"],
                }
            )

        guard_task = graph.task_open(
            intent="Attempt a prohibited stable-core change",
            acceptance_criteria=[],
            targets=["pkg/feature_0.py"],
            forbidden=["pkg/core.py"],
            risk="medium",
        )
        graph.context_build(guard_task["id"])
        forbidden_diff = (
            "diff --git a/pkg/core.py b/pkg/core.py\n"
            "--- a/pkg/core.py\n+++ b/pkg/core.py\n"
            "@@ -1,2 +1,2 @@\n-def stable_contract(value: int) -> int:\n"
            "+def stable_contract(value: int, scale: int = 10) -> int:\n"
        )
        blocked = graph.patch_validate(guard_task["id"], forbidden_diff)

        review_task = graph.task_open(
            intent="Measure review stopping behavior",
            acceptance_criteria=[],
            targets=["pkg/feature_0.py"],
            risk="medium",
        )
        review_one = graph.review_record(review_task["id"], 0)
        review_two = graph.review_record(review_task["id"], 0)

        total_baseline_reads = sum(item["baseline_file_reads"] for item in task_results)
        total_psg_reads = sum(item["psg_file_reads"] for item in task_results)
        total_baseline_tokens = sum(
            item["baseline_token_estimate"] for item in task_results
        )
        total_psg_tokens = sum(item["psg_token_estimate"] for item in task_results)
        return {
            "benchmark": "psg-sequential-v1",
            "task_count": task_count,
            "repository": {"source_files": baseline_files, "indexed": index_result},
            "summary": {
                "tasks_shippable": sum(
                    item["ship_status"] == "SHIPPABLE" for item in task_results
                ),
                "baseline_file_reads": total_baseline_reads,
                "psg_file_reads": total_psg_reads,
                "file_read_reduction_percent": round(
                    100 * (1 - total_psg_reads / total_baseline_reads), 2
                ),
                "baseline_token_estimate": total_baseline_tokens,
                "psg_token_estimate": total_psg_tokens,
                "total_context_token_reduction_percent": round(
                    100 * (1 - total_psg_tokens / total_baseline_tokens), 2
                ),
                "unauthorized_frozen_mutation_blocked": not blocked["allowed"],
                "review_stopped_at_budget": review_two["stop_general_review"]
                and not review_one["stop_general_review"],
                "review_rounds": review_two["review_rounds_used"],
            },
            "tasks": task_results,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the reproducible PSG sequential-task benchmark"
    )
    parser.add_argument("--tasks", type=int, default=12)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.tasks < 10:
        parser.error("The architecture benchmark requires at least 10 sequential tasks")
    result = run_benchmark(args.tasks)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
