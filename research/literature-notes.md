# Annotated literature notes

These notes summarize the aspects most relevant to PSG / WorkGraph. Reported results belong to the cited authors and their experimental settings. The "WorkGraph implication" paragraphs are our design interpretation, not findings from those papers.

## Repository context and retrieval

### RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation

**Reference:** Zhang et al. (2023), arXiv:2303.12570. [Paper](https://arxiv.org/abs/2303.12570) · [Code and RepoEval](https://github.com/microsoft/CodeT/tree/main/RepoCoder)

**Relevant result:** RepoCoder alternates retrieval and generation so newly generated code can improve the next retrieval query. The paper reports improvements of more than 10% over an in-file baseline in every evaluated setting and outperformance of a vanilla retrieval-augmented approach.

**WorkGraph implication:** Repository context should be task-dependent and revisable. WorkGraph's `context build` and explicit `context expand` operations make context selection observable, bounded, and auditable.

### Aider repository map

**Reference:** Aider documentation. [Repository map](https://aider.chat/docs/repomap.html)

**Relevant mechanism:** Aider produces a concise map of important classes, functions, types, and signatures. For large repositories it ranks a file-dependency graph and selects relevant map portions within a token budget.

**WorkGraph implication:** A graph is useful as a routing structure, not merely as a complete knowledge dump. WorkGraph extends the routed graph beyond code symbols to tasks, policies, decisions, evidence, and issues.

### AutoCodeRover: Autonomous Program Improvement

**Reference:** Zhang et al. (2024), arXiv:2404.05427. [Paper](https://arxiv.org/abs/2404.05427)

**Relevant mechanism:** AutoCodeRover searches over program structure such as classes and methods rather than treating a project only as files. It can incorporate spectrum-based fault localization when tests are available. The paper reports 19% resolution on its SWE-bench-lite evaluation at an average stated cost of USD 0.43.

**WorkGraph implication:** Symbol-level structure is a stronger starting point than file names alone. WorkGraph v1 implements Python AST extraction; fault-localization edges are a logical future extension.

## Planning and change impact

### CodePlan: Repository-level Coding using LLMs and Planning

**Reference:** Bairi et al. (2023), arXiv:2309.12499. [Paper](https://arxiv.org/abs/2309.12499) · [Implementation](https://github.com/microsoft/codeplan)

**Relevant result:** CodePlan combines incremental dependency analysis, change may-impact analysis, and adaptive planning. Its evaluated tasks required changes across 2–97 files. The authors report that CodePlan passed validity checks on five of six repositories in their setup while the no-planning baselines passed none.

**WorkGraph implication:** Scope cannot be enforced safely without representing both intended targets and likely impact. WorkGraph therefore keeps target/write/read-only/forbidden scopes separate and validates the resulting Git diff.

## Agent interfaces

### SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering

**Reference:** Yang et al. (2024), arXiv:2405.15793. [Paper](https://arxiv.org/abs/2405.15793)

**Relevant result:** SWE-agent studies how interface design changes agent behavior and performance, with custom operations for repository navigation, editing, and program execution.

**WorkGraph implication:** Project governance should be executable through narrow structured operations. A written convention alone cannot deterministically check the current diff or bind evidence to a worktree revision.

### Skills and MCP

**References:** [OpenAI Skills documentation](https://developers.openai.com/plugins/build/skills) · [OpenAI MCP server documentation](https://developers.openai.com/plugins/build/mcp-server) · [MCP 2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

**Relevant mechanism:** A Skill can package a repeatable workflow and supporting resources, while MCP exposes callable tools and context. The July 2026 MCP release moves the protocol core to a stateless request/response model; WorkGraph's persistent state therefore lives in its own repository-local store rather than relying on a transport session.

**WorkGraph implication:** The Skill and runtime have different jobs. `SKILL.md` teaches an agent when and how to use WorkGraph; the MCP server performs deterministic reads and writes against the graph.

## Evaluation, verification, and convergence

### SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

**Reference:** Jimenez et al. (2023), arXiv:2310.06770. [Paper](https://arxiv.org/abs/2310.06770) · [Benchmark](https://www.swebench.com/original.html)

**Relevant contribution:** SWE-bench defines 2,294 issue-resolution tasks from 12 Python repositories. Its task formulation requires a model to work with a codebase and issue description, often coordinating changes across multiple program elements and executing tests.

**WorkGraph implication:** A meaningful WorkGraph evaluation must use real repository histories, held-out tasks, executable test environments, and patch-level correctness—not only context compression.

### Agentless: Demystifying LLM-based Software Engineering Agents

**Reference:** Xia et al. (2024), arXiv:2407.01489. [Paper](https://arxiv.org/abs/2407.01489)

**Relevant mechanism:** Agentless separates localization, repair, and patch validation. Its central lesson for this project is methodological: a simpler, interpretable pipeline can be competitive, and every extra layer should justify its cost.

**WorkGraph implication:** WorkGraph keeps its phases inspectable and avoids hiding completion behind an agent's self-assessment. The ship gate is a deterministic predicate over current state and evidence.

## Open questions

1. Does persistent project state improve success across a sequence of related tasks, not only one isolated issue?
2. Does policy enforcement reduce unauthorized or unnecessary edits without suppressing valid dependency changes?
3. How often is the initial context pack sufficient, and what signals best predict safe expansion?
4. Can bounded review preserve defect discovery while reducing repeated low-value findings?
5. How does graph maintenance cost scale across languages and large monorepos?

These questions are converted into a testable protocol in [evaluation-plan.md](evaluation-plan.md).
