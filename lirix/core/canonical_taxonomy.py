from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Final, Mapping, Optional

from lirix.core.constants import (
    AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    AGENT_FEEDBACK_REASON_INTENT_INVALID,
    AGENT_FEEDBACK_REASON_OK,
    AGENT_FEEDBACK_REASON_POLICY_VIOLATION,
    AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE,
    AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
    AGENT_FEEDBACK_REASON_TIMEOUT,
    AGENT_FEEDBACK_REASON_TRANSPORT_ERROR,
    AGENT_FEEDBACK_REASON_UNKNOWN,
    FAILURE_TYPE_CONSENSUS_FAILURE,
    FAILURE_TYPE_INVALID_INTENT,
    FAILURE_TYPE_NONE,
    FAILURE_TYPE_POLICY_VIOLATION,
    FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE,
    FAILURE_TYPE_SCHEMA_VALIDATION_FAILED,
    FAILURE_TYPE_TIMEOUT,
    FAILURE_TYPE_TRANSPORT_ERROR,
    FAILURE_TYPE_UNKNOWN,
    HOOK_ERR_TIMEOUT,
    canonicalize_reason_code,
)


@dataclass(frozen=True)
class ReasonTaxon:
    """
    Single authoritative row keyed by canonical Agent Feedback reason_code (LIRIX_REASON_*).

    This table is intentionally conservative: it must not expand Lirix behavior,
    only unify existing semantics across evidence/session/failure surfaces.
    """

    reason_code: str
    default_failure_type: str
    retry_allowed: bool
    human_action_required: bool
    default_remediation: str
    severity: str = "high"


_TAXONOMY_TABLE: Final[Dict[str, ReasonTaxon]] = {
    AGENT_FEEDBACK_REASON_OK: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_OK,
        default_failure_type=FAILURE_TYPE_NONE,
        retry_allowed=False,
        human_action_required=False,
        default_remediation="No action required; continue the workflow.",
        severity="info",
    ),
    AGENT_FEEDBACK_REASON_TIMEOUT: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_TIMEOUT,
        default_failure_type=FAILURE_TYPE_TIMEOUT,
        retry_allowed=True,
        human_action_required=False,
        default_remediation=(
            "NEXT STEP: Point Lirix at faster or closer RPC endpoints (or raise "
            "`LirixConfig` timeout / quorum budgets), then retry the same call."
        ),
        severity="medium",
    ),
    AGENT_FEEDBACK_REASON_TRANSPORT_ERROR: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_TRANSPORT_ERROR,
        default_failure_type=FAILURE_TYPE_TRANSPORT_ERROR,
        retry_allowed=True,
        human_action_required=False,
        default_remediation=(
            "NEXT STEP: Remove dead RPC URLs, verify TLS/network reachability, "
            "and retry once a healthy endpoint answers `eth_chainId` / `eth_blockNumber`."
        ),
        severity="high",
    ),
    AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
        default_failure_type=FAILURE_TYPE_CONSENSUS_FAILURE,
        retry_allowed=False,
        human_action_required=True,
        default_remediation=(
            "ACTION REQUIRED: RPC quorum disagrees on canonical state. "
            "Isolate the outlier nodes (compare block hash / latest block), "
            "drop or replace them in `rpc_urls`, then re-run with a trusted set only."
        ),
        severity="critical",
    ),
    AGENT_FEEDBACK_REASON_SCHEMA_INVALID: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
        default_failure_type=FAILURE_TYPE_SCHEMA_VALIDATION_FAILED,
        retry_allowed=False,
        human_action_required=True,
        default_remediation=(
            "ACTION REQUIRED: Payload failed structural validation. "
            "Open `agent_feedback.details.context` for field-level errors, "
            "repair the mapping (types, required keys, hex encoding), and re-submit."
        ),
        severity="high",
    ),
    AGENT_FEEDBACK_REASON_INTENT_INVALID: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_INTENT_INVALID,
        default_failure_type=FAILURE_TYPE_INVALID_INTENT,
        retry_allowed=False,
        human_action_required=True,
        default_remediation=(
            "ACTION REQUIRED: Intent text or metadata is not executable. "
            "Normalize the intent string to a supported operation, align it with the payload "
            "(e.g. swap vs transfer), and run validation again."
        ),
        severity="high",
    ),
    AGENT_FEEDBACK_REASON_POLICY_VIOLATION: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_POLICY_VIOLATION,
        default_failure_type=FAILURE_TYPE_POLICY_VIOLATION,
        retry_allowed=False,
        human_action_required=True,
        default_remediation=(
            "ACTION REQUIRED: Policy blocked this path. "
            "Either relax the relevant `LirixConfig` / auditor rule, or change the payload "
            "so it satisfies the active policy bundle, then re-run."
        ),
        severity="high",
    ),
    AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE,
        default_failure_type=FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE,
        retry_allowed=True,
        human_action_required=False,
        default_remediation=(
            "NEXT STEP: Some quorum members failed transiently. "
            "Inspect `security_trace` / RPC evidence for which node errored, "
            "fix or rotate that endpoint, and retry reconciliation."
        ),
        severity="medium",
    ),
    AGENT_FEEDBACK_REASON_UNKNOWN: ReasonTaxon(
        reason_code=AGENT_FEEDBACK_REASON_UNKNOWN,
        default_failure_type=FAILURE_TYPE_UNKNOWN,
        retry_allowed=False,
        human_action_required=True,
        default_remediation=(
            "ACTION REQUIRED: Failure reason could not be classified. "
            "Read `agent_feedback.details` plus the last rejected `security_trace` step, "
            "fix the root cause you find there, then retry—do not blindly loop."
        ),
        severity="high",
    ),
}


