from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pytest

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional benchmark dependency
    pytest.skip("pandas is required for the benchmark plot", allow_module_level=True)

try:
    import seaborn as sns
except ImportError:  # pragma: no cover - optional benchmark dependency
    pytest.skip("seaborn is required for the benchmark plot", allow_module_level=True)

BASE_DIR = Path(__file__).resolve().parent
RAW_CSV = BASE_DIR / "rq4_cognitive_convergence_boundary_raw.csv"
OUT_PDF = BASE_DIR / "rq4_master_panel.pdf"


def _load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["converged_at_k"] = (
        pd.to_numeric(df["converged_at_k"], errors="coerce").fillna(-1).astype(int)
    )
    df["cumulative_completion_tokens"] = (
        pd.to_numeric(df["cumulative_completion_tokens"], errors="coerce").fillna(0).astype(int)
    )
    df["max_prompt_tokens_per_attempt"] = (
        pd.to_numeric(df["max_prompt_tokens_per_attempt"], errors="coerce").fillna(0).astype(int)
    )
    df["hard_abort_reason"] = df["hard_abort_reason"].fillna("").astype(str)
    return df


def _plot_master_panel(df: pd.DataFrame, out_pdf: Path) -> None:
    sns.set_context("paper")
    sns.set_style("ticks")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 11,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )

    model_order = ["deepseek", "volcengine"]
    model_colors = {"deepseek": "#1f4e79", "volcengine": "#b64926"}
    abort_palette = {
        "EXACT_SCHEMA_VIOLATION": "#8b1e3f",
        "CASE_TIMEOUT": "#6b7280",
        "EVM_REVERT": "#2f855a",
    }

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.8), constrained_layout=True)

    # Subplot 1: ECDF of converged K
    ax1 = axes[0]
    converged = df[df["converged_at_k"] >= 1].copy()
    for model in model_order:
        subset = converged[converged["model_name"] == model]
        total = len(df[df["model_name"] == model])
        if subset.empty or total == 0:
            continue
        counts = subset["converged_at_k"].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
        cum_rate = counts.cumsum() / total
        ax1.step(
            [1, 2, 3, 4, 5],
            cum_rate.values,
            where="post",
            linewidth=2.4,
            color=model_colors[model],
            label=model,
        )
        ax1.scatter([1, 2, 3, 4, 5], cum_rate.values, color=model_colors[model], s=20, alpha=0.9)
    ax1.set_xlim(1, 5)
    ax1.set_ylim(0.0, 1.02)
    ax1.set_xticks([1, 2, 3, 4, 5])
    ax1.set_xlabel("Retry Step K")
    ax1.set_ylabel("Cumulative Success Rate")
    ax1.set_title("Cognitive Convergence Dynamics")
    ax1.legend(frameon=False, loc="lower right")

    # Subplot 2: Box + strip for token cost by K
    ax2 = axes[1]
    cost = converged.copy()
    cost["k_cat"] = pd.Categorical(cost["converged_at_k"], categories=[1, 2, 3, 4, 5], ordered=True)
    sns.boxplot(
        data=cost,
        x="k_cat",
        y="cumulative_completion_tokens",
        color="#93c5fd",
        width=0.6,
        fliersize=0,
        linewidth=1.1,
        ax=ax2,
    )
    sns.stripplot(
        data=cost,
        x="k_cat",
        y="cumulative_completion_tokens",
        hue="model_name",
        hue_order=model_order,
        palette=model_colors,
        jitter=0.22,
        dodge=False,
        alpha=0.7,
        size=3.2,
        ax=ax2,
    )
    if ax2.legend_ is not None:
        ax2.legend_.remove()
    ax2.set_xlabel("Retry Step K")
    ax2.set_ylabel("Total Completion Tokens")
    ax2.set_title("Cost of Self-Healing")

    # Subplot 3: Absolute hard-abort pathology
    ax3 = axes[2]
    abort_df = df[df["hard_abort_reason"] != ""].copy()
    reason_order = ["EXACT_SCHEMA_VIOLATION", "CASE_TIMEOUT", "EVM_REVERT"]
    grouped = (
        abort_df.groupby(["model_name", "hard_abort_reason"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    grouped["hard_abort_reason"] = pd.Categorical(
        grouped["hard_abort_reason"], categories=reason_order, ordered=True
    )
    grouped = grouped.sort_values(["model_name", "hard_abort_reason"])
    sns.barplot(
        data=grouped,
        x="model_name",
        y="count",
        hue="hard_abort_reason",
        hue_order=reason_order,
        palette=abort_palette,
        ax=ax3,
    )
    ax3.set_xlabel("Model Name")
    ax3.set_ylabel("Number of Hard Aborts")
    ax3.set_title("Pathology of Hard Aborts")
    ax3.legend(frameon=False, title="Abort Type", loc="upper right")

    for ax in axes:
        ax.grid(axis="y", linestyle="--", linewidth=0.55, alpha=0.6)
        sns.despine(ax=ax, top=True, right=True)

    fig.savefig(out_pdf, format="pdf", dpi=300)
    plt.close(fig)


def main() -> None:
    df = _load_data(RAW_CSV)
    _plot_master_panel(df, OUT_PDF)
    print(f"[rq4] Master panel saved: {OUT_PDF}")


if __name__ == "__main__":
    main()
