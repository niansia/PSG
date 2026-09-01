"""Build, validate, and smoke-test the PSG release artifacts.

The same entry point runs in CI on every supported platform and produces the
files published with a GitHub Release, so what CI proves is what ships.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import venv
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_SOURCE = ROOT / "skills" / "psg"
REQUIRED_SKILL_FILES = (
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
    Path("references/compatibility-contract.md"),
    Path("references/convergence-recovery.md"),
    Path("references/review-boundary.md"),
    Path("references/runtime-operations.md"),
)


def project_version() -> str:
    """Read the single source of truth and prove every copy agrees with it."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        raise SystemExit("pyproject.toml does not declare a version")
    version = match.group(1)
    package = (ROOT / "src" / "psg" / "__init__.py").read_text(encoding="utf-8")
    declared = re.search(r'^__version__ = "([^"]+)"', package, re.MULTILINE)
    if not declared or declared.group(1) != version:
        found = declared.group(1) if declared else None
        raise SystemExit(
            f"src/psg/__init__.py declares {found!r}, "
            f"but pyproject.toml declares {version!r}"
        )
    installer = (ROOT / "src" / "psg" / "installer.py").read_text(encoding="utf-8")
    fallback = re.search(r'return "([^"]+)-dev"', installer)
    if not fallback or fallback.group(1) != version:
        found = fallback and fallback.group(1)
        raise SystemExit(
            f"src/psg/installer.py falls back to {found!r}, expected {version!r}"
        )
    return version


def validate_skill_source() -> None:
    """Check the Skill bundle the way a host loader will read it."""
    missing = [
        str(relative)
        for relative in REQUIRED_SKILL_FILES
        if not (SKILL_SOURCE / relative).is_file()
    ]
    if missing:
        raise SystemExit(f"Skill bundle is missing: {', '.join(missing)}")
    text = (SKILL_SOURCE / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit("SKILL.md must open with YAML frontmatter")
    frontmatter = yaml.safe_load(text.split("---", 2)[1]) or {}
    if frontmatter.get("name") != "psg":
        raise SystemExit("SKILL.md frontmatter name must be psg")
    description = str(frontmatter.get("description", "")).strip()
    if not description:
        raise SystemExit("SKILL.md frontmatter needs a description")
    if len(description) > 1024:
        raise SystemExit("SKILL.md description is too long for host loaders")
    agent = yaml.safe_load(
        (SKILL_SOURCE / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    if agent.get("interface", {}).get("display_name") != "PSG":
        raise SystemExit("agents/openai.yaml must present the PSG display name")


def build_skill_archive(version: str, output_dir: Path) -> Path:
    archive = output_dir / f"psg-skill-v{version}.zip"
    files = sorted(path for path in SKILL_SOURCE.rglob("*") if path.is_file())
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            arcname = f"psg/{path.relative_to(SKILL_SOURCE).as_posix()}"
            bundle.write(path, arcname)
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        required = {f"psg/{item.as_posix()}" for item in REQUIRED_SKILL_FILES}
        if not required <= names:
            raise SystemExit(f"Skill archive is missing: {sorted(required - names)}")
        for relative in REQUIRED_SKILL_FILES:
            name = f"psg/{relative.as_posix()}"
            if bundle.read(name) != (SKILL_SOURCE / relative).read_bytes():
                raise SystemExit(f"Skill archive diverged from source: {name}")
    return archive


def build_wheel(output_dir: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(output_dir)],
        cwd=ROOT,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    wheels = sorted(output_dir.glob("psg_runtime-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected exactly one runtime wheel, found {wheels}")
    return wheels[0]


def _venv_executable(prefix: Path, name: str) -> Path:
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    suffix = ".exe" if sys.platform == "win32" else ""
    return prefix / scripts / f"{name}{suffix}"


def smoke_test(wheel: Path, archive: Path, version: str) -> None:
    """Install the built wheel into a clean environment and actually use it."""
    with tempfile.TemporaryDirectory(prefix="psg-release-smoke-") as directory:
        prefix = Path(directory) / "venv"
        venv.create(prefix, with_pip=True, clear=True)
        python = _venv_executable(prefix, "python")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", str(wheel)],
            check=True,
            stdin=subprocess.DEVNULL,
        )
        reported = subprocess.run(
            [str(python), "-c", "import psg; print(psg.__version__)"],
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
        if reported != version:
            raise SystemExit(
                f"Installed wheel reports {reported!r}, expected {version!r}"
            )
        subprocess.run(
            [str(_venv_executable(prefix, "psg")), "--help"],
            check=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        data_root = Path(
            sysconfig.get_path(
                "data", vars={"base": str(prefix), "platbase": str(prefix)}
            )
        )
        for relative in REQUIRED_SKILL_FILES:
            shipped = data_root / "share" / "psg" / "skill" / relative
            if not shipped.is_file():
                raise SystemExit(f"Wheel did not install the Skill file: {shipped}")

        extracted = Path(directory) / "skill"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extracted)
        for relative in REQUIRED_SKILL_FILES:
            if not (extracted / "psg" / relative).is_file():
                raise SystemExit(f"Skill archive did not extract: {relative}")


def write_checksums(output_dir: Path, artifacts: list[Path]) -> Path:
    lines = []
    for path in sorted(artifacts, key=lambda item: item.name):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    checksums = output_dir / "SHA256SUMS"
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist-release")
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Build and validate without creating a clean install environment",
    )
    parser.add_argument(
        "--publish-to",
        type=Path,
        default=None,
        help="Copy the built wheel and Skill archive into this directory",
    )
    args = parser.parse_args()

    version = project_version()
    validate_skill_source()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    archive = build_skill_archive(version, output_dir)
    wheel = build_wheel(output_dir)
    if not args.skip_smoke:
        smoke_test(wheel, archive, version)
    checksums = write_checksums(output_dir, [wheel, archive])

    if args.publish_to:
        destination = args.publish_to.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        for path in (wheel, archive):
            shutil.copy2(path, destination / path.name)

    print(f"PSG {version} release artifacts in {output_dir}")
    for path in (wheel, archive, checksums):
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
