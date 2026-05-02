from __future__ import annotations

# ruff: noqa: E402,E501
# mypy: ignore-errors
import random

GLOBAL_RANDOM_SEED = 20260501
random.seed(GLOBAL_RANDOM_SEED)

import asyncio
import csv
import os
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import matplotlib
import numpy as np
from eth_abi import encode
from lirix.core.exceptions import LirixStateAssertionError
from lirix.layers.l2_schema_validator import AssertionSchema
from lirix.shield.simulator import StateDeltaValidator

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = Path(__file__).resolve().parent
SUMMARY_CSV_PATH = OUTPUT_DIR / "rq2_assertions.csv"
CATEGORY_CSV_PATH = OUTPUT_DIR / "rq2_category_breakdown.csv"
SWEEP_CSV_PATH = OUTPUT_DIR / "rq2_bilateral_band_sweep.csv"
PROFILE_COMPARISON_CSV_PATH = OUTPUT_DIR / "rq2_profile_comparison.csv"
MAIN_PNG_PATH = OUTPUT_DIR / "rq2_interception_rates.png"
CATEGORY_PNG_PATH = OUTPUT_DIR / "rq2_interception_by_category.png"
SWEEP_PNG_PATH = OUTPUT_DIR / "rq2_band_tradeoff_curve.png"
PROFILE_PNG_PATH = OUTPUT_DIR / "rq2_profile_comparison.png"
REPORT_PATH = OUTPUT_DIR / "rq2_ieee_report.md"
PR_CURVE_PNG_PATH = OUTPUT_DIR / "rq2_pr_curve_imbalanced.png"
VOLATILITY_CSV_PATH = OUTPUT_DIR / "rq2_volatility_sensitivity.csv"
VOLATILITY_PNG_PATH = OUTPUT_DIR / "rq2_volatility_sensitivity.png"
RQ2_REQUIRED_CSV_PATH = OUTPUT_DIR / "rq2_assertion_strategy_efficacy.csv"
RQ2_REQUIRED_PR_PDF_PATH = OUTPUT_DIR / "rq2_pr_curve_imbalanced.pdf"
RQ2_REQUIRED_VOL_MCC_PDF_PATH = OUTPUT_DIR / "volatility_vs_mcc.pdf"

EXPECTED_VALUE = 1000
SAMPLES_PER_SEED = 24_000
SEEDS = [20260430, 20260501, 20260502, 20260503, 20260504]
ATTACK_PRIOR = 0.01
MARKET_VOLATILITY_SIGMA = [0.001, 0.005, 0.01, 0.03, 0.05]


@dataclass(frozen=True)
class Sample:
    category: str
    expected_value: int
    actual_value: int
    return_value: int
    is_attack: bool

    @property
    def return_data(self) -> str:
        return "0x" + encode(["uint256"], [self.return_value]).hex()


@dataclass(frozen=True)
class Strategy:
    name: str
    assertions: list[AssertionSchema]


EVAL_PROFILES: dict[str, dict[str, set[str]]] = {
    "strict_security": {
        "attack_categories": {
            "benign_slippage",
            "honeypot_hard",
            "honeypot_soft",
            "inflation_soft",
            "inflation_hard",
            "near_boundary_low",
            "near_boundary_high",
        },
        "normal_categories": {"clean_exact"},
    },
    "execution_tolerant": {
        "attack_categories": {
            "honeypot_hard",
            "honeypot_soft",
            "inflation_soft",
            "inflation_hard",
            "near_boundary_low",
            "near_boundary_high",
        },
        "normal_categories": {"clean_exact", "benign_slippage"},
    },
}


def _build_samples(seed: int, market_sigma: float = 0.001) -> list[Sample]:
    rng = random.Random(seed)
    n = SAMPLES_PER_SEED // 8
    out: list[Sample] = []
    sigma_abs = max(1.0, EXPECTED_VALUE * market_sigma)
    benign_low = max(0, int(round(EXPECTED_VALUE - 2.0 * sigma_abs)))
    benign_high = int(round(EXPECTED_VALUE + 2.0 * sigma_abs))
    out.extend(
        Sample("clean_exact", EXPECTED_VALUE, EXPECTED_VALUE, EXPECTED_VALUE, False)
        for _ in range(n)
    )
    for _ in range(n):
        value = rng.randint(benign_low, benign_high)
        out.append(Sample("benign_slippage", EXPECTED_VALUE, value, value, False))
    for _ in range(n):
        value = rng.randint(0, 20)
        out.append(Sample("honeypot_hard", EXPECTED_VALUE, value, value, True))
    for _ in range(n):
        value = rng.randint(980, 998)
        out.append(Sample("honeypot_soft", EXPECTED_VALUE, value, value, True))
    for _ in range(n):
        value = rng.randint(1002, 1020)
        out.append(Sample("inflation_soft", EXPECTED_VALUE, value, value, True))
    for _ in range(n):
        value = rng.randint(1021, 5000)
        out.append(Sample("inflation_hard", EXPECTED_VALUE, value, value, True))
    out.extend(Sample("near_boundary_low", EXPECTED_VALUE, 999, 999, True) for _ in range(n))
    out.extend(Sample("near_boundary_high", EXPECTED_VALUE, 1001, 1001, True) for _ in range(n))
    rng.shuffle(out)
    return out


