from __future__ import annotations

# ruff: noqa: E402,E501
# mypy: ignore-errors
import asyncio
import csv
import gc
import hashlib
import math
import os
import random
import statistics
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import matplotlib
from benchmarks.rq_tests_py.artifact_manager import ArtifactFamily, archive_artifacts

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider

NODE_MATRIX = [3, 5, 7, 11, 15, 21, 31]
PAYLOAD_SIZE_MATRIX = [1 * 1024, 10 * 1024, 100 * 1024, 1024 * 1024]
PAYLOAD_TARGET_BYTES = 100 * 1024
SEED = 20260429
TRIALS_PER_CELL = 8

OUTPUT_DIR = Path(__file__).resolve().parent
CSV_PATH = OUTPUT_DIR / "rq3_quorum_overhead.csv"
PNG_PATH = OUTPUT_DIR / "rq3_consensus_latency.png"
RAW_CSV_PATH = OUTPUT_DIR / "rq3_quorum_trials_raw.csv"
BOX_PNG_PATH = OUTPUT_DIR / "rq3_consensus_latency_boxplot.png"
REPORT_MD_PATH = OUTPUT_DIR / "rq3_ieee_report.md"
LIVENESS_CSV_PATH = OUTPUT_DIR / "rq3_liveness_boundary.csv"
SURFACE_PNG_PATH = OUTPUT_DIR / "rq3_cpu_surface_heatmap.png"


def _shuffle_json(value: Any, rng: random.Random) -> Any:
    if isinstance(value, dict):
        items = list(value.items())
        rng.shuffle(items)
        return {k: _shuffle_json(v, rng) for k, v in items}
    if isinstance(value, list):
        return [_shuffle_json(v, rng) for v in value]
    return value


