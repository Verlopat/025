"""Trial-level descriptive statistics, paired comparisons, and six SVG figures.

No operation-level pseudoreplication. CSV/SVG work without third-party packages.
SciPy/pandas/pyarrow/matplotlib improve artifacts if installed.
"""
from __future__ import annotations
import csv
import json
import math
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

NUMERIC=("seconds","throughput","median_us","p95_us","p99_us","loads","cas","retries","hops","splits","submitted","completed","rss_mib")

def median(x):return st.median(x) if x else float("nan")
def quantile(x,p):
    if not x:return float("nan")
    x=sorted(x);j=(len(x)-1)*p;i=int(j)
    return x[i] if i+1==len(x) else x[i]+(j-i)*(x[i+1]-x[i])

def bootstrap_ci(x, statistic=median, resamples=1000, seed=123):
    if not x:return (None,None)
    rand=random.Random(seed);nums=[]
    for _ in range(resamples):
        nums.append(statistic([rand.choice(x) for _ in x]))
    return (quantile(nums,.025),quantile(nums,.975))

def sign_flip_paired_p(diffs, seed=99, samples=8192):
    """Two-sided paired sign-flip permutation test; exact for n <= 14."""
    a=[abs(float(d)) for d in diffs if d != 0]
    if not a:return 1.0
    obs=abs(sum(diffs));n=len(a)
    if n<=14:
        return sum(abs(sum(v*(1 if bits&(1<<i) else -1) for i,v in enumerate(a))) >= obs - 1e-9
                   for bits in range(1<<n))/(1<<n)
    rng=random.Random(seed)
    exceed=0
    for _ in range(samples):
        if abs(sum(x*(1 if rng.randrange(2) else -1) for x in a)) >= obs-1e-9:
            exceed+=1
    return (exceed+1)/(samples+1)

def holm(pvalues):
    n=len(pvalues);order=sorted(range(n),key=lambda i:pvalues[i]);res=[1.0]*n;last=0.0
    for j,i in enumerate(order):
        last=max(last,min(1.0,pvalues[i]*(n-j)))
        res[i]=last
    return res

def write_csv(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields or ["status"])
        writer.writeheader();writer.writerows(rows)

def values(rows,key):
    out=[]
    for r in rows:
        if r.get("run_status")!="completed":continue
        try:out.append(float(r[key]))
        except (KeyError,TypeError,ValueError):pass
    return out

def aggregate(rows, metric="throughput"):
    groups=defaultdict(list)
    for r in rows:
        k=(r["experiment"],r["workload"],r["variant"],r["n"],r["threads"],
           r.get("pause_hook","none"),r.get("pause_us","0"))
        groups[k].append(r)
    summary=[]
    for key,items in sorted(groups.items()):
        v=values(items,metric)
        if not v:continue
        lo,hi=bootstrap_ci(v)
        summary.append(dict(zip(("experiment","workload","variant","n","threads","pause_hook","pause_us"),key)) | {
            "metric":metric,"trials":len(items),"valid_trials":len(v),
            "median":median(v),"q1":quantile(v,.25),"q3":quantile(v,.75),
            "mean":st.mean(v),"std":st.stdev(v) if len(v)>1 else 0.0,
            "ci_low":lo,"ci_high":hi})
    return summary

