"""Bounded scheduler-level exploration of simplified SAW parent-CAS transition model.

Models arbitrary process stalls at each atomic load / CAS step. CAS acts as an
x86-TSO locked RMW; the only DSU writes are CAS, so store buffers are empty in
this submodel. This is *not* a replacement for Nidhugg/GenMC/RC11 checking of
compiled C++ nor a proof of unrestricted C++ correctness.
"""
from __future__ import annotations
import json
from collections import deque
from dataclasses import dataclass, replace
from .history_checker import check

@dataclass(frozen=True)
class Proc:
    index: int = 0
    stage: str = "start"
    cur: int = 0
    rx: int = -1
    ry: int = -1
    hi: int = -1
    lo: int = -1
    observed: tuple[int, int] = (-1, -1)
    start: int = 0
    split_node: int = -1
    split_parent: int = -1
    split_grand: int = -1
    split_word: tuple[int,int] = (-1,-1)
    resume_stage: str = ""

@dataclass(frozen=True)
class State:
    words: tuple[tuple[int, int], ...]
    procs: tuple[Proc, ...]
    history: tuple[tuple, ...] = ()
    steps: int = 0


def step(s: State, tid: int, traces: list[list[tuple]], unsafe: bool = False, variant: str = "p1"):
    p = s.procs[tid]
    if p.index >= len(traces[tid]):
        return None
    kind, x, y = traces[tid][p.index]
    words = list(s.words)
    events = list(s.history)
    stage = p.stage
    if stage == "start":
        p = replace(p, stage="find_x", cur=x, rx=-1, ry=-1, start=s.steps)
    elif stage in ("find_x", "find_y"):
        parent, _ = words[p.cur]
        if parent == p.cur:
            if stage == "find_x":
                p = replace(p, rx=p.cur, cur=y, stage="find_y" if kind == "unite" else "complete_find")
            else:
                p = replace(p, ry=p.cur, stage="compare")
        else:
            if variant == "a3":
                p = replace(p, split_node=p.cur, split_parent=parent,
                            split_word=words[p.cur], resume_stage=stage, stage="split_load")
            else:
                p = replace(p, cur=parent)
    elif stage == "split_load":
        grand = words[p.split_parent][0]
        if grand < p.split_parent:
            p = replace(p, split_grand=grand,stage="split_cas")
        else:
            p = replace(p,cur=p.split_parent,stage=p.resume_stage)
    elif stage == "split_cas":
        if words[p.split_node] == p.split_word:
            words[p.split_node] = (p.split_grand,p.split_word[1]+1)
        p = replace(p,cur=p.split_parent,stage=p.resume_stage)
    elif stage == "complete_find":
        events.append((p.start, s.steps + 1, tid, kind, x, y, p.rx))
        p = replace(p, index=p.index+1, stage="start")
    elif stage == "compare":
        if p.rx == p.ry:
            p = replace(p, stage="complete_false")
        else:
            p = replace(p, hi=max(p.rx,p.ry), lo=min(p.rx,p.ry), stage="validate")
    elif stage == "complete_false":
        events.append((p.start, s.steps+1, tid, kind, x, y, 0))
        p = replace(p, index=p.index+1, stage="start")
    elif stage == "validate":
        observed = words[p.hi]
        if observed[0] != p.hi:
            p = replace(p,stage="find_x",cur=x)
        else:
            p = replace(p,observed=observed,stage="commit")
    elif stage == "commit":
        if unsafe or words[p.hi] == p.observed:
            words[p.hi] = (p.lo, 0 if variant in ("b3","a1") else p.observed[1]+1)
            p = replace(p, stage="complete_true")
        else:
            p = replace(p,stage="find_x",cur=x)
    elif stage == "complete_true":
        events.append((p.start, s.steps+1, tid, kind, x, y, 1))
        p = replace(p, index=p.index+1, stage="start")
    else:
        raise AssertionError(stage)
    procs=list(s.procs);procs[tid]=p
    return State(tuple(words),tuple(procs),tuple(events),s.steps+1)


def invariant(state: State):
    return all(0<=parent<=i for i,(parent,_) in enumerate(state.words))


def final_partition_valid(state: State, traces: list[list[tuple]], n: int):
    parent=list(range(n))
    def find(x):
        while parent[x]!=x:x=parent[x]
        return x
    for tt in traces:
        for kind,x,y in tt:
            if kind == "unite":
                a,b=find(x),find(y)
                if a!=b:parent[max(a,b)]=min(a,b)
    def actual(x):
        while state.words[x][0]!=x:x=state.words[x][0]
        return x
    return all((find(i)==find(j)) == (actual(i)==actual(j))
               for i in range(n) for j in range(n))


