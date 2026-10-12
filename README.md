# 025 — SAW-TSO concurrent DSU research implementation

**Executable research artifact:** deterministic, single-word-CAS concurrent union-find with adversarial pauses and a bounded operational SC/TSO comparison. C++20 is used for real threads and atomics; Python 3 orchestrates reproducible experiments, output validation, statistics and figures.

## 0. Version checks (Ubuntu Linux)

```bash
python3 --version
g++ --version
cmake --version
ninja --version
git --version
clang --version        # optional, for external model checkers
nidhugg --help        # optional, if separately installed
genmc --help          # optional, if separately installed
```

Required: Python 3.10+, GCC 11+ with C++20, CMake 3.20+, Ninja, pthreads. Missing compilers on Ubuntu: `sudo apt update && sudo apt install -y build-essential cmake ninja-build python3`. x86-64 is recommended for host-TSO experiments. The quick runner works without `pip`, Docker, network access or administrative access.

## 1. Clone and run

```bash
git clone https://github.com/Verlopat/025.git
cd 025
python3 Main.py
```

**One command executes** CMake build, C++ unit tests, Python tests, bounded SC/TSO operational checking, reproducible paired E3–E6 *pilot* benchmarks, native concurrent-history linearizability checking, statistical summaries, six SVG figures, and environment capture. External GenMC and Nidhugg checking runs automatically only when each is installed; missing tools are reported as **not run**, never as passes.

Each invocation creates `output/test1/`, then `output/test2/`, etc. Even unsuccessful attempts retain their logs, configurations and status. Different runs never overwrite each other. Output folders are deliberately ignored by Git.

**Full, resource-intensive matrix:** `python3 Main.py --full`. This can take many hours or days, generate large files, and time out at the configured cap. **Do not use `--full` by default on a laptop.** Parameters are in `configs/full.json`; the reproducible quick smoke matrix is `configs/quick.json`. A timeout/bound is explicitly recorded rather than silently counted as success.

Other commands:

```bash
python3 Main.py --verify-only     # model-level SC/TSO exploration, unit tests
python3 Main.py --benchmark-only  # native E3–E6 without model exploration
python3 Main.py --experiments e3 e5  # only E3 and E5
python3 Main.py --skip-tests
python3 -m verify.history_checker output/test1/verify/native_history.jsonl --n 4
python3 -m python.workloads --output workloads/w1.jsonl --workload w1 --n 32 --threads 2 --ops 100 --seed 42
python3 -m python.analysis output/test1
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Optional rich outputs (Parquet/PDF, as dependencies permit):

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-optional.txt
python3 Main.py
```

The basic pipeline always writes CSV and SVG. When `pandas` + `pyarrow` are available it additionally writes compressed Parquet. When CairoSVG is present it additionally writes PDF figures. No synthetic placeholder measurements are reported as empirical findings.

## 2. Implementation inventory

| ID | Implementation | Synchronization / representation |
|---|---|---|
| B1 | sequential DSU, union by size, path compression | single thread |
| B2 | coarse-grained mutex, union by size | `std::mutex` |
| B3 / A1 | monotone ID linking with parent-only CAS | `atomic<uint64_t>`, zero version |
| B4 | monotone versioned DSU | sequentially consistent atomics |
| P1 | **SAW-DSU**, monotone ID linking with versioned validation | acquire loads, acq_rel CAS, acquire failed CAS |
| A2 | P1 with relaxed atomics (ablation) | deliberately weakened ordering |
| A3 | P1 with conditional one-step path splitting | versioned CAS for a compression step |
| A4 | P1 with pause hooks disabled | selected using pause percentage 0 |

All CAS-based variants use a packed `uint64_t` consisting of 32-bit element ID and 32-bit version. `find()` traverses downward until it observes a root; `unite()` chooses higher-ID root as CAS target and retries after a failed validation/CAS. Successful link CAS is the candidate union linearization point. The native API is in `include/dsu.hpp`.

### Research non-claims

* We do **not** claim an unrestricted lower bound for all deterministic DSU implementations, a universal wait-free algorithm, or a proof of lock-freedom from finite tests alone.
* The bounded operational scheduler explores a simplified parent-CAS machine, not every behavior of compiled C++ atomics. `SC` and `TSO` are separate labels. Its TSO model includes FIFO store buffers for ordinary writes in the store-buffering litmus; the DSU's own shared writes are all locked CAS operations, so the simplified DSU submodel yields the same outcomes under SC and TSO.
* **B3/A1 is not automatically unsafe.** With monotone non-reversible parent updates, parent-only CAS can be sufficient to prevent the specific lost-update example. The retained counterexample demonstrates a distinct **deliberately unsafe blind-write** algorithm; do not describe it as a B3 counterexample.
* **A2 is a diagnostic ablation, not evidence of a defect.** A clean model run does not show memory-order necessity.
* Experiment statistics from the quick configuration are tiny pilot samples and should not be presented as publishable significance tests.
* 32-bit counter wraparound is excluded by the scope precondition `successful_updates_per_element < 2^32`. This includes successful compression CAS updates. P1 is deterministic as an algorithm; workload seeds merely select inputs.

Detailed model definition, proof obligations, and limitations: [`docs/model.md`](docs/model.md), [`docs/invariants.md`](docs/invariants.md), [`docs/proof-obligations.md`](docs/proof-obligations.md).

## 3. Experiments and workloads