def _build_nested_payload(target_bytes: int = PAYLOAD_TARGET_BYTES) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "meta": {
            "protocol": "lirix",
            "network": "benchmark-net",
            "epoch": 1024,
            "trace": {"id": "rq3", "tags": ["entropy", "quorum", "serialization"]},
        },
        "state": {
            "accounts": [],
            "positions": [],
            "risk": {"limits": {"max_leverage": 12, "max_notional": 9_999_999}},
            "execution": {"steps": []},
        },
    }

    for i in range(240):
        payload["state"]["accounts"].append(
            {
                "address": f"0x{i:040x}",
                "nonce": i,
                "balances": {
                    "ETH": i * 17 + 3,
                    "USDC": i * 101 + 11,
                    "WBTC": i * 2 + 1,
                },
                "permissions": {
                    "can_trade": i % 2 == 0,
                    "can_withdraw": i % 3 != 0,
                    "roles": ["maker", "taker"] if i % 5 else ["guardian", "maker", "taker"],
                },
            }
        )
        payload["state"]["positions"].append(
            {
                "symbol": f"PAIR_{i % 17}",
                "size": i * 31,
                "entry_price": 1000 + i,
                "margin": {"initial": 10 + i % 7, "maintenance": 7 + i % 5},
                "oracle": {"sources": ["A", "B", "C"], "median": 1200 + i // 2},
            }
        )
        payload["state"]["execution"]["steps"].append(
            {
                "id": i,
                "op": "swap" if i % 2 == 0 else "bridge",
                "params": {"path": [f"TKN{i % 9}", f"TKN{(i + 3) % 9}"], "slippage_bps": 30},
                "receipt": {"ok": True, "gas_used": 90_000 + i * 13},
            }
        )

    # Make sure payload is at least 100KB while keeping deep structure.
    current_size = len(AsyncQuorumProvider._serialize_deterministic(payload))
    if current_size < target_bytes:
        payload["meta"]["filler"] = "X" * (target_bytes - current_size)
    return payload


def _poison_payload(payload: dict[str, Any], node_index: int) -> dict[str, Any]:
    poisoned = _shuffle_json(payload, random.Random(SEED + 10_000 + node_index))
    poisoned["state"]["risk"]["limits"]["max_notional"] += node_index + 1
    poisoned["state"]["accounts"][0]["balances"]["USDC"] += 777 + node_index
    poisoned["meta"]["trace"]["id"] = f"rq3-stale-{node_index}"
    return poisoned


class _FakeAsyncHTTPProvider:
    def __init__(self, endpoint_uri: str, request_kwargs: dict[str, Any] | None = None) -> None:
        self.endpoint_uri = endpoint_uri
        self.request_kwargs = request_kwargs or {}


class _FakeEth:
    def __init__(self, endpoint_uri: str, context: dict[str, Any]) -> None:
        self._endpoint_uri = endpoint_uri
        self._context = context

    async def call(self, _tx: Any, block_identifier: Any = None) -> Any:
        _ = block_identifier
        rtt = max(0.01, random.gauss(0.05, 0.01))
        await asyncio.sleep(rtt)
        self._context.setdefault("simulated_rtt_samples_s", []).append(rtt)
        return self._context["results_by_url"][self._endpoint_uri]

    async def get_block(self, block_number: int) -> Any:
        class _Block:
            def __init__(self, n: int) -> None:
                self.hash = f"0xblock{n:064x}"

        return _Block(block_number)

    @property
    async def block_number(self) -> int:
        return int(self._context["head_height"])


class _FakeAsyncWeb3:
    _context: dict[str, Any] = {}

    def __init__(self, provider: _FakeAsyncHTTPProvider) -> None:
        self.provider = provider
        self.eth = _FakeEth(provider.endpoint_uri, self._context)

    async def is_connected(self) -> bool:
        return True


def _required_votes(node_count: int) -> int:
    return (node_count * 2 + 2) // 3


async def _measure_parallel_hash_cpu_ms(results: list[Any]) -> float:
    async def _compute_digest(value: Any) -> str:
        return await asyncio.to_thread(AsyncQuorumProvider._hash_result, value)

    started = time.perf_counter()
    _ = await asyncio.gather(*(_compute_digest(v) for v in results))
    return (time.perf_counter() - started) * 1000


def _measure_serialization_ms(results: list[Any]) -> float:
    started = time.perf_counter()
    for item in results:
        _ = AsyncQuorumProvider._serialize_deterministic(item)
    return (time.perf_counter() - started) * 1000


def _measure_gc_collect_ms() -> float:
    started = time.perf_counter()
    gc.collect()
    return (time.perf_counter() - started) * 1000


def _count_distinct_digests(results: list[Any]) -> int:
    digests = {
        hashlib.sha256(AsyncQuorumProvider._serialize_deterministic(item)).hexdigest()
        for item in results
    }
    return len(digests)


async def _run_single_trial(
    node_count: int, payload: dict[str, Any], trial_idx: int
) -> dict[str, Any]:
    urls = [f"http://node-{i}.offline.local" for i in range(node_count)]
    byzantine_count = (node_count - 1) // 3
    regime = "within_threshold"
    honest_payload = _shuffle_json(payload, random.Random(SEED + node_count * 101 + trial_idx))

    results_by_url: dict[str, Any] = {}
    for idx, url in enumerate(urls):
        if idx < byzantine_count:
            results_by_url[url] = _poison_payload(honest_payload, idx + trial_idx * 17)
        else:
            results_by_url[url] = _shuffle_json(
                honest_payload, random.Random(SEED + idx + node_count * 100 + trial_idx * 19)
            )

    provider = AsyncQuorumProvider(urls, request_timeout=1.0)
    provider._best_url = urls[0]
    provider._best_height = 200

    _FakeAsyncWeb3._context = {
        "head_height": 200,
        "results_by_url": results_by_url,
        "simulated_rtt_samples_s": [],
    }

    values = list(results_by_url.values())
    serialize_ms = _measure_serialization_ms(values)
    gc_collect_ms = _measure_gc_collect_ms()
    gc_was_enabled = gc.isenabled()
    if gc_was_enabled:
        gc.disable()
    hash_cpu_ms = await _measure_parallel_hash_cpu_ms(values)
    quorum_started = time.perf_counter()
    with (
        patch("lirix.layers.l4_rpc_manager.AsyncHTTPProvider", _FakeAsyncHTTPProvider),
        patch("lirix.layers.l4_rpc_manager.AsyncWeb3", _FakeAsyncWeb3),
        patch.object(AsyncQuorumProvider, "refresh_quorum", return_value=200),
    ):
        result = await provider.quorum_eth_call({"to": "0x" + "0" * 40, "data": "0x"})
    if gc_was_enabled:
        gc.enable()
    quorum_elapsed_ms = (time.perf_counter() - quorum_started) * 1000
    consensus_algo_time_ms = hash_cpu_ms + quorum_elapsed_ms
    total_cpu_time_ms = serialize_ms + gc_collect_ms + consensus_algo_time_ms

    required_votes = _required_votes(node_count)
    consensus_success = len(result["quorum"]) >= required_votes
    distinct_digests = _count_distinct_digests(list(results_by_url.values()))
    simulated_rtt_samples = _FakeAsyncWeb3._context.get("simulated_rtt_samples_s", [])
    avg_simulated_rtt_ms = (
        statistics.mean(simulated_rtt_samples) * 1000.0 if simulated_rtt_samples else 0.0
    )
    theoretical_serial_time_ms = sum(simulated_rtt_samples) * 1000.0
    return {
        "trial_id": trial_idx,
        "node_count": node_count,
        "payload_size_kb": len(AsyncQuorumProvider._serialize_deterministic(payload)) // 1024,
        "byzantine_count": byzantine_count,
        "required_votes": required_votes,
        "hash_cpu_time_ms": hash_cpu_ms,
        "serialize_time_ms": serialize_ms,
        "gc_collect_time_ms": gc_collect_ms,
        "quorum_elapsed_ms": quorum_elapsed_ms,
        "consensus_algo_time_ms": consensus_algo_time_ms,
        "total_cpu_time_ms": total_cpu_time_ms,
        "avg_simulated_rtt_ms": avg_simulated_rtt_ms,
        "theoretical_serial_time_ms": theoretical_serial_time_ms,
        "entropy_digest_cardinality": distinct_digests,
        "consensus_success": consensus_success,
        "regime": regime,
        "safety_violation": False,
    }


async def _run_liveness_boundary_trial(
    node_count: int, payload: dict[str, Any], trial_idx: int
) -> dict[str, Any]:
    urls = [f"http://node-{i}.offline.local" for i in range(node_count)]
    required_votes = _required_votes(node_count)
    byzantine_count = max(0, node_count - required_votes + 1)
    regime = "above_threshold"
    honest_payload = _shuffle_json(payload, random.Random(SEED + node_count * 151 + trial_idx))

    results_by_url: dict[str, Any] = {}
    for idx, url in enumerate(urls):
        if idx < byzantine_count:
            results_by_url[url] = _poison_payload(honest_payload, idx + trial_idx * 23)
        else:
            results_by_url[url] = _shuffle_json(
                honest_payload, random.Random(SEED + idx + node_count * 211 + trial_idx * 31)
            )

    provider = AsyncQuorumProvider(urls, request_timeout=1.0)
    provider._best_url = urls[0]
    provider._best_height = 200
    _FakeAsyncWeb3._context = {
        "head_height": 200,
        "results_by_url": results_by_url,
        "simulated_rtt_samples_s": [],
    }

    values = list(results_by_url.values())
    serialize_ms = _measure_serialization_ms(values)
    gc_collect_ms = _measure_gc_collect_ms()
    gc_was_enabled = gc.isenabled()
    if gc_was_enabled:
        gc.disable()
    hash_cpu_ms = await _measure_parallel_hash_cpu_ms(values)
    quorum_started = time.perf_counter()
    consensus_success = False
    safety_violation = False
    try:
        with (
            patch("lirix.layers.l4_rpc_manager.AsyncHTTPProvider", _FakeAsyncHTTPProvider),
            patch("lirix.layers.l4_rpc_manager.AsyncWeb3", _FakeAsyncWeb3),
            patch.object(AsyncQuorumProvider, "refresh_quorum", return_value=200),
        ):
            result = await provider.quorum_eth_call({"to": "0x" + "0" * 40, "data": "0x"})
            consensus_success = len(result["quorum"]) >= required_votes
            # If consensus succeeds even after breaching threshold, treat it as safety risk signal.
            safety_violation = consensus_success
    except Exception:
        consensus_success = False
    finally:
        if gc_was_enabled:
            gc.enable()
    quorum_elapsed_ms = (time.perf_counter() - quorum_started) * 1000
    consensus_algo_time_ms = hash_cpu_ms + quorum_elapsed_ms
    total_cpu_time_ms = serialize_ms + gc_collect_ms + consensus_algo_time_ms
    distinct_digests = _count_distinct_digests(list(results_by_url.values()))
    simulated_rtt_samples = _FakeAsyncWeb3._context.get("simulated_rtt_samples_s", [])
    avg_simulated_rtt_ms = (
        statistics.mean(simulated_rtt_samples) * 1000.0 if simulated_rtt_samples else 0.0
    )
    theoretical_serial_time_ms = sum(simulated_rtt_samples) * 1000.0
    return {
        "trial_id": trial_idx,
        "node_count": node_count,
        "payload_size_kb": len(AsyncQuorumProvider._serialize_deterministic(payload)) // 1024,
        "byzantine_count": byzantine_count,
        "required_votes": required_votes,
        "hash_cpu_time_ms": hash_cpu_ms,
        "serialize_time_ms": serialize_ms,
        "gc_collect_time_ms": gc_collect_ms,
        "quorum_elapsed_ms": quorum_elapsed_ms,
        "consensus_algo_time_ms": consensus_algo_time_ms,
        "total_cpu_time_ms": total_cpu_time_ms,
        "avg_simulated_rtt_ms": avg_simulated_rtt_ms,
        "theoretical_serial_time_ms": theoretical_serial_time_ms,
        "entropy_digest_cardinality": distinct_digests,
        "consensus_success": consensus_success,
        "regime": regime,
        "safety_violation": safety_violation,
    }


def _write_main_csv(rows: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "regime",
                "node_count",
                "payload_size_kb",
                "total_cpu_time_ms",
                "p50_cpu_time_ms",
                "p95_cpu_time_ms",
                "avg_simulated_rtt_ms",
                "theoretical_serial_time_ms",
                "consensus_success_rate",
                "safety_violation_rate",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "regime": row["regime"],
                    "node_count": row["node_count"],
                    "payload_size_kb": row["payload_size_kb"],
                    "total_cpu_time_ms": f"{row['total_cpu_time_ms']:.3f}",
                    "p50_cpu_time_ms": f"{row['p50_cpu_time_ms']:.3f}",
                    "p95_cpu_time_ms": f"{row['p95_cpu_time_ms']:.3f}",
                    "avg_simulated_rtt_ms": f"{row['avg_simulated_rtt_ms']:.3f}",
                    "theoretical_serial_time_ms": f"{row['theoretical_serial_time_ms']:.3f}",
                    "consensus_success_rate": f"{row['consensus_success_rate']:.6f}",
                    "safety_violation_rate": f"{row['safety_violation_rate']:.6f}",
                }
            )