def paired_comparisons(rows,metric="throughput"):
    groups=defaultdict(dict)
    for r in rows:
        if r.get("run_status")!="completed":continue
        key=(r["experiment"],r["workload"],r["n"],r["threads"],
             r.get("pause_hook","none"),r.get("pause_us","0"))
        trial=(r["block"],r["repeat"],r["seed"])
        try:groups[key].setdefault(r["variant"],{})[trial]=float(r[metric])
        except (ValueError,KeyError):pass
    out=[]
    for key,methods in groups.items():
        if "p1" not in methods:continue
        for baseline in sorted(m for m in methods if m!="p1"):
            shared=methods["p1"].keys() & methods[baseline].keys()
            diffs=[methods["p1"][t]-methods[baseline][t] for t in sorted(shared)]
            if not diffs:continue
            lo,hi=bootstrap_ci(diffs)
            p=sign_flip_paired_p(diffs)
            out.append(dict(zip(("experiment","workload","n","threads","pause_hook","pause_us"),key)) |
                       {"metric":metric,"baseline":baseline,"pairs":len(diffs),"median_p1_minus_baseline":median(diffs),
                        "ci_low":lo,"ci_high":hi,"p_permutation":p,
                        "rank_biserial":rank_biserial(diffs)})
    adjusted=holm([r["p_permutation"] for r in out])
    for r,p in zip(out,adjusted):r["p_holm"] = p
    return out

def rank_biserial(diffs):
    ds=[(abs(v),1 if v>0 else -1) for v in diffs if v!=0]
    if not ds:return 0.0
    indexed=sorted(enumerate(ds),key=lambda x:x[1][0]);ranks=[0.0]*len(ds)
    i=0
    while i<len(indexed):
        j=i+1
        while j<len(indexed) and indexed[j][1][0]==indexed[i][1][0]:j+=1
        for k in range(i,j):ranks[indexed[k][0]]=(i+1+j)/2
        i=j
    pos=sum(r for r,(_,sign) in zip(ranks,ds) if sign==1)
    neg=sum(r for r,(_,sign) in zip(ranks,ds) if sign==-1)
    return (pos-neg)/(pos+neg)

def _svg_chart(path, title, records, field="value"):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    W,H=980,460;left=95;right=30;top=65;bottom=115
    ymax=max([max(0.0,float(r[field])) for r in records]+[1.0])*1.2
    plot_w=W-left-right;plot_h=H-top-bottom
    bars=[]
    for i,r in enumerate(records):
        x=left+(i+.12)*(plot_w/max(1,len(records)));width=.76*(plot_w/max(1,len(records)))
        v=max(0.0,float(r[field]));y=top+plot_h*(1-v/ymax);h=top+plot_h-y
        label=str(r.get("label",f"{i+1}"))
        bars.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{h:.2f}" fill="#2A628F"/>')
        bars.append(f'<text x="{x+width/2:.2f}" y="{top+plot_h+20}" text-anchor="middle" font-size="11" transform="rotate(30 {x+width/2:.2f} {top+plot_h+20})">{_xml(label)}</text>')
    ticks=''.join(f'<text x="{left-10}" y="{top+plot_h*(1-i/4)+5:.2f}" text-anchor="end" font-size="12">{ymax*i/4:.2g}</text>'
                  for i in range(5))
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
         f'<rect width="{W}" height="{H}" fill="white"/>'
         f'<text x="{W/2}" y="30" font-size="20" text-anchor="middle">{_xml(title)}</text>'
         f'<path d="M {left} {top} V {top+plot_h} H {W-right}" stroke="black" fill="none"/>'
         f'{ticks}{"".join(bars)}<text x="{left}" y="{H-20}" font-size="11">'
         'Bars show observed pilot trial summaries, not theoretical guarantees.</text></svg>')
    path.write_text(svg)