def _wilson_interval(success: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = success / total
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    margin = (z * ((p * (1.0 - p) / total + (z * z) / (4.0 * total * total)) ** 0.5)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _is_attack_by_profile(sample: Sample, profile_name: str) -> bool:
    profile = EVAL_PROFILES[profile_name]
    if sample.category in profile["attack_categories"]:
        return True
    if sample.category in profile["normal_categories"]:
        return False
    raise ValueError(f"Unknown category for profile={profile_name}: {sample.category}")


async def _evaluate_strategy(
    strategy: Strategy, samples: list[Sample], profile_name: str
) -> dict[str, Any]:
    validator = StateDeltaValidator(AsyncMock())
    payload = {"assertions": strategy.assertions}
    tp = tn = fp = fn = 0
    detected_deviations: list[float] = []
    by_category: dict[str, dict[str, int]] = {}
    for sample in samples:
        blocked = False
        try:
            await validator.validate(payload, simulation_result={"return_data": sample.return_data})
        except LirixStateAssertionError:
            blocked = True
        is_attack = _is_attack_by_profile(sample, profile_name)
        bucket = by_category.setdefault(
            sample.category, {"blocked": 0, "total": 0, "attack_total": 0}
        )
        bucket["total"] += 1
        bucket["attack_total"] += 1 if is_attack else 0
        bucket["blocked"] += 1 if blocked else 0
        if is_attack and blocked:
            tp += 1
            detected_deviations.append(float(abs(sample.actual_value - sample.expected_value)))
        elif is_attack and not blocked:
            fn += 1
        elif (not is_attack) and blocked:
            fp += 1
        else:
            tn += 1
    total_attack = tp + fn
    total_normal = tn + fp
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / total_attack) if total_attack else 0.0
    specificity = (tn / total_normal) if total_normal else 0.0
    fpr = (fp / total_normal) if total_normal else 0.0
    fnr = (fn / total_attack) if total_attack else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    mcc_denom = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    mcc = ((tp * tn - fp * fn) / mcc_denom) if mcc_denom else 0.0
    tpr_low, tpr_high = _wilson_interval(tp, total_attack)
    fpr_low, fpr_high = _wilson_interval(fp, total_normal)
    avg_detected_deviation = float(np.mean(detected_deviations)) if detected_deviations else 0.0
    min_detected_deviation = float(min(detected_deviations)) if detected_deviations else 0.0
    return {
        "strategy": strategy.name,
        "profile": profile_name,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "total_attack": total_attack,
        "total_normal": total_normal,
        "tpr": recall,
        "fpr": fpr,
        "fnr": fnr,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "balanced_accuracy": (recall + specificity) / 2.0,
        "mcc": mcc,
        "tpr_ci_low": tpr_low,
        "tpr_ci_high": tpr_high,
        "fpr_ci_low": fpr_low,
        "fpr_ci_high": fpr_high,
        "avg_detected_deviation": avg_detected_deviation,
        "min_detected_deviation": min_detected_deviation,
        "category": by_category,
    }


def _strategies() -> list[Strategy]:
    return [
        Strategy(
            "one_sided_ge_990",
            [AssertionSchema(assertion_type="return_data_int_ge", expected_value=990)],
        ),
        Strategy(
            "exact_1000",
            [AssertionSchema(assertion_type="return_data_exact", expected_value=EXPECTED_VALUE)],
        ),
        Strategy(
            "bilateral_995_1005",
            [
                AssertionSchema(assertion_type="return_data_int_ge", expected_value=995),
                AssertionSchema(assertion_type="return_data_int_le", expected_value=1005),
            ],
        ),
        Strategy(
            "bilateral_zero_tolerance_1000",
            [
                AssertionSchema(assertion_type="return_data_int_ge", expected_value=1000),
                AssertionSchema(assertion_type="return_data_int_le", expected_value=1000),
            ],
        ),
    ]


def _write_summary(rows: list[dict[str, Any]]) -> None:
    with SUMMARY_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "strategy",
                "profile",
                "tp",
                "tn",
                "fp",
                "fn",
                "total_attack",
                "total_normal",
                "tpr",
                "fpr",
                "fnr",
                "specificity",
                "precision",
                "f1",
                "balanced_accuracy",
                "mcc",
                "tpr_ci_low",
                "tpr_ci_high",
                "fpr_ci_low",
                "fpr_ci_high",
                "avg_detected_deviation",
                "min_detected_deviation",
            ],
        )
        writer.writeheader()
        for row in rows:
            out = {k: row[k] for k in writer.fieldnames}
            for key in (
                "tpr",
                "fpr",
                "fnr",
                "specificity",
                "precision",
                "f1",
                "balanced_accuracy",
                "mcc",
                "tpr_ci_low",
                "tpr_ci_high",
                "fpr_ci_low",
                "fpr_ci_high",
                "avg_detected_deviation",
                "min_detected_deviation",
            ):
                out[key] = f"{float(out[key]):.6f}"
            writer.writerow(out)


