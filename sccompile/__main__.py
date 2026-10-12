"""Use python -m sccompile for a quick local run."""
from pathlib import Path
from .experiments import run_all
import json
if __name__=='__main__':
    print(run_all(Path('output/manual'),json.loads(Path('configs/quick.json').read_text())))
