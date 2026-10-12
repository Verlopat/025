"""Finite symbolic decision certificates; only singleton forced decisions are emitted.

This is a restricted operational certificate class, NOT an algorithm for arbitrary
semi-open sets of infinite executions. Local observations consist of known node/value
pairs, with the full graph and its node IDs fixed at compilation time.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path

CERT_KINDS=('c1_global_min','c2_rooted_min','c3_lex_witness','c4_cut','c5_lookup')

@dataclass
class Certificate:
    kind: str
    alphabet: tuple[int,...]
    graph: object
    params: dict
    table: dict | None = None

    def __post_init__(self):
        if self.kind not in CERT_KINDS:raise ValueError('unsupported certificate')
        if len(self.alphabet)<2 or len(set(self.alphabet))!=len(self.alphabet):
            raise ValueError('finite ordered alphabet must contain >=2 unique values')
        self.alphabet=tuple(sorted(self.alphabet))
        n=self.graph.n
        if self.kind=='c2_rooted_min':
            center=int(self.params.get('root',self.graph.center()))
            if not 0<=center<n:raise ValueError('invalid root')
            radius=int(self.params.get('radius',1))
            if radius<0:raise ValueError('invalid radius')
            self.region=tuple(sorted(self.graph.ball(center,radius)))
        elif self.kind=='c4_cut':
            # Deterministic side of the partition, with a specified fallback pivot.
            side=tuple(self.params.get('side',range(max(1,n//2))))
            if not side or len(set(side))!=len(side) or any(type(x)!=int or not 0<=x<n for x in side):
                raise ValueError('invalid cut side')
            pivot=int(self.params.get('pivot',n-1))
            if not 0<=pivot<n:raise ValueError('invalid cut pivot')
            self.region=side
            self.pivot=pivot
        elif self.kind=='c3_lex_witness':
            subset=self.params.get('witness_values',self.alphabet[1:])
            if not subset or any(v not in self.alphabet for v in subset):
                raise ValueError('invalid witness values')
            self.witness_values=frozenset(subset)
        elif self.kind=='c5_lookup':
            if len(self.alphabet)**n>int(self.params.get('max_rows',4096)):
                raise ValueError('C5 exhaustive lookup exceeds max_rows limit')
            # Explicit finite partition: if the count of lowest labels is even,
            # select center's value; otherwise select global minimum.
            self.table={}
            center=self.graph.center()
            for x in product(self.alphabet,repeat=n):
                chosen=x[center] if x.count(self.alphabet[0])%2==0 else min(x)
                self.table[x]=chosen
        if self.kind=='c1_global_min':self.region=tuple(range(n))

    def full_decision(self,x):
        if len(x)!=self.graph.n or any(v not in self.alphabet for v in x):
            raise ValueError('invalid full input vector')
        if self.kind in ('c1_global_min','c2_rooted_min'):
            return min(x[i] for i in self.region)
        if self.kind=='c3_lex_witness':
            return next((v for v in x if v in self.witness_values),min(x))
        if self.kind=='c4_cut':
            return self.alphabet[0] if any(x[i]==self.alphabet[0] for i in self.region) else x[self.pivot]
        return self.table[tuple(x)]

    def safe_label(self,view):
        """Return a label only if every full assignment matching view has that label.

        For C1-C4 conservative symbolic conditions are sufficient, not necessary.
        For C5 all consistent completions are enumerated exactly (small instances).
        """
        known=dict(view)
        if any(i<0 or i>=self.graph.n or v not in self.alphabet for i,v in known.items()):
            raise ValueError('invalid local view')
        if self.kind in ('c1_global_min','c2_rooted_min'):
            present=[known[i] for i in self.region if i in known]
            if present and min(present)==self.alphabet[0]:return self.alphabet[0]
            if all(i in known for i in self.region):return min(present)
            return None
        if self.kind=='c3_lex_witness':
            for i in range(self.graph.n):
                if i not in known:return None
                if known[i] in self.witness_values:return known[i]
            return min(known.values())
        if self.kind=='c4_cut':
            if any(known.get(i,None)==self.alphabet[0] for i in self.region):return self.alphabet[0]
            if self.pivot in known and known[self.pivot]==self.alphabet[0]:return self.alphabet[0]
            if all(i in known for i in self.region) and self.pivot in known:
                return known[self.pivot]
            return None
        # C5 exact compatibility over an explicit finite decision partition.
        possible={out for x,out in self.table.items() if all(x[i]==v for i,v in known.items())}
        return next(iter(possible)) if len(possible)==1 else None

    def evaluate(self,view):
        """Finite state q is canonical observed (node,value) tuple; A(q) singleton/empty."""
        q=tuple(sorted(view.items()))
        forced=self.safe_label(view)
        # Strong-validity witness check: never issue a label not yet observed.
        safe=[forced] if forced is not None and forced in view.values() else []
        return {'state':q,'lambda':list(self.alphabet),'safe':safe}

    def validation(self,max_cases=4096):
        total=len(self.alphabet)**self.graph.n
        if total>max_cases:return {'status':'not_exhaustively_checked','cases':0,'total':total}
        count=0
        for x in product(self.alphabet,repeat=self.graph.n):
            f=self.full_decision(x)
            if f not in x:raise AssertionError('strong validity violated')
            for i in range(self.graph.n):
                for radius in range(self.graph.eccentricity(i)+1):
                    view={j:x[j] for j in self.graph.ball(i,radius)}
                    outcome=self.evaluate(view)['safe']
                    if outcome and outcome[0]!=f:
                        raise AssertionError('unsafe decision on compatible view')
            count+=1
        return {'status':'exhaustive_pass','cases':count,'total':total}


def compile_certificate(graph,alphabet,config,validate_cases=4096):
    if isinstance(config,(str,Path)):
        config=json.loads(Path(config).read_text())
    c=Certificate(config['kind'],tuple(alphabet),graph,dict(config.get('params',{})))
    verdict=c.validation(validate_cases)
    return c,verdict
