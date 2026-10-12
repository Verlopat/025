"""Execute selected experiment(s) in a new immutable output/testN directory."""
import argparse,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',choices=[f'e{i}' for i in range(1,8)],required=True)
    p.add_argument('--full',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parent.parent
    cmd=[sys.executable,str(root/'Main.py'),'--experiments',a.experiment]
    if a.full:cmd.append('--full')
    return subprocess.call(cmd,cwd=root)
if __name__=='__main__':raise SystemExit(main())
