"""Optional independently installed checker integrations with strict labeling.

These are not prerequisites for the offline, standard-library quick pipeline.
Each tool/flag is recorded and only actual tool output can claim a verdict.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
from pathlib import Path


def check(argv, log, timeout=90, memory_gib=10):
    import resource
    def limit():
        try:resource.setrlimit(resource.RLIMIT_AS,(memory_gib*1024**3,memory_gib*1024**3))
        except (ValueError,OSError):pass
    try:
        proc=subprocess.run([str(x) for x in argv],capture_output=True,text=True,
                            timeout=timeout,preexec_fn=limit)
        (log).write_text("$ "+" ".join(map(str,argv))+"\n"+proc.stdout+proc.stderr)
        result={"command":list(map(str,argv)),"returncode":proc.returncode,
                "status":"completed_zero_exit" if proc.returncode==0 else "checker_nonzero_exit",
                "interpretation":"Inspect checker output for assertion violations/timeouts; a zero code alone is not an unrestricted proof."}
    except subprocess.TimeoutExpired as e:
        result={"command":list(map(str,argv)),"status":"timeout","seconds":timeout}
        log.write_text((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout,bytes) else (e.stdout or ""))
    return result

def run_external(repo,run):
    repo=Path(repo);run=Path(run)
    out=run/"verify"/"external";out.mkdir(parents=True,exist_ok=True)
    native=repo/"verify"/"atomic_harness.c"
    statuses={}
    clang=shutil.which("clang")
    genmc=shutil.which("genmc")
    nidhugg=shutil.which("nidhugg")
    if genmc:
        # GenMC default is C/C++ RC11, not an interchangeable TSO setting.
        statuses["genmc_rc11"]=check([genmc,native],out/"genmc_rc11.log")
        statuses["genmc_sc"]=check([genmc,"--sc",native],out/"genmc_sc.log")
    else:
        statuses["genmc_rc11"]={"status":"not_run_missing_genmc"}
        statuses["genmc_sc"]={"status":"not_run_missing_genmc"}
    if nidhugg and clang:
        ll=out/"atomic_harness.ll"
        compilation=check([clang,"-O0","-g","-S","-emit-llvm","-pthread",native,"-o",ll],out/"clang.log")
        statuses["clang_compile"]=compilation
        if compilation["status"]=="completed_zero_exit":
            statuses["nidhugg_sc"]=check([nidhugg,"-sc",ll],out/"nidhugg_sc.log")
            statuses["nidhugg_tso"]=check([nidhugg,"-tso",ll],out/"nidhugg_tso.log")
    else:
        reason="not_run_missing_nidhugg" if not nidhugg else "not_run_missing_clang"
        statuses["nidhugg_sc"]={"status":reason}
        statuses["nidhugg_tso"]={"status":reason}
    (out/"status.json").write_text(json.dumps(statuses,indent=2))
    return statuses

if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser();a.add_argument("run_folder")
    args=a.parse_args()
    print(json.dumps(run_external(Path(__file__).resolve().parents[1],args.run_folder),indent=2))