def _write_raw_csv(raw_rows: list[dict[str, Any]]) -> None:
    with RAW_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "trial_id",
                "node_count",
                "payload_size_kb",
                "byzantine_count",
                "required_votes",
                "hash_cpu_time_ms",
                "serialize_time_ms",
                "gc_collect_time_ms",
                "quorum_elapsed_ms",
                "consensus_algo_time_ms",
                "total_cpu_time_ms",
                "avg_simulated_rtt_ms",
                "theoretical_serial_time_ms",
                "entropy_digest_cardinality",
                "consensus_success",
                "regime",
                "safety_violation",
            ],
        )
        writer.writeheader()
        for row in raw_rows:
            writer.writerow(
                {
                    "trial_id": row["trial_id"],
                    "node_count": row["node_count"],
                    "payload_size_kb": row["payload_size_kb"],
                    "byzantine_count": row["byzantine_count"],
                    "required_votes": row["required_votes"],
                    "hash_cpu_time_ms": f"{row['hash_cpu_time_ms']:.3f}",
                    "serialize_time_ms": f"{row['serialize_time_ms']:.3f}",
                    "gc_collect_time_ms": f"{row['gc_collect_time_ms']:.3f}",
                    "quorum_elapsed_ms": f"{row['quorum_elapsed_ms']:.3f}",
                    "consensus_algo_time_ms": f"{row['consensus_algo_time_ms']:.3f}",
                    "total_cpu_time_ms": f"{row['total_cpu_time_ms']:.3f}",
                    "avg_simulated_rtt_ms": f"{row['avg_simulated_rtt_ms']:.3f}",
                    "theoretical_serial_time_ms": f"{row['theoretical_serial_time_ms']:.3f}",
                    "entropy_digest_cardinality": row["entropy_digest_cardinality"],
                    "consensus_success": row["consensus_success"],
                    "regime": row["regime"],
                    "safety_violation": row["safety_violation"],
                }
            )


