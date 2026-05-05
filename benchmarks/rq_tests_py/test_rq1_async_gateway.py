from __future__ import annotations

# ruff: noqa: E402,E501,E741
# mypy: ignore-errors
import random

GLOBAL_RANDOM_SEED = 20260501
random.seed(GLOBAL_RANDOM_SEED)

import asyncio
import csv
import math
import os
import platform
import resource
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    import seaborn as sns
except ModuleNotFoundError:
    sns = None

from lirix.integrations.autogen import tool as autogen_tool

from .artifact_manager import ArtifactFamily, archive_artifacts
from .artifact_paths import relpaths_under, resolve_tdsc_rq_layout

CONCURRENCY_MATRIX = [10, 50, 100, 200, 500]
OPEN_LOOP_LAMBDA_MATRIX: list[int] = []
WARMUP_SECONDS = 10.0
MEASURE_WINDOW_SECONDS = 60.0
MEASURE_ROUNDS = 2
OUTPUT_LAYOUT = resolve_tdsc_rq_layout(1)
RUN_ROOT = OUTPUT_LAYOUT.output_dir
RQ1_CSV_DIR = RUN_ROOT / "rq1_csv"
RQ1_PNG_DIR = RUN_ROOT / "rq1_png"
RQ1_PDF_DIR = RUN_ROOT / "rq1_pdf"
CSV_PATH = RQ1_CSV_DIR / "rq1_throughput.csv"
RQ1_TARGET_CSV_PATH = RQ1_CSV_DIR / "rq1_core_metrics.csv"
RAW_CSV_PATH = RQ1_CSV_DIR / "rq1_trials_raw.csv"
CDF_CSV_PATH = RQ1_CSV_DIR / "rq1_cdf_n200_points.csv"
PNG_PATH = RQ1_PNG_DIR / "rq1_gil_jitter_cdf.png"
TAIL_CCDF_PNG_PATH = RQ1_PNG_DIR / "rq1_gil_jitter_ccdf.png"
ABS_CCDF_PDF_PATH = RQ1_PDF_DIR / "ccdf_absolute_latency.pdf"
THROUGHPUT_LATENCY_PDF_PATH = RQ1_PDF_DIR / "throughput_vs_latency.pdf"
EVENT_LOOP_JITTER_LOG_PDF_PATH = RQ1_PDF_DIR / "rq1_event_loop_jitter_log.pdf"
TPS_VS_TAIL_LATENCY_PDF_PATH = RQ1_PDF_DIR / "rq1_tps_vs_tail_latency.pdf"
PCTL_PNG_PATH = RQ1_PNG_DIR / "rq1_jitter_percentiles.png"
TPS_PNG_PATH = RQ1_PNG_DIR / "rq1_tps_scaling.png"
BOXPLOT_PNG_PATH = RQ1_PNG_DIR / "rq1_jitter_boxplot_n200.png"
REPORT_PATH = RQ1_CSV_DIR / "rq1_ieee_report.md"
DUMMY_RPC_URLS = ("http://offline.local",)
HEARTBEAT_INTERVAL_SECONDS = 0.01
CDF_TARGET_CONCURRENCY = 200
COLD_START_TRIM_RATIO = 0.05
MIN_HEARTBEAT_SAMPLES = 1

if sns is not None:
    sns.set_theme(style="whitegrid", context="paper")
else:
    plt.style.use("seaborn-v0_8-whitegrid")


def _mock_validate_and_simulate(
    _self: Any,
    intent: str,
    payload: dict[str, Any],
    security_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Deliberately blocking mixed workload; no asyncio primitives here.
    time.sleep(0.05)
    _ = sum(i * i for i in range(20000))
    return {
        "ok": True,
        "intent": intent,
        "payload_size": len(payload),
        "security_policy": security_policy,
    }


async def _baseline_worker() -> str:
    return autogen_tool.lirix_validate_intent("swap 1 ETH for USDC", DUMMY_RPC_URLS, intent="swap")


async def _lirix_worker() -> str:
    return await autogen_tool.alirix_validate_intent(
        "swap 1 ETH for USDC", DUMMY_RPC_URLS, intent="swap"
    )


@dataclass
class TrialResult:
    mode: str
    load_model: str
    load_value: int
    round_id: int
    elapsed_seconds: float
    tps: float
    jitter_ms: list[float]
    absolute_latency_ms: list[float]
    request_records: list[tuple[float, float, float]]
    event_loop_lag_ms: list[float]
    cpu_util_percent: float
    peak_rss_mb: float


async def _collect_event_loop_jitter(
    stop_event: asyncio.Event,
    interval: float = HEARTBEAT_INTERVAL_SECONDS,
) -> list[float]:
    loop = asyncio.get_running_loop()
    expected = loop.time() + interval
    jitters: list[float] = []
    while not stop_event.is_set():
        await asyncio.sleep(interval)
        now = loop.time()
        lag = max(0.0, now - expected)
        jitters.append(lag)
        expected = now + interval
    return jitters


async def _tick_probe(
    stop_event: asyncio.Event, data_list: list[float], interval: float = 0.01
) -> None:
    while not stop_event.is_set():
        start = time.perf_counter()
        await asyncio.sleep(interval)
        data_list.append(max(0.0, time.perf_counter() - start - interval))


def _percentile_values_ms(samples_ms: list[float]) -> dict[str, float]:
    if not samples_ms:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "std": 0.0}
    arr = np.asarray(samples_ms)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
    }


