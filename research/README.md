# Research map

This folder connects PSG / PSG to existing repository-level software-engineering research. Its purpose is to make the design traceable, identify what is supported by prior evidence, and separate those foundations from claims that still require evaluation.

## The short version

PSG sits at the intersection of four research threads:

| Research thread | What prior work tells us | PSG response |
| --- | --- | --- |
| Repository context retrieval | Useful code context is distributed, and selecting relevant symbols or files can outperform in-file or unfiltered context. | Incremental file/symbol graph and token-budgeted context packs. |
| Dependency-aware planning | Repository changes often require coordinated edits whose effects propagate through dependencies. | Explicit targets, graph edges, impact expansion, decisions, and mutation scope. |
| Agent interfaces and controls | The tools and interfaces exposed to an agent materially shape its behavior and performance. | Structured CLI/MCP operations for context, policy, evidence, review, and shipping. |
| Executable evaluation and convergence | Real issue resolution requires multi-file reasoning, tests, patch validation, and a defensible stopping condition. | Worktree-bound evidence, acceptance criteria, bounded review, and a ship gate. |

## Closest foundations

### 1. Selecting repository context

- **RepoCoder** uses iterative retrieval and generation for repository-level code completion. Its authors report more than a 10% improvement over an in-file baseline across their evaluated settings. PSG shares the principle that context should be selected from the repository rather than assumed to live in the active file. [Paper](https://arxiv.org/abs/2303.12570)
- **Aider's repository map** exposes important symbols and uses a dependency graph plus graph ranking to fit relevant repository information into a token budget. PSG uses a related graph-and-budget idea, while also storing task, policy, decision, and evidence nodes. [Technical documentation](https://aider.chat/docs/repomap.html)
- **AutoCodeRover** uses AST-level program structure, iterative code search, and test-based fault localization to sharpen context for issue resolution. PSG v1 similarly extracts Python symbols, but does not yet implement spectrum-based fault localization. [Paper](https://arxiv.org/abs/2404.05427)

### 2. Planning changes across dependencies

- **CodePlan** frames repository-level coding as planning and combines incremental dependency analysis, may-impact analysis, and adaptive planning. This directly supports the decision to model targets and dependency impact rather than treat a repository as an unordered bag of files. [Paper](https://arxiv.org/abs/2309.12499)

### 3. Giving agents better interfaces

- **SWE-agent** argues that an agent-computer interface can materially affect repository navigation, editing, and test execution. PSG is deliberately exposed through constrained, structured operations rather than a prose-only convention. [Paper](https://arxiv.org/abs/2405.15793)
- **OpenAI Skills** are folder bundles with a `SKILL.md` entry point and optional supporting resources. PSG follows that bundle model: the Skill teaches the workflow while the runtime provides deterministic stateful operations. [OpenAI documentation](https://developers.openai.com/plugins/build/skills)
- **Model Context Protocol** standardizes how applications expose context and tools to models. PSG's MCP server is the tool boundary; the project graph remains the authoritative local state. [MCP 2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

### 4. Proving and stopping

- **SWE-bench** consists of 2,294 real GitHub issues from 12 Python repositories and emphasizes that issue resolution can require coordination across functions, classes, files, and execution environments. It motivates evaluating complete repository changes rather than isolated generation. [Paper](https://arxiv.org/abs/2310.06770)
- **Agentless** decomposes issue resolution into localization, repair, and patch validation, showing the value of a simple, interpretable workflow rather than assuming that more agent complexity is always better. PSG adopts the same preference for observable phases and deterministic validation. [Paper](https://arxiv.org/abs/2407.01489)

## What is original in the PSG synthesis?

The individual ingredients—retrieval, dependency graphs, policies, tests, and tool interfaces—all have precedents. PSG's research proposition is their integration into a **persistent, model-independent project-state graph** that treats context selection, mutation authority, evidence freshness, review budgets, and convergence as one lifecycle.

That proposition is plausible, but it is not proven by the papers above. The current 12-task benchmark is a mechanics test. The next step is the controlled evaluation described in [evaluation-plan.md](evaluation-plan.md).

## Files in this folder

- [literature-notes.md](literature-notes.md) contains annotated reading notes and design implications.
- [evaluation-plan.md](evaluation-plan.md) defines research questions, baselines, metrics, and threats to validity.
- [references.bib](references.bib) provides reusable BibTeX entries.

Last literature check: **2026-09-01**. Prefer the linked first-party paper pages and official documentation when updating these notes.
