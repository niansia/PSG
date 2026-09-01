from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml

from .util import atomic_write_text, utc_now

HOSTS = {
    "codex": {
        "display_name": "Codex",
        "executable": "codex",
        "skill_parent": Path(".codex") / "skills",
    },
    "claude": {
        "display_name": "Claude Code",
        "executable": "claude",
        "skill_parent": Path(".claude") / "skills",
    },
    "gemini": {
        "display_name": "Gemini CLI",
        "executable": "gemini",
        "skill_parent": Path(".gemini") / "skills",
    },
}
REPOSITORY_GIT_URL = "https://github.com/niansia/PSG.git"
DEFAULT_UPDATE_CHANNEL = "stable"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def psg_version() -> str:
    try:
        return version("psg-runtime")
    except PackageNotFoundError:
        return "1.0.1-dev"


def global_home() -> Path:
    override = os.environ.get("PSG_HOME")
    return (
        Path(override).expanduser().resolve()
        if override
        else (Path.home() / ".psg").resolve()
    )


def user_home() -> Path:
    override = os.environ.get("PSG_USER_HOME")
    return Path(override).expanduser().resolve() if override else Path.home().resolve()


def global_settings() -> dict[str, Any]:
    path = global_home() / "config.yaml"
    if not path.is_file():
        return {"version": 1, "enabled": True}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "version": int(value.get("version", 1)),
        "enabled": bool(value.get("enabled", True)),
    }


def set_global_enabled(enabled: bool) -> dict[str, Any]:
    path = global_home() / "config.yaml"
    value = global_settings()
    value["enabled"] = bool(enabled)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, yaml.safe_dump(value, sort_keys=False))
    return {"scope": "global", "enabled": bool(enabled), "path": str(path)}


def skill_source() -> Path:
    override = os.environ.get("PSG_SKILL_SOURCE")
    candidates = [
        Path(override).expanduser() if override else None,
        Path(__file__).resolve().parents[2] / "skills" / "psg",
        Path(sysconfig.get_path("data")) / "share" / "psg" / "skill",
    ]
    for candidate in candidates:
        if candidate and (candidate / "SKILL.md").is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "The PSG Skill bundle is missing from this installation. Reinstall the "
        "psg-runtime wheel or set PSG_SKILL_SOURCE to the complete skill folder."
    )


