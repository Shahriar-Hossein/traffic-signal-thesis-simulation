import csv,glob,json,sys,os
sys.path.insert(0,'.')
from core.policy import priority_green
D="data/study_collection_20260929"
out={}
for p in sorted(glob.glob(D+"/*_seed*/")):
    n=os.path.basename(p.rstrip("/"))
    fs=glob.glob(p+"priority/*_phases.csv")
    if not fs: continue
    bad=[];ph=0
    for r in csv.DictReader(open(fs[0])):
        ph+=1
        w=json.loads(r['decision_counts'])[r['direction']]
        if int(float(r['green_selected_sec']))!=priority_green(w):
            bad.append((r['round_index'],r['phase_index'],r['direction'],r['green_selected_sec'],priority_green(w),w))
    out[n]=(ph,bad)
    if bad: print(n,bad)
print("plans",len(out),"phases",sum(v[0] for v in out.values()),"mismatch plans",sum(1 for v in out.values() if v[1]))
