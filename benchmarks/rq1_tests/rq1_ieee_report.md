# RQ1 Async Gateway Benchmark (IEEE-style Artifact)

## Experiment Setup
- UTC timestamp: 2026-04-30T18:18:44.519501+00:00
- Python: 3.14.3
- Platform: macOS-26.2-arm64-arm-64bit-Mach-O
- Concurrency matrix: [10, 50, 100, 200, 500]
- Open-loop Poisson lambda matrix (rps): []
- Warmup seconds per cell: 10.0
- Measurement window per round: 60.0 s
- Measurement rounds per cell: 2
- Heartbeat period: 10.0 ms
- Cold-start trim ratio (jitter): 5%
- Minimum heartbeat samples per summary cell: 1
- Open-loop latency is measured as completion_time - intended_start_time to reduce coordinated-omission bias.
- Blocking payload: `time.sleep(0.05) + sum(i*i for i in range(20000))`

## Key Results
- N=200: p99 jitter baseline=60002.448 ms, lirix=8.562 ms, reduction=7008.40x; TPS baseline=18.16, lirix=237.82, gain=13.09x
- N=500: p99 jitter baseline=60032.892 ms, lirix=7.053 ms, reduction=8511.65x; TPS baseline=17.73, lirix=251.64, gain=14.19x

## Generated Artifacts
- `rq1_throughput.csv`: aggregated summary (percentiles, TPS mean, 95% CI)
- `rq1_core_metrics.csv`: final RQ1 target metrics
- `rq1_trials_raw.csv`: per-round raw metrics
- `rq1_cdf_n200_points.csv`: CDF points at N=200
- `rq1_gil_jitter_cdf.png`: jitter CDF at N=200
- `rq1_gil_jitter_ccdf.png`: tail-risk CCDF at N=200
- `ccdf_absolute_latency.pdf`: open-loop absolute latency CCDF (x-axis log scale, with P95/P99 markers)
- `throughput_vs_latency.pdf`: saturation knee curve (lambda vs P99 absolute latency)
- `rq1_event_loop_jitter_log.pdf`: p99 event-loop lag vs concurrency (log-y)
- `rq1_tps_vs_tail_latency.pdf`: TPS vs P99 absolute latency scatter
- `rq1_jitter_percentiles.png`: p95/p99 jitter vs concurrency
- `rq1_tps_scaling.png`: TPS scaling with 95% CI
- `rq1_jitter_boxplot_n200.png`: jitter boxplot at N=200
