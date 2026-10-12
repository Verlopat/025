#!/usr/bin/env python3
"""Clone, cd, python3 Main.py. One immutable output/testN directory per run."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,subprocess,sys,time,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from sccompile.experiments import run_all,RUNNERS
from sccompile.plot import create_figures


def allocate_run(root):
    root.mkdir(parents=True,exist_ok=True)
    for i in range(1,1000000):
        candidate=root/f'test{i}'
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:continue
    raise RuntimeError('output directory capacity exhausted')


def probe(argv):
    try:r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=8)
    except (OSError,subprocess.TimeoutExpired):return 'unavailable'
    return (r.stdout or r.stderr).strip().splitlines()[0][:200] if r.returncode==0 else 'unavailable'


def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def environment():
    meta={'python':sys.version,'os':platform.platform(),'cpu':platform.processor(),
          'host':platform.machine(),'time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
          'git_commit':probe(['git','rev-parse','HEAD']),
          'python_version':probe(['python3','--version']),
          'source_hashes':{str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'sccompile').glob('*.py'))}}
    return meta


def run_tests():
    cmd=[sys.executable,'-m','unittest','discover','-s','tests','-v']
    return subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=240)


def main():
    ap=argparse.ArgumentParser(description='Reproducible stabilizing-consensus compiler and experiments')
    ap.add_argument('--full',action='store_true',help='larger matrix; can be slow')
    ap.add_argument('--experiments',nargs='+',choices=list(RUNNERS))
    ap.add_argument('--verify-only',action='store_true',help='run only E1 and E7')
    ap.add_argument('--skip-tests',action='store_true')
    ap.add_argument('--output-root',default='output')
    args=ap.parse_args()
    cfg_file=ROOT/'configs'/('full.json' if args.full else 'quick.json')
    cfg=json.loads(cfg_file.read_text())
    run=allocate_run(ROOT/args.output_root)
    manifest={'run_dir':str(run),'config_file':str(cfg_file.relative_to(ROOT)),
              'config_sha256':sha256(cfg_file),'config':cfg,'selected_experiments':args.experiments}
    (run/'config.json').write_text(json.dumps(cfg,indent=2))
    (run/'environment.json').write_text(json.dumps(environment(),indent=2))
    status={'state':'running','success':False,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    (run/'status.json').write_text(json.dumps(status,indent=2))
    print(f'Run directory: {run}',flush=True)
    try:
        if not args.skip_tests:
            result=run_tests()
            (run/'tests.log').write_text(result.stdout+'\n'+result.stderr)
            if result.returncode!=0:
                raise RuntimeError('unit tests failed; see tests.log')
            print('Unit tests: pass',flush=True)
        selected=args.experiments or (['e1','e7'] if args.verify_only else list(RUNNERS))
        manifest['selected_experiments']=selected
        data=run_all(run/'results',cfg,selected)
        files=create_figures(run/'results'/'trials.csv',run/'figures')
        manifest['figures']=files;manifest['result']=data
        (run/'manifest.json').write_text(json.dumps(manifest,indent=2))
        errors=sum(row['count'] for row in data['counts'] if row['status'] in ('error','fail'))
        status.update({'state':'completed' if not errors else 'experiment_errors',
                       'success':not bool(errors),'errors':errors,'figures':len(files),
                       'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        print(f'Experiments: {len(selected)}; figures: {len(files)}; errors: {errors}',flush=True)
        if errors:return 2
        return 0
    except Exception as exc:
        (run/'fatal.log').write_text(traceback.format_exc())
        status.update({'state':'failed','error':str(exc)})
        print(f'FAILED: {exc} (see {run})',file=sys.stderr)
        return 1
    finally:
        (run/'status.json').write_text(json.dumps(status,indent=2))

if __name__=='__main__':raise SystemExit(main())
