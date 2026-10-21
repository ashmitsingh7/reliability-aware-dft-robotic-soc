"""results/coverage.csv: per-block coverage by test mechanism (ATPG-level, from the fault database) and
campaign-level detection by scheduler."""
import csv
from fault_campaign import load_db
from common import *
def main():
    rows = load_db(); camp = {r["fault_id"]: r for r in csv.DictReader(open(RESULTS + "/fault_campaign.csv"))}
    out = []
    for b in BLOCKS + [dict(name="ALL")]:
        rs = [r for r in rows if b["name"] in ("ALL", r["block"])]; n = len(rs)
        f = lambda k: sum(1 for r in rs if k(r)) / n
        out.append(dict(block=b["name"], faults_collapsed=n, full_scan=f(lambda r: r["detect_full"]),
            partial_scan=f(lambda r: r["detect_partial"]), mbist=f(lambda r: r["detect_mbist"]) if b["name"] in ("regfile", "ALL") else "",
            online_any_window=f(lambda r: r["detect_online_mask"] > 0),
            online_single_window_mean=sum(bin(r["detect_online_mask"]).count("1") for r in rs) / (n * ONLINE_K),
            union_all_mechanisms=f(lambda r: r["detect_full"] or r["detect_mbist"] or r["detect_online_mask"]),
            campaign_baseline=sum(int(camp[r["fault_id"]]["baseline_detected"]) for r in rs) / n,
            campaign_adaptive=sum(int(camp[r["fault_id"]]["adaptive_detected"]) for r in rs) / n))
    with open(RESULTS + "/coverage.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    for o in out: print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items()})
if __name__ == "__main__": main()
