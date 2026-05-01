# RQ2 L5 双边断言零容错拦截实验（IEEE-style Artifact）

## Experiment Setup
- UTC timestamp: 2026-04-30T15:47:00.088867+00:00
- Python: 3.14.3
- Platform: macOS-26.2-arm64-arm-64bit-Mach-O
- Seeds: [20260430, 20260501, 20260502, 20260503, 20260504]
- Samples per seed: 24000
- Label profile A (strict_security): 只把 clean_exact 视作正常，其余偏离均视作风险样本
- Label profile B (execution_tolerant): 把 benign_slippage 视作正常执行偏差
- Attack categories baseline: honeypot_hard/soft, inflation_hard/soft, near_boundary_low/high
- Imbalanced-prior projection: attack prior=1.00% (for production-like PR analysis)
- Volatility sensitivity sigma grid: [0.001, 0.005, 0.01, 0.03, 0.05]

## Key Findings
- Zero-tolerance (strict profile): TPR=0.9718, FPR=0.0000, FNR=0.0282, MCC=0.9010
- Zero-tolerance (tolerant profile): TPR=1.0000, FPR=0.4014, FNR=0.0000, MCC=0.7266
- Profile sensitivity for zero-tolerance: FPR gap (tolerant - strict) = 0.4014
- Best MCC under strict profile: `exact_1000` (MCC=0.9010, TPR=0.9718, FPR=0.0000)
- Best MCC under tolerant profile: `exact_1000` (MCC=0.7266, TPR=1.0000, FPR=0.4014)
- Band sweep best epsilon by MCC (strict profile): 0 (TPR=0.9717, FPR=0.0000, MCC=0.9005)
- AUPRC under 1% attack prior: strict=1.0000, tolerant=0.6684
- Volatility stress (exact_1000, tolerant profile): FPR @ sigma=0.001 is 0.4008, @ sigma=0.050 is 0.4973
- Volatility-to-MCC collapse: exact_1000 drops from MCC=0.1214 (sigma=0.001) to MCC=0.1000 (sigma=0.050), while bilateral_995_1005 keeps MCC=0.0243 at highest sigma.

## Generated Artifacts
- `rq2_assertions.csv`: confusion-matrix and full metrics with 95% CI
- `rq2_category_breakdown.csv`: per-category interception detail
- `rq2_profile_comparison.csv`: strict vs tolerant profile sensitivity table
- `rq2_bilateral_band_sweep.csv`: bilateral tolerance sweep curve data (dual profiles)
- `rq2_interception_rates.png`: strict-profile TPR/FPR main comparison with CI
- `rq2_interception_by_category.png`: category-level interception matrix
- `rq2_band_tradeoff_curve.png`: epsilon trade-off curve (strict+tolerant overlay)
- `rq2_profile_comparison.png`: profile sensitivity comparison chart
- `rq2_pr_curve_imbalanced.png`: PR curve under 1% attack prior
- `rq2_volatility_sensitivity.csv`: volatility sensitivity table
- `rq2_volatility_sensitivity.png`: volatility vs FPR curve
- `rq2_assertion_strategy_efficacy.csv`: required RQ2 raw table (weighted confusion matrix + precision/recall/FPR/AUPRC/MCC)
- `rq2_imbalanced_pr_curve.pdf`: IEEE-style PR curve for imbalanced prior
- `volatility_vs_mcc.pdf`: IEEE-style volatility vs MCC survival surface
