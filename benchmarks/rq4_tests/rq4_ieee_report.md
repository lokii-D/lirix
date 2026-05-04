# RQ4: Cognitive Convergence Boundary

## Experimental Scope
- Defense focus: censored bias and cognitive/network timeout disentanglement.
- Total evaluated samples: 200 across models `deepseek` and `volcengine`.
- K upper bound: 5.
- Refreshes are archived to `benchmarks/rq4_tests/<branch>/runs/run-###/` with zero-padded numbering.

## Current Artifact Paths
- Raw CSV: `rq4_cognitive_convergence_boundary_raw.csv`
- Detail CSV: `rq4_cognitive_self_healing_case_details.csv`
- Curve CSV: `rq4_cognitive_self_healing_cumulative_curve.csv`
- Plot: `rq4_cognitive_self_healing_convergence.png`
- Extended metrics: `rq4_cognitive_self_healing_extended_metrics.csv`
- By-kind CSV: `rq4_cognitive_self_healing_by_kind.csv`
- K distribution CSV: `rq4_cognitive_self_healing_k_distribution.csv`
- Failure breakdown CSV: `rq4_cognitive_self_healing_failure_code_breakdown.csv`
- Report: `rq4_ieee_report.md`
- Archived refreshes: `benchmarks/rq4_tests/<branch>/runs/run-###/`

## Figure Artifacts
- Figure 1: `rmst_and_abort_decomposition.pdf`
- Figure 2: `context_saturation_decay.pdf`
- Supplemental Figure 1: `rq4_cognitive_self_healing_km_unconverged_survival.png`
- Supplemental Figure 2: `rq4_cognitive_self_healing_k_boxplot_by_kind.png`
- Extended analysis: `rq4_cognitive_self_healing_extended_analysis.png`

## Core Results
- `deepseek`: convergence=0.950, conditional_mean_k=1.779, rmst=1.990, hard_abort_rate=0.050.
- `volcengine`: convergence=1.000, conditional_mean_k=1.820, rmst=1.820, hard_abort_rate=0.000.

## Discussion
- The upper panel in Figure 1 isolates pure cognitive convergence speed by conditioning on successful samples only.
- The lower panel separates cognitive collapse (schema loops) from infrastructure failures (timeouts), reducing censored-bias interpretation risk.
- Figure 2 exposes the context saturation boundary where additional prompt-token load correlates with a sharp success-rate decline.

## Reproducibility
- Seed: 20260430.
- Timeouts: API=45.0s, Lirix=20.0s, case=900.0s.
