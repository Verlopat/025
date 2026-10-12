"""Reproducible paired experiment runner; quick pilots and full parameter matrices."""
import csv
import json
import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from .workloads import generate
from verify.operational import run_suite
from verify.history_checker import check_file

VARIANTS=["b1","b2","b3","b4","p1","a1","a2","a3"]
FIELDS=["experiment","trial","block","repeat","run_status","error","cpu_percent","rss_mib",
        "history_linearizable", "linearizability_explored"]

def read_config(repo, mode):
    return json.loads((Path(repo)/"configs"/("full.json" if mode=="full" else "quick.json")).read_text())

def bench(binary, spec, timeout):
    argv=[str(binary)]
    for key,value in spec.items():
        argv.extend(["--"+key.replace("_","-"),str(value)])
    started=time.monotonic()
    try:
        proc=subprocess.run(argv,text=True,capture_output=True,timeout=timeout,check=False)
        if proc.returncode not in (0,2):
            return {"run_status":"failed","error":proc.stderr.strip()[:500],"wall_seconds":time.monotonic()-started}
        row=json.loads(proc.stdout)
        row["run_status"]="completed" if proc.returncode==0 else "assertion_failure"
        row["error"]=proc.stderr.strip()[:500]
        row["wall_seconds"]=time.monotonic()-started
        return row
    except subprocess.TimeoutExpired:
        return {"run_status":"timeout","error":"runner subprocess exceeded timeout","wall_seconds":time.monotonic()-started}

def _resource():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024
    except ImportError:
        return None

def specs(mode, cfg):
    repeats=cfg["repetitions"]
    sizes=cfg["sizes"]
    threads=cfg["threads"]
    ops=cfg["ops"]
    # E3: W1,W2,W3,W4,W7,W8; randomized, paired order per seed and method.
    for w in ("w1","w2","w3","w4","w7","w8"):
        for n in sizes:
            for p in threads:
                methods=["b2","b3","b4","p1","a3"]+(["b1"] if p==1 else [])
                for rep in range(repeats):
                    seed=cfg["seed"]+rep
                    order=methods[:];random.Random(seed+n+p+int(w[1])).shuffle(order)
                    for method in order:
                        yield "e3",rep,0,{"n":n,"threads":p,"ops":ops,"seed":seed,
                                          "variant":method,"workload":w}
    # E4: pause stresses. Same explicit deterministic pause decision function across methods.
    for w in ("w2","w4","w5"):
        for p in threads:
            if p==1:continue
            for duration in cfg["pause_us"]:
                for hook in ("after_root","before_cas","after_failure"):
                    for rep in range(repeats):
                        seed=cfg["seed"]+rep
                        for method in ("b2","b3","b4","p1"):
                            yield "e4",rep,0,{"n":sizes[0],"threads":p,"ops":ops,"seed":seed,
                                              "variant":method,"workload":w,
                                              "pause_hook":hook,"pause_us":duration,"pause_percent":5,
                                              "deadline_ms":cfg["deadline_ms"]}
    # E5: P1 path-splitting ablation, chain/read workloads.
    for w in ("w3","w7"):
        for p in threads:
            for rep in range(repeats):
                for method in ("p1","a3"):
                    yield "e5",rep,0,{"n":sizes[0],"threads":p,"ops":ops,
                                      "seed":cfg["seed"]+rep,"variant":method,"workload":w}
    # E6: two blocks, same trace, machine stability.
    for block in (0,1):
        for w in ("w1","w2"):
            for p in threads:
                for rep in range(cfg["stability_repetitions"]):
                    for method in ("p1","b2"):
                        yield "e6",rep,block,{"n":sizes[0],"threads":p,"ops":ops,
                                             "seed":cfg["seed"],"variant":method,"workload":w}

def run(repo, directory, mode="quick", experiments=None):
    repo=Path(repo);directory=Path(directory);cfg=read_config(repo,mode)
    raw=directory/"results"/"raw";raw.mkdir(parents=True,exist_ok=True)
    (directory/"configs").mkdir(exist_ok=True)
    (directory/"configs"/"selected.json").write_text(json.dumps(cfg,indent=2))
    (directory/"workloads").mkdir(exist_ok=True)
    generate(directory/"workloads"/"w1_sample.jsonl","w1",n=cfg["sizes"][0],
             threads=cfg["threads"][0],ops=10,seed=cfg["seed"])
    allowed=set(experiments) if experiments else set(["e1","e2","e3","e4","e5","e6"])
    results={}
    if "e1" in allowed or "e2" in allowed:
        # Model-level SC/TSO execution exploration, **not** external weak-memory proof.
        verdicts=run_suite(directory/"verify",bounds=cfg["verification_sizes"],
                           max_states=cfg["verification_max_states"])
        for exp,model in (("e1","sc"),("e2","tso")):
            subset=[v for v in verdicts if v.get("result",{}).get("model")==model
                    and v["suite"]=="saw_dsu"]
            with (raw/f"{exp}_verification.json").open("w") as f:json.dump(subset,f,indent=2)
            results[exp]={"checks":len(subset),"statuses":sorted({x["result"]["status"] for x in subset})}
    rows=[]
    if any(e in allowed for e in ("e3","e4","e5","e6")):
        for experiment,rep,block,spec in specs(mode,cfg):
            if experiment not in allowed:continue
            sample=dict(spec)
            run_result=bench(repo/"build"/"saw_bench",sample,cfg["timeout_seconds"])
            row={"experiment":experiment,"trial":f"{experiment}-{block}-{rep}-{spec['workload']}-{spec['threads']}-{spec['n']}-{spec.get('pause_us',0)}-{spec.get('pause_hook','none')}",
                 "block":block,"repeat":rep,
                 "history_linearizable":"", "linearizability_explored":"",**spec,**run_result}
            rows.append(row)
        with (raw/"all_trials.csv").open("w",newline="") as f:
            fields=sorted(set().union(*(x.keys() for x in rows))) if rows else FIELDS
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        for exp in ("e3","e4","e5","e6"):
            group=[x for x in rows if x["experiment"]==exp]
            if not group:continue
            with (raw/f"{exp}_trials.csv").open("w",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(group)
            results[exp]={"trials":len(group),"completed":sum(x["run_status"]=="completed" for x in group)}
        # small concurrent history from native executable, checked by backtracking oracle.
        hist=directory/"verify"/"native_history.jsonl";hist.parent.mkdir(exist_ok=True,parents=True)
        small={"n":4,"threads":2,"ops":2,"variant":"p1","workload":"w6","seed":cfg["seed"],"history":hist}
        verdict=bench(repo/"build"/"saw_bench",small,30)
        if hist.exists():
            oracle=check_file(hist,4)
            (directory/"verify"/"native_linearizability.json").write_text(json.dumps(oracle,indent=2))
            results["native_history"]={"bench_status":verdict.get("run_status"),**oracle}
        try:
            import pandas as pd
            import pyarrow # noqa: F401
            pd.DataFrame(rows).to_parquet(raw/"all_trials.parquet",index=False,compression="zstd")
            results["parquet"]="written"
        except ImportError:
            results["parquet"]="unavailable: install requirements-optional.txt; CSV written"
    (directory/"experiment_status.json").write_text(json.dumps(results,indent=2))
    return results