def _write_category_breakdown(rows: list[dict[str, Any]]) -> None:
    categories = sorted({k for row in rows for k in row["category"]})
    with CATEGORY_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["profile", "strategy", "category", "blocked", "total", "interception_rate"],
        )
        writer.writeheader()
        for row in rows:
            for c in categories:
                v = row["category"].get(c, {"blocked": 0, "total": 0})
                rate = (v["blocked"] / v["total"]) if v["total"] else 0.0
                writer.writerow(
                    {
                        "strategy": row["strategy"],
                        "profile": row["profile"],
                        "category": c,
                        "blocked": v["blocked"],
                        "total": v["total"],
                        "interception_rate": f"{rate:.6f}",
                    }
                )


def _write_main_plot(rows: list[dict[str, Any]]) -> None:
    plot_rows = [r for r in rows if r["profile"] == "strict_security"]
    labels = [r["strategy"] for r in plot_rows]
    tpr = [r["tpr"] for r in plot_rows]
    fpr = [r["fpr"] for r in plot_rows]
    tpr_err = [max(r["tpr"] - r["tpr_ci_low"], r["tpr_ci_high"] - r["tpr"]) for r in plot_rows]
    fpr_err = [max(r["fpr"] - r["fpr_ci_low"], r["fpr_ci_high"] - r["fpr"]) for r in plot_rows]
    x = np.arange(len(labels))
    width = 0.36
    plt.figure(figsize=(10, 6))
    plt.bar(x - width / 2, tpr, yerr=tpr_err, capsize=4, width=width, label="TPR / Interception")
    plt.bar(
        x + width / 2, fpr, yerr=fpr_err, capsize=4, width=width, label="FPR / Collateral Block"
    )
    plt.ylim(0.0, 1.05)
    plt.ylabel("Rate")
    plt.xticks(x, labels, rotation=10)
    plt.title("RQ2 Strict-Security Profile: Interception vs False Positive (95% Wilson CI)")
    plt.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(MAIN_PNG_PATH, dpi=220)
    plt.close()


def _write_category_plot(rows: list[dict[str, Any]]) -> None:
    plot_rows = [r for r in rows if r["profile"] == "strict_security"]
    strategy_names = [r["strategy"] for r in plot_rows]
    categories = sorted({k for row in plot_rows for k in row["category"]})
    data = np.zeros((len(strategy_names), len(categories)), dtype=float)
    for i, row in enumerate(plot_rows):
        for j, c in enumerate(categories):
            v = row["category"].get(c, {"blocked": 0, "total": 0})
            data[i, j] = (v["blocked"] / v["total"]) if v["total"] else 0.0
    plt.figure(figsize=(12, 4.6))
    im = plt.imshow(data, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    plt.xticks(np.arange(len(categories)), categories, rotation=25, ha="right")
    plt.yticks(np.arange(len(strategy_names)), strategy_names)
    plt.title("RQ2 Strict-Security Category-Level Interception Matrix")
    plt.colorbar(im, label="Interception rate")
    plt.tight_layout()
    plt.savefig(CATEGORY_PNG_PATH, dpi=220)
    plt.close()


def _write_band_sweep(seed: int) -> list[dict[str, Any]]:
    samples = _build_samples(seed)
    rows: list[dict[str, Any]] = []
    for eps in range(0, 21):
        strategy = Strategy(
            name=f"band_{EXPECTED_VALUE - eps}_{EXPECTED_VALUE + eps}",
            assertions=[
                AssertionSchema(
                    assertion_type="return_data_int_ge", expected_value=EXPECTED_VALUE - eps
                ),
                AssertionSchema(
                    assertion_type="return_data_int_le", expected_value=EXPECTED_VALUE + eps
                ),
            ],
        )
        for profile_name in EVAL_PROFILES:
            result = asyncio.run(_evaluate_strategy(strategy, samples, profile_name=profile_name))
            rows.append(
                {
                    "profile": profile_name,
                    "epsilon": eps,
                    "tpr": result["tpr"],
                    "fpr": result["fpr"],
                    "mcc": result["mcc"],
                }
            )
    with SWEEP_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["profile", "epsilon", "tpr", "fpr", "mcc"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "profile": row["profile"],
                    "epsilon": row["epsilon"],
                    "tpr": f"{row['tpr']:.6f}",
                    "fpr": f"{row['fpr']:.6f}",
                    "mcc": f"{row['mcc']:.6f}",
                }
            )
    plt.figure(figsize=(9, 5))
    strict_rows = [r for r in rows if r["profile"] == "strict_security"]
    tolerant_rows = [r for r in rows if r["profile"] == "execution_tolerant"]
    x = [r["epsilon"] for r in strict_rows]
    plt.plot(x, [r["tpr"] for r in strict_rows], marker="o", label="TPR (strict)")
    plt.plot(x, [r["fpr"] for r in strict_rows], marker="x", label="FPR (strict)")
    plt.plot(x, [r["mcc"] for r in strict_rows], marker="s", label="MCC (strict)")
    plt.plot(
        x, [r["tpr"] for r in tolerant_rows], marker="o", linestyle="--", label="TPR (tolerant)"
    )
    plt.plot(
        x, [r["fpr"] for r in tolerant_rows], marker="x", linestyle="--", label="FPR (tolerant)"
    )
    plt.xlabel("Bilateral tolerance epsilon")
    plt.ylabel("Metric")
    plt.title("RQ2 Bilateral Assertion Trade-off Curve (Dual Labeling Profiles)")
    plt.ylim(-0.05, 1.05)
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(SWEEP_PNG_PATH, dpi=220)
    plt.close()
    return rows


