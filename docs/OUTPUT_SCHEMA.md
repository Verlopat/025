# Output schema

Each invocation of `python3 Main.py` atomically allocates `output/testN`.

- `config.json`: exact pilot/extended configuration used.
- `environment.json`: OS, Python, machine and source SHA-256 manifest.
- `status.json`: running/completed/failed and error tally.
- `tests.log`: unittest stdout and stderr (unless `--skip-tests`).
- `results/trials.csv`: one row per executed simulation, with experiment, seed,
  graph family, protocol, certificate, stabilization time, bound, validity,
  output changes, message-volume proxies, runtime, peak process RSS, status.
- `results/counts.json`: outcome counts per experiment (including expected
  counterexamples from negative controls).
- `results/paired_stats.json`: paired median differences, deterministic
  percentile-bootstrap CIs, exact sign-test p-values and Holm correction.
- `results/counterexamples.json`: bounded set of failed traces/witnesses.
- `results/e1_validation.json`: exhaustive compiler validation counts.
- `results/e4_path_witnesses.json`: graph-distance lower-bound witnesses.
- `results/e7_candidate_failures.json`: counterexamples for flawed candidate update.
- `figures/F1...F5.svg`: plots from real trial rows; empty plots if an
  experiment was omitted, never fabricated measurements.
- `manifest.json`: run summary with provenance and figure paths.

Stabilization is checked by extending all simulations past graph diameter to
D+2 and requiring an unchanged suffix; closure for well-formed P1/P2 follows
from the immutable full-information state at t>=D, not merely a finite horizon.
The `counterexample` status is expected for intentionally faulty baselines;
`error` is reserved for runtime/assertion errors and fails the main command.
