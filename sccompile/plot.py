"""Dependency-free vector plots from real experiment rows (F1-F5)."""
from __future__ import annotations
import csv,html
from pathlib import Path
from collections import defaultdict


def create_figures(raw_csv,outdir):
    with Path(raw_csv).open(newline='',encoding='utf8') as file:
        rows=list(csv.DictReader(file))
    dest=Path(outdir);dest.mkdir(parents=True,exist_ok=True)
    specs={
      'F1_graph_scaling':('e3','n','stabilization_round','Graph size (n)','Stabilization rounds'),
      'F2_path_tightness':('e4','n','stabilization_round','Path size (n)','Stabilization rounds'),
      'F3_message_cost':('e3','n','message_payload_items','Graph size (n)','Payload items'),
      'F4_output_changes':('e5','n','output_changes','Graph size (n)','Output changes'),
      'F5_regular_graph_scaling':('e6','diameter','stabilization_round','Graph diameter','Stabilization rounds')}
    files=[]
    for fname,(exp,xfield,yfield,xlabel,ylabel) in specs.items():
        by=defaultdict(list)
        for r in rows:
            if r['experiment']!=exp or r['status']!='pass':continue
            try:x=float(r[xfield]);y=float(r[yfield])
            except (ValueError,TypeError):continue
            by[r['protocol']+' / '+r['graph_family']].append((x,y))
        colors=['#2563eb','#ea580c','#16a34a','#9333ea','#dc2626','#0891b2','#a16207']
        W,H=860,470;left,bottom,right,top=85,395,820,45
        allpoints=[p for items in by.values() for p in items]
        xs=[x for x,y in allpoints] or [0,1];ys=[y for x,y in allpoints] or [0,1]
        xmin,xmax=min(xs),max(xs);ymin,ymax=min(0,min(ys)),max(ys)
        if xmin==xmax:xmax=xmin+1
        if ymin==ymax:ymax=ymin+1
        def pos(x,y):return (left+(x-xmin)/(xmax-xmin)*(right-left),bottom-(y-ymin)/(ymax-ymin)*(bottom-top))
        lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
               '<rect width="100%" height="100%" fill="white"/>',
               f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#222"/>',
               f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#222"/>',
               f'<text x="400" y="447" fill="#111" font-size="15" text-anchor="middle">{html.escape(xlabel)}</text>',
               f'<text x="20" y="240" transform="rotate(-90 20 240)" fill="#111" font-size="15" text-anchor="middle">{html.escape(ylabel)}</text>']
        for j in range(5):
            y=ymin+(ymax-ymin)*j/4
            yp=pos(xmin,y)[1]
            lines += [f'<line x1="{left}" y1="{yp:.1f}" x2="{right}" y2="{yp:.1f}" stroke="#e5e7eb"/>',
                      f'<text x="{left-9}" y="{yp+4:.1f}" text-anchor="end" font-size="11">{y:.2g}</text>']
        for j in range(5):
            x=xmin+(xmax-xmin)*j/4;xp=pos(x,ymin)[0]
            lines.append(f'<text x="{xp:.1f}" y="{bottom+18}" text-anchor="middle" font-size="11">{x:.2g}</text>')
        for i,(series,coords) in enumerate(sorted(by.items())):
            color=colors[i%len(colors)];coords.sort()
            seq=' '.join(f'{u:.1f},{v:.1f}' for x,y in coords for u,v in [pos(x,y)])
            lines.append(f'<polyline points="{seq}" stroke="{color}" fill="none" stroke-width="2"/>')
            for x,y in coords:
                u,v=pos(x,y);lines.append(f'<circle cx="{u:.1f}" cy="{v:.1f}" r="3" fill="{color}"/>')
        lines.append('<g font-size="10">')
        for i,series in enumerate(sorted(by)):
            x=460;y=55+14*i
            lines.append(f'<text x="{x}" y="{y}" fill="{colors[i%len(colors)]}">{html.escape(series)}</text>')
        lines.append('</g></svg>')
        path=dest/(fname+'.svg');path.write_text('\n'.join(lines));files.append(str(path))
    return files
