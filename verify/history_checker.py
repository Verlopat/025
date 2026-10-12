"""Exact DFS linearizability of *completed, bounded* invocation/response histories.

Sequential semantics use ID-priority linking (P1/B3/B4/A1/A2/A3). For
mutex/rank baselines the union-by-size tie-break rule is used instead.
Pending invocations are not supported by this offline bounded checker.
"""
from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache


def check(events: list[dict], n: int, policy: str = "id") -> dict:
    if n < 1 or len(events) > 16:
        raise ValueError("history bound: n >=1, at most 16 completed operations")
    for e in events:
        if not (0 <= e["x"] < n and 0 <= e["y"] < n and e["start"] < e["end"]):
            raise ValueError("invalid event")
    # An operation returning before a later operation starts must precede it.
    required = tuple(sum(1 << j for j, f in enumerate(events)
                         if i != j and f["end"] < e["start"])
                     for i, e in enumerate(events))
    # required[i] is the set of operations definitely before i.
    explored = 0

    def root(par, x):
        while par[x] != x:
            x = par[x]
        return x

    @lru_cache(None)
    def solve(done: int, parents: tuple, sizes: tuple):
        nonlocal explored
        explored += 1
        if done == (1 << len(events)) - 1:
            return ()
        for i, e in enumerate(events):
            if (done >> i) & 1 or (required[i] & done) != required[i]:
                continue
            par = list(parents); sz = list(sizes)
            x, y = root(par, e["x"]), root(par, e["y"])
            if e["op"] == "find":
                if x != e["result"]:
                    continue
            elif e["op"] == "unite":
                merged = x != y
                if int(merged) != e["result"]:
                    continue
                if merged:
                    if policy == "id":
                        hi, lo = max(x, y), min(x, y)
                        par[hi] = lo
                    elif policy == "size":
                        if sz[x] < sz[y] or (sz[x] == sz[y] and x > y):
                            x, y = y, x
                        par[y] = x; sz[x] += sz[y]
                    else:
                        raise ValueError("unknown policy")
            else:
                raise ValueError("unknown operation")
            suffix = solve(done | (1 << i), tuple(par), tuple(sz))
            if suffix is not None:
                return (i,) + suffix
        return None

    solution = solve(0, tuple(range(n)), tuple([1] * n))
    return {"linearizable": solution is not None, "explored_states": explored,
            "witness_order": list(solution) if solution is not None else None,
            "history_length": len(events), "policy": policy}


def check_file(path: str | Path, n: int, policy: str = "id") -> dict:
    events = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return check(events, n, policy)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("history"); ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--policy", choices=("id", "size"), default="id")
    args = ap.parse_args()
    result = check_file(args.history, args.n, args.policy)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["linearizable"] else 2)