def lookup_reason_taxon(reason_code: str) -> ReasonTaxon:
    token = str(reason_code or "").strip()
    if not token:
        return _TAXONOMY_TABLE[AGENT_FEEDBACK_REASON_UNKNOWN]
    return _TAXONOMY_TABLE.get(token, _TAXONOMY_TABLE[AGENT_FEEDBACK_REASON_UNKNOWN])


def registered_taxonomy_reason_codes() -> frozenset[str]:
    """Keys of the authoritative LIRIX_REASON_* taxonomy table (for closure tests and audits)."""

    return frozenset(_TAXONOMY_TABLE.keys())


def retry_allowed_for_hook_error_code(error_code: str) -> bool:
    """
    Decide retry_allowed for isolated hook errors from the hook error_code token.

    LIRIX_HOOK_TIMEOUT aligns with AGENT_FEEDBACK_REASON_TIMEOUT (taxonomy retry bit).
    Other hook-local codes map through canonicalize_reason_code(..., fallback_error_code=).
    """
    token = str(error_code or "").strip()
    if token == HOOK_ERR_TIMEOUT:
        return lookup_reason_taxon(AGENT_FEEDBACK_REASON_TIMEOUT).retry_allowed
    reason = canonicalize_reason_code("", fallback_error_code=token)
    return lookup_reason_taxon(reason).retry_allowed


# RPC disagreement reason namespace (local, not LIRIX_REASON_*).
# Make the mapping explicit to avoid drift from guess-based canonicalization.
RPC_REASON_TO_CANONICAL_REASON: Final[Mapping[str, str]] = {
    "none": AGENT_FEEDBACK_REASON_OK,
    "timeout": AGENT_FEEDBACK_REASON_TIMEOUT,
    "transport_error": AGENT_FEEDBACK_REASON_TRANSPORT_ERROR,
    "inconsistent_result": AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    "suspicious_consistency": AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    "consensus_failure": AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    # Malformed responses are integrity failures; map to schema-invalid for strict remediation.
    "malformed_response": AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
}


def canonical_reason_from_rpc_reason(rpc_reason_code: str) -> Optional[str]:
    token = str(rpc_reason_code or "").strip().lower()
    if not token:
        return None
    return RPC_REASON_TO_CANONICAL_REASON.get(token)
