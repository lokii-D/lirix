from __future__ import annotations

from typing import Any, Mapping

from lirix.core.contracts import is_hex_digest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.session import (
    ALLOWED_BUNDLE_VERSION_MATRIX,
    FORENSIC_BUNDLE_VERSION,
    REPLAY_BUNDLE_VERSION,
)


def verify_forensic_bundle(
    bundle: Mapping[str, Any],
    *,
    enforce_replay_link: bool = False,
    replay_bundle: Mapping[str, Any] | None = None,
) -> None:
    """
    Fail-closed integrity check for forensic bundles.

    This verifier is intentionally structural: it ensures consumers can trust shape,
    versioning, and digest formats without re-running validation.
    """
    fver = bundle.get("forensic_version")
    if fver != FORENSIC_BUNDLE_VERSION:
        raise ConfigurationGuardException(
            human_readable_reason=(
                f"Unsupported or missing forensic_version (expected {FORENSIC_BUNDLE_VERSION})."
            ),
            context={
                "reason": "forensic_bundle_version",
                "forensic_version": fver,
                "expected": FORENSIC_BUNDLE_VERSION,
            },
        )

    rb_ver = bundle.get("replay_bundle_version")
    if rb_ver is not None and rb_ver != REPLAY_BUNDLE_VERSION:
        raise ConfigurationGuardException(
            human_readable_reason=(
                f"Unsupported replay_bundle_version (expected {REPLAY_BUNDLE_VERSION})."
            ),
            context={
                "reason": "forensic_bundle_replay_version",
                "replay_bundle_version": rb_ver,
                "expected": REPLAY_BUNDLE_VERSION,
            },
        )
    if (
        rb_ver is not None
        and (
            str(rb_ver),
            FORENSIC_BUNDLE_VERSION,
        )
        not in ALLOWED_BUNDLE_VERSION_MATRIX
    ):
        raise ConfigurationGuardException(
            human_readable_reason="Unsupported replay/forensic version matrix.",
            context={
                "reason": "forensic_bundle_version_matrix",
                "replay_bundle_version": rb_ver,
                "forensic_version": fver,
            },
        )

    sid = bundle.get("session_id")
    if not isinstance(sid, str) or not sid.strip():
        raise ConfigurationGuardException(
            human_readable_reason="forensic bundle session_id must be a non-empty string.",
            context={"reason": "forensic_bundle_malformed", "field": "session_id"},
        )

    for key in ("rejected_events", "error_codes", "raw_error_codes", "canonical_error_codes"):
        val = bundle.get(key)
        if val is not None and not isinstance(val, list):
            raise ConfigurationGuardException(
                human_readable_reason=f"forensic bundle {key} must be a list.",
                context={"reason": "forensic_bundle_malformed", "field": key},
            )

    rbd = bundle.get("replay_bundle_digest")
    if enforce_replay_link:
        if not is_hex_digest(rbd):
            raise ConfigurationGuardException(
                human_readable_reason="replay_bundle_digest must be a 64-char hex digest.",
                context={"reason": "forensic_bundle_replay_digest_malformed"},
            )
        if replay_bundle is not None:
            if not isinstance(replay_bundle, Mapping):
                raise ConfigurationGuardException(
                    human_readable_reason="replay_bundle must be a mapping when provided.",
                    context={"reason": "forensic_bundle_replay_bundle_malformed"},
                )
            rb_d = replay_bundle.get("bundle_digest")
            if not isinstance(rb_d, str) or not is_hex_digest(rb_d):
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "replay_bundle.bundle_digest must be a 64-char hex digest when bound."
                    ),
                    context={"reason": "forensic_bundle_replay_bundle_digest_malformed"},
                )
            if str(rb_d) != str(rbd):
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "forensic_bundle replay_bundle_digest does not match replay bundle_digest."
                    ),
                    context={
                        "reason": "forensic_replay_bundle_digest_mismatch",
                        "observed_forensic_digest": str(rbd),
                        "expected_from_replay_bundle": str(rb_d),
                    },
                )
    else:
        if rbd is not None and not isinstance(rbd, str):
            raise ConfigurationGuardException(
                human_readable_reason="replay_bundle_digest must be a string when present.",
                context={"reason": "forensic_bundle_malformed", "field": "replay_bundle_digest"},
            )

    rcd = bundle.get("registry_closure_digest")
    if rcd is not None and not is_hex_digest(rcd):
        raise ConfigurationGuardException(
            human_readable_reason=(
                "registry_closure_digest must be a 64-char hex digest when present."
            ),
            context={"reason": "forensic_bundle_registry_closure_digest_malformed"},
        )
