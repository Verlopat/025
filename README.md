# 025 — Finite-Certificate Stabilizing Consensus Compiler

An executable Python research prototype that compiles **finite symbolic decision certificates** into deterministic synchronous distributed consensus protocols, tests them on static connected graphs, and measures their stabilization time. Includes adversarial inputs, certificate-aware decisions, a full-information flooding baseline, exhaustive bounded checking, and E1–E7 pilot experiments.

## Quick start

Ubuntu version checks:

```bash
python3 --version
git --version
```

Requires **Python 3.10+**. No pip installation, Docker, GPU, or external services are needed.

```bash
git clone https://github.com/Verlopat/025.git
cd 025
python3 Main.py
```

Running again creates a separate `output/test2/`, then `output/test3/`, etc.
Each directory contains the configuration, environment hashes, test log, raw CSV,
statistical summary, failures/counterexamples, SVG figures and run status.

```bash
python3 Main.py --verify-only      # E1 + E7 only
python3 Main.py --experiments e2 e4
python3 Main.py --full             # larger bounded experiment matrix
python3 -m unittest discover -s tests -v
```

`--full` increases seeds, graph sizes and the E7 exhaustive bound. It is NOT an
unbounded exhaustive search of all graphs or a complete publication-scale evaluation.

## Research task

Each node of a static connected undirected graph starts with an immutable input
from a finite alphabet, exchanges messages synchronously, and may revise its output.
**Stabilizing consensus** requires all nodes eventually to output the same genuine
initial input forever. This differs from terminating consensus and from
**self-stabilization** from arbitrary corrupted process states.

A finite certificate describes an executable decision selector `f(x)` and its
observable local forced decisions. The compiler emits an object with `init`,
`message`, `transition`, and `output` functions. It observes only node inputs
learned through graph messages. If a certificate is not locally decisive, its
output is the smallest locally observed input, preserving strong validity.
At graph diameter, all nodes have learned all inputs, so the compiled certificate
is decidable and outputs agree; see [`docs/FORMAL_MODEL.md`](docs/FORMAL_MODEL.md).

This is an **effective finite restriction** motivated by semi-open decision-set
topology; it is not a general solver for arbitrary topological execution spaces.

## Architecture

```text
Main.py
  |-- tests/                      unittest regression checks
  |-- sccompile/graphs.py          paths, cycles, grids, seeded regular graphs
  |-- sccompile/inputs.py          adversarial, balanced, random, block inputs
  |-- sccompile/certificates.py    symbolic finite certificate families C1-C5
  |-- sccompile/compiler.py        emitted local state machine
  |-- sccompile/protocols.py       baseline/ablation decision functions
  |-- sccompile/simulator.py       synchronous neighbor-message execution
  |-- sccompile/verify.py          exhaustive bounded verdicts, path witnesses
  |-- sccompile/experiments.py     E1-E7 trial generation
  |-- sccompile/statistics.py      paired bootstrap and exact sign test
  |-- sccompile/plot.py            dependency-free SVG figures
  |-- configs/                     quick/full and certificate JSON
  |-- docs/                        model, proof obligations, result schemas
  |-- output/testN/                per-run artifacts (ignored by Git)
```

## Certificate formats

JSON objects have `kind` and optional `params`. C1–C4 are sound conservative
symbolic conditions: they emit a forced singleton when it is safely deducible.
C5 is an enumerated small-instance lookup partition with exact compatible-completion
filtering, limited by `max_rows`.

| ID | JSON `kind` | Deterministic global selector |
|---|---|---|
| C1 | `c1_global_min` | Minimum of all node inputs |
| C2 | `c2_rooted_min` | Minimum within a designated root's radius-r region |
| C3 | `c3_lex_witness` | First (lowest-ID) witnessed value in a designated subset, else global minimum |
| C4 | `c4_cut` | Lowest value if present on a specified side, else chosen pivot input |
| C5 | `c5_lookup` | Enumerated valid decision table, selected from input parity and center value |

All five selectors satisfy strong validity. They need not satisfy min-validity,
which is a **stricter** requirement used in the tight path lower-bound result.

Compile a protocol and execute a synchronous round without any experiments:

