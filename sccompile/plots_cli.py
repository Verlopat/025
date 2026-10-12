"""python3 -m sccompile.plots_cli output/testN"""
import argparse
from pathlib import Path
from .plot import create_figures

def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir');a=p.parse_args()
    base=Path(a.run_dir)
    print('\n'.join(create_figures(base/'results'/'trials.csv',base/'figures')))
if __name__=='__main__':main()
