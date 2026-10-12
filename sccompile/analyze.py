"""Inspect counted outcomes and paired differences from a completed run."""
import argparse,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir',help='output/testN or its results directory')
    a=p.parse_args();root=Path(a.run_dir)
    if (root/'results').exists():root=root/'results'
    for name in ('counts.json','paired_stats.json'):
        file=root/name
        print(name+':',json.dumps(json.loads(file.read_text()),indent=2) if file.exists() else 'not available')
if __name__=='__main__':main()