def _ci95_half_width(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    std = statistics.stdev(samples)
    return 1.96 * (std / math.sqrt(len(samples)))


def _build_summary_row(
    mode: str, concurrency: int, trials: list[TrialResult]
) -> dict[str, float | int | str]:
    all_jitter_ms = [j for t in trials for j in t.jitter_ms]
    trim = int(len(all_jitter_ms) * COLD_START_TRIM_RATIO)
    trimmed = all_jitter_ms[trim:] if len(all_jitter_ms) > trim else all_jitter_ms
    if len(trimmed) < MIN_HEARTBEAT_SAMPLES:
        raise RuntimeError(
            f"Insufficient heartbeat samples for mode={mode}, load={concurrency}: "
            f"{len(trimmed)} < {MIN_HEARTBEAT_SAMPLES}. Increase MEASURE_WINDOW_SECONDS."
        )
    all_jitter_ms = trimmed
    pctl = _percentile_values_ms(all_jitter_ms)
    all_abs_latency_ms = [j for t in trials for j in t.absolute_latency_ms]
    abs_pctl = (
        _percentile_values_ms(all_abs_latency_ms)
        if all_abs_latency_ms
        else {"p99": 0.0, "mean": 0.0}
    )
    all_event_loop_lag_ms = [lag for t in trials for lag in t.event_loop_lag_ms]
    event_loop_lag_pctl = (
        _percentile_values_ms(all_event_loop_lag_ms)
        if all_event_loop_lag_ms
        else {"p99": 0.0, "mean": 0.0}
    )
    tps_values = [t.tps for t in trials]
    elapsed_values = [t.elapsed_seconds for t in trials]
    cpu_values = [t.cpu_util_percent for t in trials]
    rss_values = [t.peak_rss_mb for t in trials]
    return {
        "mode": mode,
        "load_value": concurrency,
        "rounds": len(trials),
        "jitter_samples": len(all_jitter_ms),
        "p50_jitter_ms": pctl["p50"],
        "p90_jitter_ms": pctl["p90"],
        "p95_jitter_ms": pctl["p95"],
        "p99_jitter_ms": pctl["p99"],
        "mean_jitter_ms": pctl["mean"],
        "std_jitter_ms": pctl["std"],
        "tps_mean": statistics.mean(tps_values) if tps_values else 0.0,
        "tps_ci95": _ci95_half_width(tps_values),
        "elapsed_mean_s": statistics.mean(elapsed_values) if elapsed_values else 0.0,
        "p99_absolute_latency_ms": abs_pctl["p99"],
        "mean_absolute_latency_ms": abs_pctl["mean"],
        "mean_event_loop_lag_ms": event_loop_lag_pctl["mean"],
        "p99_event_loop_lag_ms": event_loop_lag_pctl["p99"],
        "cpu_util_mean_percent": statistics.mean(cpu_values) if cpu_values else 0.0,
        "cpu_util_peak_percent": max(cpu_values) if cpu_values else 0.0,
        "peak_rss_mb_max": max(rss_values) if rss_values else 0.0,
    }


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports ru_maxrss in bytes.
    return float(r.ru_maxrss) / (1024.0 * 1024.0)


async def _run_closed_loop(
    worker: Callable[[], Awaitable[str]], concurrency: int, duration_seconds: float
) -> tuple[
    float,
    list[float],
    int,
    float,
    float,
    list[float],
    list[tuple[float, float, float]],
    list[float],
]:
    stop_event = asyncio.Event()
    jitter_task = asyncio.create_task(_collect_event_loop_jitter(stop_event))
    tick_probe_data: list[float] = []
    tick_probe_task = asyncio.create_task(_tick_probe(stop_event, tick_probe_data))
    end_time = time.perf_counter() + duration_seconds
    completed = 0
    started = time.perf_counter()
    cpu_start = time.process_time()
    rss_start = _rss_mb()

    request_records: list[tuple[float, float, float]] = []

    async def _slot() -> None:
        nonlocal completed
        while time.perf_counter() < end_time:
            intended_start_timestamp_ms = time.time() * 1000.0
            await worker()
            actual_completion_timestamp_ms = time.time() * 1000.0
            request_records.append(
                (
                    intended_start_timestamp_ms,
                    actual_completion_timestamp_ms,
                    actual_completion_timestamp_ms - intended_start_timestamp_ms,
                )
            )
            completed += 1

    await asyncio.gather(*(_slot() for _ in range(concurrency)))
    total_time = time.perf_counter() - started
    cpu_elapsed = time.process_time() - cpu_start
    cpu_util = (cpu_elapsed / total_time) * 100.0 if total_time > 0 else 0.0
    peak_rss = max(rss_start, _rss_mb())
    stop_event.set()
    await asyncio.sleep(0)
    jitters_seconds = await jitter_task
    await tick_probe_task
    absolute_latency_ms = [record[2] for record in request_records]
    return (
        total_time,
        [j * 1000.0 for j in jitters_seconds],
        completed,
        cpu_util,
        peak_rss,
        absolute_latency_ms,
        request_records,
        [v * 1000.0 for v in tick_probe_data],
    )


async def _run_open_loop(
    worker: Callable[[], Awaitable[str]], lambda_rps: int, duration_seconds: float
) -> tuple[
    float,
    list[float],
    int,
    float,
    float,
    list[float],
    list[tuple[float, float, float]],
    list[float],
]:
    stop_event = asyncio.Event()
    jitter_task = asyncio.create_task(_collect_event_loop_jitter(stop_event))
    tick_probe_data: list[float] = []
    tick_probe_task = asyncio.create_task(_tick_probe(stop_event, tick_probe_data))
    rng = np.random.default_rng(20260430 + lambda_rps)
    started = time.perf_counter()
    started_wall_ms = time.time() * 1000.0
    cpu_start = time.process_time()
    rss_start = _rss_mb()
    intended_offsets: list[float] = []
    elapsed = 0.0
    while elapsed < duration_seconds:
        elapsed += float(rng.exponential(1.0 / lambda_rps))
        if elapsed < duration_seconds:
            intended_offsets.append(elapsed)
    tasks: list[asyncio.Task[tuple[float, float, float]]] = []
    completion_deadline = started + duration_seconds + 5.0

    async def _timed_worker(intended_start_epoch_ms: float) -> tuple[float, float, float]:
        await worker()
        actual_completion_timestamp_ms = time.time() * 1000.0
        absolute_latency_ms = actual_completion_timestamp_ms - intended_start_epoch_ms
        return intended_start_epoch_ms, actual_completion_timestamp_ms, absolute_latency_ms

    async def _dispatch_after_offset(
        offset: float, intended_start_epoch_ms: float
    ) -> tuple[float, float, float]:
        intended_start = started + offset
        sleep_s = intended_start - time.perf_counter()
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)
        return await _timed_worker(intended_start_epoch_ms)

    for offset in intended_offsets:
        intended_start_epoch_ms = started_wall_ms + offset * 1000.0
        tasks.append(asyncio.create_task(_dispatch_after_offset(offset, intended_start_epoch_ms)))
    request_records: list[tuple[float, float, float]] = []
    if tasks:
        remaining = max(0.0, completion_deadline - time.perf_counter())
        done, pending = await asyncio.wait(tasks, timeout=remaining)
        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None:
                raise exc
            request_records.append(task.result())
        if pending:
            for p in pending:
                p.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            print(
                f"[RQ1] Open-loop cutoff mode-tasks: lambda={lambda_rps}, "
                f"scheduled={len(tasks)}, completed={len(request_records)}, cancelled={len(pending)}"
            )
    abs_latency_ms = [record[2] for record in request_records]
    total_time = time.perf_counter() - started
    cpu_elapsed = time.process_time() - cpu_start
    cpu_util = (cpu_elapsed / total_time) * 100.0 if total_time > 0 else 0.0
    peak_rss = max(rss_start, _rss_mb())
    stop_event.set()
    await asyncio.sleep(0)
    jitters_seconds = await jitter_task
    await tick_probe_task
    return (
        total_time,
        [j * 1000.0 for j in jitters_seconds],
        len(tasks),
        cpu_util,
        peak_rss,
        abs_latency_ms,
        request_records,
        [v * 1000.0 for v in tick_probe_data],
    )


