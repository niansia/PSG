from __future__ import annotations

import sys
from typing import Any

CLAIMED = "CLAIMED"
RUNTIME_ATTESTED = "RUNTIME_ATTESTED"
USER_APPROVED = "USER_APPROVED"
EXTERNAL_ATTESTED = "EXTERNAL_ATTESTED"

VALID_TRUST_TIERS = {
    CLAIMED,
    RUNTIME_ATTESTED,
    USER_APPROVED,
    EXTERNAL_ATTESTED,
}
FUNCTIONAL_TRUST_TIERS = {RUNTIME_ATTESTED, EXTERNAL_ATTESTED}
APPROVAL_TRUST_TIERS = {USER_APPROVED, EXTERNAL_ATTESTED}


class ApprovalRefused(PermissionError):
    """Raised when an authority-changing action lacks operator approval."""


_APPROVAL_NONCE = object()


class OperatorApproval:
    """Opaque proof that this process completed the interactive approval gate."""

    __slots__ = ("_nonce",)

    def __init__(self, nonce: object) -> None:
        if nonce is not _APPROVAL_NONCE:
            raise TypeError("OperatorApproval can only be created by the trust gate.")
        self._nonce = nonce


def require_interactive_user_approval(
    action: str, facts: dict[str, Any]
) -> OperatorApproval:
    """Require a live local operator before runtime can mint USER_APPROVED.

    The gate lives below the CLI so importing :mod:`psg.runtime` cannot bypass it.
    Requiring a terminal on stdin and stdout makes captured subprocesses and piped
    answers fail closed. This is not cryptographic proof of a human: a Host that
    grants an Agent the same PTY and OS identity remains the outer trust boundary.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ApprovalRefused(
            f"{action} changes PSG authority and requires an interactive terminal. "
            "PSG does not accept a piped, redirected, or captured answer. "
            "Run this command yourself in a terminal."
        )
    print()
    print("PSG USER APPROVAL")
    print()
    print(f"Action: {action}")
    for key, value in facts.items():
        if isinstance(value, (list, tuple)):
            print(f"{key}:")
            for item in value or ["(none)"]:
                print(f"  {item}")
        else:
            print(f"{key}: {value}")
    print()
    print("This action changes PSG authority.")
    try:
        answer = input("Type APPROVE to continue: ")
    except EOFError as exc:
        raise ApprovalRefused(
            f"{action} was not approved: no interactive answer."
        ) from exc
    if answer.strip() != "APPROVE":
        raise ApprovalRefused(f"{action} was not approved.")
    return OperatorApproval(_APPROVAL_NONCE)


def require_runtime_user_approval(
    trust_tier: str,
    action: str,
    facts: dict[str, Any],
    *,
    approval: OperatorApproval | None = None,
) -> OperatorApproval | None:
    """Validate caller-supplied trust at the runtime boundary.

    CLAIMED needs no operator action. USER_APPROVED must come from the interactive
    gate unless the current runtime operation passes its opaque approval to a
    nested mutation. Runtime/external attestation cannot be asserted by a public
    Python caller in v1 because no authenticated adapter exists.
    """
    if trust_tier == CLAIMED:
        return None
    if trust_tier != USER_APPROVED:
        raise ApprovalRefused(
            f"{trust_tier} cannot be supplied by a runtime caller. "
            "Use a runtime-attested check or an authenticated adapter."
        )
    if isinstance(approval, OperatorApproval) and approval._nonce is _APPROVAL_NONCE:
        return approval
    return require_interactive_user_approval(action, facts)


def evidence_trust(value: dict[str, Any] | None) -> str:
    tier = str((value or {}).get("trust_tier", CLAIMED))
    return tier if tier in VALID_TRUST_TIERS else CLAIMED


def node_trust(node: dict[str, Any] | None) -> str:
    return evidence_trust((node or {}).get("payload", {}))


def is_user_approved(node: dict[str, Any] | None) -> bool:
    return node_trust(node) in APPROVAL_TRUST_TIERS
