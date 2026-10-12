"""Deterministic local transition/output functions and baselines."""
from __future__ import annotations

PROTOCOLS=('p1','p2','b2_max','b3_center','b4_minmax','b5_intersection','b5_repaired','a1','a2_unsafe','a3_delayed','a4_cap','a5_reverse')


def emit(protocol, node, own, view, cert=None, *, round_index=0, center=0,
         delay=2, candidates=None, reverse=False, stored_safe=None, full_size=None):
    values=list(view.values())
    if protocol in ('p1','a1','b5_repaired'):return min(values)
    if protocol=='b2_max':return max(values)
    if protocol=='b3_center':return view.get(center,own)
    if protocol=='b4_minmax':
        # Static-network comparator; NOT a reimplementation of published dynamic MinMax.
        return min(values) if full_size is not None and len(view)==full_size else (min(values) if round_index%2==0 else max(values))
    if protocol=='b5_intersection':return min(candidates[node]) if candidates[node] else own
    if cert is None:raise ValueError(f'{protocol} needs a certificate')
    fallback=max(values) if reverse else min(values)
    if protocol=='a3_delayed':return stored_safe if stored_safe is not None else fallback
    if protocol=='a2_unsafe':
        # Intentionally incorrect: local candidate singleton is not globally safe.
        return min(values) if len(set(values))==1 else max(values)
    safe=cert.evaluate(view)['safe']
    return safe[0] if safe else fallback
