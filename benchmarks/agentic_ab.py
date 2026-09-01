from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psg.config import save_yaml
from psg.runtime import PSG

MODEL = "gpt-5.5"
# END_TO_END is the headline: neither side is told where the change belongs, so PSG
# has to localize the request itself. CONTROLLED_ROUTING hands both sides the same
# target, isolating governance value from localization value. Telling only the ON
# side the target would make PSG look good by giving it the answer.
END_TO_END = "end_to_end"
CONTROLLED_ROUTING = "controlled_routing"
REASONING_EFFORT = "low"
TIMEOUT_SECONDS = 240


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    prompt: str
    target: str
    hidden_test: str


TASKS = [
    AgentTask(
        "slugify",
        "Update slugify so leading/trailing separators disappear and any run of non-alphanumeric characters becomes one dash. Preserve lowercase output.",
        "src/text_tools.py",
        "from src.text_tools import slugify\n\n\ndef test_hidden_slugify():\n    assert slugify('  Hello,  PSG!!! ') == 'hello-psg'\n    assert slugify('---') == ''\n",
    ),
    AgentTask(
        "clamp",
        "Update clamp so it raises ValueError when the minimum is greater than the maximum, while preserving normal inclusive clamping.",
        "src/number_tools.py",
        "import pytest\nfrom src.number_tools import clamp\n\n\ndef test_hidden_clamp():\n    assert clamp(8, 1, 5) == 5\n    with pytest.raises(ValueError):\n        clamp(2, 5, 1)\n",
    ),
    AgentTask(
        "parse_bool",
        "Make parse_bool ignore surrounding whitespace and case, accept yes/no and 1/0, and raise ValueError for unknown text.",
        "src/config_tools.py",
        "import pytest\nfrom src.config_tools import parse_bool\n\n\ndef test_hidden_parse_bool():\n    assert parse_bool(' YES ') is True\n    assert parse_bool('0') is False\n    with pytest.raises(ValueError):\n        parse_bool('maybe')\n",
    ),
    AgentTask(
        "discount",
        "Update discounted_total so percentage discounts are limited to 0 through 100 and negative subtotals are rejected with ValueError.",
        "src/price_tools.py",
        "import pytest\nfrom src.price_tools import discounted_total\n\n\ndef test_hidden_discount():\n    assert discounted_total(80.0, 150.0) == 0.0\n    assert discounted_total(80.0, -10.0) == 80.0\n    with pytest.raises(ValueError):\n        discounted_total(-1.0, 10.0)\n",
    ),
    AgentTask(
        "email",
        "Make normalize_email trim whitespace, lowercase the address, and reject values that do not contain exactly one @ with non-empty local and domain parts.",
        "src/contact_tools.py",
        "import pytest\nfrom src.contact_tools import normalize_email\n\n\ndef test_hidden_email():\n    assert normalize_email(' User@Example.COM ') == 'user@example.com'\n    for value in ('no-at', '@example.com', 'a@@b.com'):\n        with pytest.raises(ValueError):\n            normalize_email(value)\n",
    ),
    AgentTask(
        "dedupe",
        "Update unique_items to remove duplicates while preserving first-seen order, including for unhashable list and dictionary values.",
        "src/collection_tools.py",
        "from src.collection_tools import unique_items\n\n\ndef test_hidden_dedupe():\n    assert unique_items([1, 1, 2, 1]) == [1, 2]\n    assert unique_items([[1], [1], [2]]) == [[1], [2]]\n    assert unique_items([{'a': 1}, {'a': 1}]) == [{'a': 1}]\n",
    ),
    AgentTask(
        "retry_delay",
        "Update retry_delay to use exponential backoff from the base delay, cap the result, and reject negative attempt numbers.",
        "src/retry_tools.py",
        "import pytest\nfrom src.retry_tools import retry_delay\n\n\ndef test_hidden_retry_delay():\n    assert retry_delay(0, base=0.5, cap=5.0) == 0.5\n    assert retry_delay(5, base=0.5, cap=5.0) == 5.0\n    with pytest.raises(ValueError):\n        retry_delay(-1)\n",
    ),
    AgentTask(
        "redact",
        "Update redact_secret so secrets of length four or less are fully masked and longer secrets reveal only the final four characters.",
        "src/security_tools.py",
        "from src.security_tools import redact_secret\n\n\ndef test_hidden_redact():\n    assert redact_secret('abc') == '***'\n    assert redact_secret('abcdefgh') == '****efgh'\n    assert redact_secret('') == ''\n",
    ),
    AgentTask(
        "page_window",
        "Make page_window return a zero-based [start, stop) range, reject page numbers or sizes below one, and never return a stop beyond total items.",
        "src/paging_tools.py",
        "import pytest\nfrom src.paging_tools import page_window\n\n\ndef test_hidden_page_window():\n    assert page_window(2, 10, 15) == (10, 15)\n    assert page_window(3, 10, 15) == (15, 15)\n    with pytest.raises(ValueError):\n        page_window(0, 10, 15)\n",
    ),
    AgentTask(
        "parse_tags",
        "Update parse_tags to split comma-separated input, trim whitespace, discard empty entries, compare case-insensitively, and preserve the first spelling of each tag.",
        "src/tag_tools.py",
        "from src.tag_tools import parse_tags\n\n\ndef test_hidden_parse_tags():\n    assert parse_tags(' Python, ai, PYTHON, , Tools ') == ['Python', 'ai', 'Tools']\n    assert parse_tags(' , ') == []\n",
    ),
]