def _precision_under_prior(tpr: float, fpr: float, attack_prior: float) -> float:
    denom = tpr * attack_prior + fpr * (1.0 - attack_prior)
    if denom <= 0:
        return 1.0
    return (tpr * attack_prior) / denom


def _auprc_from_points(points: list[tuple[float, float]]) -> float:
    if not points:
        return 0.0
    pts = sorted(points, key=lambda x: x[1])  # by recall
    area = 0.0
    prev_recall = 0.0
    prev_precision = pts[0][0]
    for precision, recall in pts:
        dr = max(0.0, recall - prev_recall)
        area += dr * ((prev_precision + precision) / 2.0)
        prev_recall = recall
        prev_precision = precision
    if prev_recall < 1.0:
        area += (1.0 - prev_recall) * prev_precision
    return area


def _write_imbalanced_pr_artifact(
    sweep_rows: list[dict[str, Any]], attack_prior: float
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    plt.figure(figsize=(9, 5))
    for profile_name, linestyle in (("strict_security", "-"), ("execution_tolerant", "--")):
        subset = [r for r in sweep_rows if r["profile"] == profile_name]
        curve: list[tuple[float, float]] = []
        for row in subset:
            recall = float(row["tpr"])
            fpr = float(row["fpr"])
            precision = _precision_under_prior(recall, fpr, attack_prior)
            curve.append((precision, recall))
            out.append(
                {
                    "profile": profile_name,
                    "epsilon": row["epsilon"],
                    "recall": recall,
                    "precision_prior_1pct": precision,
                }
            )
        auprc = _auprc_from_points(curve)
        x = [r for _, r in curve]
        y = [p for p, _ in curve]
        plt.plot(
            x, y, marker="o", linestyle=linestyle, label=f"PR ({profile_name}), AUPRC={auprc:.4f}"
        )
        out.append(
            {
                "profile": profile_name,
                "epsilon": "AUPRC",
                "recall": 1.0,
                "precision_prior_1pct": auprc,
            }
        )
    plt.xlabel("Recall (TPR)")
    plt.ylabel("Precision (Attack prior=1%)")
    plt.ylim(0.0, 1.05)
    plt.title("RQ2 PR Curve under Imbalanced Prior")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PR_CURVE_PNG_PATH, dpi=220)
    plt.close()
    return out


def _write_volatility_sensitivity() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sigma in MARKET_VOLATILITY_SIGMA:
        sample = _build_samples(SEEDS[0], market_sigma=sigma)
        for profile_name in EVAL_PROFILES:
            for strategy in _strategies():
                result = asyncio.run(
                    _evaluate_strategy(strategy, sample, profile_name=profile_name)
                )
                rows.append(
                    {
                        "sigma": sigma,
                        "profile": profile_name,
                        "strategy": strategy.name,
                        "tpr": result["tpr"],
                        "fpr": result["fpr"],
                        "precision_prior_1pct": _precision_under_prior(
                            result["tpr"], result["fpr"], ATTACK_PRIOR
                        ),
                    }
                )
    with VOLATILITY_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["sigma", "profile", "strategy", "tpr", "fpr", "precision_prior_1pct"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sigma": f"{row['sigma']:.6f}",
                    "profile": row["profile"],
                    "strategy": row["strategy"],
                    "tpr": f"{row['tpr']:.6f}",
                    "fpr": f"{row['fpr']:.6f}",
                    "precision_prior_1pct": f"{row['precision_prior_1pct']:.6f}",
                }
            )
    plt.figure(figsize=(10, 6))
    focus = [r for r in rows if r["profile"] == "execution_tolerant"]
    for strategy in [s.name for s in _strategies()]:
        series = sorted([r for r in focus if r["strategy"] == strategy], key=lambda x: x["sigma"])
        plt.plot(
            [r["sigma"] for r in series],
            [r["fpr"] for r in series],
            marker="o",
            label=f"{strategy} FPR",
        )
    plt.xlabel("Market volatility sigma")
    plt.ylabel("False Positive Rate")
    plt.title("RQ2 Volatility Sensitivity (Execution-Tolerant Profile)")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(VOLATILITY_PNG_PATH, dpi=220)
    plt.close()
    return rows