async def _run_trials() -> list[TrialResult]:
    trials: list[TrialResult] = []
    total_cells = 2 * (
        (len(CONCURRENCY_MATRIX) * (MEASURE_ROUNDS + 1))
        + (len(OPEN_LOOP_LAMBDA_MATRIX) * (MEASURE_ROUNDS + 1))
    )
    finished_cells = 0
    print(f"[RQ1] Start benchmark. Total steps={total_cells}")
    with patch(
        "lirix.integrations.autogen.tool.Lirix.validate_and_simulate",
        new=_mock_validate_and_simulate,
    ):
        for mode, worker in (("baseline", _baseline_worker), ("lirix", _lirix_worker)):
            print(f"[RQ1] Mode={mode} begin closed-loop matrix={CONCURRENCY_MATRIX}")
            for n in CONCURRENCY_MATRIX:
                print(f"[RQ1] Warmup mode={mode} scenario=closed_loop N={n}")
                await _run_closed_loop(worker, n, WARMUP_SECONDS)
                finished_cells += 1
                print(f"[RQ1] Progress {finished_cells}/{total_cells}")
                for round_id in range(MEASURE_ROUNDS):
                    print(
                        f"[RQ1] Measure mode={mode} scenario=closed_loop N={n} round={round_id + 1}/{MEASURE_ROUNDS}"
                    )
                    (
                        elapsed,
                        jitter_ms,
                        completed,
                        cpu_util,
                        peak_rss,
                        abs_latency_ms,
                        request_records,
                        event_loop_lag_ms,
                    ) = await _run_closed_loop(worker, n, MEASURE_WINDOW_SECONDS)
                    trials.append(
                        TrialResult(
                            mode=mode,
                            load_model="closed_loop_concurrency",
                            load_value=n,
                            round_id=round_id,
                            elapsed_seconds=elapsed,
                            tps=float(completed) / elapsed if elapsed > 0 else 0.0,
                            jitter_ms=jitter_ms,
                            absolute_latency_ms=abs_latency_ms,
                            request_records=request_records,
                            event_loop_lag_ms=event_loop_lag_ms,
                            cpu_util_percent=cpu_util,
                            peak_rss_mb=peak_rss,
                        )
                    )
                    finished_cells += 1
                    print(f"[RQ1] Progress {finished_cells}/{total_cells}")
            print(f"[RQ1] Mode={mode} begin open-loop matrix={OPEN_LOOP_LAMBDA_MATRIX}")
            for lam in OPEN_LOOP_LAMBDA_MATRIX:
                print(f"[RQ1] Warmup mode={mode} scenario=open_loop lambda={lam}")
                await _run_open_loop(worker, lam, WARMUP_SECONDS)
                finished_cells += 1
                print(f"[RQ1] Progress {finished_cells}/{total_cells}")
                for round_id in range(MEASURE_ROUNDS):
                    print(
                        f"[RQ1] Measure mode={mode} scenario=open_loop lambda={lam} round={round_id + 1}/{MEASURE_ROUNDS}"
                    )
                    (
                        elapsed,
                        jitter_ms,
                        completed,
                        cpu_util,
                        peak_rss,
                        abs_latency_ms,
                        request_records,
                        event_loop_lag_ms,
                    ) = await _run_open_loop(worker, lam, MEASURE_WINDOW_SECONDS)
                    trials.append(
                        TrialResult(
                            mode=mode,
                            load_model="open_loop_poisson_rps",
                            load_value=lam,
                            round_id=round_id,
                            elapsed_seconds=elapsed,
                            tps=float(completed) / elapsed if elapsed > 0 else 0.0,
                            jitter_ms=jitter_ms,
                            absolute_latency_ms=abs_latency_ms,
                            request_records=request_records,
                            event_loop_lag_ms=event_loop_lag_ms,
                            cpu_util_percent=cpu_util,
                            peak_rss_mb=peak_rss,
                        )
                    )
                    finished_cells += 1
                    print(f"[RQ1] Progress {finished_cells}/{total_cells}")
    print("[RQ1] Trial collection done")
    return trials


