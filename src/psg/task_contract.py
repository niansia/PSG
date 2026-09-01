from __future__ import annotations

from typing import Any

from .util import canonical_json, sha256_text

CONTRACT_VERSION = 1
MAX_REVIEW_ROUNDS = 2
MAX_FIX_CYCLES = 2
RELATIONS_TO_TASK = {
    "caused_by_patch",
    "violates_acceptance",
    "violates_project_constraint",
    "pre_existing",
    "unrelated",
    "future_improvement",
}
CURRENT_TASK_RELATIONS = {
    "caused_by_patch",
    "violates_acceptance",
    "violates_project_constraint",
}
FOLLOW_UP_RELATIONS = RELATIONS_TO_TASK - CURRENT_TASK_RELATIONS
BLOCKING_SEVERITIES = {"blocker", "major"}

# A task is DRAFT until initial localization has produced a concrete mutation
# boundary. Only a SEALED contract carries write authority, and only a SEALED
# contract has a meaningful hash.
CONTRACT_STATE_DRAFT = "draft"
CONTRACT_STATE_SEALED = "sealed"
AUTHORITY_KEYS = ("authorized_write", "authorized_read_only", "authorized_forbidden")
# Above this many authorized write paths, a boundary stops being "narrow" and
# needs a person to look at it.
BROAD_WRITE_PATH_LIMIT = 12
GLOB_CHARACTERS = "*?["


def is_sealed(payload: dict[str, Any]) -> bool:
    return payload.get("contract_state") == CONTRACT_STATE_SEALED


def authority_boundary(payload: dict[str, Any]) -> dict[str, list[str]]:
    """Return the mutation authority actually in force.

    A sealed contract answers with the authority frozen at seal time. A draft
    answers with what was requested, which carries no write authority yet: the
    router has not run, so nothing has been authorized.
    """
    if is_sealed(payload):
        return {
            "write": list(payload.get("authorized_write", [])),
            "read_only": list(payload.get("authorized_read_only", [])),
            "forbidden": list(payload.get("authorized_forbidden", [])),
        }
    working_set = payload.get("working_set")
    if "contract_state" not in payload and working_set:
        # A task opened before contract sealing existed: its routed working set was
        # its authority, so keep honouring that rather than stranding the task.
        return {
            "write": list(working_set.get("write", [])),
            "read_only": list(working_set.get("read_only", [])),
            "forbidden": list(working_set.get("forbidden", [])),
        }
    return {
        "write": list(payload.get("write", [])),
        "read_only": list(payload.get("read_only", [])),
        "forbidden": list(payload.get("forbidden", [])),
    }


def has_write_authority(payload: dict[str, Any]) -> bool:
    """A draft contract holds no write authority; localization must seal it first."""
    return is_sealed(payload) or (
        "contract_state" not in payload and bool(payload.get("working_set"))
    )