def _write_main_plot(rows: list[dict[str, Any]]) -> None:
    focus = [
        row
        for row in rows
        if row["regime"] == "within_threshold"
        and row["payload_size_kb"] == (PAYLOAD_TARGET_BYTES // 1024)
    ]
    xs = [row["node_count"] for row in focus]
    ys = [row["total_cpu_time_ms"] for row in focus]
    yerr = [row["p95_cpu_time_ms"] - row["p50_cpu_time_ms"] for row in focus]
    plt.figure(figsize=(8, 5))
    plt.plot(xs, ys, marker="o", linewidth=2.0, label="Mean total CPU time")
    plt.errorbar(
        xs,
        ys,
        yerr=yerr,
        fmt="none",
        ecolor="tab:orange",
        elinewidth=1.2,
        capsize=4,
        label="Tail gap (p95 - p50)",
    )
    plt.xlabel("Node Count")
    plt.ylabel("CPU Time (ms)")
    plt.title("RQ3: Quorum Consensus CPU Cost under Entropy Injection")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.8)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PNG_PATH, dpi=180)
    plt.close()


def _write_boxplot(raw_rows: list[dict[str, Any]]) -> None:
    grouped = {n: [] for n in NODE_MATRIX}
    for row in raw_rows:
        if row["regime"] == "within_threshold" and row["payload_size_kb"] == (
            PAYLOAD_TARGET_BYTES // 1024
        ):
            grouped[row["node_count"]].append(row["total_cpu_time_ms"])
    plt.figure(figsize=(9, 5.5))
    data = [grouped[n] for n in NODE_MATRIX]
    plt.boxplot(data, tick_labels=[str(n) for n in NODE_MATRIX], showmeans=True)
    plt.xlabel("Node Count")
    plt.ylabel("Total CPU Time (ms)")
    plt.title("RQ3: Distribution of CPU Time across Trials")
    plt.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.8)
    plt.tight_layout()
    plt.savefig(BOX_PNG_PATH, dpi=180)
    plt.close()