def _summarize_trials(trials: list[TrialResult]) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for mode in ("baseline", "lirix"):
        for n in CONCURRENCY_MATRIX:
            selected = [
                t
                for t in trials
                if t.mode == mode
                and t.load_model == "closed_loop_concurrency"
                and t.load_value == n
            ]
            rows.append(_build_summary_row(mode, n, selected))
        for lam in OPEN_LOOP_LAMBDA_MATRIX:
            selected = [
                t
                for t in trials
                if t.mode == mode
                and t.load_model == "open_loop_poisson_rps"
                and t.load_value == lam
            ]
            row = _build_summary_row(mode, lam, selected)
            row["scenario"] = "open_loop_poisson_rps"
            rows.append(row)
    return rows


def _extract_cdf_samples(trials: list[TrialResult]) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {"baseline": [], "lirix": []}
    for mode in ("baseline", "lirix"):
        selected = [
            t
            for t in trials
            if t.mode == mode
            and t.load_model == "closed_loop_concurrency"
            and t.load_value == CDF_TARGET_CONCURRENCY
        ]
        samples[mode] = [j for t in selected for j in t.jitter_ms]
    return samples


def _write_raw_csv(trials: list[TrialResult]) -> None:
    RQ1_CSV_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "intended_start_timestamp_ms",
                "actual_completion_timestamp_ms",
                "absolute_latency_ms",
                "concurrency_level_N",
                "injection_rate_lambda",
                "cpu_utilization_percent",
                "is_baseline_or_lirix",
            ],
        )
        writer.writeheader()
        for t in trials:
            for intended_ms, completion_ms, abs_ms in t.request_records:
                writer.writerow(
                    {
                        "intended_start_timestamp_ms": f"{intended_ms:.3f}",
                        "actual_completion_timestamp_ms": f"{completion_ms:.3f}",
                        "absolute_latency_ms": f"{abs_ms:.3f}",
                        "concurrency_level_N": (
                            t.load_value if t.load_model == "closed_loop_concurrency" else ""
                        ),
                        "injection_rate_lambda": (
                            t.load_value if t.load_model == "open_loop_poisson_rps" else ""
                        ),
                        "cpu_utilization_percent": f"{t.cpu_util_percent:.3f}",
                        "is_baseline_or_lirix": t.mode,
                    }
                )


def _write_summary_csv(rows: list[dict[str, float | int | str]]) -> None:
    RQ1_CSV_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "mode",
                "scenario",
                "load_value",
                "rounds",
                "jitter_samples",
                "p50_jitter_ms",
                "p90_jitter_ms",
                "p95_jitter_ms",
                "p99_jitter_ms",
                "mean_absolute_latency_ms",
                "p99_absolute_latency_ms",
                "mean_jitter_ms",
                "mean_event_loop_lag_ms",
                "p99_event_loop_lag_ms",
                "std_jitter_ms",
                "tps_mean",
                "tps_ci95",
                "elapsed_mean_s",
                "cpu_util_mean_percent",
                "cpu_util_peak_percent",
                "peak_rss_mb_max",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "mode": row["mode"],
                    "scenario": row.get("scenario", "closed_loop_concurrency"),
                    "load_value": row["load_value"],
                    "rounds": row["rounds"],
                    "jitter_samples": row["jitter_samples"],
                    "p50_jitter_ms": f"{float(row['p50_jitter_ms']):.3f}",
                    "p90_jitter_ms": f"{float(row['p90_jitter_ms']):.3f}",
                    "p95_jitter_ms": f"{float(row['p95_jitter_ms']):.3f}",
                    "p99_jitter_ms": f"{float(row['p99_jitter_ms']):.3f}",
                    "mean_absolute_latency_ms": f"{float(row['mean_absolute_latency_ms']):.3f}",
                    "p99_absolute_latency_ms": f"{float(row['p99_absolute_latency_ms']):.3f}",
                    "mean_jitter_ms": f"{float(row['mean_jitter_ms']):.3f}",
                    "mean_event_loop_lag_ms": f"{float(row['mean_event_loop_lag_ms']):.3f}",
                    "p99_event_loop_lag_ms": f"{float(row['p99_event_loop_lag_ms']):.3f}",
                    "std_jitter_ms": f"{float(row['std_jitter_ms']):.3f}",
                    "tps_mean": f"{float(row['tps_mean']):.3f}",
                    "tps_ci95": f"{float(row['tps_ci95']):.3f}",
                    "elapsed_mean_s": f"{float(row['elapsed_mean_s']):.6f}",
                    "cpu_util_mean_percent": f"{float(row['cpu_util_mean_percent']):.3f}",
                    "cpu_util_peak_percent": f"{float(row['cpu_util_peak_percent']):.3f}",
                    "peak_rss_mb_max": f"{float(row['peak_rss_mb_max']):.3f}",
                }
            )