The runner includes all E1–E6 families, with smaller default parameters:

| Experiment | Purpose | Expected artifacts |
|---|---|---|
| E1 | bounded SC scheduler-level safety/history checking | `verify/verdicts.json`, `results/raw/e1_verification.json` |
| E2 | bounded TSO comparisons, explicit litmus and negative control | `verify/unsafe_counterexample.json`, `results/raw/e2_verification.json` |
| E3 | throughput, latency, work under W1/W2/W3/W4/W7/W8 | `results/raw/e3_trials.csv` |
| E4 | cooperative adversarial pause/resilience under W2/W4/W5 | `results/raw/e4_trials.csv` |
| E5 | P1 vs path-splitting A3 under W3/W7 | `results/raw/e5_trials.csv` |
| E6 | paired repeated machine-stability trials across two blocks | `results/raw/e6_trials.csv` |

W1 uniform; W2 star; W3 adjacent chain union requests; W4 two-cluster cross unions; W5 adversarial star; W6 small histories; W7 read-heavy initialized chain; W8 write-heavy. Inputs use a reproducible SplitMix-style generator keyed by `(seed, thread, operation_index)`. Pauses are cooperative and decided by a deterministic hash; they are not an exact replay of OS scheduling.

`completed` is the number of finished operations; `submitted` is the configured operation count. A deadline is checked **between** operations, so it is not an operating-system-level hard cancellation bound. Long-running individual operations may exceed it. Pauses of the mutex B2 are not injected at the same internal CAS hooks: interpret its pause experiment accordingly.

**Full-study protocol:** `docs/experiment-protocol.md` explains pairing, intended trial counts, warm-up needs, native affinity, external checker limits, and where the quick version differs. Full-study publication-grade runs require a controlled machine state, larger samples, independent model-checker runs, and manual review.

## 4. Per-run output structure

```text
output/testN/
├── build.log, tests.log, pipeline.log
├── manifest.json
├── run_status.json, experiment_status.json
├── configs/selected.json
├── workloads/w1_sample.jsonl
├── verify/
│   ├── verdicts.json
│   ├── native_history.jsonl
│   ├── native_linearizability.json
│   ├── unsafe_counterexample.json      # only if found
│   └── external/status.json            # explicit installed/missing statuses
├── results/raw/
│   ├── all_trials.csv
│   ├── all_trials.parquet               # optional
│   ├── e1_verification.json, e2_verification.json
│   └── e3_trials.csv, e4_trials.csv, e5_trials.csv, e6_trials.csv
├── results/derived/
│   ├── analysis_summary.json
│   ├── summary_*.csv, paired_*.csv, run_statuses.csv
│   └── T2_verification.csv, T3_performance.csv, T4_work.csv, T5_pauses.csv, T6_stability.csv
└── figures/
    ├── F1_verification.svg ... F6_completion.svg
    └── *.pdf                         # optional
```

Raw rows have identifiers `experiment`, `trial`, `repeat`, `block`, `seed`, `variant`, `workload`, `threads`, `n`, and `run_status`. Measurement fields include `seconds`, `throughput`, `median_us`, `p95_us`, `p99_us`, `loads`, `hops`, `cas`, `retries`, `splits`, `completed`, `submitted` and `valid_final`. Invalid/time-out runs are preserved and excluded from throughput summaries. For performance comparisons the unit is an entire **trial**; the runner applies paired sign-flip permutation tests, Holm correction and percentile bootstrap intervals. These are descriptive pilots with two repetitions by default.

## 5. External model checking

Native C11 harness: [`verify/atomic_harness.c`](verify/atomic_harness.c). When installed, GenMC is invoked for **RC11** and **SC**, and Nidhugg for **SC** and **TSO** on Clang-generated LLVM IR, with 90-second and 10-GiB caps. All invocation flags, outputs and status codes are retained. The runner does not auto-install checkers or mislabel RC11 as TSO. Check installed versions and your specific tool's CLI before relying on results.

Useful upstream project references:

* [GenMC repository](https://github.com/MPI-SWS/genmc)
* [Nidhugg repository](https://github.com/nidhugg/nidhugg)

Each external harness consists of two bounded concurrent unions on three elements, with post-join partition and monotonicity assertions. It checks a *transcription of the core algorithm* rather than instrumenting the compiled C++ benchmark directly. Further studies must separately justify model-to-implementation correspondence.

## 6. Project layout

```text
.
├── Main.py
├── CMakeLists.txt
├── CMakePresets.json
├── include/dsu.hpp
├── src/benchmark.cpp
├── tests/unit.cpp
├── tests/test_checker.py, test_native.py, test_workloads.py
├── verify/operational.py, history_checker.py, atomic_harness.c, external.py
├── python/experiments.py, workloads.py, metadata.py, analysis.py
├── configs/quick.json, full.json
├── docs/model.md, invariants.md, proof-obligations.md, experiment-protocol.md
├── .github/workflows/ci.yml
├── requirements.txt, requirements-optional.txt
├── pyproject.toml, Makefile, .env.example
└── output/                       # created/updated automatically
```

## 7. Research citation and license

Software is provided under MIT (see `LICENSE`); `CITATION.cff` includes repository citation metadata. External checkers are separately licensed tools and are not vendored here. Source code, docs and configuration are stored in Git; generated workloads, build artifacts, benchmark outputs and any future manuscript text are outside the tracked source tree.
