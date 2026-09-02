# Trust and security

PSG treats Agent input as a claim, not as authority. Its trust model is deliberately small so the runtime can enforce it without pretending to authenticate identities it cannot verify.

## Trust tiers

| Tier | Meaning | Created by ordinary MCP? |
| --- | --- | ---: |
| `CLAIMED` | Agent statements, reviewer labels, external-tool labels, proposals, and caller-provided descriptions | Yes |
| `RUNTIME_ATTESTED` | Evidence produced by PSG executing a configured check against a known worktree | No |
| `USER_APPROVED` | A person completes a separate interactive local approval action | No |
| `EXTERNAL_ATTESTED` | Reserved for a future authenticated CI or connector adapter | No |

An MCP caller cannot promote itself by sending `source="external_tool"`, `source="user_asserted"`, or a different `actor_id`. Those remain `CLAIMED`. PSG v1 has no authenticated external attestation adapter, so `EXTERNAL_ATTESTED` is reserved rather than simulated.

## User-owned approval boundary

Ordinary MCP may propose Decisions and Debt, report verification claims, record review findings, and request evaluation. It cannot:

- accept a Decision or Debt;
- waive an acceptance criterion;
- unlock a frozen or architecture-locked node;
- accept a dirty portable-state change;
- approve a broad inferred task scope; or
- attest that a high-risk review is independently performed.

The interactive gate is enforced by the runtime operation itself, below the CLI. The CLI delegates to that boundary instead of minting authority first, so importing `psg.runtime` and calling an approval method directly reaches the same terminal check. Non-interactive and piped input are rejected before governance state changes. An Agent should present the proposed action and wait for the user rather than invoking an approval command or runtime method for itself.

Caller-supplied `_trust_tier=USER_APPROVED` is not a capability. Every public runtime path that accepts it re-enters the same operator gate; caller-supplied `RUNTIME_ATTESTED` and `EXTERNAL_ATTESTED` are rejected because those tiers require runtime execution or an authenticated adapter. A small opaque approval object is used only to prevent a single approved runtime operation from prompting twice while it applies its own nested mutation effect.

This still is not cryptographic proof that a human pressed the key. If a Host grants an Agent a full PTY under the same OS identity, that Host has also granted the ability to drive this terminal interaction. PSG documents that as the outer trust boundary rather than claiming to solve it inside a local Python library.

## Verification command boundary

The MCP `verification_run` operation accepts only check names declared under `verification.commands` in `.psg/config.yaml`.

```text
Agent chooses which approved check to run
                 ↓
Runtime resolves the configured command
                 ↓
Runtime executes it and attests the result
```

Arbitrary command text is not available on the MCP surface. A person may deliberately run a one-off local command through the advanced CLI, but that is a separate shell authority boundary, not an Agent shortcut around the allowlist.

Raw command output stays under ignored `.psg/local/` storage. Portable state contains compact evidence metadata, result, worktree fingerprint, reference, timestamp, and hashes—not full stdout or stderr that could expose secrets, personal data, or machine paths.

## Evidence freshness

Trusted evidence is tied to the exact worktree state for which it was produced. After relevant files change, stale verification or acceptance evidence cannot satisfy the ship gate. A caller-supplied passing label does not override a stale fingerprint.

The gate evaluates the actual final Git state, including staged and unstaged changes, renames, deletions, and untracked files. Policy is not limited to an Agent's proposed patch.

## Portable-state boundary

PSG separates durable and local state:

```text
.psg/state/project.yaml  — compact, commit-capable portable state
.psg/local/              — SQLite, events, caches, raw logs, handoffs
```

SQLite is a derived local index. Portable YAML is the repository-traveling representation for durable tasks, Decisions, Constraints, Debt, verification metadata, and Issues.

At startup, PSG imports portable governance state only when either:

- its current hash matches the last runtime export; or
- Git reports the portable file as clean, covering a committed pull or checkout.

A hash mismatch combined with a dirty Git file is treated as an untrusted modification. It is not imported automatically, and configured verification does not run until a person inspects and explicitly accepts it. The same protection applies to governance configuration whose dirty contents could change approved commands or policy.

## Mutation guardrails

The effective runtime guardrails include:

- sealed task write, read-only, and forbidden boundaries;
- file, symbol, Decision, and architecture locks;
- dependency and interface policy;
- evidence freshness;
- runtime-counted review and fix budgets; and
- current-task-only blocking classification.

Guardrails shown by `psg guardrails` describe effective behavior. PSG does not expose a generic rules DSL in which changing an arbitrary label silently disables a hard invariant.

## Authority order and Skill coexistence

PSG is a governance layer, not an exclusive coding mode. Other Skills may test, design, refactor, or apply framework-specific practices. Their final changes still pass through PSG's task and mutation boundaries.

The effective priority is:

1. Host and system rules.
2. The user's current explicit instruction.
3. Accepted PSG Decisions and Constraints.
4. Repository-local rules.
5. Task-specific Skills.
6. General Skills.
7. PSG heuristics.
8. Model preference.

Context from another Skill can inform a proposal. It cannot silently widen a sealed Task Contract, unlock a frozen node, weaken required verification, or reopen accepted debt. The full coexistence rules are in the [Skill compatibility contract](../skills/psg/references/compatibility-contract.md).

## Snapshot safety

PSG snapshots capture and restore graph/governance state. Snapshot restore does not reset Git, overwrite source files, or roll back repository history.

For the runtime components behind these boundaries, see [architecture](architecture.md). For the tests that support the claims, see [acceptance evidence](acceptance.md).
