from __future__ import annotations

import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_skill_source_and_release_archive_are_complete_and_in_sync() -> None:
    source = ROOT / "skills" / "psg"
    archive = ROOT / "artifacts" / "psg-skill-v1.0.0.zip"
    required = {
        "psg/SKILL.md",
        "psg/agents/openai.yaml",
        "psg/references/compatibility-contract.md",
        "psg/references/convergence-recovery.md",
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
    wheel = ROOT / "artifacts" / "psg_runtime-1.0.0-py3-none-any.whl"
    relative_files = {
        Path("SKILL.md"),
        Path("agents/openai.yaml"),
        Path("references/compatibility-contract.md"),
        Path("references/convergence-recovery.md"),
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
