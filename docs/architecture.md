# Runtime architecture

WorkGraph keeps source code authoritative and stores only semantic index, intent, policy, evidence, and evolution state.

```text
Agent skill
    -> MCP tools / CLI
        -> WorkGraph runtime
            -> ContextRouter
            -> PolicyEngine
            -> VerificationEngine
            -> ConvergenceEngine
            -> SQLite Store + JSONL events
        <-> Git repository and deterministic checks
```

## Revision and provenance

File and symbol nodes carry SHA-256 content revisions. Index-derived edges identify `python_ast` provenance. User decisions identify `user_explicit` and `documented_decision` provenance. Context confidence multiplies freshness, language coverage, source confidence, and dependency certainty; low confidence expands retrieval rather than implying safety.

## Enforcement boundary

The runtime never applies patches. `patch_validate` parses the actual unified Git diff and rejects:

- files outside the task's `WRITE` set;
- explicit `READ_ONLY` or `FORBIDDEN` files;
- nodes governed as `read_only` or `frozen`;
- public signature/schema-like changes in `interface_locked` files; and
- tasks whose baseline Git HEAD is stale.

The ship gate repeats validation against the final current diff. Verification and acceptance evidence carry a working-tree fingerprint, so code changed after a passing test makes that evidence stale. Prompt instructions guide the agent, but the validator supplies the enforceable decision.

Unfreezing requires an explicit override plus an existing Decision node; a reason string alone is insufficient.

## Snapshot boundary

Snapshots serialize WorkGraph database state and bind it to Git revision. Restore creates a safety snapshot and restores graph state only. Source recovery remains an explicit human/Git operation, avoiding hidden destructive resets.
