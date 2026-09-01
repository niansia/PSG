from __future__ import annotations

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


def evidence_trust(value: dict[str, Any] | None) -> str:
    tier = str((value or {}).get("trust_tier", CLAIMED))
    return tier if tier in VALID_TRUST_TIERS else CLAIMED


def node_trust(node: dict[str, Any] | None) -> str:
    return evidence_trust((node or {}).get("payload", {}))


def is_user_approved(node: dict[str, Any] | None) -> bool:
    return node_trust(node) in APPROVAL_TRUST_TIERS
