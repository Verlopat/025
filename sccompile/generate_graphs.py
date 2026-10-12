"""python3 -m sccompile.generate_graphs --family path --n 12 --output graph.json"""
import argparse,json
from pathlib import Path
from .graphs import make_graph

def main():
    p=argparse.ArgumentParser();p.add_argument('--family',default='path')
    p.add_argument('--n',type=int,default=12);p.add_argument('--degree',type=int,default=3)
    p.add_argument('--seed',type=int,default=42);p.add_argument('--output',required=True)
    a=p.parse_args();g=make_graph(a.family,a.n,a.seed,a.degree)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'graph':g.to_dict(),'diameter':g.diameter(),'radius':g.radius(),
                                'center':g.center(),'seed':a.seed},indent=2))
    print(path)
if __name__=='__main__':main()
