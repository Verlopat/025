# Invariants and validation

I1. Element IDs in every parent field are in `[0,n)`.

I2. P1/B3/B4/A1/A2/A3 monotonicity: non-root parent of node i is strictly smaller than i. This excludes parent-pointer cycles because IDs strictly decrease on each non-self edge.

I3. CAS modifies one 64-bit packed parent/version word. With no wrap, expected-word equality rules out a successful commit against a superseded version. A node remains a root only until it is linked once (apart from A3 splitting of non-root nodes).

I4. After all operations finish, final connectivity must equal the sequential oracle applied to all submitted/actually completed `unite` requests, irrespective of order. The native runner compares equivalence relations, not root identity, since B1/B2 choose union-by-size representatives.

I5. The bounded offline history checker checks exact per-operation return values and real-time precedence; for P1 the sequential oracle uses the minimum-ID representative. Unlike final partition checking, this can detect non-linearizable intermediate return values.

I6. Version counters must not wrap (`successful_updates_per_element < 2^32`); a realistic run must report this scope assumption. Parent-only B3/A1 has no version and should be analyzed in light of the monotonic linking property instead of automatically labeled unsound.

C++ tests and the native trial validator check I1/I2/I4 on executed schedules. `verify/operational.py` exhaustively checks bounded representations (I1/I2/I5) unless it reports a reached state limit. `verify/atomic_harness.c` checks a bounded C11 instance under optional external tools. Finite checks are evidence, not universal correctness proofs.
