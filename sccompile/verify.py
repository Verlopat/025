"""Exhaustive small-instance and adversarial consensus checking."""
from __future__ import annotations
from itertools import product
from dataclasses import asdict
from .certificates import compile_certificate
from .simulator import simulate


def verify_exhaustive(graph,alphabet,cert_configs=('c1_global_min','c2_rooted_min',
                                                     'c3_lex_witness','c4_cut','c5_lookup'),
                      max_cases=4096, counterexample_limit=8):
    total=len(alphabet)**graph.n
    if total>max_cases:
        return {'status':'not_run_bound_exceeded','total_cases':total,'max_cases':max_cases,'cases':0}
    results=[];failures=[];count=0
    for kind in cert_configs:
        cert,verdict=compile_certificate(graph,alphabet,{'kind':kind,'params':{'max_rows':max_cases}},
                                         validate_cases=max_cases)
        cases=0;max_stab=0;max_res=0;bad=0
        for x in product(alphabet,repeat=graph.n):
            m,trace=simulate(graph,x,'p2',cert,keep_trace=True)
            cases+=1;count+=1
            ok=m.stable_agreement and m.valid and m.selected==cert.full_decision(x)
            if not ok:
                bad+=1
                if len(failures)<counterexample_limit:
                    failures.append({'certificate':kind,'inputs':x,'metrics':asdict(m),'trace':trace})
            max_stab=max(max_stab,m.stabilization_round or 0)
            max_res=max(max_res,m.certificate_resolution or 0)
        results.append({'certificate':kind,'cases':cases,'violations':bad,
                        'maximum_stabilization':max_stab,'maximum_resolution':max_res,
                        'certificate_validation':verdict['status']})
    return {'status':'pass' if not failures else 'fail','cases':count,
            'total_cases_per_certificate':total,'results':results,'counterexamples':failures}


def path_lower_bound_witness(n):
    """The indistinguishable opposite endpoint has distance n-1 in a path."""
    if n<2:raise ValueError('n>=2')
    return {'n':n,'opposite_endpoint_distance':n-1,
            'local_indistinguishability_rounds':list(range(n-1)),
            'restricted_task':'global-minimum selecting consensus'}