def explore(n=3, programs=None, model="sc", max_states=100000, unsafe=False, variant="p1"):
    if programs is None:
        programs=[[('unite',2,1)],[('unite',2,0)]]
    if model not in ("sc", "tso"):raise ValueError("model must be sc or tso")
    if variant not in ("p1","b3","b4","a1","a2","a3"):
        raise ValueError("unsupported operational variant")
    programs = [[tuple(op) for op in program] for program in programs]
    if n<2 or n>6 or len(programs)>3 or sum(map(len,programs))>8:
        raise ValueError("small-instance bounded checking only")
    if any(not (0<=x<n and 0<=y<n and kind in ("find","unite"))
           for program in programs for kind,x,y in program):
        raise ValueError("invalid operation")
    init=State(tuple((i,0) for i in range(n)),tuple(Proc() for _ in programs))
    queue=deque([(init,())]);seen={replace(init,steps=0):True};completed=0
    while queue:
        state,trace=queue.popleft()
        if len(seen)>max_states:
            return {"status":"bound_reached","states":len(seen),"completed_schedules":completed,
                    "model":model,"variant":variant,"checker":"operational", "counterexample":None}
        if not invariant(state):
            return {"status":"counterexample","failure":"monotonicity","trace":trace,
                    "state":repr(state),"states":len(seen),"model":model,"variant":variant}
        if all(p.index==len(programs[i]) for i,p in enumerate(state.procs)):
            completed+=1
            es=[{"start":a,"end":b,"tid":tid,"op":k,"x":x,"y":y,"result":r}
                for a,b,tid,k,x,y,r in state.history]
            verdict=check(es,n)
            if not verdict["linearizable"] or not final_partition_valid(state,programs,n):
                return {"status":"counterexample", "failure":"linearizability_or_partition",
                        "trace":trace,"events":es,"words":state.words,"states":len(seen),
                        "model":model,"oracle":verdict,"variant":variant}
            continue
        for tid in range(len(programs)):
            new=step(state,tid,programs,unsafe,variant)
            if new is None:continue
            # The logical event counter is not part of abstract program state; it
            # remains in the key because it determines real-time constraints.
            if new not in seen:
                seen[new]=True;queue.append((new,trace+(tid,)))
    return {"status":"no_counterexample_within_bounds", "states":len(seen),
            "completed_schedules":completed,"model":model,"variant":variant,"checker":"operational",
            "counterexample":None, "programs":programs, "scope":"CAS-only operational submodel"}


def store_buffering_litmus(model="tso"):
    """Store-buffering litmus: x=y=0, P0: x=1; r0=y, P1: y=1; r1=x.

    In SC outcome (0,0) is impossible; TSO may buffer both stores so it occurs.
    This is *not* a DSU counterexample (DSU writes are locked CAS).
    """
    if model not in ("sc","tso"):raise ValueError(model)
    init=(0,0,(),(),0,0,-1,-1)
    # x,y,buffer0,buffer1,pc0,pc1,r0,r1; store buffer (var, val) FIFO
    todo=deque([init]);seen={init};outcomes=set()
    while todo:
        x,y,b0,b1,p0,p1,r0,r1=st=todo.popleft()
        if p0==2 and p1==2 and not b0 and not b1:
            outcomes.add((r0,r1));continue
        successors=[]
        for tid in (0,1):
            pc=p0 if tid==0 else p1
            if pc==0:
                if model=="tso":
                    successors.append((x,y,b0+((0,1),),b1,1,p1,r0,r1) if tid==0 else
                                      (x,y,b0,b1+((1,1),),p0,1,r0,r1))
                else:
                    successors.append((1,y,b0,b1,1,p1,r0,r1) if tid==0 else
                                      (x,1,b0,b1,p0,1,r0,r1))
            elif pc==1:
                if tid==0: successors.append((x,y,b0,b1,2,p1,y,r1))
                else: successors.append((x,y,b0,b1,p0,2,r0,x))
        if b0:successors.append((b0[0][1],y,b0[1:],b1,p0,p1,r0,r1))
        if b1:successors.append((x,b1[0][1],b0,b1[1:],p0,p1,r0,r1))
        for nxt in successors:
            if nxt not in seen:seen.add(nxt);todo.append(nxt)
    return {"model":model,"outcomes":sorted(map(list,outcomes)),"permits_0_0":(0,0) in outcomes,
            "purpose":"model sanity litmus, not a DSU execution"}


def run_suite(output, bounds=(3,4), models=("sc","tso"), max_states=100000):
    from pathlib import Path
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    programs=[[[('unite',2,1)],[('unite',2,0)]],
              [[('unite',2,1),('find',2,0)],[('unite',1,0)]],
              [[('find',2,0),('unite',2,1)],[('unite',2,0)]]]
    results=[]
    variants=("p1","b3","b4","a1","a2","a3")
    for model in models:
        results.append({"suite":"litmus","result":store_buffering_litmus(model)})
        for n in bounds:
            for i,program in enumerate(programs):
                for variant in variants:
                    result=explore(n,program,model,max_states,variant=variant)
                    record={"suite":"saw_dsu","scenario":i,"n":n,"variant":variant,"result":result}
                    results.append(record)
                    if result["status"]=="counterexample":
                        (out/f"counterexample_{model}_{n}_{i}_{variant}.json").write_text(json.dumps(record,indent=2))
    negative=explore(5,[[('unite',4,3)],[('unite',4,2)]],"sc",max_states,unsafe=True)
    results.append({"suite":"deliberately_unsafe_blind_write","result":negative})
    if negative["status"]=="counterexample":
        (out/"unsafe_counterexample.json").write_text(json.dumps(negative,indent=2))
    (out/"verdicts.json").write_text(json.dumps(results,indent=2))
    return results

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="output/manual-verification")
    parser.add_argument("--max-states",type=int,default=100000)
    a=parser.parse_args()
    print(json.dumps(run_suite(a.output,max_states=a.max_states),indent=2))
