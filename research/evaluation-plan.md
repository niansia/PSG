# Evaluation plan

## Goal

Evaluate whether persistent project state plus explicit mutation and convergence controls improves repository-level coding over simpler context-and-test workflows.

The study must test PSG as a system, but also isolate which components create value. A positive result on the included synthetic benchmark is insufficient because its repository, tasks, and expected behavior were generated for the implementation.

## Research questions

| ID | Question | Primary metric |
| --- | --- | --- |
| RQ1 | Does graph-routed context reduce repository reading without reducing task success? | Resolved rate, context tokens, unique files read |
| RQ2 | Do mutation policies reduce out-of-scope edits and regressions? | Unauthorized mutation rate, changed-file precision, regression rate |
| RQ3 | Does persistent state help across related task sequences? | Later-task resolved rate, rediscovery cost, decision retention |
| RQ4 | Does evidence freshness prevent false "done" states after the worktree changes? | False-shippable rate under adversarial post-verification edits |
| RQ5 | Do review/fix budgets reduce loops without hiding blocking defects? | Blocking-defect recall, review rounds, time and token cost |

## Hypotheses

- **H1:** PSG reduces context tokens and unique file reads relative to full-repository or unguided search while remaining non-inferior on resolved rate.
- **H2:** Diff-level policy enforcement reduces unauthorized changes relative to prompt-only scope instructions.
- **H3:** The advantage of persistent state grows over sequences of related tasks because accepted decisions and verified state can be reused.
- **H4:** Worktree-bound evidence produces fewer false-shippable outcomes than evidence records without revision binding.
- **H5:** A fixed review budget reduces repeated review cost while preserving detection of seeded blocking defects.

## Systems and ablations

Use the same coding model, temperature, tool environment, repository checkout, timeout, and task prompt across conditions.

1. **Agent baseline:** normal repository tools, Git, and tests; no PSG.
2. **Repo-map baseline:** concise symbol/dependency map with the same nominal context budget; no persistent task/evidence graph.
3. **PSG context only:** index and router enabled; policies and ship gate disabled.
4. **PSG + policy:** context routing and mutation validation; no persistent evidence freshness.
5. **Full PSG:** context, policy, evidence binding, review budget, and ship gate.
6. **Ablations:** remove one of dependency expansion, decision memory, evidence fingerprinting, or review budget from the full condition.

The agent must not know which condition is expected to win. Randomize condition order and use separate clean worktrees.

## Task sets

### Real issue resolution

- Use a contamination-aware, held-out subset of executable repository issues.
- Include small localized fixes, cross-file changes, interface changes, and tasks with irrelevant nearby code.
- Report repository and difficulty strata separately; do not hide failures inside a single mean.

### Long-chain project benchmark

Create 10–20 task sequences per repository where later tasks depend on earlier accepted decisions. Each sequence should contain:

- a requirement clarification that becomes a recorded decision;
- an intentionally frozen or interface-locked area;
- a legitimate dependency expansion;
- a regression detectable only by tests;
- an edit made after verification to test evidence freshness;
- two review rounds, one with a seeded blocking issue and one with no new blocker.

### Adversarial governance cases

Test explicit attempts to:

- modify forbidden and frozen files;
- introduce an untracked file outside write scope;
- reuse passing evidence after changing the worktree;
- mark criteria passed without evidence;
- unfreeze a node without a recorded decision;
- exceed review or fix budgets.

## Metrics

### Correctness

- Resolved rate under the repository's executable tests
- Regression rate on pre-existing tests
- Patch applicability and build/type-check success
- Acceptance-criterion pass rate confirmed by an independent evaluator

### Context and cost

- Input/output tokens by phase
- Unique files and symbols read
- Context-pack precision and recall against files in the reference patch, reported only as diagnostic proxies
- Wall-clock time and model/tool cost
- Index build and incremental-update overhead

### Governance

- Unauthorized mutation rate
- Changed-file precision and recall
- False-shippable and false-blocked rates
- Stale-evidence rejection rate
- Blocking-issue recall and non-blocking issue volume by review round

### Persistence

- Repeated reads of unchanged project facts
- Correct recall of accepted decisions on later tasks
- State conflicts or stale-node rate
- Storage growth and incremental index latency over the task sequence

## Protocol

1. Pin repository commits and containerize dependencies.
2. Prepare hidden evaluation tests without exposing reference patches.
3. Pre-register tasks, success conditions, stopping rules, and exclusions.
4. Run at least three independent model seeds per task-condition pair where stochasticity is enabled.
5. Cap tokens, time, context expansions, review rounds, and fix cycles equally across conditions.
6. Record full tool traces, Git diffs, PSG events, test outputs, and costs.
7. Re-run final tests from a clean environment after the agent stops.
8. Have an independent evaluator label scope violations and criterion satisfaction while blinded to condition.
9. Report paired confidence intervals and per-repository results, including every failure mode.

## Analysis

- Use paired comparisons because every task runs in every condition.
- Report effect sizes and bootstrap confidence intervals, not only p-values.
- Test non-inferiority on resolved rate before claiming context-efficiency gains.
- Analyze long-chain tasks by task position to see whether persistent-state effects accumulate.
- Separate policy violations correctly blocked from legitimate impact expansions incorrectly blocked.
- Publish raw traces and the exact benchmark generator when licensing permits.

## Threats to validity

- **Benchmark contamination:** public issues may appear in model training data. Prefer post-cutoff or private/held-out tasks and report dates.
- **Test weakness:** passing tests may not imply a correct patch. Add hidden tests and blinded criterion review.
- **Reference-patch bias:** a different correct patch may touch different files. Treat changed-file overlap as diagnostic, not ground truth correctness.
- **Model dependence:** repeat on at least two model families and report interactions.
- **Language bias:** v1 symbol extraction favors Python. Do not generalize to other languages until equivalent indexers are evaluated.
- **Tooling advantage:** equalize available repository and test tools so results isolate PSG controls rather than shell access.
- **Synthetic carryover:** keep the existing 12-task benchmark as a regression test, not as headline external evidence.

## Release criteria for a stronger claim

Do not describe PSG as improving real-world agent performance until a held-out evaluation shows:

1. resolved-rate non-inferiority to the strongest matched baseline;
2. a statistically and practically meaningful reduction in context or file reads;
3. a lower unauthorized-mutation or false-shippable rate;
4. reproducible results across more than one repository and model family;
5. published task definitions, raw aggregates, and known limitations.
