import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def cmd(args, cwd=None):
    try:
        r=subprocess.run(args,cwd=cwd,text=True,capture_output=True,timeout=8)
        return (r.stdout or r.stderr).strip()[:4000]
    except (OSError,subprocess.TimeoutExpired):
        return "unavailable"

def collect(repo, run, mode, config):
    repo=Path(repo);run=Path(run)
    files={}
    for folder in ("src","include","python","verify","tests","configs"):
        for p in (repo/folder).rglob("*"):
            if p.is_file() and "__pycache__" not in str(p):
                files[str(p.relative_to(repo))]=hashlib.sha256(p.read_bytes()).hexdigest()
    info={"timestamp_utc":datetime.now(timezone.utc).isoformat(),
          "mode":mode,"config":config,"platform":platform.platform(),
          "python":sys.version,"processor":platform.processor(),
          "logical_cpus":os.cpu_count(),"git_commit":cmd(["git","rev-parse","HEAD"],repo),
          "git_status":cmd(["git","status","--short"],repo),
          "g++":cmd(["g++","--version"]),"cmake":cmd(["cmake","--version"]),
          "ninja":cmd(["ninja","--version"]),
          "genmc":shutil.which("genmc"),"nidhugg":shutil.which("nidhugg"),
          "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None,
          "files_sha256":files}
    (run/"manifest.json").write_text(json.dumps(info,indent=2))
    return info