def _build_required_rq2_rows(volatility_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tolerant_focus = [r for r in volatility_rows if r["profile"] == "execution_tolerant"]
    attack_prior = ATTACK_PRIOR
    normal_prior = 1.0 - attack_prior
    synthetic_total = 10000.0
    for row in tolerant_focus:
        tpr = float(row["tpr"])
        fpr = float(row["fpr"])
        fnr = max(0.0, 1.0 - tpr)
        tnr = max(0.0, 1.0 - fpr)
        tp = tpr * attack_prior * synthetic_total
        fn = fnr * attack_prior * synthetic_total
        fp = fpr * normal_prior * synthetic_total
        tn = tnr * normal_prior * synthetic_total
        precision = _precision_under_prior(tpr, fpr, attack_prior)
        recall = tpr
        mcc_denom = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
        mcc = ((tp * tn - fp * fn) / mcc_denom) if mcc_denom else 0.0
        rows.append(
            {
                "market_volatility_sigma": float(row["sigma"]),
                "assertion_strategy": row["strategy"],
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn,
                "precision": precision,
                "recall": recall,
                "fpr": fpr,
                "auprc": 0.0,
                "mcc": mcc,
            }
        )
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_strategy.setdefault(str(row["assertion_strategy"]), []).append(row)
    for _, strategy_rows in by_strategy.items():
        points = [(float(r["precision"]), float(r["recall"])) for r in strategy_rows]
        auprc = _auprc_from_points(points)
        for r in strategy_rows:
            r["auprc"] = auprc
    return rows


def _write_required_rq2_csv(rows: list[dict[str, Any]]) -> None:
    sorted_rows = sorted(
        rows, key=lambda x: (x["assertion_strategy"], x["market_volatility_sigma"])
    )
    with RQ2_REQUIRED_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "market_volatility_sigma",
                "assertion_strategy",
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
                "precision",
                "recall",
                "fpr",
                "auprc",
                "mcc",
            ],
        )
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(
                {
                    "market_volatility_sigma": f"{float(row['market_volatility_sigma']):.6f}",
                    "assertion_strategy": row["assertion_strategy"],
                    "true_positive": f"{float(row['true_positive']):.6f}",
                    "false_positive": f"{float(row['false_positive']):.6f}",
                    "true_negative": f"{float(row['true_negative']):.6f}",
                    "false_negative": f"{float(row['false_negative']):.6f}",
                    "precision": f"{float(row['precision']):.6f}",
                    "recall": f"{float(row['recall']):.6f}",
                    "fpr": f"{float(row['fpr']):.6f}",
                    "auprc": f"{float(row['auprc']):.6f}",
                    "mcc": f"{float(row['mcc']):.6f}",
                }
            )


def _write_required_pr_curve_pdf(rows: list[dict[str, Any]]) -> None:
    plt.figure(figsize=(9.5, 6))
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_strategy.setdefault(str(row["assertion_strategy"]), []).append(row)
    for strategy, strategy_rows in sorted(by_strategy.items()):
        series = sorted(strategy_rows, key=lambda x: x["recall"])
        x = [float(r["recall"]) for r in series]
        y = [float(r["precision"]) for r in series]
        auprc = float(series[0]["auprc"]) if series else 0.0
        plt.plot(x, y, marker="o", linewidth=1.8, label=f"{strategy} (AUPRC={auprc:.4f})")
    plt.xlabel("Recall (TPR)")
    plt.ylabel("Precision")
    plt.ylim(0.0, 1.05)
    plt.xlim(0.0, 1.02)
    plt.title("RQ2 PR Curve under 1% Attack Prior (Imbalanced Regime)")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.savefig(RQ2_REQUIRED_PR_PDF_PATH)
    plt.close()


def _write_required_volatility_vs_mcc_pdf(rows: list[dict[str, Any]]) -> None:
    plt.figure(figsize=(9.5, 6))
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_strategy.setdefault(str(row["assertion_strategy"]), []).append(row)
    for strategy, strategy_rows in sorted(by_strategy.items()):
        series = sorted(strategy_rows, key=lambda x: x["market_volatility_sigma"])
        x = [float(r["market_volatility_sigma"]) for r in series]
        y = [float(r["mcc"]) for r in series]
        plt.plot(x, y, marker="o", linewidth=1.9, label=strategy)
    plt.axhline(0.0, color="black", linewidth=1.0, linestyle=":")
    plt.xlabel("Market Volatility ($\\sigma$)")
    plt.ylabel("MCC Score")
    plt.ylim(-1.0, 1.0)
    plt.title("RQ2 Volatility Survival Surface: Assertion Strategy vs MCC")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend(loc="best", fontsize=9)
    plt.tight_layout()
    plt.savefig(RQ2_REQUIRED_VOL_MCC_PDF_PATH)
    plt.close()


