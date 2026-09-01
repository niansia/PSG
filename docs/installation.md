# Installation and host setup

PSG has two installed parts: the Python runtime (`psg` and `psg-mcp`) and the complete `psg/` Skill folder. `SKILL.md` is the entry playbook; its neighboring references and agent metadata are part of the product and always travel with it.

## Normal installation

### Windows

```powershell
python -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2"; psg setup
```

### macOS / Linux

```bash
python3 -m pip install "psg-runtime[mcp] @ git+https://github.com/niansia/PSG.git@v1.1.2" && psg setup
```

`psg setup` detects installed Codex, Claude Code, and Gemini CLI executables. For every detected host it:

1. copies the complete Skill bundle into the host's user Skill directory;
2. registers the `psg-mcp` stdio server through the host's native MCP command;
3. records integration state under the user's PSG home; and
4. reports any host that still needs attention.

Then initialize each Git project once:

```text
cd your-project
psg init
```

`psg init` creates `.psg/`, performs the first incremental index, and automatically runs setup if a detected host is missing its integration.

PSG deliberately uses the Python package as its distribution channel. Native standalone binaries and package-manager entries such as WinGet, Scoop, Homebrew, and npm are deferred distribution polish; when they arrive they will remain wrappers around the same runtime rather than new architectural dependencies.

## Supported hosts

| Host | Skill destination | MCP registration |
| --- | --- | --- |
| Codex | `~/.codex/skills/psg/` | `codex mcp` |
| Claude Code | `~/.claude/skills/psg/` | user-scope [`claude mcp`](https://code.claude.com/docs/en/mcp#mcp-installation-scopes) |
| Gemini CLI | `~/.gemini/skills/psg/` | user-scope [`gemini mcp`](https://geminicli.com/docs/tools/mcp-server/) |

Claude Code documents personal Skills under `~/.claude/skills/<skill-name>/`, and Gemini CLI documents user Skills under `~/.gemini/skills/` or its `.agents/skills/` alias. See [Claude Code Skill locations](https://code.claude.com/docs/en/skills#where-skills-live) and [Gemini CLI discovery tiers](https://geminicli.com/docs/cli/using-agent-skills/#discovery-tiers).

OpenAI's Skill API accepts a directory upload or a zip bundle rather than only one Markdown file. This is why PSG never installs only the entry playbook: [OpenAI Skill creation API](https://developers.openai.com/api/reference/python/resources/skills/methods/create).

Grok, Copilot CLI, Cursor, and other adapters are intentionally deferred until their Skill and MCP contracts can be verified. PSG v1 does not guess or edit another product's undocumented configuration.

## Setup controls

The default is auto-detection:

```text
psg setup
```

Explicit selection is available for diagnostics or controlled installations:

```text
psg setup codex
psg setup claude
psg setup gemini
psg setup --all
```

`--all` means all detected hosts. The positional `psg setup all` form is an advanced override that also prepares directories for supported hosts whose CLI is not currently detected; MCP registration for an absent CLI will be reported as incomplete.

Use `psg setup --skill-dir C:\custom\skills` to copy the bundle to a custom parent directory without registering a Host MCP entry.

If a host starts MCP outside the repository, its process must inherit the project working directory or be given `PSG_PROJECT_ROOT` as the absolute project path. Normal Codex, Claude Code, and Gemini CLI project sessions inherit the working directory and do not need a per-project MCP registration.

## Review hosts

Codex, Claude Code, and Gemini CLI run the full runtime and enforce the Task Contract. A
chat model can also review against the same contract without any installation:

```powershell
psg handoff --output PSG_REVIEW.md
```

Paste that file into ChatGPT, Claude, or Gemini. It carries the Task Contract, the changed
files and symbols, relevant constraints and decisions, trusted verification, accepted debt,
known issues with their relation to the task, the current ship preview, and follow-up
findings — and nothing else. The reviewer follows the boundary; only the execution hosts
enforce it. `psg handoff` never changes task status and never writes to the event log.

## Update and removal

```text
psg update
psg update --channel dev
psg uninstall
```

`psg update` discovers the newest stable `vX.Y.Z` Git release tag, upgrades to that exact tag, refreshes the bundled Skill, and re-registers the detected MCP integrations. Prerelease tags and `main` are never selected by the stable channel. `psg update --channel dev` explicitly follows `main`; `psg update --source ...` remains an advanced custom-source override. `psg uninstall` removes PSG's Host integrations and runtime package, but never searches for or deletes project `.psg/` directories. Reinstalling PSG can reuse those durable project states.

## Global and project lifecycle

The Skill is globally available but a project opts in only when it contains `.psg/config.yaml`:

```text
global install      → PSG available
psg init            → current project opts in
psg off             → current project pauses
psg off --global    → all automatic PSG governance pauses
```

`psg on` and `psg on --global` reverse those switches. `psg status` shows project health, detected Agents, Skill/MCP integration, Git state, and the current task.

## Approval boundary

Ordinary MCP can create claims and proposals, but it cannot accept portable-state edits, approve Decisions or Debt, waive criteria, unlock frozen nodes, or attest an independent high-risk review. Those operations are deliberately local user actions.

When an Agent presents one of these proposals, review it before using the matching CLI approval command. Do not grant a reusable shell rule that lets an Agent run PSG approval commands automatically; the local CLI is the v1 fallback approval boundary until host-native user attestation is available.

## Wheel and development installs

From the bundled wheel:

```powershell
python -m pip install ".\psg_runtime-1.1.2-py3-none-any.whl[mcp]"; psg setup
```

From a source checkout:

```powershell
python -m pip install ".[mcp,dev]"; psg setup
```

Use `psg --json status` or `psg --json doctor` when machine-readable output is needed. The graph/task/verification/snapshot subcommands remain available as advanced and debug interfaces, but ordinary users should not need them.
