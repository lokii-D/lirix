from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from lirix import Lirix


def _install_fast_success_monkeypatches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _async_reconcile(self) -> int:  # type: ignore[no-untyped-def]
        return 1

    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _async_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        },
    )

    async def _simulate_async(
        self: object,
        _payload: object,
        *,
        async_web3: object,
        block_number: int,
        state_overrides: object | None = None,
    ) -> dict[str, object]:
        _ = async_web3, state_overrides
        return {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)


_PERF_PAYLOAD = {"to": "0x1111111111111111111111111111111111111111", "data": "0x"}


def _install_realistic_fixture_monkeypatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Heavier deterministic stubs: richer L5 outcome + RPC evidence snapshot shape (still no live network)."""
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)

    def _sync_reconcile(self) -> int:  # type: ignore[no-untyped-def]
        return 18_000_001

    async def _async_reconcile(self) -> int:  # type: ignore[no-untyped-def]
        return 18_000_001

    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", _sync_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _async_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())

    def _evidence_snapshot(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "fixture_network": True,
            "endpoints": [{"url": "https://example.invalid", "kind": "fixture"}],
            "block_hint": 18_000_001,
        }

    monkeypatch.setattr("lirix._client_core.RPCManager.evidence_snapshot", _evidence_snapshot)

    def _simulate(self, payload, web3, block_number, state_overrides=None):  # type: ignore[no-untyped-def]
        return {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x" + "00" * 32,
            "gas_used": 210000,
            "layer": "L5",
            "simulation_assumptions": ["fixture_network_fixed_rpc"],
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate", _simulate)

    async def _simulate_async(self, payload, async_web3, block_number, state_overrides=None):  # type: ignore[no-untyped-def]
        return {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x" + "00" * 32,
            "gas_used": 210000,
            "layer": "L5",
            "simulation_assumptions": ["fixture_network_fixed_rpc"],
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)


def _sample_latency_ms(callable_obj: Any, *, rounds: int, warmup_rounds: int = 3) -> list[float]:
    for _ in range(warmup_rounds):
        callable_obj()
    samples: list[float] = []
    for _ in range(rounds):
        start = time.perf_counter()
        callable_obj()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


def _latency_stats(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    p50 = statistics.median(ordered)
    p95_idx = max(0, int(len(ordered) * 0.95) - 1)
    p95 = ordered[p95_idx]
    return {"p50": p50, "p95": p95}


def _assert_latency_budget(
    samples_ms: list[float], *, p50_budget_ms: float, p95_budget_ms: float
) -> None:
    stats = _latency_stats(samples_ms)
    p50 = stats["p50"]
    p95 = stats["p95"]
    assert p50 <= p50_budget_ms, f"p50 latency budget exceeded: {p50:.2f}ms > {p50_budget_ms}ms"
    assert p95 <= p95_budget_ms, f"p95 latency budget exceeded: {p95:.2f}ms > {p95_budget_ms}ms"


def _concurrent_error_rate(callable_obj: Any, *, workers: int, rounds_per_worker: int) -> float:
    total = workers * rounds_per_worker

    def _one() -> int:
        failures = 0
        for _ in range(rounds_per_worker):
            try:
                callable_obj()
            except Exception:  # noqa: BLE001
                failures += 1
        return failures

    with ThreadPoolExecutor(max_workers=workers) as pool:
        failures = sum(pool.map(lambda _idx: _one(), range(workers)))
    return failures / max(total, 1)


async def _measure_sync_entrypoint_from_async_context(
    guard: Lirix, payload: dict[str, Any], *, rounds: int
) -> list[float]:
    samples: list[float] = []
    for _ in range(rounds):
        start = time.perf_counter()
        out = await asyncio.to_thread(guard.validate_and_simulate, "swap", payload)
        assert out["status"] == "approved"
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


@pytest.mark.perf
@pytest.mark.slow
def test_main_paths_quick_gate_budgets_and_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fast_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = _PERF_PAYLOAD

    validate_only_samples = _sample_latency_ms(
        lambda: guard.validate_only("swap", payload),
        rounds=25,
        warmup_rounds=5,
    )
    validate_and_simulate_samples = _sample_latency_ms(
        lambda: guard.validate_and_simulate("swap", payload),
        rounds=25,
        warmup_rounds=5,
    )
    simulate_only_samples = _sample_latency_ms(
        lambda: guard.simulate_only(payload),
        rounds=25,
        warmup_rounds=5,
    )
    concurrent_error_rate = _concurrent_error_rate(
        lambda: guard.validate_only("swap", payload),
        workers=4,
        rounds_per_worker=8,
    )

    _assert_latency_budget(validate_only_samples, p50_budget_ms=10.0, p95_budget_ms=20.0)
    _assert_latency_budget(validate_and_simulate_samples, p50_budget_ms=14.0, p95_budget_ms=24.0)
    _assert_latency_budget(simulate_only_samples, p50_budget_ms=12.0, p95_budget_ms=22.0)
    assert (
        concurrent_error_rate <= 0.01
    ), f"concurrent error rate too high: {concurrent_error_rate:.2%}"


@pytest.mark.perf
@pytest.mark.slow
def test_main_paths_realistic_fixture_quick_gate_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_realistic_fixture_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = _PERF_PAYLOAD

    validate_only_samples = _sample_latency_ms(
        lambda: guard.validate_only("swap", payload),
        rounds=20,
        warmup_rounds=4,
    )
    validate_and_simulate_samples = _sample_latency_ms(
        lambda: guard.validate_and_simulate("swap", payload),
        rounds=20,
        warmup_rounds=4,
    )
    simulate_only_samples = _sample_latency_ms(
        lambda: guard.simulate_only(payload),
        rounds=20,
        warmup_rounds=4,
    )
    concurrent_error_rate = _concurrent_error_rate(
        lambda: guard.validate_and_simulate("swap", payload),
        workers=4,
        rounds_per_worker=8,
    )

    _assert_latency_budget(validate_only_samples, p50_budget_ms=14.0, p95_budget_ms=28.0)
    _assert_latency_budget(validate_and_simulate_samples, p50_budget_ms=18.0, p95_budget_ms=32.0)
    _assert_latency_budget(simulate_only_samples, p50_budget_ms=16.0, p95_budget_ms=30.0)
    assert (
        concurrent_error_rate <= 0.01
    ), f"concurrent error rate too high: {concurrent_error_rate:.2%}"


@pytest.mark.asyncio
@pytest.mark.perf
@pytest.mark.slow
async def test_run_coroutine_sync_thread_handoff_budget_in_async_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = _PERF_PAYLOAD
    samples = await _measure_sync_entrypoint_from_async_context(guard, payload, rounds=16)
    _assert_latency_budget(samples, p50_budget_ms=30.0, p95_budget_ms=60.0)


@pytest.mark.asyncio
@pytest.mark.perf
@pytest.mark.slow
async def test_run_coroutine_sync_thread_handoff_stability_under_fanout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = _PERF_PAYLOAD

    async def _one_call() -> dict[str, Any]:
        return await asyncio.to_thread(guard.validate_and_simulate, "swap", payload)

    outputs = await asyncio.gather(*(_one_call() for _ in range(24)))
    assert len(outputs) == 24
    assert all(out["status"] == "approved" for out in outputs)


@pytest.mark.skipif(
    os.getenv("LIRIX_RUN_PERF_BASELINE", "0") != "1",
    reason="Set LIRIX_RUN_PERF_BASELINE=1 to collect non-blocking performance baseline report.",
)
@pytest.mark.perf
@pytest.mark.slow
def test_main_paths_baseline_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fast_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = _PERF_PAYLOAD

    validate_only_samples = _sample_latency_ms(
        lambda: guard.validate_only("swap", payload),
        rounds=100,
        warmup_rounds=10,
    )
    validate_and_simulate_samples = _sample_latency_ms(
        lambda: guard.validate_and_simulate("swap", payload),
        rounds=100,
        warmup_rounds=10,
    )
    simulate_only_samples = _sample_latency_ms(
        lambda: guard.simulate_only(payload),
        rounds=100,
        warmup_rounds=10,
    )
    concurrent_error_rate = _concurrent_error_rate(
        lambda: guard.validate_and_simulate("swap", payload),
        workers=8,
        rounds_per_worker=20,
    )
    assert concurrent_error_rate == 0.0
    print(
        "PERF_BASELINE "
        f"validate_only={_latency_stats(validate_only_samples)} "
        f"validate_and_simulate={_latency_stats(validate_and_simulate_samples)} "
        f"simulate_only={_latency_stats(simulate_only_samples)} "
        f"concurrent_error_rate={concurrent_error_rate:.2%}"
    )


@pytest.mark.skipif(
    os.getenv("LIRIX_RUN_PERF_REALISTIC_BASELINE", "0") != "1",
    reason=(
        "Set LIRIX_RUN_PERF_REALISTIC_BASELINE=1 (optionally LIRIX_PERF_REALISTIC_BASELINE_JSON_OUT=path) "
        "to emit a sign-off perf baseline JSON."
    ),
)
@pytest.mark.perf
@pytest.mark.slow
def test_main_paths_realistic_fixture_baseline_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_realistic_fixture_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = _PERF_PAYLOAD

    validate_only_samples = _sample_latency_ms(
        lambda: guard.validate_only("swap", payload),
        rounds=80,
        warmup_rounds=8,
    )
    validate_and_simulate_samples = _sample_latency_ms(
        lambda: guard.validate_and_simulate("swap", payload),
        rounds=80,
        warmup_rounds=8,
    )
    simulate_only_samples = _sample_latency_ms(
        lambda: guard.simulate_only(payload),
        rounds=80,
        warmup_rounds=8,
    )
    concurrent_error_rate = _concurrent_error_rate(
        lambda: guard.validate_and_simulate("swap", payload),
        workers=8,
        rounds_per_worker=16,
    )
    assert concurrent_error_rate == 0.0

    vo = _latency_stats(validate_only_samples)
    vas = _latency_stats(validate_and_simulate_samples)
    so = _latency_stats(simulate_only_samples)
    report_obj: dict[str, Any] = {
        "schema_version": "1.0",
        "profile": "realistic_fixture_network",
        "metrics": {
            "validate_only_ms": {"p50": vo["p50"], "p95": vo["p95"]},
            "validate_and_simulate_ms": {"p50": vas["p50"], "p95": vas["p95"]},
            "simulate_only_ms": {"p50": so["p50"], "p95": so["p95"]},
            "concurrent_error_rate": concurrent_error_rate,
        },
    }
    out = os.getenv("LIRIX_PERF_REALISTIC_BASELINE_JSON_OUT")
    if out:
        Path(out).write_text(json.dumps(report_obj, sort_keys=True), encoding="utf-8")
    print("PERF_REALISTIC_BASELINE_JSON " + json.dumps(report_obj, sort_keys=True))