def _write_profile_comparison(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_strategy: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_strategy.setdefault(row["strategy"], {})[row["profile"]] = row
    for strategy, profile_rows in by_strategy.items():
        strict = profile_rows.get("strict_security")
        tolerant = profile_rows.get("execution_tolerant")
        if not strict or not tolerant:
            continue
        out.append(
            {
                "strategy": strategy,
                "strict_tpr": strict["tpr"],
                "strict_fpr": strict["fpr"],
                "strict_mcc": strict["mcc"],
                "tolerant_tpr": tolerant["tpr"],
                "tolerant_fpr": tolerant["fpr"],
                "tolerant_mcc": tolerant["mcc"],
                "fpr_gap": tolerant["fpr"] - strict["fpr"],
            }
        )
    with PROFILE_COMPARISON_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "strategy",
                "strict_tpr",
                "strict_fpr",
                "strict_mcc",
                "tolerant_tpr",
                "tolerant_fpr",
                "tolerant_mcc",
                "fpr_gap",
            ],
        )
        writer.writeheader()
        for row in out:
            writer.writerow(
                {
                    "strategy": row["strategy"],
                    "strict_tpr": f"{row['strict_tpr']:.6f}",
                    "strict_fpr": f"{row['strict_fpr']:.6f}",
                    "strict_mcc": f"{row['strict_mcc']:.6f}",
                    "tolerant_tpr": f"{row['tolerant_tpr']:.6f}",
                    "tolerant_fpr": f"{row['tolerant_fpr']:.6f}",
                    "tolerant_mcc": f"{row['tolerant_mcc']:.6f}",
                    "fpr_gap": f"{row['fpr_gap']:.6f}",
                }
            )
    labels = [r["strategy"] for r in out]
    x = np.arange(len(labels))
    width = 0.25
    plt.figure(figsize=(11, 6))
    plt.bar(x - width, [r["strict_tpr"] for r in out], width=width, label="TPR (strict)")
    plt.bar(x, [r["strict_fpr"] for r in out], width=width, label="FPR (strict)")
    plt.bar(x + width, [r["tolerant_fpr"] for r in out], width=width, label="FPR (tolerant)")
    plt.xticks(x, labels, rotation=10)
    plt.ylim(0.0, 1.05)
    plt.ylabel("Rate")
    plt.title("RQ2 Labeling-Profile Sensitivity Analysis")
    plt.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PROFILE_PNG_PATH, dpi=220)
    plt.close()
    return out


