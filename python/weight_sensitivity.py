"""Sensitivity of the adaptive scheduler to the Eq.(2) weights (same faults, same injection times, same mission).
No 'optimal' weight set is claimed.  NOTE: the Faults_i term is zero before the first detection, so it cannot
influence first-detection metrics in this campaign design (documented limitation)."""
import csv
from fault_campaign import *
SETS = {"equal(1,1,1,1,1) [default]": (1, 1, 1, 1, 1), "crit_only": (1, 0, 0, 0, 0), "health_only": (0, 1, 0, 0, 0),
        "aging_only": (0, 0, 1, 0, 0), "faults_only": (0, 0, 0, 1, 0), "mission_only": (0, 0, 0, 0, 1),
        "crit_heavy(4,1,1,1,1)": (4, 1, 1, 1, 1), "health_heavy(1,4,1,1,1)": (1, 4, 1, 1, 1),
        "aging_heavy(1,1,4,1,1)": (1, 1, 4, 1, 1), "mission_heavy(1,1,1,1,4)": (1, 1, 1, 1, 4), "no_crit(0,1,1,1,1)": (0, 1, 1, 1, 1)}
def main():
    stats = load_stats(); rows = load_db(); trace = mission.generate(); M = len(trace); inj = injections(rows, M); out = []
    for name, w in SETS.items():
        P = Params(w=w, mode=0); L = timeline(P, trace, stats); LR = log_rows("adaptive", L, stats); rs = []
        for r, c0 in zip(rows, inj):
            a = first_detection(r, c0, L, P); rs.append(dict(det=a[0], cyc=a[1], name=a[2], state=a[3], cum=a[4], inj=c0))
        s = summarize(rows, rs, LR, M)
        online_by_blk = {BNAMES[b]: sum(1 for d in LR if d["n_online"] and d["selected_block"] == BNAMES[b]) for b in range(NB)}
        out.append(dict(weight_set=name, w1=w[0], w2=w[1], w3=w[2], w4=w[3], w5=w[4], fault_coverage=s["fault_coverage"],
                        mean_latency=s["mean_detection_latency_cycles"], censored_mean_latency=s["censored_mean_latency_cycles"],
                        total_test_cycles=s["total_test_cycles"], coverage_crit4=s["coverage_crit4"], coverage_crit1=s["coverage_crit1"],
                        **{f"online_tests_{k}": v for k, v in online_by_blk.items()}))
    with open(RESULTS + "/weight_sensitivity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    for o in out: print(f"{o['weight_set']:32s} cov={o['fault_coverage']:.4f} lat={o['censored_mean_latency']:.0f} cyc={o['total_test_cycles']}")
if __name__ == "__main__": main()
