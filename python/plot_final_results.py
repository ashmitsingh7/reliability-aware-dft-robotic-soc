import json, csv, ast, statistics
from pathlib import Path
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]; out=root/'results_final'/'plots'; out.mkdir(parents=True,exist_ok=True)
s=json.load(open(root/'results_final/campaign_summary.json'))['profiles']
labels=['reference','obs+fair','obs+fair+esc']; names=['s2a_all3_evid','s3_obs','s3_obs_esc']
for kind,fn in [('persistent','interruption_persistent.png'),('transient','interruption_transient.png')]:
 vals=[s[n][kind]['mean_interruption_cycles'] for n in names]
 fig,ax=plt.subplots(figsize=(6,3.5)); ax.bar(labels,vals,color=['#777','#2a9d8f','#e76f51']); ax.set_ylabel('Mean interruption cycles'); ax.set_title(kind.capitalize()+' faults; 2,515 paired episodes'); ax.tick_params(axis='x',rotation=15); fig.tight_layout(); fig.savefig(out/fn,dpi=180); plt.close(fig)
vals=[]
for row in csv.DictReader(open(root/'results_final/profiles/s3_obs/persistent_episodes.csv')):
 for x in ast.literal_eval(row['healthy_full_scan_delay_after_flag']):
  if x is not None: vals.append(float(x))
fig,ax=plt.subplots(figsize=(6,3.5)); ax.hist(vals,bins=range(0,156,5),color='#2a9d8f',edgecolor='white'); ax.axvline(154,color='#e76f51',linestyle='--',label='configured 154-tick criterion'); ax.set_xlabel('Post-flag healthy-block FULL delay (ticks)'); ax.set_ylabel('Episode/block observations'); ax.legend(); fig.tight_layout(); fig.savefig(out/'fairness_delay_histogram.png',dpi=180); plt.close(fig)
print('plots generated:', sorted(x.name for x in out.glob('*.png')))
