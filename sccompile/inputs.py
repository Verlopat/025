"""Deterministic input generation with SHA-derived seed hierarchy."""
from __future__ import annotations
import hashlib, random


def derived_seed(*parts):
    payload='|'.join(map(str,parts)).encode('utf8')
    return int.from_bytes(hashlib.sha256(payload).digest()[:8],'big')


def input_vector(graph,k,regime,seed=0):
    n=graph.n
    if k<2:raise ValueError('k >= 2 required')
    rng=random.Random(seed)
    if regime in ('random','i2'):
        return tuple(rng.randrange(k) for _ in range(n))
    if regime in ('balanced','i3'):
        vals=[i%k for i in range(n)];rng.shuffle(vals);return tuple(vals)
    if regime in ('block','i4'):
        return tuple(min(k-1,i*k//n) for i in range(n))
    if regime in ('gradient','i5'):
        return tuple((i*k//n)%k for i in range(n))
    if regime in ('alternating','i6'):
        return tuple(i%k for i in range(n))
    if regime in ('endpoint_min','i7'):
        return tuple(0 if i==0 else k-1 for i in range(n))
    if regime in ('cut','i8'):
        return tuple(0 if i<n//2 else k-1 for i in range(n))
    raise ValueError(f'unknown input regime {regime}')