BASE_MODULES = {
    "src/text_tools.py": "def slugify(value: str) -> str:\n    return value.lower().replace(' ', '-')\n",
    "src/number_tools.py": "def clamp(value: float, minimum: float, maximum: float) -> float:\n    return max(minimum, min(maximum, value))\n",
    "src/config_tools.py": "def parse_bool(value: str) -> bool:\n    return value == 'true'\n",
    "src/price_tools.py": "def discounted_total(subtotal: float, percent: float) -> float:\n    return subtotal * (1 - percent / 100)\n",
    "src/contact_tools.py": "def normalize_email(value: str) -> str:\n    return value.lower()\n",
    "src/collection_tools.py": "def unique_items(values: list[object]) -> list[object]:\n    return list(set(values))\n",
    "src/retry_tools.py": "def retry_delay(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:\n    return base * attempt\n",
    "src/security_tools.py": "def redact_secret(value: str) -> str:\n    return '*' * len(value)\n",
    "src/paging_tools.py": "def page_window(page: int, size: int, total: int) -> tuple[int, int]:\n    start = page * size\n    return start, start + size\n",
    "src/tag_tools.py": "def parse_tags(value: str) -> list[str]:\n    return value.split(',')\n",
}


VISIBLE_TESTS = """\
from src.collection_tools import unique_items
from src.config_tools import parse_bool
from src.contact_tools import normalize_email
from src.number_tools import clamp
from src.paging_tools import page_window
from src.price_tools import discounted_total
from src.retry_tools import retry_delay
from src.security_tools import redact_secret
from src.tag_tools import parse_tags
from src.text_tools import slugify


def test_existing_behavior_smoke():
    assert slugify('hello world') == 'hello-world'
    assert clamp(3, 1, 5) == 3
    assert parse_bool('true') is True
    assert discounted_total(100, 20) == 80
    assert normalize_email('A@B.COM') == 'a@b.com'
    assert unique_items([1, 2]) == [1, 2]
    assert retry_delay(1) == 1
    assert redact_secret('abcd') == '****'
    assert page_window(1, 10, 100) == (10, 20)
    assert parse_tags('a,b') == ['a', 'b']
"""