def requires_scope_approval(
    *,
    write: list[str],
    read_only: list[str],
    forbidden: list[str],
    risk: str,
    localization: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Decide whether a person must approve this write authority before work starts.

    A narrow, concrete boundary derived by conservative localization is the
    ordinary case and seals automatically. Wildcards, high risk, and sprawling
    write sets are the cases where an agent's interpretation of the request
    should not silently become authority.
    """
    reasons: list[str] = []
    kind = (localization or {}).get("kind")
    if kind == "ambiguous_localization":
        # Several files matched about equally well. Guessing would grant authority
        # over all of them, so the choice belongs to a person.
        reasons.append("ambiguous_localization")
    elif kind == "no_lexical_match":
        reasons.append("no_localization_match")
    if risk == "high":
        reasons.append("high_risk_task")
    if any(character in item for item in write for character in GLOB_CHARACTERS):
        reasons.append("wildcard_write_scope")
    if len(write) > BROAD_WRITE_PATH_LIMIT:
        reasons.append(f"write_scope_exceeds_{BROAD_WRITE_PATH_LIMIT}_paths")
    if write and not (read_only or forbidden) and len(write) > 1:
        reasons.append("write_scope_without_any_protected_boundary")
    return bool(reasons), reasons


def default_review_boundary() -> dict[str, Any]:
    return {
        "blocking_relations": sorted(CURRENT_TASK_RELATIONS),
        "blocking_severities": sorted(BLOCKING_SEVERITIES),
        "requires_sufficient_evidence": True,
        "no_scope_expansion_by_review": True,
        "follow_up_relations": sorted(FOLLOW_UP_RELATIONS),
    }


def default_completion_boundary(
    *, review_budget: int, fix_budget: int, risk: str
) -> dict[str, Any]:
    """Project the completion boundary, clamped to the hard runtime maximums.

    Tasks imported from an older portable state can carry wider budgets than this
    runtime enforces; the contract must never advertise a budget convergence will
    not honour.
    """
    return {
        "mandatory_acceptance": "pass_or_approved_waiver",
        "required_verification": "passing_fresh_trusted",
        "current_task_blockers": 0,
        "mutation_guardrail": "pass",
        "evidence_fresh": True,
        "high_risk_review": risk == "high",
        "review_budget": max(1, min(int(review_budget), MAX_REVIEW_ROUNDS)),
        "fix_budget": max(1, min(int(fix_budget), MAX_FIX_CYCLES)),
        "stop_when_shippable": True,
    }


def task_contract(task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload", {})
    working_set = payload.get("working_set", {})
    authority = authority_boundary(payload)
    return {
        "contract_version": int(payload.get("contract_version", CONTRACT_VERSION)),
        "contract_state": payload.get("contract_state", CONTRACT_STATE_DRAFT),
        "task_id": task["id"],
        "goal_boundary": {
            "intent": task["intent"],
            "acceptance_criteria": [
                {
                    "id": item["id"],
                    "text": item["text"],
                    "mandatory": bool(item.get("mandatory", True)),
                }
                for item in task.get("criteria", [])
            ],
        },
        "context_boundary": {
            "targets": payload.get("targets", []),
            "read": working_set.get("read", []),
            "constraints": payload.get("constraints", []),
        },
        # Authority, not context. The router may widen what is READ; it can never
        # widen what may be WRITTEN.
        "mutation_boundary": authority,
        "requested_mutation_boundary": {
            "write": list(payload.get("write", [])),
            "read_only": list(payload.get("read_only", [])),
            "forbidden": list(payload.get("forbidden", [])),
        },
        "scope_boundary": {"non_goals": payload.get("non_goals", [])},
        "review_boundary": payload.get("review_boundary", default_review_boundary()),
        "completion_boundary": payload.get(
            "completion_boundary",
            default_completion_boundary(
                review_budget=int(task["review_budget"]),
                fix_budget=int(task["fix_budget"]),
                risk=str(task["risk"]),
            ),
        ),
        "risk_boundary": {
            "risk": task["risk"],
            "builder_actor": payload.get("builder_actor") or None,
            "independent_review_required": task["risk"] == "high",
        },
    }


def contract_hash(task: dict[str, Any]) -> str:
    payload = task.get("payload", {})
    identity = {
        "contract_version": int(payload.get("contract_version", CONTRACT_VERSION)),
        "task_id": task["id"],
        "intent": task["intent"],
        "criteria": [
            {
                "id": item["id"],
                "text": item["text"],
                "mandatory": bool(item.get("mandatory", True)),
            }
            for item in task.get("criteria", [])
        ],
        "constraints": payload.get("constraints", []),
        "targets": payload.get("targets", []),
        "requested_write": payload.get("write", []),
        "requested_read_only": payload.get("read_only", []),
        "requested_forbidden": payload.get("forbidden", []),
        # The authority the runtime will actually enforce. Hashing only the
        # request would let localization grant write scope the hash never saw.
        "contract_state": payload.get("contract_state", CONTRACT_STATE_DRAFT),
        "authorized_write": payload.get("authorized_write", []),
        "authorized_read_only": payload.get("authorized_read_only", []),
        "authorized_forbidden": payload.get("authorized_forbidden", []),
        "non_goals": payload.get("non_goals", []),
        "review_boundary": payload.get("review_boundary", default_review_boundary()),
        "completion_boundary": payload.get(
            "completion_boundary",
            default_completion_boundary(
                review_budget=int(task["review_budget"]),
                fix_budget=int(task["fix_budget"]),
                risk=str(task["risk"]),
            ),
        ),
        "risk": task["risk"],
        "builder_actor": payload.get("builder_actor") or None,
    }
    return "sha256:" + sha256_text(canonical_json(identity))


def blocks_current_task(issue: dict[str, Any]) -> bool:
    return bool(
        issue.get("status") == "open"
        and issue.get("severity") in BLOCKING_SEVERITIES
        and issue.get("relation_to_task") in CURRENT_TASK_RELATIONS
        and issue.get("evidence_sufficient")
    )


def render_handoff(pack: dict[str, Any]) -> str:
    contract = pack["task_contract"]
    goal = contract["goal_boundary"]
    context = contract["context_boundary"]
    mutation = contract["mutation_boundary"]
    scope = contract["scope_boundary"]
    lines = [
        "# PSG REVIEW CONTRACT",
        "",
        "## Task",
        "",
        f"{contract['task_id']} · Contract v{contract['contract_version']}",
        "",
        "## Goal",
        "",
        goal["intent"],
        "",
        "## Acceptance Criteria",
        "",
    ]
    lines.extend(
        f"- {item['id']}: {item['text']}" for item in goal["acceptance_criteria"]
    )
    if not goal["acceptance_criteria"]:
        lines.append("- None")

    def section(title: str, values: list[str]) -> None:
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {value}" for value in values)
        if not values:
            lines.append("- None")

    section("IN SCOPE", list(context["targets"]))
    section("OUT OF SCOPE", list(scope["non_goals"]))
    section("WRITE", list(mutation["write"]))
    section("READ ONLY", list(mutation["read_only"]))
    section("FORBIDDEN / FROZEN", list(mutation["forbidden"]) + pack["frozen"])
    section("Relevant Constraints", list(context["constraints"]))
    section(
        "Relevant Decisions",
        [f"{item['id']}: {item['title']}" for item in pack["relevant_decisions"]],
    )
    section(
        "Changed Files / Symbols",
        [
            f"{item['path']}"
            + (f" — {', '.join(item['symbols'])}" if item["symbols"] else "")
            for item in pack["changed"]
        ],
    )
    section(
        "Trusted Verification",
        [
            f"{item['name']} — {item['result'].upper()} ({item['id']})"
            for item in pack["trusted_verification"]
        ],
    )
    section(
        "Accepted Debt",
        [f"{item['id']}: {item['title']}" for item in pack["accepted_debt"]],
    )
    section(
        "Known Issues",
        [
            f"{item['id']} [{item['severity']}/{item['relation_to_task']}] "
            f"{'BLOCKS' if item['blocks_current_task'] else 'FOLLOW-UP'} — {item['claim']}"
            for item in pack["known_issues"]
        ],
    )
    lines.extend(
        [
            "",
            "## Current Ship State",
            "",
            (
                f"**{pack['current_ship_state']['status']}** — "
                f"{pack['current_ship_state']['recommendation']}"
            ),
            "",
            "## Review Rule",
            "",
            "A finding may block this task only if it is evidence-backed and:",
            "",
            "1. caused by the current patch;",
            "2. violates an acceptance criterion; or",
            "3. violates an accepted project constraint.",
            "",
            (
                "Pre-existing issues, unrelated issues, and future improvements are "
                "follow-up findings. They must not expand this task."
            ),
            "",
            "**Review the task, not the entire project.**",
            "",
        ]
    )
    return "\n".join(lines)