def _write_report(
    rows: list[dict[str, Any]],
    sweep: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
    pr_rows: list[dict[str, Any]],
    volatility_rows: list[dict[str, Any]],
) -> None:
    strict_view = [r for r in rows if r["profile"] == "strict_security"]
    tolerant_view = [r for r in rows if r["profile"] == "execution_tolerant"]
    top_strict = max(strict_view, key=lambda r: (r["mcc"], r["tpr"], -r["fpr"]))
    top_tolerant = max(tolerant_view, key=lambda r: (r["mcc"], r["tpr"], -r["fpr"]))
    strict_zero = next(r for r in strict_view if r["strategy"] == "bilateral_zero_tolerance_1000")
    tolerant_zero = next(
        r for r in tolerant_view if r["strategy"] == "bilateral_zero_tolerance_1000"
    )
    strict_sweep = [r for r in sweep if r["profile"] == "strict_security"]
    best_sweep = max(strict_sweep, key=lambda r: r["mcc"])
    zero_gap = next(r for r in profile_rows if r["strategy"] == "bilateral_zero_tolerance_1000")
    strict_auprc = next(
        r for r in pr_rows if r["profile"] == "strict_security" and r["epsilon"] == "AUPRC"
    )
    tolerant_auprc = next(
        r for r in pr_rows if r["profile"] == "execution_tolerant" and r["epsilon"] == "AUPRC"
    )
    vol_focus = [
        r
        for r in volatility_rows
        if r["profile"] == "execution_tolerant" and r["strategy"] == "exact_1000"
    ]
    vol_max = max(vol_focus, key=lambda x: x["sigma"])
    vol_min = min(vol_focus, key=lambda x: x["sigma"])
    required_rows = _build_required_rq2_rows(volatility_rows)
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in required_rows:
        by_strategy.setdefault(str(row["assertion_strategy"]), []).append(row)
    exact_series = sorted(by_strategy["exact_1000"], key=lambda x: x["market_volatility_sigma"])
    tolerant_series = sorted(
        by_strategy["bilateral_995_1005"], key=lambda x: x["market_volatility_sigma"]
    )
    exact_low = exact_series[0]
    exact_high = exact_series[-1]
    tolerant_high = tolerant_series[-1]
    lines = [
        "# RQ2 L5 双边断言零容错拦截实验（IEEE-style Artifact）",
        "",
        "## Experiment Setup",
        f"- UTC timestamp: {datetime.now(timezone.utc).isoformat()}",
        f"- Python: {platform.python_version()}",
        f"- Platform: {platform.platform()}",
        f"- Seeds: {SEEDS}",
        f"- Samples per seed: {SAMPLES_PER_SEED}",
        "- Label profile A (strict_security): 只把 clean_exact 视作正常，其余偏离均视作风险样本",
        "- Label profile B (execution_tolerant): 把 benign_slippage 视作正常执行偏差",
        "- Attack categories baseline: honeypot_hard/soft, inflation_hard/soft, near_boundary_low/high",
        f"- Imbalanced-prior projection: attack prior={ATTACK_PRIOR:.2%} (for production-like PR analysis)",
        f"- Volatility sensitivity sigma grid: {MARKET_VOLATILITY_SIGMA}",
        "",
        "## Key Findings",
        (
            f"- Zero-tolerance (strict profile): TPR={strict_zero['tpr']:.4f}, "
            f"FPR={strict_zero['fpr']:.4f}, FNR={strict_zero['fnr']:.4f}, MCC={strict_zero['mcc']:.4f}"
        ),
        (
            f"- Zero-tolerance (tolerant profile): TPR={tolerant_zero['tpr']:.4f}, "
            f"FPR={tolerant_zero['fpr']:.4f}, FNR={tolerant_zero['fnr']:.4f}, MCC={tolerant_zero['mcc']:.4f}"
        ),
        (
            f"- Profile sensitivity for zero-tolerance: FPR gap (tolerant - strict) = {zero_gap['fpr_gap']:.4f}"
        ),
        (
            f"- Best MCC under strict profile: `{top_strict['strategy']}` "
            f"(MCC={top_strict['mcc']:.4f}, TPR={top_strict['tpr']:.4f}, FPR={top_strict['fpr']:.4f})"
        ),
        (
            f"- Best MCC under tolerant profile: `{top_tolerant['strategy']}` "
            f"(MCC={top_tolerant['mcc']:.4f}, TPR={top_tolerant['tpr']:.4f}, FPR={top_tolerant['fpr']:.4f})"
        ),
        (
            f"- Band sweep best epsilon by MCC (strict profile): {best_sweep['epsilon']} "
            f"(TPR={best_sweep['tpr']:.4f}, FPR={best_sweep['fpr']:.4f}, MCC={best_sweep['mcc']:.4f})"
        ),
        (
            f"- AUPRC under 1% attack prior: strict={strict_auprc['precision_prior_1pct']:.4f}, "
            f"tolerant={tolerant_auprc['precision_prior_1pct']:.4f}"
        ),
        (
            f"- Volatility stress (exact_1000, tolerant profile): FPR @ sigma={vol_min['sigma']:.3f} is {vol_min['fpr']:.4f}, "
            f"@ sigma={vol_max['sigma']:.3f} is {vol_max['fpr']:.4f}"
        ),
        (
            f"- Volatility-to-MCC collapse: exact_1000 drops from MCC={exact_low['mcc']:.4f} "
            f"(sigma={exact_low['market_volatility_sigma']:.3f}) to MCC={exact_high['mcc']:.4f} "
            f"(sigma={exact_high['market_volatility_sigma']:.3f}), while bilateral_995_1005 keeps "
            f"MCC={tolerant_high['mcc']:.4f} at highest sigma."
        ),
        "",
        "## Generated Artifacts",
        f"- `{SUMMARY_CSV_PATH.name}`: confusion-matrix and full metrics with 95% CI",
        f"- `{CATEGORY_CSV_PATH.name}`: per-category interception detail",
        f"- `{PROFILE_COMPARISON_CSV_PATH.name}`: strict vs tolerant profile sensitivity table",
        f"- `{SWEEP_CSV_PATH.name}`: bilateral tolerance sweep curve data (dual profiles)",
        f"- `{MAIN_PNG_PATH.name}`: strict-profile TPR/FPR main comparison with CI",
        f"- `{CATEGORY_PNG_PATH.name}`: category-level interception matrix",
        f"- `{SWEEP_PNG_PATH.name}`: epsilon trade-off curve (strict+tolerant overlay)",
        f"- `{PROFILE_PNG_PATH.name}`: profile sensitivity comparison chart",
        f"- `{PR_CURVE_PNG_PATH.name}`: PR curve under 1% attack prior",
        f"- `{VOLATILITY_CSV_PATH.name}`: volatility sensitivity table",
        f"- `{VOLATILITY_PNG_PATH.name}`: volatility vs FPR curve",
        f"- `{RQ2_REQUIRED_CSV_PATH.name}`: required RQ2 raw table (weighted confusion matrix + precision/recall/FPR/AUPRC/MCC)",
        f"- `{RQ2_REQUIRED_PR_PDF_PATH.name}`: IEEE-style PR curve for imbalanced prior",
        f"- `{RQ2_REQUIRED_VOL_MCC_PDF_PATH.name}`: IEEE-style volatility vs MCC survival surface",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_rq2_assertions_benchmark() -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    seeds_out: list[list[dict[str, Any]]] = []
    expanded_specs = [
        (profile, strategy) for profile in EVAL_PROFILES for strategy in _strategies()
    ]
    for seed in SEEDS:
        sample = _build_samples(seed)
        seed_rows = [
            asyncio.run(_evaluate_strategy(strategy, sample, profile_name=profile))
            for profile, strategy in expanded_specs
        ]
        seeds_out.append(seed_rows)
    merged: list[dict[str, Any]] = []
    for idx, (profile_name, strategy) in enumerate(expanded_specs):
        base = dict(seeds_out[0][idx])
        for extra_seed_rows in seeds_out[1:]:
            row = extra_seed_rows[idx]
            for key in ("tp", "tn", "fp", "fn", "total_attack", "total_normal"):
                base[key] += row[key]
            for cat, v in row["category"].items():
                existing = base["category"].setdefault(
                    cat, {"blocked": 0, "total": 0, "attack_total": 0}
                )
                existing["blocked"] += v["blocked"]
                existing["total"] += v["total"]
                existing["attack_total"] += v["attack_total"]
        base["strategy"] = strategy.name
        base["profile"] = profile_name
        total_attack = base["total_attack"]
        total_normal = base["total_normal"]
        base["tpr"] = (base["tp"] / total_attack) if total_attack else 0.0
        base["fpr"] = (base["fp"] / total_normal) if total_normal else 0.0
        base["fnr"] = (base["fn"] / total_attack) if total_attack else 0.0
        base["specificity"] = (base["tn"] / total_normal) if total_normal else 0.0
        base["precision"] = (
            (base["tp"] / (base["tp"] + base["fp"])) if (base["tp"] + base["fp"]) else 0.0
        )
        base["f1"] = (
            (2.0 * base["precision"] * base["tpr"] / (base["precision"] + base["tpr"]))
            if (base["precision"] + base["tpr"])
            else 0.0
        )
        base["balanced_accuracy"] = (base["tpr"] + base["specificity"]) / 2.0
        mcc_denom = (
            (base["tp"] + base["fp"])
            * (base["tp"] + base["fn"])
            * (base["tn"] + base["fp"])
            * (base["tn"] + base["fn"])
        ) ** 0.5
        base["mcc"] = (
            ((base["tp"] * base["tn"] - base["fp"] * base["fn"]) / mcc_denom) if mcc_denom else 0.0
        )
        base["tpr_ci_low"], base["tpr_ci_high"] = _wilson_interval(base["tp"], total_attack)
        base["fpr_ci_low"], base["fpr_ci_high"] = _wilson_interval(base["fp"], total_normal)
        merged.append(base)
    _write_summary(merged)
    _write_category_breakdown(merged)
    _write_main_plot(merged)
    _write_category_plot(merged)
    sweep = _write_band_sweep(seed=SEEDS[0])
    pr_rows = _write_imbalanced_pr_artifact(sweep, attack_prior=ATTACK_PRIOR)
    volatility_rows = _write_volatility_sensitivity()
    required_rows = _build_required_rq2_rows(volatility_rows)
    _write_required_rq2_csv(required_rows)
    _write_required_pr_curve_pdf(required_rows)
    _write_required_volatility_vs_mcc_pdf(required_rows)
    profile_rows = _write_profile_comparison(merged)
    _write_report(merged, sweep, profile_rows, pr_rows, volatility_rows)
    return merged


def test_rq2_assertions_benchmark() -> None:
    if os.getenv("RUN_RQ2_BENCHMARK") != "1":
        return
    rows = run_rq2_assertions_benchmark()
    assert len(rows) >= 8
    assert SUMMARY_CSV_PATH.exists()
    assert CATEGORY_CSV_PATH.exists()
    assert SWEEP_CSV_PATH.exists()
    assert PROFILE_COMPARISON_CSV_PATH.exists()
    assert MAIN_PNG_PATH.exists()
    assert CATEGORY_PNG_PATH.exists()
    assert SWEEP_PNG_PATH.exists()
    assert PROFILE_PNG_PATH.exists()
    assert PR_CURVE_PNG_PATH.exists()
    assert VOLATILITY_CSV_PATH.exists()
    assert VOLATILITY_PNG_PATH.exists()
    assert RQ2_REQUIRED_CSV_PATH.exists()
    assert RQ2_REQUIRED_PR_PDF_PATH.exists()
    assert RQ2_REQUIRED_VOL_MCC_PDF_PATH.exists()
    assert REPORT_PATH.exists()


if __name__ == "__main__":
    run_rq2_assertions_benchmark()
