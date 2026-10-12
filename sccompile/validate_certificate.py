"""python3 -m sccompile.validate_certificate --config configs/c2.json"""
import argparse,json
from .graphs import make_graph
from .compiler import compile_protocol

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/c2.json')
    p.add_argument('--family',default='path');p.add_argument('--n',type=int,default=4)
    p.add_argument('--k',type=int,default=2);p.add_argument('--limit',type=int,default=4096)
    a=p.parse_args();g=make_graph(a.family,a.n)
    policy=compile_protocol(g,tuple(range(a.k)),a.config,a.limit)
    print(json.dumps(policy.specification(),indent=2))
if __name__=='__main__':main()
