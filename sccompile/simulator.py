"""Synchronous per-edge full-information exchange and finite-closure checks."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from .protocols import PROTOCOLS,emit

@dataclass
class Metrics:
    protocol:str
    n:int
    graph:str
    diameter:int
    radius:int
    stabilization_round:int|None
    valid:bool
    stable_agreement:bool
    selected:int|None
    output_changes:int
    max_agent_changes:int
    message_count:int
    message_payload_items:int
    certificate_resolution:int|None
    predicted_min_round:int
    rounds_simulated:int
    final_outputs:list[int]


def predict_min_round(graph,inputs):
    minimum=min(inputs)
    sources=[i for i,v in enumerate(inputs) if v==minimum]
    return max(min(graph.distances(i)[j] for j in sources) for i in range(graph.n))


def simulate(graph,inputs,protocol='p1',certificate=None,*,cap_radius=None,
             delay=2, keep_trace=False):
    if protocol not in PROTOCOLS:raise ValueError(f'unknown protocol {protocol}')
    if len(inputs)!=graph.n:raise ValueError('input vector length mismatches graph')
    if certificate is not None and certificate.graph.adj!=graph.adj:
        raise ValueError('certificate graph mismatch')
    n=graph.n; diameter=graph.diameter();center=graph.center()
    views=[{i:inputs[i]} for i in range(n)]
    candidates=[{inputs[i]} for i in range(n)]
    outputs_history=[];resolution=None;message_count=0;payload=0
    stored_safe=[None]*n
    trace=[]
    horizon=diameter+2
    def append_output(t):
        nonlocal resolution
        results=[];all_resolved=True
        for i in range(n):
            if protocol=='a3_delayed' and t%max(1,delay)==0:
                safe=certificate.evaluate(views[i])['safe']
                if safe:stored_safe[i]=safe[0]
            out=emit(protocol,i,inputs[i],views[i],cert=certificate,
                     round_index=t,center=center,delay=delay,candidates=candidates,
                     stored_safe=stored_safe[i],full_size=n,
                     reverse=(protocol=='a5_reverse'))
            if out not in views[i].values():
                raise AssertionError('strong-validity local witness violated')
            results.append(out)
            if protocol in ('p2','a2_unsafe','a3_delayed','a4_cap','a5_reverse'):
                all_resolved=all_resolved and bool(certificate.evaluate(views[i])['safe'])
        if all_resolved and resolution is None and certificate is not None:resolution=t
        outputs_history.append(results)
        if keep_trace:
            trace.append({'round':t,'outputs':results.copy(),
                          'views':[{str(k):v for k,v in sorted(view.items())} for view in views]})
    append_output(0)
    for t in range(1,horizon+1):
        # Every round all old views send simultaneously; updates are applied afterward.
        old=views
        for i in range(n):
            for j in graph.adj[i]:
                message_count+=1;payload+=len(old[i])
        if cap_radius is None or t<=cap_radius:
            views=[]
            for i in range(n):
                new=dict(old[i])
                for j in graph.adj[i]:new.update(old[j])
                views.append(new)
        if protocol=='b5_intersection':
            old_c=candidates
            candidates=[old_c[i].intersection(set().union(*(old_c[j] for j in graph.adj[i])))
                        if graph.adj[i] else set(old_c[i]) for i in range(n)]
        append_output(t)
    # Full-state closure is guaranteed for baseline and certificate protocols at diameter,
    # while capped and deliberately faulty schemes must be explicitly checked at horizon.
    final=outputs_history[-1]
    agreement=len(set(final))==1
    closed=outputs_history[-1]==outputs_history[-2]
    if agreement and closed:
        stable_t=next((t for t in range(len(outputs_history))
                       if all(x==final for x in outputs_history[t:])),None)
    else:stable_t=None
    changes=[sum(outputs_history[t][i]!=outputs_history[t-1][i]
                 for t in range(1,len(outputs_history))) for i in range(n)]
    selected=final[0] if agreement else None
    valid=selected in inputs if selected is not None else False
    metrics=Metrics(protocol,n,graph.family,diameter,graph.radius(),stable_t,
                    valid,bool(agreement and closed and valid),selected,sum(changes),
                    max(changes),message_count,payload,resolution,
                    predict_min_round(graph,inputs),horizon,list(final))
    if protocol in ('p1','a1') and stable_t!=metrics.predicted_min_round:
        raise AssertionError('P1 exact minimum propagation relation violated')
    if protocol in ('p2','a3_delayed') and not metrics.stable_agreement:
        raise AssertionError('correct certificate failed to stabilize')
    if protocol=='p2' and selected!=certificate.full_decision(inputs):
        raise AssertionError('compiled protocol wrong final selected value')
    return (metrics,trace) if keep_trace else metrics
