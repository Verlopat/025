# Reproducibility and experimental protocol

## Pilot vs full study

`python3 Main.py` is a laptop-safe pilot. It uses n=32, two threads, 300 ops/thread, two paired repetitions and 10us pauses. It does not claim thermal stability, publishable confidence intervals or a complete TSO proof. `--full` loads `configs/full.json`: n=10^4,10^5,10^6, threads 1,2,4,6,8, paired repetitions 30, 50 stability repetitions, and multiple pause durations; it is deliberately explicit because the matrix is expensive.

## E1 / E2

Explore small input sequences under model-scoped SC and TSO. Save verdicts, state bounds, counterexample traces, exact configuration, tool status and runtime/memory limits. Default operational checker bounds: n=3, <=3 process groups and <=8 operations. External Nidhugg on the C11 transcription is the primary route to actual TSO; GenMC RC11 is not automatically TSO. Declare inconclusive `bound_reached` and external not-installed states separately.

## E3 / E4 / E5 / E6

Compare identical seed/workload pairs across implementations; method order is shuffled per block to reduce order effect. Keep separate measurements for success, failure, timeouts, and incomplete operations. The runner captures one row per benchmark trial, never treats individual operation samples as independent repetitions, and records per-thread locally aggregated counters. E4's hooks use `after_root`, `before_cas`, `after_failure` and deterministic selection. The mutex baseline does not have equivalent internal hooks, and the contrast is limited accordingly. Optional A3 must have bounded clean verification before being treated as a confirmed correctness-preserving method; quick E5 is exploratory only.

## Instrumentation

Native throughput = completed ops / steady wall time; latency quantiles are *sampled* individual operations, not the latency of every operation. Parent loads, retries and CAS attempts count instrumentation events. Final partitions are checked against a sequential oracle over the actual input union requests. The 32-bit version bound is a model precondition. Native benchmark time also includes thread-start barrier release and teardown; the quick trial timings are especially susceptible to this noise.

## Statistical method

Primary descriptive stats: medians, quartiles, mean and SD. For each exact matched trial, compute P1-minus-baseline difference. The built-in analysis uses a two-sided sign-flip permutation test, percentile bootstrap CI (1000 replicates in pilots), rank-biserial signed-rank effect size and Holm correction across generated tests. These analyses are intended for exploratory estimation; production methodology should pre-register families, run >=30 pairs, use >=10000 bootstrap replicates, review symmetry assumptions and power/thermal telemetry, and adjust experimental software accordingly. No cherry-picking incomplete trials. Keep raw config hashes and seeds.

## Machine control for publishable runs

Record AC power, CPU governor, x86 hybrid-core selection, affinity, frequency/temperature logs, compiler optimization flags, SSH/desktop activity and thermal excursions. Pin a tested toolchain and record compiler/version git hashes. The base runner collects tool versions and host affinity but does **not** automatically enforce fixed affinity/governor, 30-second warm-up, 60-second timed steady-state, or isolated-core settings. These are remaining controls for a publication-grade experiment.
