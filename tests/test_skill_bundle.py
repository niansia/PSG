from __future__ import annotations

import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_skill_source_and_release_archive_are_complete_and_in_sync() -> None:
    source = ROOT / "skills" / "psg"
    archive = ROOT / "artifacts" / "psg-skill-v1.1.0.zip"
    required = {
        "psg/SKILL.md",
        "psg/agents/openai.yaml",
        "psg/references/compatibility-contract.md",
        "psg/references/convergence-recovery.md",
        "psg/references/review-boundary.md",
        "psg/references/runtime-operations.md",
    }
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert required <= names
        for name in required:
            relative = Path(name).relative_to("psg")
            assert bundle.read(name) == (source / relative).read_bytes()


def test_runtime_wheel_embeds_the_complete_skill_bundle() -> None:
    source = ROOT / "skills" / "psg"
    wheel = ROOT / "artifacts" / "psg_runtime-1.1.0-py3-none-any.whl"
    relative_files = {
        Path("SKILL.md"),
        Path("agents/openai.yaml"),
        Path("references/compatibility-contract.md"),
        Path("references/convergence-recovery.md"),
        Path("references/review-boundary.md"),
        Path("references/runtime-operations.md"),
    }
    with zipfile.ZipFile(wheel) as bundle:
        names = bundle.namelist()
        for relative in relative_files:
            suffix = f"share/psg/skill/{relative.as_posix()}"
            matches = [name for name in names if name.endswith(suffix)]
            assert len(matches) == 1
            assert bundle.read(matches[0]) == (source / relative).read_bytes()

    skill_text = (source / "SKILL.md").read_text(encoding="utf-8")
    assert skill_text.startswith("---\n")
    frontmatter = yaml.safe_load(skill_text.split("---", 2)[1])
    assert frontmatter["name"] == "psg"
    assert frontmatter["description"]
    agent = yaml.safe_load(
        (source / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert agent["interface"]["display_name"] == "PSG"


def test_runtime_wheel_ships_only_this_project() -> None:
    """A reused setuptools build directory silently smuggles stale packages into the wheel."""
    wheel = ROOT / "artifacts" / "psg_runtime-1.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as bundle:
        names = bundle.namelist()
        top_level = {name.split("/", 1)[0] for name in names if "/" in name}
        unexpected = {
            item
            for item in top_level
            if item != "psg" and not item.startswith("psg_runtime-")
        }
        assert not unexpected, (
            f"wheel carries unexpected packages: {sorted(unexpected)}"
        )
        crlf = b"\x0d\x0a"
        carriage = [
            name for name in names if name.endswith(".py") and crlf in bundle.read(name)
        ]
        assert not carriage, f"wheel carries CRLF line endings: {carriage}"
