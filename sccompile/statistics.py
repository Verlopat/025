"""Deterministic exact sign-test and bootstrap paired median intervals."""
from __future__ import annotations
import math,random,statistics


def paired_summary(a,b,seed=7,resamples=1000):
    if len(a)!=len(b) or not a:raise ValueError('nonempty paired observations required')
    diffs=[y-x for x,y in zip(a,b)]
    nz=[d for d in diffs if d!=0]
    if len(nz)<=1024:
        k=min(sum(d>0 for d in nz),sum(d<0 for d in nz))
        p=min(1.,2*sum(math.comb(len(nz),i) for i in range(k+1))/2**len(nz)) if nz else 1.
    else:p=None
    rng=random.Random(seed); med=[]
    for _ in range(resamples):
        med.append(statistics.median(rng.choices(diffs,k=len(diffs))))
    med.sort()
    return {'pairs':len(a),'median_a':statistics.median(a),'median_b':statistics.median(b),
            'median_difference_b_minus_a':statistics.median(diffs),
            'bootstrap_ci_95':[med[int(.025*(resamples-1))],med[int(.975*(resamples-1))]],
            'sign_test_two_sided_p':p,'nonzero_pairs':len(nz),
            'test_note':'exact sign test, not a Wilcoxon signed-rank test'}


def holm(pvalues):
    idx=sorted(range(len(pvalues)),key=lambda i:pvalues[i]);out=[None]*len(pvalues)
    previous=0
    for j,i in enumerate(idx):
        previous=max(previous,min(1.,(len(pvalues)-j)*pvalues[i]));out[i]=previous
    return out