def setup_skill(
    host: str = "auto",
    *,
    skill_dir: str | Path | None = None,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    source = skill_source()
    selected = _select_hosts(host)
    if skill_dir:
        destinations = [("custom", Path(skill_dir).expanduser().resolve() / "psg")]
    else:
        destinations = [
            (
                name,
                (user_home() / HOSTS[name]["skill_parent"] / "psg").resolve(),
            )
            for name in selected
        ]
    installed: list[dict[str, Any]] = []
    for name, destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        installed.append(
            {
                "host": name,
                "path": str(destination),
                "skill_entry": str(destination / "SKILL.md"),
            }
        )

    integrations: list[dict[str, Any]] = []
    if not skill_dir:
        for name in selected:
            integrations.append(_register_mcp(name, runner=runner))

    settings = (
        {
            **global_settings(),
            "scope": "global",
            "path": str(global_home() / "config.yaml"),
        }
        if skill_dir
        else set_global_enabled(global_settings()["enabled"])
    )
    result = {
        "version": psg_version(),
        "installed": installed,
        "integrations": integrations,
        "source": str(source),
        "global": settings,
        "runtime": {
            "cli": _entrypoint("psg"),
            "mcp_command": _entrypoint("psg-mcp"),
        },
        "ready": bool(installed)
        and all(item.get("mcp_registered") for item in integrations),
        "warnings": []
        if installed
        else [
            "No supported Codex, Claude Code, or Gemini CLI executable was detected."
        ],
        "next": "Run 'psg init' once inside each Git project you want governed.",
    }
    if not skill_dir:
        _write_registry(result)
    return result


def installation_status() -> dict[str, Any]:
    registry = _read_registry()
    recorded = {
        str(item.get("host")): item
        for item in registry.get("installed", [])
        if item.get("host")
    }
    integrations = {
        str(item.get("host")): item
        for item in registry.get("integrations", [])
        if item.get("host")
    }
    agents = []
    for name, config in HOSTS.items():
        executable = shutil.which(str(config["executable"]))
        destination = (user_home() / config["skill_parent"] / "psg").resolve()
        agents.append(
            {
                "id": name,
                "name": config["display_name"],
                "detected": bool(executable),
                "skill_installed": (destination / "SKILL.md").is_file(),
                "mcp_registered": bool(
                    integrations.get(name, {}).get("mcp_registered", False)
                ),
                "path": str(destination),
                "recorded": name in recorded,
            }
        )
    return {
        "version": psg_version(),
        "global_enabled": global_settings()["enabled"],
        "agents": agents,
        "registry": str(global_home() / "install.json"),
    }


def update_installation(
    source: str | None = None,
    *,
    channel: str = DEFAULT_UPDATE_CHANNEL,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    run = runner or _run_command
    resolved_source, release = _resolve_update_source(
        source=source, channel=channel, runner=run
    )
    upgrade = run(
        [sys.executable, "-m", "pip", "install", "--upgrade", resolved_source]
    )
    if upgrade.returncode != 0:
        raise RuntimeError(_command_error("PSG runtime update failed", upgrade))
    setup = run([sys.executable, "-m", "psg.cli", "--json", "setup"])
    if setup.returncode != 0:
        raise RuntimeError(_command_error("PSG integration refresh failed", setup))
    try:
        refreshed = json.loads(setup.stdout)
    except json.JSONDecodeError:
        refreshed = {"output": setup.stdout.strip()}
    return {
        "updated": True,
        "channel": "custom" if source else channel,
        "release": release,
        "source": resolved_source,
        "integrations": refreshed,
        "message": (
            f"PSG {release} was installed from the "
            f"{'custom source' if source else channel + ' channel'}; "
            "the Skill bundle and MCP registrations were refreshed."
        ),
    }


def _resolve_update_source(
    *, source: str | None, channel: str, runner: CommandRunner
) -> tuple[str, str]:
    if source:
        return source, "custom"
    if channel == "dev":
        return f"psg-runtime[mcp] @ git+{REPOSITORY_GIT_URL}@main", "main"
    if channel != DEFAULT_UPDATE_CHANNEL:
        raise ValueError(f"Unsupported PSG update channel: {channel}")
    tag = _latest_stable_tag(runner)
    return f"psg-runtime[mcp] @ git+{REPOSITORY_GIT_URL}@{tag}", tag


def _latest_stable_tag(runner: CommandRunner) -> str:
    process = runner(["git", "ls-remote", "--tags", "--refs", REPOSITORY_GIT_URL])
    if process.returncode != 0:
        raise RuntimeError(
            _command_error("Could not discover the latest stable PSG release", process)
        )
    releases: list[tuple[tuple[int, int, int], str]] = []
    for line in process.stdout.splitlines():
        match = re.search(r"refs/tags/(v(\d+)\.(\d+)\.(\d+))$", line.strip())
        if match:
            releases.append(
                (
                    (int(match.group(2)), int(match.group(3)), int(match.group(4))),
                    match.group(1),
                )
            )
    if not releases:
        raise RuntimeError("No stable PSG release tag matching vX.Y.Z was found.")
    return max(releases)[1]


def uninstall_installation(
    *, remove_runtime: bool = True, runner: CommandRunner | None = None
) -> dict[str, Any]:
    run = runner or _run_command
    registry = _read_registry()
    host_names = {
        str(item.get("host"))
        for item in registry.get("installed", [])
        if item.get("host") in HOSTS
    }
    host_names.update(
        name
        for name, config in HOSTS.items()
        if shutil.which(str(config["executable"]))
    )
    integrations = [_remove_mcp(name, runner=run) for name in sorted(host_names)]

    removed: list[str] = []
    candidates = {
        Path(str(item["path"])).expanduser().resolve()
        for item in registry.get("installed", [])
        if item.get("path")
    }
    candidates.update(
        (user_home() / config["skill_parent"] / "psg").resolve()
        for config in HOSTS.values()
    )
    for destination in sorted(candidates, key=str):
        if _is_psg_skill_directory(destination):
            shutil.rmtree(destination)
            removed.append(str(destination))

    runtime_removed = False
    runtime_error = ""
    if remove_runtime:
        process = run([sys.executable, "-m", "pip", "uninstall", "-y", "psg-runtime"])
        runtime_removed = process.returncode == 0
        if not runtime_removed:
            runtime_error = _command_error("Runtime uninstall failed", process)

    registry_path = global_home() / "install.json"
    if registry_path.is_file():
        registry_path.unlink()
    return {
        "uninstalled": (not remove_runtime or runtime_removed)
        and all(item["removed"] for item in integrations),
        "runtime_removed": runtime_removed,
        "runtime_error": runtime_error,
        "skills_removed": removed,
        "integrations": integrations,
        "project_state": "preserved",
        "message": "Project .psg/ directories were not changed.",
    }


def _select_hosts(host: str) -> list[str]:
    if host == "all":
        return list(HOSTS)
    if host != "auto":
        if host not in HOSTS:
            raise ValueError(f"Unsupported PSG host: {host}")
        return [host]
    detected = [
        name
        for name, config in HOSTS.items()
        if shutil.which(str(config["executable"]))
    ]
    return detected


def _register_mcp(host: str, *, runner: CommandRunner | None = None) -> dict[str, Any]:
    run = runner or _run_command
    executable = shutil.which(str(HOSTS[host]["executable"]))
    mcp_command = _entrypoint("psg-mcp")
    if not executable:
        return {
            "host": host,
            "mcp_registered": False,
            "error": f"{HOSTS[host]['display_name']} CLI was not found on PATH.",
        }
    _remove_mcp(host, runner=run, executable=executable)
    if host == "codex":
        command = [executable, "mcp", "add", "psg", "--", mcp_command]
    elif host == "claude":
        command = [
            executable,
            "mcp",
            "add",
            "--scope",
            "user",
            "psg",
            "--",
            mcp_command,
        ]
    else:
        command = [
            executable,
            "mcp",
            "add",
            "--scope",
            "user",
            "--transport",
            "stdio",
            "--description",
            "Project State Graph governance runtime",
            "psg",
            mcp_command,
        ]
    process = run(command)
    return {
        "host": host,
        "mcp_registered": process.returncode == 0,
        "command": mcp_command,
        "error": ""
        if process.returncode == 0
        else _command_error("MCP registration failed", process),
    }


def _remove_mcp(
    host: str,
    *,
    runner: CommandRunner | None = None,
    executable: str | None = None,
) -> dict[str, Any]:
    run = runner or _run_command
    resolved = executable or shutil.which(str(HOSTS[host]["executable"]))
    if not resolved:
        return {"host": host, "removed": True, "skipped": "host_not_found"}
    if host == "codex":
        command = [resolved, "mcp", "remove", "psg"]
    else:
        command = [resolved, "mcp", "remove", "--scope", "user", "psg"]
    process = run(command)
    # Removal is idempotent: a missing PSG entry already satisfies the target state.
    return {"host": host, "removed": True, "returncode": process.returncode}


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _entrypoint(name: str) -> str:
    scripts = Path(sysconfig.get_path("scripts"))
    candidates = [scripts / f"{name}.exe", scripts / name]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return shutil.which(name) or name


def _command_error(prefix: str, process: subprocess.CompletedProcess[str]) -> str:
    detail = (process.stderr or process.stdout or "unknown error").strip()
    return f"{prefix}: {detail[-800:]}"


def _write_registry(value: dict[str, Any]) -> None:
    path = global_home() / "install.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(value)
    payload["updated_at"] = utc_now()
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _read_registry() -> dict[str, Any]:
    path = global_home() / "install.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _is_psg_skill_directory(path: Path) -> bool:
    if path.name != "psg" or not path.is_dir():
        return False
    entry = path / "SKILL.md"
    if not entry.is_file():
        return False
    try:
        head = entry.read_text(encoding="utf-8")[:500]
    except OSError:
        return False
    return "name: psg" in head