def _write_rq1_target_csv(rows: list[dict[str, float | int | str]]) -> None:
    with RQ1_TARGET_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "mode",
                "scenario",
                "concurrency_level_N",
                "injection_rate_lambda",
                "tps_mean",
                "p99_absolute_latency_ms",
                "p99_event_loop_lag_ms",
                "cpu_util_peak",
            ],
        )
        writer.writeheader()
        for row in rows:
            scenario = str(row.get("scenario", "closed_loop_concurrency"))
            load_value = int(row["load_value"])
            writer.writerow(
                {
                    "mode": row["mode"],
                    "scenario": scenario,
                    "concurrency_level_N": (
                        load_value if scenario == "closed_loop_concurrency" else ""
                    ),
                    "injection_rate_lambda": (
                        load_value if scenario == "open_loop_poisson_rps" else ""
                    ),
                    "tps_mean": f"{float(row['tps_mean']):.3f}",
                    "p99_absolute_latency_ms": f"{float(row['p99_absolute_latency_ms']):.3f}",
                    "p99_event_loop_lag_ms": f"{float(row['p99_event_loop_lag_ms']):.3f}",
                    "cpu_util_peak": f"{float(row['cpu_util_peak_percent']):.3f}",
                }
            )


def _cdf_curve(samples_ms: list[float]) -> tuple[np.ndarray, np.ndarray]:
    if not samples_ms:
        return np.asarray([]), np.asarray([])
    sorted_ms = np.sort(np.asarray(samples_ms))
    y = np.arange(1, len(sorted_ms) + 1) / len(sorted_ms)
    return sorted_ms, y


def _ccdf_curve(samples_ms: list[float]) -> tuple[np.ndarray, np.ndarray]:
    x, cdf = _cdf_curve(samples_ms)
    if x.size == 0:
        return x, cdf
    return x, 1.0 - cdf


def _write_cdf_csv(cdf_samples: dict[str, list[float]]) -> None:
    baseline_x, baseline_y = _cdf_curve(cdf_samples["baseline"])
    lirix_x, lirix_y = _cdf_curve(cdf_samples["lirix"])
    with CDF_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["mode", "jitter_ms", "cdf"])
        writer.writeheader()
        for x, y in zip(baseline_x.tolist(), baseline_y.tolist()):
            writer.writerow({"mode": "baseline", "jitter_ms": f"{x:.6f}", "cdf": f"{y:.6f}"})
        for x, y in zip(lirix_x.tolist(), lirix_y.tolist()):
            writer.writerow({"mode": "lirix", "jitter_ms": f"{x:.6f}", "cdf": f"{y:.6f}"})


def _write_cdf_plot(cdf_samples: dict[str, list[float]]) -> None:
    baseline_x, baseline_y = _cdf_curve(cdf_samples["baseline"])
    lirix_x, lirix_y = _cdf_curve(cdf_samples["lirix"])
    plt.figure(figsize=(10, 6))
    if baseline_x.size > 0:
        plt.plot(baseline_x, baseline_y, linewidth=2.0, label="Baseline (sync in event loop)")
    if lirix_x.size > 0:
        plt.plot(lirix_x, lirix_y, linewidth=2.0, label="Lirix (asyncio.to_thread)")
    plt.xlabel("Jitter latency (ms)")
    plt.ylabel("CDF")
    plt.title(f"RQ1 Jitter CDF @ N={CDF_TARGET_CONCURRENCY}")
    plt.ylim(0.0, 1.0)
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PNG_PATH, dpi=220)
    plt.close()


def _write_ccdf_plot(cdf_samples: dict[str, list[float]]) -> None:
    baseline_x, baseline_y = _ccdf_curve(cdf_samples["baseline"])
    lirix_x, lirix_y = _ccdf_curve(cdf_samples["lirix"])
    plt.figure(figsize=(10, 6))
    if baseline_x.size > 0:
        plt.plot(baseline_x, baseline_y, linewidth=2.0, label="Baseline tail")
    if lirix_x.size > 0:
        plt.plot(lirix_x, lirix_y, linewidth=2.0, label="Lirix tail")
    plt.yscale("log")
    plt.xlabel("Jitter latency (ms)")
    plt.ylabel("CCDF (log scale)")
    plt.title(f"RQ1 Tail Risk (CCDF) @ N={CDF_TARGET_CONCURRENCY}")
    plt.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(TAIL_CCDF_PNG_PATH, dpi=220)
    plt.close()


def _trim_cold_start(samples_ms: list[float]) -> list[float]:
    if not samples_ms:
        return []
    trim = int(len(samples_ms) * COLD_START_TRIM_RATIO)
    if len(samples_ms) <= trim:
        return samples_ms
    return samples_ms[trim:]