def _summarize(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for regime in ("within_threshold", "above_threshold"):
        for node_count in NODE_MATRIX:
            for payload_size in PAYLOAD_SIZE_MATRIX:
                payload_kb = payload_size // 1024
                bucket = [
                    row
                    for row in raw_rows
                    if row["node_count"] == node_count
                    and row["payload_size_kb"] == payload_kb
                    and row["regime"] == regime
                ]
                if not bucket:
                    continue
                total_vals = [float(row["total_cpu_time_ms"]) for row in bucket]
                p50 = statistics.median(total_vals)
                p95 = sorted(total_vals)[max(0, int(len(total_vals) * 0.95) - 1)]
                rows.append(
                    {
                        "regime": regime,
                        "node_count": node_count,
                        "payload_size_kb": payload_kb,
                        "total_cpu_time_ms": statistics.mean(total_vals),
                        "p50_cpu_time_ms": p50,
                        "p95_cpu_time_ms": p95,
                        "avg_simulated_rtt_ms": statistics.mean(
                            float(row["avg_simulated_rtt_ms"]) for row in bucket
                        ),
                        "theoretical_serial_time_ms": statistics.mean(
                            float(row["theoretical_serial_time_ms"]) for row in bucket
                        ),
                        "serialize_time_ms": statistics.mean(
                            float(row["serialize_time_ms"]) for row in bucket
                        ),
                        "gc_collect_time_ms": statistics.mean(
                            float(row["gc_collect_time_ms"]) for row in bucket
                        ),
                        "consensus_algo_time_ms": statistics.mean(
                            float(row["consensus_algo_time_ms"]) for row in bucket
                        ),
                        "consensus_success_rate": sum(
                            1 for row in bucket if bool(row["consensus_success"])
                        )
                        / len(bucket),
                        "safety_violation_rate": sum(
                            1 for row in bucket if bool(row["safety_violation"])
                        )
                        / len(bucket),
                    }
                )
    return rows


def _write_liveness_csv(summary_rows: list[dict[str, Any]]) -> None:
    with LIVENESS_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "regime",
                "node_count",
                "payload_size_kb",
                "consensus_success_rate",
                "safety_violation_rate",
                "serialize_time_ms",
                "gc_collect_time_ms",
                "consensus_algo_time_ms",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(
                {
                    "regime": row["regime"],
                    "node_count": row["node_count"],
                    "payload_size_kb": row["payload_size_kb"],
                    "consensus_success_rate": f"{row['consensus_success_rate']:.6f}",
                    "safety_violation_rate": f"{row['safety_violation_rate']:.6f}",
                    "serialize_time_ms": f"{row['serialize_time_ms']:.3f}",
                    "gc_collect_time_ms": f"{row['gc_collect_time_ms']:.3f}",
                    "consensus_algo_time_ms": f"{row['consensus_algo_time_ms']:.3f}",
                }
            )


def _write_surface_plot(summary_rows: list[dict[str, Any]]) -> None:
    within = [r for r in summary_rows if r["regime"] == "within_threshold"]
    x_nodes = NODE_MATRIX
    y_sizes = [s // 1024 for s in PAYLOAD_SIZE_MATRIX]
    grid = np.zeros((len(y_sizes), len(x_nodes)), dtype=float)
    for i, size_kb in enumerate(y_sizes):
        for j, node in enumerate(x_nodes):
            row = next(
                (r for r in within if r["payload_size_kb"] == size_kb and r["node_count"] == node),
                None,
            )
            grid[i, j] = float(row["total_cpu_time_ms"]) if row else np.nan
    plt.figure(figsize=(9.5, 5.5))
    im = plt.imshow(grid, cmap="magma", aspect="auto")
    plt.xticks(range(len(x_nodes)), [str(n) for n in x_nodes])
    plt.yticks(range(len(y_sizes)), [str(k) for k in y_sizes])
    plt.xlabel("Node Count")
    plt.ylabel("Payload Size (KB)")
    plt.title("RQ3 CPU Cost Surface (Within Byzantine Threshold)")
    plt.colorbar(im, label="Mean CPU Time (ms)")
    plt.tight_layout()
    plt.savefig(SURFACE_PNG_PATH, dpi=180)
    plt.close()


def _write_report(summary_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> None:
    payload_bytes = len(
        AsyncQuorumProvider._serialize_deterministic(_build_nested_payload(PAYLOAD_TARGET_BYTES))
    )
    entropy_mean = statistics.mean(float(r["entropy_digest_cardinality"]) for r in raw_rows)
    within = [r for r in summary_rows if r["regime"] == "within_threshold"]
    above = [r for r in summary_rows if r["regime"] == "above_threshold"]
    within_ok = all(
        math.isclose(float(r["consensus_success_rate"]), 1.0, rel_tol=0.0, abs_tol=1e-9)
        for r in within
    )
    above_safe = all(
        math.isclose(float(r["safety_violation_rate"]), 0.0, rel_tol=0.0, abs_tol=1e-9)
        for r in above
    )
    above_liveness_loss = all(
        math.isclose(float(r["consensus_success_rate"]), 0.0, rel_tol=0.0, abs_tol=1e-9)
        for r in above
    )
    lines = [
        "# RQ3 Quorum Benchmark Report",
        "",
        "## Experiment Setup",
        f"- Node matrix: {NODE_MATRIX}",
        f"- Payload matrix (KB): {[s // 1024 for s in PAYLOAD_SIZE_MATRIX]}",
        f"- Trials per cell: {TRIALS_PER_CELL}",
        f"- Baseline payload reference size: {payload_bytes / 1024:.2f} KB",
        "- Entropy injection: shuffled key order for honest nodes + Byzantine stale-state poisoning.",
        "- Network path: fully intercepted via mocked AsyncHTTPProvider/AsyncWeb3 (in-memory only).",
        "",
        "## Key Results",
    ]
    for row in within:
        lines.append(
            f"- within-threshold | N={row['node_count']} | payload={row['payload_size_kb']}KB: "
            f"mean={row['total_cpu_time_ms']:.3f} ms, p50={row['p50_cpu_time_ms']:.3f} ms, "
            f"p95={row['p95_cpu_time_ms']:.3f} ms, consensus_success_rate={row['consensus_success_rate']:.3f}, "
            f"serialize={row['serialize_time_ms']:.3f} ms, gc={row['gc_collect_time_ms']:.3f} ms, "
            f"consensus_algo={row['consensus_algo_time_ms']:.3f} ms"
        )
    lines.extend(
        [
            "",
            "## Safety/Liveness Boundary",
            f"- Safety intact above threshold (no false consensus): {above_safe}",
            f"- Liveness lost above threshold (expected fail-closed): {above_liveness_loss}",
            f"- Full liveness within threshold: {within_ok}",
            "",
            "## Entropy Signal",
            f"- Mean digest-cardinality across all samples: {entropy_mean:.2f}",
            "- Digest cardinality > 1 confirms poisoned branch divergence while honest nodes stay hash-consistent after deterministic serialization.",
            "",
        ]
    )
    REPORT_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_rq3_quorum_benchmark() -> list[dict[str, Any]]:
    raw_rows: list[dict[str, Any]] = []
    for payload_size in PAYLOAD_SIZE_MATRIX:
        payload = _build_nested_payload(payload_size)
        for node_count in NODE_MATRIX:
            for trial_idx in range(TRIALS_PER_CELL):
                raw_rows.append(asyncio.run(_run_single_trial(node_count, payload, trial_idx)))
                raw_rows.append(
                    asyncio.run(_run_liveness_boundary_trial(node_count, payload, trial_idx))
                )

    rows = _summarize(raw_rows)
    _write_main_csv(rows)
    _write_raw_csv(raw_rows)
    _write_main_plot(rows)
    _write_boxplot(raw_rows)
    _write_liveness_csv(rows)
    _write_surface_plot(rows)
    _write_report(rows, raw_rows)
    archive_artifacts(
        ArtifactFamily(name="rq3", output_dir=OUTPUT_DIR),
        [
            CSV_PATH.name,
            RAW_CSV_PATH.name,
            BOX_PNG_PATH.name,
            LIVENESS_CSV_PATH.name,
            SURFACE_PNG_PATH.name,
            REPORT_MD_PATH.name,
        ],
    )
    return rows


def test_rq3_quorum_benchmark() -> None:
    if os.getenv("RUN_RQ3_BENCHMARK") != "1":
        return
    rows = run_rq3_quorum_benchmark()
    assert len(rows) >= len(NODE_MATRIX) * len(PAYLOAD_SIZE_MATRIX)
    within = [r for r in rows if r["regime"] == "within_threshold"]
    above = [r for r in rows if r["regime"] == "above_threshold"]
    assert all(math.isclose(float(r["consensus_success_rate"]), 1.0, abs_tol=1e-9) for r in within)
    assert all(math.isclose(float(r["safety_violation_rate"]), 0.0, abs_tol=1e-9) for r in above)
    assert CSV_PATH.exists()
    assert PNG_PATH.exists()
    assert RAW_CSV_PATH.exists()
    assert BOX_PNG_PATH.exists()
    assert LIVENESS_CSV_PATH.exists()
    assert SURFACE_PNG_PATH.exists()
    assert REPORT_MD_PATH.exists()


if __name__ == "__main__":
    run_rq3_quorum_benchmark()
