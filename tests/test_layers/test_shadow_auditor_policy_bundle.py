from __future__ import annotations

import hashlib
import json

import pytest
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema


def _integrity_digest(policy: dict) -> str:
    normalized = ShadowPolicySchema.model_validate(policy).model_dump(mode="python")
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def _policy(
    *, policy_id: str, policy_version: str, environment: str, max_slippage_bps: int | None = None
) -> dict:
    payload: dict = {
        "policy_id": policy_id,
        "policy_version": policy_version,
        "environment": environment,
        "allowed_target_contracts": "ANY",
        "forbidden_methods": [],
    }
    if max_slippage_bps is not None:
        payload["max_slippage_bps"] = max_slippage_bps
    return payload


def _version(
    *,
    version: str,
    environment: str,
    policy_id: str,
    status: str = "active",
    rollback_to: str | None = None,
    max_slippage_bps: int | None = None,
) -> dict:
    policy = _policy(
        policy_id=policy_id,
        policy_version=version,
        environment=environment,
        max_slippage_bps=max_slippage_bps,
    )
    payload: dict = {
        "version": version,
        "environment": environment,
        "status": status,
        "integrity_digest": _integrity_digest(policy),
        "policy": policy,
    }
    if rollback_to is not None:
        payload["rollback_to"] = rollback_to
    return payload


def test_shadow_auditor_digest_verified_selects_by_environment_and_reports_effective_mode() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    report = auditor.decision_report(
        security_policy={
            "policy_bundle": {
                "bundle_id": "enterprise-pack",
                "active_version": "2026.05",
                "versions": [
                    _version(
                        version="2026.05",
                        environment="prod",
                        policy_id="prod-hard",
                        max_slippage_bps=25,
                    ),
                    _version(
                        version="2026.05",
                        environment="staging",
                        policy_id="staging-soft",
                        max_slippage_bps=200,
                    ),
                ],
            },
            "policy_environment": "prod",
        }
    )
    assert report["policy_id"] == "prod-hard"
    assert report["environment"] == "prod"
    assert report["bundle"]["source"] == "bundle:enterprise-pack"
    assert report["lifecycle_mode"] == "digest_verified"


def test_shadow_auditor_environment_fallback_records_conflict() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    report = auditor.decision_report(
        security_policy={
            "policy_bundle": {
                "bundle_id": "enterprise-pack",
                "versions": [
                    _version(version="2026.05", environment="prod", policy_id="prod-hard")
                ],
            },
            "policy_environment": "qa",
        }
    )
    conflicts = report["bundle"]["conflicts"]
    assert conflicts
    assert conflicts[0]["key"] == "environment"
    assert conflicts[0]["reason"] == "requested_environment_not_found_fallback_used"


def test_shadow_auditor_prefers_explicit_policy_version_for_environment() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    report = auditor.decision_report(
        security_policy={
            "policy_bundle": {
                "bundle_id": "enterprise-pack",
                "versions": [
                    _version(version="a", environment="prod", policy_id="prod-a"),
                    _version(version="b", environment="prod", policy_id="prod-b"),
                ],
            },
            "policy_environment": "prod",
            "policy_version": "b",
        }
    )
    assert report["policy_id"] == "prod-b"


def test_shadow_auditor_rollback_applies_when_selected_version_inactive() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    report = auditor.decision_report(
        security_policy={
            "policy_bundle": {
                "bundle_id": "enterprise-pack",
                "active_version": "2026.06",
                "versions": [
                    _version(
                        version="2026.06",
                        environment="prod",
                        policy_id="prod-paused",
                        status="paused",
                        rollback_to="2026.05",
                    ),
                    _version(version="2026.05", environment="prod", policy_id="prod-stable"),
                ],
            },
            "policy_environment": "prod",
        }
    )
    assert report["policy_id"] == "prod-stable"
    assert report["bundle"]["rollback_applied"] is True
    assert report["bundle"]["conflicts"]
    assert any(c.get("reason") == "rollback_applied" for c in report["bundle"]["conflicts"])


def test_shadow_auditor_inactive_with_missing_rollback_fails_closed_in_digest_verified() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    with pytest.raises(LirixPolicyViolationException):
        auditor.decision_report(
            security_policy={
                "policy_bundle": {
                    "bundle_id": "enterprise-pack",
                    "active_version": "x",
                    "versions": [
                        _version(
                            version="x",
                            environment="prod",
                            policy_id="prod-x",
                            status="paused",
                            rollback_to="missing",
                        )
                    ],
                },
                "policy_environment": "prod",
            }
        )


def test_shadow_auditor_import_export_policy_bundle_roundtrip() -> None:
    raw_bundle = {
        "bundle_id": "roundtrip-pack",
        "active_version": "v1",
        "versions": [_version(version="v1", environment="prod", policy_id="prod")],
    }
    imported = ShadowAuditor.import_policy_bundle(raw_bundle)
    exported = ShadowAuditor.export_policy_bundle(imported)
    assert exported["bundle_id"] == "roundtrip-pack"
    assert exported["versions"][0]["version"] == "v1"


@pytest.mark.migration
class TestShadowAuditorPolicyBundleMigrationCompatibility:
    def test_shadow_auditor_legacy_lifecycle_input_is_ignored_and_instance_mode_is_source_of_truth(
        self,
    ) -> None:
        auditor = ShadowAuditor(lifecycle_mode="digest_verified")
        report = auditor.decision_report(
            security_policy={
                "policy_lifecycle_mode": "legacy",
                "policy_bundle": {
                    "bundle_id": "enterprise-pack",
                    "active_version": "2026.05",
                    "versions": [
                        _version(
                            version="2026.05",
                            environment="prod",
                            policy_id="prod-hard",
                            max_slippage_bps=25,
                        )
                    ],
                },
                "policy_environment": "prod",
            }
        )
        assert report["lifecycle_mode"] == "digest_verified"

    @pytest.mark.parametrize("legacy_alias", ["legacy", "signed_only"])
    def test_shadow_auditor_legacy_alias_inputs_are_migration_only_and_do_not_override_instance(
        self,
        legacy_alias: str,
    ) -> None:
        auditor = ShadowAuditor(lifecycle_mode="digest_verified")
        report = auditor.decision_report(
            security_policy={
                "policy_lifecycle_mode": legacy_alias,
                "policy_bundle": {
                    "bundle_id": "alias-pack",
                    "versions": [_version(version="1", environment="prod", policy_id="prod")],
                },
                "policy_environment": "prod",
            }
        )
        assert report["lifecycle_mode"] == "digest_verified"

    def test_shadow_auditor_signed_only_alias_rejects_invalid_integrity_payload(self) -> None:
        auditor = ShadowAuditor(lifecycle_mode="digest_verified")
        with pytest.raises(LirixPolicyViolationException):
            auditor.decision_report(
                security_policy={
                    "policy_lifecycle_mode": "signed_only",
                    "policy_bundle": {
                        "bundle_id": "signed-pack",
                        "versions": [
                            {
                                "version": "1",
                                "environment": "prod",
                                "status": "active",
                                "signature": "bad",
                                "policy": _policy(
                                    policy_id="prod", policy_version="1", environment="prod"
                                ),
                            }
                        ],
                    },
                    "policy_environment": "prod",
                }
            )