def _extract_open_loop_abs_latency_samples(trials: list[TrialResult]) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {"baseline": [], "lirix": []}
    for mode in ("baseline", "lirix"):
        selected = [t for t in trials if t.mode == mode and t.load_model == "open_loop_poisson_rps"]
        merged = [lat for t in selected for lat in t.absolute_latency_ms]
        samples[mode] = _trim_cold_start(merged)
    return samples


def _write_absolute_latency_ccdf_pdf(trials: list[TrialResult]) -> None:
    samples = _extract_open_loop_abs_latency_samples(trials)
    plt.figure(figsize=(10, 6))
    mode_color = {"baseline": "#d62728", "lirix": "#1f77b4"}
    for mode in ("baseline", "lirix"):
        x, y = _ccdf_curve(samples[mode])
        if x.size == 0:
            continue
        ccdf_y = np.maximum(y, 1.0 / len(x))
        p95 = float(np.percentile(x, 95))
        p99 = float(np.percentile(x, 99))
        plt.plot(
            x, ccdf_y, linewidth=2.0, color=mode_color[mode], label=f"{mode.capitalize()} CCDF"
        )
        plt.axvline(
            p95,
            linestyle="--",
            linewidth=1.2,
            color=mode_color[mode],
            alpha=0.6,
            label=f"{mode.capitalize()} P95",
        )
        plt.axvline(
            p99,
            linestyle=":",
            linewidth=1.2,
            color=mode_color[mode],
            alpha=0.8,
            label=f"{mode.capitalize()} P99",
        )
    plt.xscale("log")
    plt.xlabel("Absolute Latency (ms)")
    plt.ylabel("CCDF (P[latency >= x])")
    plt.title("RQ1 Open-loop Absolute Tail Latency CCDF")
    plt.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(ABS_CCDF_PDF_PATH)
    plt.close()


def _write_throughput_vs_latency_pdf(summary_rows: list[dict[str, float | int | str]]) -> None:
    lambdas = OPEN_LOOP_LAMBDA_MATRIX
    baseline_p99 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "baseline"
                and r.get("scenario") == "open_loop_poisson_rps"
                and r["load_value"] == lam
            )["p99_absolute_latency_ms"]
        )
        for lam in lambdas
    ]
    lirix_p99 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "lirix"
                and r.get("scenario") == "open_loop_poisson_rps"
                and r["load_value"] == lam
            )["p99_absolute_latency_ms"]
        )
        for lam in lambdas
    ]
    plt.figure(figsize=(10, 6))
    plt.plot(lambdas, baseline_p99, marker="o", linewidth=2.0, color="#d62728", label="Baseline")
    plt.plot(lambdas, lirix_p99, marker="o", linewidth=2.0, color="#1f77b4", label="Lirix")
    plt.xlabel("Target Throughput (Poisson lambda, req/s)")
    plt.ylabel("P99 Latency (ms)")
    plt.title("RQ1 Saturation Knee: Throughput vs P99 Latency")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(THROUGHPUT_LATENCY_PDF_PATH)
    plt.close()


def _write_event_loop_jitter_log_pdf(summary_rows: list[dict[str, float | int | str]]) -> None:
    n_values = CONCURRENCY_MATRIX
    baseline_p99 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "baseline"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["p99_event_loop_lag_ms"]
        )
        for n in n_values
    ]
    lirix_p99 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "lirix"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["p99_event_loop_lag_ms"]
        )
        for n in n_values
    ]
    plt.figure(figsize=(10, 6))
    plt.plot(n_values, baseline_p99, marker="o", linewidth=2.2, color="#d62728", label="Baseline")
    plt.plot(n_values, lirix_p99, marker="o", linewidth=2.2, color="#1f77b4", label="Lirix")
    plt.yscale("log")
    plt.xlabel(r"Concurrency Level $N$")
    plt.ylabel("p99_event_loop_lag_ms (log scale)")
    plt.title("RQ1 Event-loop Heartbeat Lag: Baseline vs Lirix")
    plt.grid(True, which="both", linestyle="--", linewidth=0.7, alpha=0.8)
    plt.legend()
    plt.tight_layout()
    plt.savefig(EVENT_LOOP_JITTER_LOG_PDF_PATH)
    plt.close()


def _write_tps_vs_tail_latency_pdf(summary_rows: list[dict[str, float | int | str]]) -> None:
    plt.figure(figsize=(10, 6))
    mode_color = {"baseline": "#d62728", "lirix": "#1f77b4"}
    scenario_marker = {"closed_loop_concurrency": "o", "open_loop_poisson_rps": "s"}
    for mode in ("baseline", "lirix"):
        for scenario in ("closed_loop_concurrency", "open_loop_poisson_rps"):
            selected = [
                r
                for r in summary_rows
                if r["mode"] == mode and r.get("scenario", "closed_loop_concurrency") == scenario
            ]
            if not selected:
                continue
            x = [float(r["tps_mean"]) for r in selected]
            y = [float(r["p99_absolute_latency_ms"]) for r in selected]
            labels = [int(r["load_value"]) for r in selected]
            plt.scatter(
                x,
                y,
                s=75,
                marker=scenario_marker[scenario],
                color=mode_color[mode],
                alpha=0.85,
                label=f"{mode.capitalize()} / {scenario.replace('_', '-')}",
            )
            for xx, yy, ll in zip(x, y, labels):
                plt.annotate(
                    str(ll), (xx, yy), textcoords="offset points", xytext=(4, 4), fontsize=8
                )
    plt.xlabel("TPS (Throughput)")
    plt.ylabel("p99_absolute_latency_ms")
    plt.title("RQ1 Throughput vs Absolute Tail Latency")
    plt.grid(True, linestyle="--", linewidth=0.7, alpha=0.8)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.savefig(TPS_VS_TAIL_LATENCY_PDF_PATH)
    plt.close()


