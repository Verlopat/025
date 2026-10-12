# Model, assumptions, and bounded proof obligations

## System

A finite connected undirected graph G=(V,E) with nodes 0,...,n-1.
All nodes run the same deterministic program, know the fixed graph, and start
simultaneously. Each node has immutable input x_i from a finite ordered set V.
Communication is reliable and synchronous. In round t+1, every process receives
its neighbors' round-t messages, then updates its state and current output.
There are no crashes, byzantine messages, losses, or transient state corruption.

## Task

There must be a time T and value v equal to some initial x_i such that
for every node and every t>=T, its output equals v. Earlier outputs may change.
This is stabilizing consensus, NOT self-stabilization from arbitrary corrupted
internal states. Strong validity only requires v be an initial input; min validity
additionally requires v=min(x).

The compiler accepts a **finite decision certificate**, not arbitrary
infinite semi-open sets. The project implements five effective finite families.
Each procedure inspects observed immutable (node-id, input) witnesses.
The implementation's certificate state is represented explicitly by the
canonical observed view, a finite object for fixed n and alphabet.

## P1 formal invariant

At round t, node i's view contains exactly (j,x_j) for nodes j with
shortest-path distance d(i,j)<=t. Base t=0 is initialization. Inductive step:
the union of closed neighborhoods of radius t is the closed radius-(t+1) ball.
Hence the local output min(view) is the minimum of all inputs in that ball.
By diameter D all nodes output the global minimum. This proves strong validity,
agreement, and closure for P1 within D rounds.

For a set S_min of global-minimum holders, the exact first stable consensus round
of P1 is max_i min_{u in S_min} d(i,u). With a unique minimum at a path endpoint,
this is n-1.

## Path lower bound, restricted task

Consider two binary assignments identical in every radius-t view of one
path endpoint, with t<n-1. In one assignment, the far endpoint is 0 and all
other inputs are 1; in the other, all inputs are 1. An endpoint cannot
know which instance it is in before round n-1, so a globally minimum-selecting
deterministic protocol has a worst-case instance requiring at least n-1 rounds.
This is not a general lower bound for all strong-validity consensus protocols:
a center leader's valid input can be broadcast within graph radius rounds.

## P2 certificate soundness and stabilization

For each observed local view, a safe singleton is returned only if every
compatible full input assignment has the same certificate-selected label.
The returned label must appear in the local witness set. Otherwise, the output
falls back to min(observed values), which is always a genuine initial input.
Since every node has the entire input vector by round D, its certificate
label becomes unambiguous. The compiled rule then outputs the same globally
selected valid label, and views never change thereafter. Thus P2 stabilizes
by D under this fixed connected reliable-graph model.

C1-C4 use conservative conditions sufficient for forcing a label. C5 enumerates
all completions and uses the unique result when there is one. Bounded exhaustive
validation checks actual outputs for all assignments up to the run cap.

## Finite scope and exclusions

The source's motivating semi-open topological characterization is not in general
computably decidable; this repository does not implement that unrestricted
characterization or prove a new general semi-open solvability theorem. No Lean
machine proof is provided. The proof arguments above are written reasoning,
with executable exhaustive checks of declared small bounds. Random regular
examples are not claimed to be spectrally certified expanders. The MinMax-like
baseline is a static comparator, not the published dynamic-network protocol.

A1 removes the certificate. A2 is deliberately unsafe; A3 evaluates the
certificate intermittently but caches safe decisions; A4 caps view growth and
may fail to converge; A5 modifies the fallback tie-order.
