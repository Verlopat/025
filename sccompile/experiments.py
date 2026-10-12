"""E1-E7 deterministic experiments. Results are generated, never hard-coded."""
from __future__ import annotations
import csv,json,time,resource
from dataclasses import asdict
from itertools import product
from pathlib import Path
from collections import defaultdict
from .graphs import make_graph
from .inputs import input_vector,derived_seed
from .certificates import compile_certificate
from .simulator import simulate
from .verify import verify_exhaustive,path_lower_bound_witness
from .statistics import paired_summary,holm

FIELDS=('experiment','graph_family','n','k','seed','regime','protocol','certificate',
        'stabilization_round','predicted_min_round','diameter','radius','valid','stable_agreement',
        'selected','output_changes','max_agent_changes','message_count','message_payload_items',
        'certificate_resolution','runtime_ms','maxrss_kib','status')

class Records:
    def __init__(self,out):
        self.path=Path(out);self.path.mkdir(parents=True,exist_ok=True)
        self.file=(self.path/'trials.csv').open('w',newline='',encoding='utf8')
        self.writer=csv.DictWriter(self.file,fieldnames=FIELDS)
        self.writer.writeheader();self.counts=defaultdict(int);self.failures=[];self.pairs=defaultdict(dict)
    def close(self):self.file.close()
    def trial(self,exp,graph,inputs,protocol,cert=None,seed=0,regime='',extra=None):
        t0=time.perf_counter_ns()
        params=extra or {}
        try:
            response=simulate(graph,inputs,protocol,cert,keep_trace=params.get('trace',False),
                 cap_radius=params.get('cap_radius'),delay=params.get('delay',2))
            m,trace=response if isinstance(response,tuple) else (response,[])
            verdict=bool(m.stable_agreement and m.valid)
            status='pass' if verdict else 'counterexample'
            vals=asdict(m)
        except (AssertionError,ValueError) as exc:
            status='error';vals={};trace=[{'error':str(exc)}]
        elapsed=(time.perf_counter_ns()-t0)/1e6
        row={'experiment':exp,'graph_family':graph.family,'n':graph.n,
             'k':len(set(inputs)),'seed':seed,'regime':regime,'protocol':protocol,
             'certificate':cert.kind if cert else '',
             'runtime_ms':round(elapsed,4),
             'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'status':status}
        row.update({k:v for k,v in vals.items() if k in FIELDS})
        self.writer.writerow({k:row.get(k,'') for k in FIELDS})
        self.counts[(exp,status)]+=1
        if status!='pass' and len(self.failures)<30:
            self.failures.append({'experiment':exp,'row':row,'inputs':inputs,'trace':trace})
        return row


def choose_k_alphabet(k):return tuple(range(k))


def trial_variants(rec,exp,graph,x,seed,regime,include=('p1','p2'),cert_kind='c2_rooted_min'):
    c,v=compile_certificate(graph,tuple(range(max(x)+1 if max(x)>0 else 2)),
                  {'kind':cert_kind},validate_cases=0)
    for protocol in include:
        rec.trial(exp,graph,x,protocol,c if protocol.startswith(('p2','a2','a3','a4','a5')) else None,
                  seed=seed,regime=regime)


def run_e1(rec,cfg):
    records=[]
    for family,n in [('path',4),('cycle',4),('grid',4)]:
        graph=make_graph(family,n)
        result=verify_exhaustive(graph,(0,1),max_cases=cfg['max_exhaustive'])
        records.append({'family':family,'n':n,'result':result})
        for entry in result.get('results',[]):
            rec.counts[('e1','pass')]+=entry['cases']-entry['violations']
            rec.counts[('e1','fail')]+=entry['violations']
        for err in result.get('counterexamples',[]):rec.failures.append(err)
    (rec.path/'e1_validation.json').write_text(json.dumps(records,indent=2))


def run_e2(rec,cfg):
    for family,n in [('path',cfg['size']),('cycle',cfg['size']),
                     ('grid',16),('regular',cfg['size'])]:
        g=make_graph(family,n,degree=4,seed=11)
        for regime in ['random','block','endpoint_min']:
            for s in range(cfg['seeds']):
                k=3;x=input_vector(g,k,regime,derived_seed('e2',family,regime,s))
                for name in ['c2_rooted_min','c4_cut','c3_lex_witness']:
                    c,_=compile_certificate(g,tuple(range(k)),{'kind':name},validate_cases=0)
                    baseline=rec.trial('e2',g,x,'p1',seed=s,regime=regime)
                    variant=rec.trial('e2',g,x,'p2',c,seed=s,regime=regime)
                    if baseline['status']=='pass' and variant['status']=='pass':
                        key=f'{family}_{name}'
                        pair=rec.pairs[key]
                        pair[(regime,s)]=(baseline['stabilization_round'],variant['stabilization_round'])
                    if s==0:
                        rec.trial('e2',g,x,'a1',seed=s,regime=regime)
                        rec.trial('e2',g,x,'a3_delayed',c,seed=s,regime=regime,extra={'delay':2})
                        rec.trial('e2',g,x,'a4_cap',c,seed=s,regime=regime,
                                  extra={'cap_radius':1})


def run_e3(rec,cfg):
    for family,sizes in [('path',[8,cfg['size']]),('cycle',[8,cfg['size']]),
                         ('grid',[9,16]),('regular',[16,cfg['size']])]:
        for n in sizes:
            g=make_graph(family,n,degree=4,seed=19)
            for unique_min in [0,g.center()]:
                x=[2]*n;x[unique_min]=0
                for prot in ['p1','b2_max']:
                    row=rec.trial('e3',g,tuple(x),prot,seed=unique_min,regime='unique_min')
                    if prot=='p1' and row['stabilization_round']!=row['predicted_min_round']:
                        raise AssertionError('graph minimum-propagation theorem failed')


def run_e4(rec,cfg):
    witnesses=[]
    for n in [2,3,4,6,8,12,cfg['size']]:
        g=make_graph('path',n)
        x=(0,)+tuple(1 for _ in range(n-1))
        result=rec.trial('e4',g,x,'p1',regime='endpoint_min')
        if result['stabilization_round']!=n-1:
            raise AssertionError('path upper/lower bound mismatch')
        witnesses.append(path_lower_bound_witness(n))
    (rec.path/'e4_path_witnesses.json').write_text(json.dumps(witnesses,indent=2))


def run_e5(rec,cfg):
    for family,n in [('path',cfg['size']),('cycle',cfg['size']),('grid',16)]:
        g=make_graph(family,n)
        for k in [2,3,5]:
            c,_=compile_certificate(g,tuple(range(k)),{'kind':'c2_rooted_min'},validate_cases=0)
            for regime in ['random','alternating','block','endpoint_min']:
                for s in range(cfg['seeds']):
                    x=input_vector(g,k,regime,derived_seed('e5',family,k,regime,s))
                    for name in ['p1','p2','b5_intersection','b5_repaired']:
                        rec.trial('e5',g,x,name,c if name=='p2' else None,
                                  seed=s,regime=regime)


def run_e6(rec,cfg):
    for n in [16,cfg['size']]:
        for degree in [3,4]:
            if n*degree%2:continue
            for s in range(cfg['seeds']):
                g=make_graph('regular',n,seed=derived_seed('e6',n,degree,s),degree=degree)
                c,_=compile_certificate(g,(0,1,2),{'kind':'c2_rooted_min'},validate_cases=0)
                for regime in ['random','endpoint_min']:
                    x=input_vector(g,3,regime,derived_seed(n,s,regime))
                    for prot in ['p1','p2','b3_center','b4_minmax']:
                        rec.trial('e6',g,x,prot,c if prot=='p2' else None,seed=s,regime=regime)


def run_e7(rec,cfg):
    examples=[]
    for family in ['path','cycle']:
        for n in [3,4,5,cfg['e7_n']]:
            g=make_graph(family,n)
            for x in product((0,1),repeat=n):
                baseline=rec.trial('e7',g,x,'p1',regime='exhaustive')
                bad=rec.trial('e7',g,x,'b5_intersection',regime='exhaustive',
                              extra={'trace':True})
                rec.trial('e7',g,x,'b5_repaired',regime='exhaustive')
                if bad['status']!='pass' and len(examples)<8:
                    _,trace=simulate(g,x,'b5_intersection',keep_trace=True)
                    examples.append({'graph':family,'n':n,'inputs':x,
                                     'baseline':baseline['stabilization_round'],
                                     'candidate_status':bad['status'],'trace':trace})
    (rec.path/'e7_candidate_failures.json').write_text(json.dumps(examples,indent=2))

RUNNERS={'e1':run_e1,'e2':run_e2,'e3':run_e3,'e4':run_e4,'e5':run_e5,'e6':run_e6,'e7':run_e7}


def run_all(out,config,selected=None):
    rec=Records(out);selected=selected or list(RUNNERS)
    try:
        for exp in selected:
            if exp not in RUNNERS:raise ValueError('unsupported experiment '+exp)
            RUNNERS[exp](rec,config)
    finally:rec.close()
    counts=[{'experiment':x,'status':y,'count':z} for (x,y),z in sorted(rec.counts.items())]
    (rec.path/'counts.json').write_text(json.dumps(counts,indent=2))
    (rec.path/'counterexamples.json').write_text(json.dumps(rec.failures,indent=2))
    stats={}
    for name,pairs in rec.pairs.items():
        a=[x for x,y in pairs.values()];b=[y for x,y in pairs.values()]
        if a:stats[name]=paired_summary(a,b)
    vals=[v['sign_test_two_sided_p'] for v in stats.values() if v['sign_test_two_sided_p'] is not None]
    corrected=holm(vals)
    for j,(key,v) in enumerate((key,v) for key,v in stats.items() if v['sign_test_two_sided_p'] is not None):
        v['holm_adjusted_p']=corrected[j]
    (rec.path/'paired_stats.json').write_text(json.dumps(stats,indent=2))
    return {'counts':counts,'stats':stats,'counterexamples':len(rec.failures),
            'trials_file':str(rec.path/'trials.csv')}
