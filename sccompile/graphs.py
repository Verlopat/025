"""Connected, simple undirected graph generation and exact distance routines."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class Graph:
    adj: tuple[tuple[int, ...], ...]
    family: str = 'custom'

    def __post_init__(self):
        n = len(self.adj)
        if not n:
            raise ValueError('graph cannot be empty')
        for u, neighbors in enumerate(self.adj):
            if len(neighbors) != len(set(neighbors)) or u in neighbors:
                raise ValueError('loops/duplicate edges forbidden')
            for v in neighbors:
                if not isinstance(v,int) or not (0 <= v < n) or u not in self.adj[v]:
                    raise ValueError('graph must be undirected with valid IDs')
        if len(self.distances(0)) != n:
            raise ValueError('graph must be connected')

    @property
    def n(self): return len(self.adj)
    @property
    def edges(self): return sum(map(len, self.adj)) // 2

    def distances(self, start):
        dist = {start: 0}; queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in self.adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    queue.append(v)
        return dist

    def ball(self, u, radius):
        return frozenset(v for v,d in self.distances(u).items() if d <= radius)

    def eccentricity(self, node): return max(self.distances(node).values())
    def diameter(self): return max(self.eccentricity(u) for u in range(self.n))
    def radius(self): return min(self.eccentricity(u) for u in range(self.n))
    def center(self):
        return min(range(self.n),key=lambda u: (self.eccentricity(u),u))
    def to_dict(self):
        return {'family':self.family,'n':self.n,'edges':[[i,j] for i in range(self.n) for j in self.adj[i] if i<j]}


def from_edges(n, edges, family='custom'):
    if n < 1: raise ValueError('n must be positive')
    adj=[set() for _ in range(n)]
    for u,v in edges:
        if not isinstance(u,int) or not isinstance(v,int) or not (0<=u<n and 0<=v<n) or u==v:
            raise ValueError('invalid edge')
        adj[u].add(v); adj[v].add(u)
    return Graph(tuple(tuple(sorted(s)) for s in adj),family)


def random_regular(n, degree, seed):
    """Seeded degree-preserving edge-swap generator; always verify resulting graph."""
    if degree < 2 or degree >= n or (n*degree)%2:
        raise ValueError('invalid regular degree or parity')
    edges=set()
    for u in range(n):
        for offset in range(1,degree//2+1):
            edges.add(tuple(sorted((u,(u+offset)%n))))
    if degree % 2:
        for u in range(n//2):edges.add((u,u+n//2))
    rng=random.Random(seed)
    initial=sorted(edges)
    for _ in range(max(20,n*degree*10)):
        old1,old2=rng.sample(initial,2)
        a,b=old1;c,d=old2
        if rng.getrandbits(1):c,d=d,c
        new1=tuple(sorted((a,c)));new2=tuple(sorted((b,d)))
        if len({a,b,c,d})<4 or new1==new2 or new1 in edges or new2 in edges:continue
        edges.remove(old1);edges.remove(old2)
        edges.add(new1);edges.add(new2)
        initial.remove(old1);initial.remove(old2)
        initial.extend([new1,new2])
    # Repair disconnected swap outcomes by reverting to the guaranteed-connected circulant.
    try:
        return from_edges(n,edges,'regular')
    except ValueError:
        rng=random.Random(seed); perm=list(range(n));rng.shuffle(perm)
        original=set()
        for u in range(n):
            for offset in range(1,degree//2+1):
                original.add(tuple(sorted((perm[u],perm[(u+offset)%n]))))
        if degree%2:
            for u in range(n//2):original.add(tuple(sorted((perm[u],perm[u+n//2]))))
        return from_edges(n,original,'regular')


def make_graph(family,n,seed=0,degree=3):
    if family=='path':return from_edges(n,[(i,i+1) for i in range(n-1)],family)
    if family=='cycle':
        if n < 3: raise ValueError('cycle needs >=3 vertices')
        return from_edges(n,[(i,(i+1)%n) for i in range(n)],family)
    if family=='grid':
        side=round(n**.5)
        if side*side!=n:raise ValueError('grid n must be a square')
        edges=[]
        for i in range(side):
            for j in range(side):
                u=i*side+j
                if i+1<side:edges.append((u,u+side))
                if j+1<side:edges.append((u,u+1))
        return from_edges(n,edges,family)
    if family=='regular':return random_regular(n,degree,seed)
    raise ValueError(f'unknown graph family: {family}')
