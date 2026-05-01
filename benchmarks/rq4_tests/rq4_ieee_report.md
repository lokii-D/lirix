# RQ4: Cognitive Convergence Boundary (IEEE-style Report)

## Experimental Scope
- Defense focus: censored bias and cognitive/network timeout disentanglement.
- Total evaluated samples: 200 across models deepseek, volcengine.
- K upper bound: 5.

## Mandatory Raw Data
- Raw CSV: `rq4_cognitive_convergence_boundary_raw.csv`
- Fields: `model_name`, `case_id`, `converged_at_k`, `hard_abort_reason`, `max_prompt_tokens_per_attempt`, `cumulative_completion_tokens`.

## Figure Artifacts
- Figure 1: `rmst_and_abort_decomposition.pdf`
- Figure 2: `context_saturation_decay.pdf`

## Core Results
- deepseek: convergence=0.950, conditional_mean_k=1.779, rmst=1.990, hard_abort_rate=0.050.
- volcengine: convergence=1.000, conditional_mean_k=1.820, rmst=1.820, hard_abort_rate=0.000.

## Discussion
- The upper panel in Figure 1 isolates pure cognitive convergence speed by conditioning on successful samples only.
- The lower panel separates cognitive collapse (schema loops) from infrastructure failures (timeouts), reducing censored-bias interpretation risk.
- Figure 2 exposes the context saturation boundary where additional prompt-token load correlates with a sharp success-rate decline.

## Reproducibility
- Seed: 20260430.
- Timeouts: API=45.0s, Lirix=20.0s, case=900.0s.
