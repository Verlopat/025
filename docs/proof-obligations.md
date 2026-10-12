# Explicit theorem/proof status (software support document)

### Established from program structure (conditional on the stated model)

**Acyclicity.** Initially `parent[i]=i`. Every P1 successful root-link CAS writes `parent[high]=low<high`. No step writes a parent larger than the current node ID. Under optional splitting, `grandparent<parent<current` and a conditional CAS preserves strict descent. Hence following any non-self parent pointer strictly decreases the natural-number ID and cannot cycle. This induction does not establish full linearizability or lock-freedom.

**Successful-CAS conditional state identity.** A CAS of a packed `(parent,version)` word succeeds only when the target atomic word still matches its expected value. For a bounded execution without version wrap, it cannot overwrite a *different* intervening packed state. Note: deterministic monotone linking also precludes root->nonroot->root ABA, so this property alone does not establish novelty against parent-only CAS.

**Deterministic work accounting.** A `find` of depth h performs O(h+1) parent loads and (only under A3) up to O(h) compression CAS. A single `unite` attempt performs two traversals, one root revalidation load and at most one linking CAS. For a completed invocation with r failed/retried attempts, total work is `O(sum_of_attempt_path_lengths + r)`; `O(h_x+h_y+r)` applies only if h denotes *total observed traversal length over all attempts*. This is not an O(alpha(n)) guarantee; ID linking alone admits O(n)-depth trees.

### Executable counterexample (blind-write negative control)

Nodes {2,3,4} start singleton. Thread A prepares to link 4 under 3, then stalls. Thread B links 4 under 2 and returns success. Thread A resumes and performs an *unconditional stale write* setting parent[4]=3, overwriting B's link. Both report success but the final partition leaves node 2 disconnected from {3,4}. The schedule is found by the internal explorer and saved in `verify/unsafe_counterexample.json`. This demonstrates a lost update for blind stores, **not** an impossibility theorem for CAS-only DSU.

### Not established

* A proof that all concurrent P1 `find` / `unite` histories are linearizable for all n, histories and allowable compiler/architecture executions.
* A universal lock-freedom theorem in the full C++ memory model.
* A separation from every deterministic CAS-only DSU, or a general amortized lower bound.
* A new TSO-only counterexample to the proposed CAS algorithm.
* A formal correspondence theorem between the C++ implementation and the C11 harness / operational explorer.

Future proof development should use explicit linearization-point simulation, stability lemmas for stale-root observations, C++ memory-order semantics, and mechanized verification. Experiment verdicts must never be upgraded to proofs.
