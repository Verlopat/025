#!/usr/bin/env python3
"""Single-command runner. Each invocation creates output/testN with isolated artifacts."""
from __future__ import annotations
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent

def environment():
    example=ROOT/".env"
    if example.exists():
        for line in example.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line:continue
            k,v=line.split("=",1)
            if k.strip():os.environ.setdefault(k.strip(),v.strip())

def directory():
    root=ROOT/"output";root.mkdir(exist_ok=True)
    i=1
    while True:
        dest=root/f"test{i}"
        try:dest.mkdir();return dest
        except FileExistsError:i+=1

def command(argv,log=None,timeout=300):
    result=subprocess.run([str(v) for v in argv],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    if log:
        with Path(log).open("a") as f:
            f.write("$ "+" ".join(map(str,argv))+"\n"+result.stdout+result.stderr+"\n")
    if result.returncode:raise RuntimeError(f"command failed ({result.returncode}): {' '.join(map(str,argv))}\n{result.stderr[-2500:]}")
    return result.stdout

def build(run):
    command(["cmake","-S",ROOT,"-B",ROOT/"build","-G","Ninja","-DCMAKE_BUILD_TYPE=Release"],run/"build.log")
    command(["cmake","--build",ROOT/"build","--parallel","4"],run/"build.log")

def test(run):
    command(["ctest","--test-dir",ROOT/"build","--output-on-failure"],run/"tests.log")
    command([sys.executable,"-m","unittest","discover","-s","tests","-p","test_*.py","-v"],run/"tests.log")

def main():
    environment()
    parser=argparse.ArgumentParser(description="SAW-DSU research reproducibility pipeline")
    parser.add_argument("--full",action="store_true",help="full, resource-intensive E1-E6 matrix")
    parser.add_argument("--verify-only",action="store_true")
    parser.add_argument("--benchmark-only",action="store_true")
    parser.add_argument("--skip-tests",action="store_true")
    parser.add_argument("--no-external",action="store_true",help="skip optional checker integrations")
    parser.add_argument("--experiments",nargs="+",choices=("e1","e2","e3","e4","e5","e6"),
                        help="restrict pipeline to selected experiments")
    a=parser.parse_args()
    mode="full" if a.full else "quick"
    run=directory();log=run/"pipeline.log"
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),logging.FileHandler(log)])
    logging.info("Run directory: %s",run)
    logging.info("Mode: %s",mode)
    status={"mode":mode,"started_utc":datetime.now(timezone.utc).isoformat(),"run":str(run),"status":"started"}
    try:
        for utility in ("cmake","ninja","g++"):
            if not shutil.which(utility):
                raise RuntimeError(f"missing {utility}; on Ubuntu: sudo apt install build-essential cmake ninja-build")
        from python.metadata import collect
        from python.experiments import run as experiments
        from python.analysis import analyze
        cfg=json.loads((ROOT/"configs"/("full.json" if a.full else "quick.json")).read_text())
        collect(ROOT,run,mode,cfg)
        build(run)
        if not a.skip_tests:test(run)
        selected=set(a.experiments) if a.experiments else ({"e1","e2"} if a.verify_only else ({"e3","e4","e5","e6"} if a.benchmark_only else None))
        status["experiments"]=experiments(ROOT,run,mode,selected)
        if selected is None or any(x in selected for x in ("e3","e4","e5","e6")):
            status["analysis"]=analyze(run)
        if not a.no_external:
            from verify.external import run_external
            status["external_checkers"]=run_external(ROOT,run)
        status["status"]="completed"
        logging.info("Completed. All artifacts: %s",run)
    except (Exception,KeyboardInterrupt) as e:
        logging.error("Run failed: %s",e)
        traceback.print_exc()
        status["status"]="failed";status["error"]=str(e)
    finally:
        status["finished_utc"]=datetime.now(timezone.utc).isoformat()
        (run/"run_status.json").write_text(json.dumps(status,indent=2))
    print(json.dumps({"status":status["status"],"run_directory":str(run)},indent=2))
    return 0 if status["status"]=="completed" else 1

if __name__=="__main__":raise SystemExit(main())
