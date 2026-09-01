from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from psg.runtime import PSG


@pytest.fixture(autouse=True)
def isolated_psg_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSG_HOME", str(tmp_path / "global-psg"))
    monkeypatch.setenv("PSG_USER_HOME", str(tmp_path / "user-home"))


def run(repo: Path, *args: str) -> str:
    process = subprocess.run(
        list(args),
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(process.stderr)
    return process.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "backend.py").write_text(
        "def locked_api(value: int) -> int:\n    return value * 2\n",
        encoding="utf-8",
    )
    (root / "src" / "app.py").write_text(
        "from src.backend import locked_api\n\ndef feature(value: int) -> int:\n    return locked_api(value) + 1\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_app.py").write_text(
        "from src.app import feature\n\ndef test_feature():\n    assert feature(2) == 5\n",
        encoding="utf-8",
    )
    run(root, "git", "init", "-b", "main")
    run(root, "git", "config", "user.email", "psg@example.invalid")
    run(root, "git", "config", "user.name", "PSG Test")
    run(root, "git", "add", ".")
    run(root, "git", "commit", "-m", "baseline")
    return root


@pytest.fixture()
def graph(repo: Path) -> PSG:
    instance = PSG.initialize(repo, project="sample")
    instance.index()
    return instance


@pytest.fixture()
def task(graph: PSG) -> dict:
    opened = graph.task_open(
        intent="Change the feature without changing the backend contract",
        acceptance_criteria=["Feature behavior is verified"],
        constraints=["Backend API remains unchanged"],
        targets=["src/app.py"],
        read_only=["src/backend.py"],
        risk="medium",
    )
    graph.context_build(opened["id"])
    return opened