def _write_percentile_plot(summary_rows: list[dict[str, float | int | str]]) -> None:
    n_values = CONCURRENCY_MATRIX
    baseline_p95 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "baseline"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["p95_jitter_ms"]
        )
        for n in n_values
    ]
    lirix_p95 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "lirix"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["p95_jitter_ms"]
        )
        for n in n_values
    ]
    baseline_p99 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "baseline"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["p99_jitter_ms"]
        )
        for n in n_values
    ]
    lirix_p99 = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "lirix"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["p99_jitter_ms"]
        )
        for n in n_values
    ]
    plt.figure(figsize=(10, 6))
    plt.plot(n_values, baseline_p95, marker="o", label="Baseline p95")
    plt.plot(n_values, lirix_p95, marker="o", label="Lirix p95")
    plt.plot(n_values, baseline_p99, marker="x", linestyle="--", label="Baseline p99")
    plt.plot(n_values, lirix_p99, marker="x", linestyle="--", label="Lirix p99")
    plt.yscale("log")
    plt.xlabel("Concurrency N")
    plt.ylabel("Jitter (ms, log scale)")
    plt.title("RQ1 Jitter Percentiles Across Concurrency")
    plt.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PCTL_PNG_PATH, dpi=220)
    plt.close()


def _write_tps_plot(summary_rows: list[dict[str, float | int | str]]) -> None:
    n_values = CONCURRENCY_MATRIX
    baseline_mean = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "baseline"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["tps_mean"]
        )
        for n in n_values
    ]
    lirix_mean = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "lirix"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["tps_mean"]
        )
        for n in n_values
    ]
    baseline_ci = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "baseline"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["tps_ci95"]
        )
        for n in n_values
    ]
    lirix_ci = [
        float(
            next(
                r
                for r in summary_rows
                if r["mode"] == "lirix"
                and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
                and r["load_value"] == n
            )["tps_ci95"]
        )
        for n in n_values
    ]
    plt.figure(figsize=(10, 6))
    plt.errorbar(
        n_values,
        baseline_mean,
        yerr=baseline_ci,
        marker="o",
        capsize=4,
        label="Baseline TPS (95% CI)",
    )
    plt.errorbar(
        n_values, lirix_mean, yerr=lirix_ci, marker="o", capsize=4, label="Lirix TPS (95% CI)"
    )
    plt.xlabel("Concurrency N")
    plt.ylabel("Throughput (TPS)")
    plt.title("RQ1 Throughput Scaling with 95% Confidence Interval")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(TPS_PNG_PATH, dpi=220)
    plt.close()


def _write_boxplot_n200(trials: list[TrialResult]) -> None:
    baseline = [
        j
        for t in trials
        if t.mode == "baseline"
        and t.load_model == "closed_loop_concurrency"
        and t.load_value == CDF_TARGET_CONCURRENCY
        for j in t.jitter_ms
    ]
    lirix = [
        j
        for t in trials
        if t.mode == "lirix"
        and t.load_model == "closed_loop_concurrency"
        and t.load_value == CDF_TARGET_CONCURRENCY
        for j in t.jitter_ms
    ]
    plt.figure(figsize=(8, 6))
    plt.boxplot([baseline, lirix], tick_labels=["Baseline", "Lirix"], showfliers=True, whis=(5, 95))
    plt.yscale("log")
    plt.ylabel("Jitter (ms, log scale)")
    plt.title(f"RQ1 Jitter Distribution Boxplot @ N={CDF_TARGET_CONCURRENCY}")
    plt.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.tight_layout()
    plt.savefig(BOXPLOT_PNG_PATH, dpi=220)
    plt.close()


def _speedup_line(summary_rows: list[dict[str, float | int | str]], n: int) -> str:
    b = next(
        r
        for r in summary_rows
        if r["mode"] == "baseline"
        and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
        and r["load_value"] == n
    )
    l = next(
        r
        for r in summary_rows
        if r["mode"] == "lirix"
        and r.get("scenario", "closed_loop_concurrency") == "closed_loop_concurrency"
        and r["load_value"] == n
    )
    b_p99 = float(b["p99_jitter_ms"])
    l_p99 = float(l["p99_jitter_ms"])
    b_tps = float(b["tps_mean"])
    l_tps = float(l["tps_mean"])
    jitter_gain = (b_p99 / l_p99) if l_p99 > 0 else float("inf")
    tps_gain = (l_tps / b_tps) if b_tps > 0 else float("inf")
    return (
        f"- N={n}: p99 jitter baseline={b_p99:.3f} ms, lirix={l_p99:.3f} ms, "
        f"reduction={jitter_gain:.2f}x; TPS baseline={b_tps:.2f}, lirix={l_tps:.2f}, gain={tps_gain:.2f}x"
    )


