"""Deterministic W1-W8 operation generator mirroring native benchmark.cpp."""
import json
from pathlib import Path
MASK = (1 << 64) - 1

def scramble(z):
    z = (z + 0x9e3779b97f4a7c15) & MASK
    z = ((z ^ (z >> 30)) * 0xbf58476d1ce4e5b9) & MASK
    z = ((z ^ (z >> 27)) * 0x94d049bb133111eb) & MASK
    return z ^ (z >> 31)

def operation(workload, n, tid, index, seed, find_percent=40):
    if n < 2 or workload not in {f"w{i}" for i in range(1,9)}:
        raise ValueError("invalid workload or n")
    k = scramble(seed ^ (tid << 32) ^ index)
    j = scramble(k)
    find = k % 100 < find_percent
    x, y = j % n, scramble(j) % n
    if workload in ("w2", "w5"):
        x,y = 0, 1 + scramble((k + 9) & MASK) % (n-1)
    if workload == "w3":
        x = n-2-index % (n-1);y=x+1
    if workload == "w4":
        x,y = j % (n//2), n//2 + scramble(j) % (n-n//2)
    if workload == "w7": find = k % 100 < 99
    if workload == "w8": find = k % 100 < 15
    return {"tid":tid,"idx":index,"op":"find" if find else "unite","x":x,"y":y}

def generate(path, workload="w1", n=64, threads=2, ops=100, seed=42, find_percent=40):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w") as f:
        for tid in range(threads):
            for idx in range(ops):
                f.write(json.dumps(operation(workload,n,tid,idx,seed,find_percent),sort_keys=True)+"\n")
    return {"path":str(p),"records":ops*threads,"seed":seed,"workload":workload}

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True);ap.add_argument("--workload",default="w1")
    ap.add_argument("--n",type=int,default=64);ap.add_argument("--threads",type=int,default=2)
    ap.add_argument("--ops",type=int,default=100);ap.add_argument("--seed",type=int,default=42)
    a=ap.parse_args(); print(json.dumps(generate(a.output,a.workload,a.n,a.threads,a.ops,a.seed)))