```python
from sccompile.graphs import make_graph
from sccompile.compiler import compile_protocol

graph = make_graph('path', 4)
compiled = compile_protocol(graph, (0, 1), {'kind': 'c2_rooted_min', 'params': {'radius': 1}})
states = [compiled.init(i, x) for i, x in enumerate((1, 1, 0, 1))]
messages = [compiled.message(state) for state in states]
states = [compiled.transition(states[i], [messages[j] for j in graph.adj[i]]) for i in range(graph.n)]
print([s.output_value for s in states])
```

Generate and validate certificates, graphs, or reanalyze results:

```bash
python3 -m sccompile.generate_graphs --family regular --n 24 --degree 3 --seed 42 --output output/manual/graph.json
python3 -m sccompile.validate_certificate --config configs/c2.json --family path --n 4 --k 2
python3 -m sccompile.run_experiment --experiment e2
python3 -m sccompile.analyze output/test1
python3 -m sccompile.plots_cli output/test1
```

## Methods and evaluations

| ID | Method / experiment | What it actually checks |
|---|---|---|
| P1 | Flooding-Min | Exact minimum-selection with stabilization <= graph diameter |
| P2 | Compiled certificate | Certificate-forced decisions plus strongly valid fallback |
| B2 | Flooding-Max | Symmetric valid order-statistic baseline |
| B3 | Center leader | Broadcast radius comparator, not min-validity |
| B4 | Min/max-inspired comparator | Heuristic static control, **not** the published dynamic MinMax algorithm |
| B5 | Candidate intersection | Intentionally flawed control, recorded counterexamples |
| A1–A5 | Ablations | Certificate removed, unsafe decision, delayed evaluation, capped view, reversed fallback |
| E1 | Compiler verification | Exhaustive small graph/input/certificate combinations |
| E2 | Early decision | Paired P1/P2 certificates on identical cases |
| E3 | Scaling | Paths, cycles, grids, regular graphs; exact P1 prediction |
| E4 | Tight path | P1 endpoint minimum takes exactly n-1 rounds |
| E5 | Initialization | Opinion counts, output changes, negative control |
| E6 | Regular-graph study | Throughput, message proxy, stabilization and actual diameter |
| E7 | Rule counterexamples | Exhaustive small inputs with repaired baseline comparison |

**Theoretical status:** P1's propagation invariant proves global minimum is known
by graph diameter, and local-view indistinguishability gives a path lower bound
`n-1` **only for global-minimum-selecting protocols**. Strong-validity alone
allows a center-leader protocol whose stabilization is bounded by graph radius.
The compiler is sound under the declared static fault-free model; external theorem
provers and a general topological equivalence proof are not part of the implementation.

**Verification status:** Small finite input spaces can be exhaustively enumerated.
This is bounded evidence, never a universal model-checker proof for arbitrary
executions. The `b5_intersection` and capped-view methods can yield failures;
these appear as `counterexample`, not fabricated passes. An unexpected assertion
or runtime error fails the main command.

## Data and analysis

Trial rows: graph family, graph size, input regime, actual stabilization round,
minimum-propagation prediction, message/payload proxies, output changes,
certificate-resolution round, runtime, memory high-water mark and status.
Statistical summaries use paired bootstrap medians with exact two-sided sign
tests and Holm adjustment. Because the quick suite has few seeds, results are
**pilot measurements** rather than confirmatory significance claims.

Five SVG figures F1–F5 are generated from CSV data. E1 machine-verification
summaries, an E7 failure matrix, certificate checks and graph-theoretic path
witnesses are also retained. See [`docs/OUTPUT_SCHEMA.md`](docs/OUTPUT_SCHEMA.md).

## Reproducibility and performance

Default workload is intentionally laptop-friendly. CPU-only and standard-library
Python minimize setup requirements. Larger graph diameters increase round count;
C5 lookup table size grows exponentially with graph size and is explicitly capped.
Every run captures exact config/source hashes, Python and OS details. Randomness
is used only to generate inputs/graphs (SHA-256-seeded), never by the protocols.

The project is MIT-licensed; GitHub Actions executes unit and quick integration tests.
