# Annotated literature notes

These notes summarize the aspects most relevant to PSG / PSG. Reported results belong to the cited authors and their experimental settings. The "PSG implication" paragraphs are our design interpretation, not findings from those papers.

## Repository context and retrieval

### RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation

**Reference:** Zhang et al. (2023), arXiv:2303.12570. [Paper](https://arxiv.org/abs/2303.12570) · [Code and RepoEval](https://github.com/microsoft/CodeT/tree/main/RepoCoder)

**Relevant result:** RepoCoder alternates retrieval and generation so newly generated code can improve the next retrieval query. The paper reports improvements of more than 10% over an in-file baseline in every evaluated setting and outperformance of a vanilla retrieval-augmented approach.

**PSG implication:** Repository context should be task-dependent and revisable. PSG's `context build` and explicit `context expand` operations make context selection observable, bounded, and auditable.

### Aider repository map

**Reference:** Aider documentation. [Repository map](https://aider.chat/docs/repomap.html)

**Relevant mechanism:** Aider produces a concise map of important classes, functions, types, and signatures. For large repositories it ranks a file-dependency graph and selects relevant map portions within a token budget.

**PSG implication:** A graph is useful as a routing structure, not merely as a complete knowledge dump. PSG extends the routed graph beyond code symbols to tasks, policies, decisions, evidence, and issues.

### AutoCodeRover: Autonomous Program Improvement

**Reference:** Zhang et al. (2024), arXiv:2404.05427. [Paper](https://arxiv.org/abs/2404.05427)

**Relevant mechanism:** AutoCodeRover searches over program structure such as classes and methods rather than treating a project only as files. It can incorporate spectrum-based fault localization when tests are available. The paper reports 19% resolution on its SWE-bench-lite evaluation at an average stated cost of USD 0.43.

**PSG implication:** Symbol-level structure is a stronger starting point than file names alone. PSG v1 implements Python AST extraction; fault-localization edges are a logical future extension.

## Planning and change impact

### CodePlan: Repository-level Coding using LLMs and Planning

**Reference:** Bairi et al. (2023), arXiv:2309.12499. [Paper](https://arxiv.org/abs/2309.12499) · [Implementation](https://github.com/microsoft/codeplan)

**Relevant result:** CodePlan combines incremental dependency analysis, change may-impact analysis, and adaptive planning. Its evaluated tasks required changes across 2–97 files. The authors report that CodePlan passed validity checks on five of six repositories in their setup while the no-planning baselines passed none.

**PSG implication:** Scope cannot be enforced safely without representing both intended targets and likely impact. PSG therefore keeps target/write/read-only/forbidden scopes separate and validates the resulting Git diff.

## Agent interfaces

### SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering

**Reference:** Yang et al. (2024), arXiv:2405.15793. [Paper](https://arxiv.org/abs/2405.15793)

**Relevant result:** SWE-agent studies how interface design changes agent behavior and performance, with custom operations for repository navigation, editing, and program execution.

**PSG implication:** Project governance should be executable through narrow structured operations. A written convention alone cannot deterministically check the current diff or bind evidence to a worktree revision.

### Skills and MCP

**References:** [OpenAI Skills documentation](https://developers.openai.com/plugins/build/skills) · [OpenAI MCP server documentation](https://developers.openai.com/plugins/build/mcp-server) · [MCP 2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

**Relevant mechanism:** A Skill can package a repeatable workflow and supporting resources, while MCP exposes callable tools and context. The July 2026 MCP release moves the protocol core to a stateless request/response model; PSG's persistent state therefore lives in its own repository-local store rather than relying on a transport session.

**PSG implication:** The Skill and runtime have different jobs. `SKILL.md` teaches an agent when and how to use PSG; the MCP server performs deterministic reads and writes against the graph.

## Persistent state and agent memory

### Cognitive Architectures for Language Agents (CoALA)

**Reference:** Sumers et al. (2023), arXiv:2309.02427. [Paper](https://arxiv.org/abs/2309.02427)

**Relevant framing:** CoALA describes language agents in terms of modular memory components and a structured action space, giving a vocabulary for separating what an agent knows from what it does.

**PSG implication:** PSG's graph is a deliberately narrow instance of durable agent memory. It stores decisions, constraints, task boundaries, and evidence—not conversation—and keeps them in a repository-local, human-readable projection so a person can audit and a different model can reuse them.

### MemGPT: Towards LLMs as Operating Systems

**Reference:** Packer et al. (2023), arXiv:2310.08560. [Paper](https://arxiv.org/abs/2310.08560)

**Relevant mechanism:** MemGPT manages tiered memory so an agent can operate beyond a fixed context window, borrowing the idea of a memory hierarchy from operating systems.

**PSG implication:** PSG shares the premise that useful state must outlive one context window, and differs in where that state lives. PSG keeps it in Git-adjacent project files under user control rather than in a model-managed store, because its purpose is governance and auditability, not context extension.

## Why self-assessment is not evidence

### Large Language Models Cannot Self-Correct Reasoning Yet

**Reference:** Huang et al. (2024), ICLR 2024, arXiv:2310.01798. [Paper](https://arxiv.org/abs/2310.01798)

**Relevant result:** The paper reports that LLMs struggle to self-correct without external feedback, and that performance can degrade after intrinsic self-correction.

**PSG implication:** This is the direct basis for PSG's rule that a model's own claim of completion is not evidence. The ship gate is a deterministic predicate over runtime-attested checks and worktree-bound evidence precisely because intrinsic self-assessment is unreliable.

### Is the Cure Worse Than the Disease? Overfitting in Automated Program Repair

**Reference:** Smith et al. (2015), ESEC/FSE 2015. [Paper](https://doi.org/10.1145/2786805.2786825)

**Relevant result:** Evaluated against tests held out from the repair process, generated patches overfit the tests used to produce them; on well-tested programs the studied tools were about as likely to break tests as to fix them, and patch quality tracked the coverage of the suite used during repair.

**PSG implication:** A green check is not automatically a correct change. PSG therefore binds evidence to a specific worktree fingerprint, distinguishes a policy pass from a functional check, and treats a stale or unattested pass as insufficient. PSG does not solve overfitting; it refuses to hide it behind a self-reported success.

## Evaluation, verification, and convergence

### SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

**Reference:** Jimenez et al. (2023), arXiv:2310.06770. [Paper](https://arxiv.org/abs/2310.06770) · [Benchmark](https://www.swebench.com/original.html)

**Relevant contribution:** SWE-bench defines 2,294 issue-resolution tasks from 12 Python repositories. Its task formulation requires a model to work with a codebase and issue description, often coordinating changes across multiple program elements and executing tests.

**PSG implication:** A meaningful PSG evaluation must use real repository histories, held-out tasks, executable test environments, and patch-level correctness—not only context compression.

### Agentless: Demystifying LLM-based Software Engineering Agents

**Reference:** Xia et al. (2024), arXiv:2407.01489. [Paper](https://arxiv.org/abs/2407.01489)

**Relevant mechanism:** Agentless separates localization, repair, and patch validation. Its central lesson for this project is methodological: a simpler, interpretable pipeline can be competitive, and every extra layer should justify its cost.

**PSG implication:** PSG keeps its phases inspectable and avoids hiding completion behind an agent's self-assessment. The ship gate is a deterministic predicate over current state and evidence.

## Open questions

1. Does persistent project state improve success across a sequence of related tasks, not only one isolated issue?
2. Does policy enforcement reduce unauthorized or unnecessary edits without suppressing valid dependency changes?
3. How often is the initial context pack sufficient, and what signals best predict safe expansion?
4. Can bounded review preserve defect discovery while reducing repeated low-value findings?
5. How does graph maintenance cost scale across languages and large monorepos?

These questions are converted into a testable protocol in [evaluation-plan.md](evaluation-plan.md).
