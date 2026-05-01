# RQ3 Quorum Benchmark Report

## Experiment Setup
- Node matrix: [3, 5, 7, 11, 15, 21, 31]
- Payload matrix (KB): [1, 10, 100, 1024]
- Trials per cell: 8
- Baseline payload reference size: 100.01 KB
- Entropy injection: shuffled key order for honest nodes + Byzantine stale-state poisoning.
- Network path: fully intercepted via mocked AsyncHTTPProvider/AsyncWeb3 (in-memory only).

## Key Results
- within-threshold | N=3 | payload=100KB: mean=101.931 ms, p50=104.470 ms, p95=107.889 ms, consensus_success_rate=1.000, serialize=6.442 ms, gc=20.749 ms, consensus_algo=74.740 ms
- within-threshold | N=3 | payload=1024KB: mean=116.186 ms, p50=116.196 ms, p95=128.527 ms, consensus_success_rate=1.000, serialize=10.295 ms, gc=22.361 ms, consensus_algo=83.531 ms
- within-threshold | N=5 | payload=100KB: mean=125.584 ms, p50=127.243 ms, p95=134.101 ms, consensus_success_rate=1.000, serialize=10.741 ms, gc=21.484 ms, consensus_algo=93.359 ms
- within-threshold | N=5 | payload=1024KB: mean=142.910 ms, p50=140.265 ms, p95=148.081 ms, consensus_success_rate=1.000, serialize=16.958 ms, gc=22.487 ms, consensus_algo=103.465 ms
- within-threshold | N=7 | payload=100KB: mean=129.849 ms, p50=128.877 ms, p95=133.437 ms, consensus_success_rate=1.000, serialize=14.762 ms, gc=20.923 ms, consensus_algo=94.164 ms
- within-threshold | N=7 | payload=1024KB: mean=160.006 ms, p50=159.454 ms, p95=162.704 ms, consensus_success_rate=1.000, serialize=23.680 ms, gc=22.947 ms, consensus_algo=113.379 ms
- within-threshold | N=11 | payload=100KB: mean=169.394 ms, p50=167.452 ms, p95=173.828 ms, consensus_success_rate=1.000, serialize=23.562 ms, gc=22.458 ms, consensus_algo=123.374 ms
- within-threshold | N=11 | payload=1024KB: mean=207.650 ms, p50=205.007 ms, p95=210.552 ms, consensus_success_rate=1.000, serialize=38.769 ms, gc=24.960 ms, consensus_algo=143.921 ms
- within-threshold | N=15 | payload=100KB: mean=188.933 ms, p50=188.186 ms, p95=190.296 ms, consensus_success_rate=1.000, serialize=31.738 ms, gc=22.822 ms, consensus_algo=134.374 ms
- within-threshold | N=15 | payload=1024KB: mean=260.725 ms, p50=248.558 ms, p95=263.802 ms, consensus_success_rate=1.000, serialize=52.095 ms, gc=28.234 ms, consensus_algo=180.396 ms
- within-threshold | N=21 | payload=100KB: mean=233.545 ms, p50=232.706 ms, p95=238.071 ms, consensus_success_rate=1.000, serialize=46.001 ms, gc=23.205 ms, consensus_algo=164.338 ms
- within-threshold | N=21 | payload=1024KB: mean=315.522 ms, p50=315.218 ms, p95=321.955 ms, consensus_success_rate=1.000, serialize=70.741 ms, gc=24.941 ms, consensus_algo=219.840 ms
- within-threshold | N=31 | payload=100KB: mean=324.823 ms, p50=313.363 ms, p95=356.695 ms, consensus_success_rate=1.000, serialize=72.640 ms, gc=33.569 ms, consensus_algo=218.614 ms
- within-threshold | N=31 | payload=1024KB: mean=434.870 ms, p50=436.557 ms, p95=437.795 ms, consensus_success_rate=1.000, serialize=109.209 ms, gc=33.690 ms, consensus_algo=291.972 ms

## Safety/Liveness Boundary
- Safety intact above threshold (no false consensus): True
- Liveness lost above threshold (expected fail-closed): True
- Full liveness within threshold: True

## Entropy Signal
- Mean digest-cardinality across all samples: 5.43
- Digest cardinality > 1 confirms poisoned branch divergence while honest nodes stay hash-consistent after deterministic serialization.