def _xml(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def make_figures(rows,verification,directory):
    figs=Path(directory);figs.mkdir(parents=True,exist_ok=True)
    output={}
    metrics=[("F2_throughput.svg","Throughput by method (ops/s)","throughput","e3"),
             ("F3_latency.svg","Median operation latency (microseconds)","median_us","e3"),
             ("F4_retries.svg","Mean retries per completed operation","retries","e4"),
             ("F5_parent_loads.svg","Parent loads per completed operation","loads","e5"),
             ("F6_completion.svg","Completion ratio under pause injection","completed","e4")]
    vplot=[]
    for r in verification:
        if r.get("suite")=="saw_dsu":
            verdict=r["result"];vplot.append({"label":f'{verdict["model"]}-n{r["n"]}-s{r["scenario"]}',
                                             "value":1 if verdict["status"]=="no_counterexample_within_bounds" else 0})
    _svg_chart(figs/"F1_verification.svg","Bounded operational verification (1=clean within bounds)",vplot)
    output["F1_verification.svg"]=len(vplot)
    for filename,title,metric,exp in metrics:
        groups=defaultdict(list)
        for r in rows:
            if r.get("experiment")!=exp or r.get("run_status")!="completed":continue
            groups[(r["variant"],r["workload"])].append(r)
        plot=[]
        for (variant,workload),group in sorted(groups.items()):
            if metric=="retries":
                vals=[float(r["retries"])/max(1,int(r["completed"])) for r in group]
            elif metric=="loads":
                vals=[float(r["loads"])/max(1,int(r["completed"])) for r in group]
            elif filename=="F6_completion.svg":
                vals=[float(r["completed"])/max(1,int(r["submitted"])) for r in group]
            else: vals=values(group,metric)
            if vals:plot.append({"label":variant+"-"+workload,"value":median(vals)})
        _svg_chart(figs/filename,title,plot[:24]);output[filename]=len(plot)
    try:
        import matplotlib.pyplot as plt
        for filename in output:
            # Preserve self-contained SVG as authoritative; PDF conversion optional.
            try:
                import cairosvg
                cairosvg.svg2pdf(url=str(figs/filename),write_to=str(figs/filename.replace(".svg",".pdf")))
            except ImportError:break
    except ImportError:pass
    return output

def analyze(run):
    run=Path(run);raw=run/"results"/"raw"
    derived=run/"results"/"derived";derived.mkdir(exist_ok=True,parents=True)
    with (raw/"all_trials.csv").open(newline="") as f:rows=list(csv.DictReader(f))
    for metric in ("throughput","median_us","p99_us","loads","cas","retries","completed"):
        write_csv(derived/f"summary_{metric}.csv",aggregate(rows,metric))
        write_csv(derived/f"paired_{metric}.csv",paired_comparisons(rows,metric))
    # Report statuses instead of treating failures as missing-zero performance values.
    statuses=defaultdict(int)
    for r in rows:statuses[(r["experiment"],r["run_status"])]+=1
    status_rows=[{"experiment":x,"status":y,"count":count} for (x,y),count in sorted(statuses.items())]
    write_csv(derived/"run_statuses.csv",status_rows)
    vpath=run/"verify"/"verdicts.json"
    verification=json.loads(vpath.read_text()) if vpath.exists() else []
    if verification:
        write_csv(derived/"T2_verification.csv",[
            {"suite":x["suite"],"n":x.get("n", ""),"model":x["result"].get("model",""),
             "scenario":x.get("scenario",""),"status":x["result"].get("status",""),
             "states":x["result"].get("states","")} for x in verification])
    for exp,filename in (("e3","T3_performance.csv"),("e4","T5_pauses.csv"),
                         ("e5","T4_work.csv"),("e6","T6_stability.csv")):
        write_csv(derived/filename,[r for r in aggregate(rows) if r["experiment"]==exp])
    figures=make_figures(rows,verification,run/"figures")
    statuses_json={f"{e}:{s}":n for (e,s),n in statuses.items()}
    info={"total_trials":len(rows),"statuses":statuses_json,"figures":figures,
          "analysis_unit":"paired benchmark trial, not individual operation",
          "statistical_test":"two-sided paired sign-flip permutation, Holm correction",
          "confidence_interval":"percentile bootstrap, 1000 resamples (pilot)",
          "derived_path":str(derived)}
    (derived/"analysis_summary.json").write_text(json.dumps(info,indent=2))
    return info

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("run_folder");a=ap.parse_args()
    print(json.dumps(analyze(a.run_folder),indent=2))