def _run(
    cwd: Path,
    *args: str,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def _write_base_repository(root: Path) -> str:
    for relative, content in BASE_MODULES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_existing.py").write_text(VISIBLE_TESTS, encoding="utf-8")
    for index in range(20):
        (root / "src" / f"catalog_{index:02d}.py").write_text(
            f"def catalog_{index:02d}(value: int) -> int:\n    return value + {index}\n",
            encoding="utf-8",
        )
    (root / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.pytest_cache/\n.psg/local/\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\n', encoding="utf-8"
    )
    _run(root, "git", "init", "-b", "main")
    _run(root, "git", "config", "user.email", "benchmark@example.invalid")
    _run(root, "git", "config", "user.name", "PSG Benchmark")
    graph = PSG.initialize(root, project="agentic-ab-benchmark")
    graph.config["verification"]["commands"] = {
        "test": {
            "command": "python -m pytest -q",
            "kind": "test",
            "required": True,
            "timeout_seconds": 120,
        }
    }
    save_yaml(graph.paths.config, graph.config)
    PSG.accept_portable_state(
        root, reason="Benchmark fixture defines its allowlisted test command"
    )
    graph = PSG(root)
    graph.index(force=True)
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-m", "agentic benchmark baseline")
    return _run(root, "git", "rev-parse", "HEAD").stdout.strip()


def _open_contract(root: Path, task: AgentTask, mode: str) -> str:
    """Open the ON-condition contract with exactly the knowledge the OFF side has."""
    graph = PSG(root)
    scope: dict[str, Any] = {}
    if mode == CONTROLLED_ROUTING:
        # Both conditions were told the target, so PSG may be told it too.
        scope = {
            "targets": [task.target],
            "write": [task.target],
            "read_only": ["tests/test_existing.py"],
            "forbidden": [
                relative for relative in BASE_MODULES if relative != task.target
            ],
        }
    opened = graph.task_open(
        intent=task.prompt,
        acceptance_criteria=["The requested behavior passes executable tests"],
        non_goals=["Unrelated cleanup, dependency changes, and catalog modules"],
        risk="low",
        **scope,
    )
    # Sealing happens here: in end-to-end mode the mutation boundary is whatever
    # PSG's own localization derives, with no benchmark oracle behind it.
    graph.context_build(opened["id"])
    return opened["id"]


def _json_events(raw: str) -> list[dict[str, Any]]:
    events = []
    for line in raw.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _extract_usage(events: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    for event in events:
        usage = event.get("usage")
        if not isinstance(usage, dict):
            usage = event.get("token_usage")
        if not isinstance(usage, dict):
            continue
        for key, current in totals.items():
            value = usage.get(key)
            if isinstance(value, int):
                totals[key] = max(current, value)
    return totals


def _trace_file_reads(events: list[dict[str, Any]], known_paths: set[str]) -> list[str]:
    commands: list[str] = []

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, str(child_key))
        elif isinstance(value, list):
            for child in value:
                visit(child, key)
        elif isinstance(value, str) and key in {"command", "cmd"}:
            commands.append(value.replace("\\", "/"))

    visit(events)
    reads = {
        path
        for path in known_paths
        if any(
            re.search(rf"(?<![\w./-]){re.escape(path)}(?![\w./-])", cmd)
            for cmd in commands
        )
    }
    return sorted(reads)


def _path_pattern(raw: str) -> re.Pattern[str]:
    """Match a local path however Codex happened to spell it in the trace.

    Paths arrive singly escaped, doubly escaped, and quadruply escaped (JSON inside
    JSON), and a long command line is wrapped by the terminal, splitting a path
    across a newline mid-word. Both defeat plain string replacement.
    """
    gap = r"(?:\\r\\n|\\n|\r\n|\n)*"
    separator = gap + r"[\\/]+" + gap
    segments = []
    for segment in re.split(r"[\\/]+", raw):
        segments.append(gap.join(re.escape(char) for char in segment))
    return re.compile(separator.join(segments), re.IGNORECASE)


def _sanitizer(worktree: Path, base: Path) -> Callable[[str], str]:
    """Redact local absolute paths so raw traces are publishable."""
    replacements = [
        (worktree, "<WORKTREE>"),
        (base, "<BENCHMARK_BASE>"),
        (Path(tempfile.gettempdir()), "<TMP>"),
        (Path.home(), "<USER_HOME>"),
    ]
    patterns = [(_path_pattern(str(source)), token) for source, token in replacements]

    def sanitize(value: str) -> str:
        for pattern, token in patterns:
            value = pattern.sub(token, value)
        return value

    return sanitize


def _psg_outcome(root: Path, contract_id: str | None) -> dict[str, Any]:
    """Read what PSG itself concluded about the task, without mutating it."""
    empty = {
        "psg_task_status": None,
        "review_rounds": None,
        "fix_cycles": None,
        "contract_state": None,
        "authorized_write": [],
        "requires_scope_approval": False,
    }
    if not contract_id:
        return empty
    task = PSG(root).store.get_task(contract_id)
    if not task:
        return empty
    payload = task.get("payload", {})
    return {
        "psg_task_status": task["status"],
        "review_rounds": int(task["review_rounds"]),
        "fix_cycles": int(task["fix_cycles"]),
        # In end-to-end mode this is the boundary PSG localized on its own.
        "contract_state": payload.get("contract_state"),
        "authorized_write": list(payload.get("authorized_write", [])),
        "requires_scope_approval": bool(payload.get("requires_scope_approval", False)),
    }


def _changed_paths(root: Path) -> list[str]:
    output = _run(root, "git", "status", "--porcelain=v1", "-z").stdout
    paths = []
    for entry in output.split("\0"):
        if not entry:
            continue
        path = entry[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ")[-1]
        if not path.startswith(".psg/"):
            paths.append(path)
    return sorted(set(paths))


def _run_tests(root: Path, task: AgentTask) -> dict[str, Any]:
    baseline = _run(
        root, "python", "-m", "pytest", "tests/test_existing.py", "-q", check=False
    )
    hidden_path = root / "tests" / f"test_hidden_{task.task_id}.py"
    hidden_path.write_text(task.hidden_test, encoding="utf-8")
    hidden = _run(root, "python", "-m", "pytest", str(hidden_path), "-q", check=False)
    hidden_path.unlink()
    return {
        "task_success": baseline.returncode == 0 and hidden.returncode == 0,
        "regression": baseline.returncode != 0,
        "baseline_exit_code": baseline.returncode,
        "hidden_exit_code": hidden.returncode,
        "baseline_output": (baseline.stdout + baseline.stderr)[-2000:],
        "hidden_output": (hidden.stdout + hidden.stderr)[-2000:],
    }


def _run_agent(
    root: Path, prompt: str, *, timeout_seconds: int
) -> tuple[str, float, int]:
    instruction = (
        prompt
        + "\n\nImplement the request in this repository. Use any project-local workflow "
        "that is active. Keep the change focused and run the relevant tests."
    )
    psg_mcp = shutil.which("psg-mcp")
    if not psg_mcp:
        raise RuntimeError("psg-mcp is required for the matched benchmark")
    psg_mcp_toml = json.dumps(psg_mcp.replace("\\", "/"))
    project_root_toml = json.dumps(str(root).replace("\\", "/"))
    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "-c",
        f"mcp_servers.psg.command={psg_mcp_toml}",
        "-c",
        f"mcp_servers.psg.env.PSG_PROJECT_ROOT={project_root_toml}",
        "--json",
        "--ephemeral",
        "--color",
        "never",
        "--model",
        MODEL,
        "-c",
        f'model_reasoning_effort="{REASONING_EFFORT}"',
        "--sandbox",
        "danger-full-access",
        "--cd",
        str(root),
        instruction,
    ]
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        stdout = process.stdout
        stderr = process.stderr
        return_code = process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return_code = 124
    elapsed = time.perf_counter() - started
    raw = stdout
    if stderr and return_code:
        raw += "\n" + json.dumps({"stderr": stderr[-4000:]}, ensure_ascii=False)
    return raw, elapsed, return_code


def run_benchmark(
    *,
    output: Path,
    traces: Path,
    task_limit: int = 10,
    timeout_seconds: int = TIMEOUT_SECONDS,
    allow_short: bool = False,
    conditions: tuple[str, ...] = ("OFF", "ON"),
    mode: str = END_TO_END,
) -> dict[str, Any]:
    if mode not in {END_TO_END, CONTROLLED_ROUTING}:
        raise ValueError(f"Unknown benchmark mode: {mode}")
    selected = TASKS[:task_limit]
    if len(selected) < 10 and not allow_short:
        raise ValueError("The published agentic benchmark requires all 10 paired tasks")
    if shutil.which("codex") is None:
        raise RuntimeError("codex CLI is required")
    output = output.resolve()
    traces = traces.resolve()
    traces.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="psg-agentic-ab-") as directory:
        base = Path(directory) / "base"
        base.mkdir()
        baseline_commit = _write_base_repository(base)
        known_paths = set(BASE_MODULES) | {
            "tests/test_existing.py",
            *{f"src/catalog_{index:02d}.py" for index in range(20)},
        }
        rows: list[dict[str, Any]] = []
        for task in selected:
            for condition in conditions:
                worktree = Path(directory) / f"{task.task_id}-{condition.lower()}"
                _run(
                    base,
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(worktree),
                    baseline_commit,
                )
                graph = PSG(worktree)
                contract_id = None
                if condition == "ON":
                    graph.set_enabled(True)
                    contract_id = _open_contract(worktree, task, mode)
                else:
                    graph.set_enabled(False)
                # Identical prompt on both sides. In controlled-routing mode both are
                # told the target; in end-to-end mode neither is.
                prompt = task.prompt
                if mode == CONTROLLED_ROUTING:
                    prompt = f"{task.prompt}\n\nTarget file: {task.target}"
                raw, elapsed, exit_code = _run_agent(
                    worktree, prompt, timeout_seconds=timeout_seconds
                )
                sanitize = _sanitizer(worktree, base)
                trace_file = traces / f"{task.task_id}-{condition.lower()}.jsonl"
                trace_file.write_text(sanitize(raw.rstrip()) + "\n", encoding="utf-8")
                events = _json_events(raw)
                changed = _changed_paths(worktree)
                psg_outcome = _psg_outcome(worktree, contract_id)
                tests = _run_tests(worktree, task)
                tests["baseline_output"] = sanitize(tests["baseline_output"])
                tests["hidden_output"] = sanitize(tests["hidden_output"])
                outside = [path for path in changed if path != task.target]
                rows.append(
                    {
                        "task_id": task.task_id,
                        "condition": condition,
                        "mode": mode,
                        "model": MODEL,
                        "reasoning_effort": REASONING_EFFORT,
                        "baseline_commit": baseline_commit,
                        "prompt": task.prompt,
                        "target": task.target,
                        "task_contract_id": contract_id,
                        "agent_exit_code": exit_code,
                        "wall_time_seconds": round(elapsed, 3),
                        "usage": _extract_usage(events),
                        "trace_inferred_unique_files_read": _trace_file_reads(
                            events, known_paths
                        ),
                        "changed_files": changed,
                        "out_of_scope_edits": outside,
                        **psg_outcome,
                        **tests,
                        # PSG declared the task done while the hidden test fails.
                        "false_shippable": bool(
                            psg_outcome["psg_task_status"] == "shippable"
                            and not tests["task_success"]
                        ),
                        "trace": str(trace_file.relative_to(output.parent)),
                    }
                )
                _run(base, "git", "worktree", "remove", "--force", str(worktree))

    def aggregate(condition: str) -> dict[str, Any]:
        values = [item for item in rows if item["condition"] == condition]
        return {
            "tasks": len(values),
            "task_success": sum(item["task_success"] for item in values),
            "regressions": sum(item["regression"] for item in values),
            "out_of_scope_edits": sum(
                bool(item["out_of_scope_edits"]) for item in values
            ),
            "unique_file_reads": sum(
                len(item["trace_inferred_unique_files_read"]) for item in values
            ),
            "input_tokens": sum(item["usage"]["input_tokens"] for item in values),
            "cached_input_tokens": sum(
                item["usage"]["cached_input_tokens"] for item in values
            ),
            "output_tokens": sum(item["usage"]["output_tokens"] for item in values),
            "wall_time_seconds": round(
                sum(item["wall_time_seconds"] for item in values), 3
            ),
            "review_rounds": sum(item["review_rounds"] or 0 for item in values),
            "fix_cycles": sum(item["fix_cycles"] or 0 for item in values),
            "false_shippable": sum(item["false_shippable"] for item in values),
            "reported_cost_usd": None,
        }

    off = aggregate("OFF")
    on = aggregate("ON")
    result = {
        "benchmark": f"psg-agentic-ab-v2-{mode}",
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol": {
            "agent": "Codex CLI",
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "mode": mode,
            "mode_meaning": (
                "end_to_end: neither condition is told where the change belongs, so PSG "
                "must localize the request itself"
                if mode == END_TO_END
                else "controlled_routing: both conditions are told the same target, "
                "isolating governance value from localization value"
            ),
            "target_disclosure_is_symmetric": True,
            "task_pairs": len(selected),
            "same_prompt_per_pair": True,
            "same_repository_commit_per_pair": True,
            "separate_clean_worktrees": True,
            "timeout_seconds_per_run": timeout_seconds,
            "conditions": {
                "OFF": "PSG installed but disabled for the project",
                "ON": "PSG enabled with a predeclared Task Contract and runtime enforcement",
            },
            "file_read_metric": "lower-bound count of repository paths explicitly named in Codex command events",
            "cost_limitation": "Codex CLI did not expose a per-run dollar charge; tokens and wall time are reported without inventing a price",
        },
        "correctness_non_inferior": on["task_success"] >= off["task_success"],
        "summary": {"OFF": off, "ON": on},
        "runs": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the matched 10-pair Codex PSG OFF versus ON benchmark"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/results/agentic-ab-latest.json"),
    )
    parser.add_argument(
        "--smoke-condition",
        choices=["off", "on", "both"],
        default="both",
        help="Limit a --smoke run to one condition",
    )
    parser.add_argument(
        "--traces",
        type=Path,
        default=Path("benchmarks/results/agentic-ab-traces"),
    )
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS)
    parser.add_argument(
        "--mode",
        choices=[END_TO_END, CONTROLLED_ROUTING],
        default=END_TO_END,
        help=(
            "end_to_end (headline): neither side is told the target. "
            "controlled_routing: both sides are told the same target."
        ),
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run one pair for harness validation; never use this result as published evidence",
    )
    args = parser.parse_args()
    conditions = {
        "off": ("OFF",),
        "on": ("ON",),
        "both": ("OFF", "ON"),
    }[args.smoke_condition]
    result = run_benchmark(
        output=args.output,
        traces=args.traces,
        task_limit=1 if args.smoke else 10,
        timeout_seconds=args.timeout,
        allow_short=args.smoke,
        conditions=conditions if args.smoke else ("OFF", "ON"),
        mode=args.mode,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