def _write_report(summary_rows: list[dict[str, float | int | str]]) -> None:
    lines = [
        "# RQ1 Async Gateway Benchmark (IEEE-style Artifact)",
        "",
        "## Experiment Setup",
        f"- UTC timestamp: {datetime.now(timezone.utc).isoformat()}",
        f"- Python: {platform.python_version()}",
        f"- Platform: {platform.platform()}",
        f"- Concurrency matrix: {CONCURRENCY_MATRIX}",
        f"- Open-loop Poisson lambda matrix (rps): {OPEN_LOOP_LAMBDA_MATRIX}",
        f"- Warmup seconds per cell: {WARMUP_SECONDS}",
        f"- Measurement window per round: {MEASURE_WINDOW_SECONDS} s",
        f"- Measurement rounds per cell: {MEASURE_ROUNDS}",
        f"- Heartbeat period: {HEARTBEAT_INTERVAL_SECONDS * 1000:.1f} ms",
        f"- Cold-start trim ratio (jitter): {COLD_START_TRIM_RATIO:.0%}",
        f"- Minimum heartbeat samples per summary cell: {MIN_HEARTBEAT_SAMPLES}",
        "- Open-loop latency is measured as completion_time - intended_start_time to reduce coordinated-omission bias.",
        "- Blocking payload: `time.sleep(0.05) + sum(i*i for i in range(20000))`",
        "",
        "## Key Results",
        _speedup_line(summary_rows, 200),
        _speedup_line(summary_rows, 500),
        "",
        "## Generated Artifacts",
        f"- `{CSV_PATH.name}`: aggregated summary (percentiles, TPS mean, 95% CI)",
        f"- `{RQ1_TARGET_CSV_PATH.name}`: final RQ1 target metrics",
        f"- `{RAW_CSV_PATH.name}`: per-round raw metrics",
        f"- `{CDF_CSV_PATH.name}`: CDF points at N=200",
        f"- `{PNG_PATH.name}`: jitter CDF at N=200",
        f"- `{TAIL_CCDF_PNG_PATH.name}`: tail-risk CCDF at N=200",
        f"- `{ABS_CCDF_PDF_PATH.name}`: open-loop absolute latency CCDF (x-axis log scale, with P95/P99 markers)",
        f"- `{THROUGHPUT_LATENCY_PDF_PATH.name}`: saturation knee curve (lambda vs P99 absolute latency)",
        f"- `{EVENT_LOOP_JITTER_LOG_PDF_PATH.name}`: p99 event-loop lag vs concurrency (log-y)",
        f"- `{TPS_VS_TAIL_LATENCY_PDF_PATH.name}`: TPS vs P99 absolute latency scatter",
        f"- `{PCTL_PNG_PATH.name}`: p95/p99 jitter vs concurrency",
        f"- `{TPS_PNG_PATH.name}`: TPS scaling with 95% CI",
        f"- `{BOXPLOT_PNG_PATH.name}`: jitter boxplot at N=200",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_rq1_benchmark() -> list[dict[str, float | int | str]]:
    print("[RQ1] Running benchmark pipeline ...")
    trials = asyncio.run(_run_trials())
    print("[RQ1] Summarizing trials ...")
    summary_rows = _summarize_trials(trials)
    cdf_samples = _extract_cdf_samples(trials)
    print("[RQ1] Writing artifacts ...")
    RQ1_PNG_DIR.mkdir(parents=True, exist_ok=True)
    RQ1_PDF_DIR.mkdir(parents=True, exist_ok=True)
    _write_raw_csv(trials)
    _write_summary_csv(summary_rows)
    _write_rq1_target_csv(summary_rows)
    _write_cdf_csv(cdf_samples)
    _write_cdf_plot(cdf_samples)
    _write_ccdf_plot(cdf_samples)
    _write_absolute_latency_ccdf_pdf(trials)
    _write_throughput_vs_latency_pdf(summary_rows)
    _write_event_loop_jitter_log_pdf(summary_rows)
    _write_tps_vs_tail_latency_pdf(summary_rows)
    _write_percentile_plot(summary_rows)
    _write_tps_plot(summary_rows)
    _write_boxplot_n200(trials)
    _write_report(summary_rows)
    archive_artifacts(
        ArtifactFamily(name="rq1", output_dir=RUN_ROOT),
        relpaths_under(
            RUN_ROOT,
            [
                CSV_PATH,
                RQ1_TARGET_CSV_PATH,
                RAW_CSV_PATH,
                CDF_CSV_PATH,
                PNG_PATH,
                TAIL_CCDF_PNG_PATH,
                ABS_CCDF_PDF_PATH,
                THROUGHPUT_LATENCY_PDF_PATH,
                EVENT_LOOP_JITTER_LOG_PDF_PATH,
                TPS_VS_TAIL_LATENCY_PDF_PATH,
                PCTL_PNG_PATH,
                TPS_PNG_PATH,
                BOXPLOT_PNG_PATH,
                REPORT_PATH,
            ],
        ),
    )
    print("[RQ1] Benchmark finished")
    return summary_rows


def test_rq1_async_gateway_benchmark() -> None:
    if os.getenv("RUN_RQ1_BENCHMARK") != "1":
        return
    rows = run_rq1_benchmark()
    assert len(rows) == len(CONCURRENCY_MATRIX) * 2
    assert CSV_PATH.exists()
    assert RAW_CSV_PATH.exists()
    assert CDF_CSV_PATH.exists()
    assert PNG_PATH.exists()
    assert TAIL_CCDF_PNG_PATH.exists()
    assert ABS_CCDF_PDF_PATH.exists()
    assert THROUGHPUT_LATENCY_PDF_PATH.exists()
    assert PCTL_PNG_PATH.exists()
    assert TPS_PNG_PATH.exists()
    assert BOXPLOT_PNG_PATH.exists()
    assert REPORT_PATH.exists()


if __name__ == "__main__":
    run_rq1_benchmark()
