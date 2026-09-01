from __future__ import annotations

import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_skill_source_and_release_archive_are_complete_and_in_sync() -> None:
    source = ROOT / "skills" / "psg"
    archive = ROOT / "artifacts" / "psg-skill-v1.1.2.zip"
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
    wheel = ROOT / "artifacts" / "psg_runtime-1.1.2-py3-none-any.whl"
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
    wheel = ROOT / "artifacts" / "psg_runtime-1.1.2-py3-none-any.whl"
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


TRANSLATIONS = {
    "README.md": "English",
    "README.zh-TW.md": "繁體中文",
    "README.zh-CN.md": "简体中文",
    "README.ja.md": "日本語",
}


def test_every_readme_translation_links_to_the_others() -> None:
    """A translation nobody can reach from the others is a translation nobody reads."""
    for name in TRANSLATIONS:
        path = ROOT / name
        assert path.is_file(), f"missing translation: {name}"
        text = path.read_text(encoding="utf-8")
        for other, label in TRANSLATIONS.items():
            if other == name:
                # The current language is shown as bold text, not a link back to itself.
                assert f"**{label}**" in text, f"{name} does not mark itself as {label}"
            else:
                assert f"]({other})" in text, f"{name} does not link to {other}"


def test_readme_translations_stay_structurally_in_sync() -> None:
    """Headings drift first when a translation is left behind."""
    counts = {}
    for name in TRANSLATIONS:
        text = (ROOT / name).read_text(encoding="utf-8")
        counts[name] = sum(1 for line in text.splitlines() if line.startswith("## "))
    reference = counts["README.md"]
    for name, count in counts.items():
        assert count == reference, (
            f"{name} has {count} top-level sections, README.md has {reference}"
        )
