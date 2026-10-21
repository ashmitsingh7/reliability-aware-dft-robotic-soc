"""Matplotlib figures from results/*.csv -> results/plots/"""
import os, pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from common import *
def main():
    P = RESULTS + "/plots"; os.makedirs(P, exist_ok=True)
    fc = pd.read_csv(RESULTS + "/fault_campaign.csv"); sr = pd.read_csv(RESULTS + "/scheduler_results.csv")
    ws = pd.read_csv(RESULTS + "/weight_sensitivity.csv"); sw = pd.read_csv(RESULTS + "/baseline_period_sweep.csv")
    A = sr[sr["mode"] == "adaptive"]; B = sr[sr["mode"] == "baseline_N20"]
    def save(n): plt.tight_layout(); plt.savefig(f"{P}/{n}.png", dpi=130); plt.close()
    # 1 coverage by block
    g = fc.groupby("block")[["baseline_detected", "adaptive_detected"]].mean().reindex(BNAMES)
    g.plot.bar(); plt.ylabel("fault coverage (campaign)"); plt.title("Fault coverage per block: baseline(N=20) vs adaptive"); save("1_fault_coverage")
    # 2 latency
    plt.figure(); plt.hist([fc.baseline_latency_cycles.dropna(), fc.adaptive_latency_cycles.dropna()], bins=30, label=["baseline N=20", "adaptive"])
    plt.xlabel("detection latency (cycles)"); plt.legend(); plt.title("Detection latency (detected faults only)"); save("2_detection_latency")
    # 3 test cycles
    plt.figure(); plt.bar(["baseline N=20", "adaptive"], [B.test_cycles.sum(), A.test_cycles.sum()], label="total")
    plt.bar(["baseline N=20", "adaptive"], [B.interruption_cycles.sum(), A.interruption_cycles.sum()], label="mission-interrupting")
    plt.ylabel("test cycles over mission"); plt.legend(); save("3_test_cycles")
    # 4 tests by block
    t = pd.DataFrame({b: [((B.selected_block.isin([b, "ALL"])) & (B.test_cycles > 0)).sum(), ((A.selected_block == b) & (A.test_cycles > 0)).sum()] for b in BNAMES}, index=["baseline", "adaptive"])
    t.T.plot.bar(); plt.ylabel("test decisions"); plt.title("Tests per block"); save("4_tests_by_block")
    # 5 decisions by state
    d = A[A.test_cycles > 0].groupby(["state", "test_types"]).size().unstack(fill_value=0)
    d.plot.bar(stacked=True); plt.ylabel("decisions"); plt.title("Adaptive scheduler decisions by state"); save("5_decisions_by_state")
    # 6 priority evolution
    plt.figure(figsize=(9, 4))
    for b in BNAMES: plt.plot(A.tick, A[f"prio_{b}"], label=b, lw=.8)
    plt.xlabel("tick"); plt.ylabel("Priority_i (Eq. 2, equal weights)"); plt.legend(); save("6_priority_evolution")
    # 7 aging/health
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    for b in BNAMES: ax[0].plot(A.tick, A[f"aging_{b}"], label=b); ax[1].plot(A.tick, A[f"health_{b}"], label=b, lw=.7)
    ax[0].set_title("behavioural aging score"); ax[1].set_title("health term (incl. staleness)"); ax[0].legend()
    st = A.state.map({"IDLE": 0, "ACTIVE": 1, "DEGRADED": 2}); ax[0].fill_between(A.tick, 0, 255 * (st == 2), alpha=.1, color="r", label="DEGRADED")
    save("7_aging_health_evolution")
    # 8 weight sensitivity
    fig, ax = plt.subplots(1, 2, figsize=(11, 4)); ax[0].barh(ws.weight_set, ws.fault_coverage); ax[0].set_xlim(.75, .86); ax[0].set_title("coverage")
    ax[1].barh(ws.weight_set, ws.censored_mean_latency); ax[1].set_title("censored mean latency (cycles)"); ax[1].set_yticks([]); save("8_weight_sensitivity")
    # 9 baseline period sweep (coverage vs test cycles)
    plt.figure(); plt.plot(sw.total_test_cycles[1:], sw.fault_coverage[1:], "o-", label="baseline N=5..80")
    plt.plot(sw.total_test_cycles[0], sw.fault_coverage[0], "r*", ms=14, label="adaptive"); plt.xscale("log")
    plt.xlabel("total test cycles"); plt.ylabel("fault coverage"); plt.legend(); save("9_coverage_vs_test_cycles")
    print("plots written:", sorted(os.listdir(P)))
if __name__ == "__main__": main()
