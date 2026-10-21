"""Builds results/baseline_vs_adaptive.csv (metric table) from fault_campaign.csv + scheduler_results.csv."""
import csv, pandas as pd
from common import *
def main():
    fc = pd.read_csv(RESULTS + "/fault_campaign.csv"); sr = pd.read_csv(RESULTS + "/scheduler_results.csv")
    M = sr[sr["mode"] == "adaptive"].shape[0]; mend = M * EPOCH_CYCLES; rows = []
    def metric(name, a, b): rows.append(dict(metric=name, adaptive=a, baseline_N20=b))
    for tag, col in (("adaptive", "adaptive"), ("baseline", "baseline")): pass
    def S(mode): return sr[sr["mode"] == mode]
    for lab, key, mode in (("a", "adaptive", "adaptive"), ("b", "baseline", "baseline_N20")): pass
    A, B = S("adaptive"), S("baseline_N20")
    metric("faults_injected", len(fc), len(fc))
    metric("fault_coverage", fc.adaptive_detected.mean(), fc.baseline_detected.mean())
    for k, nm in ((4, "safety"), (3, "motor/encoder"), (2, "comm"), (1, "regfile")):
        s = fc[fc.criticality == k]; metric(f"coverage_criticality_{k}_{nm}", s.adaptive_detected.mean(), s.baseline_detected.mean())
    la = (fc.adaptive_latency_cycles.dropna()); lb = fc.baseline_latency_cycles.dropna()
    metric("mean_detection_latency_cycles", la.mean(), lb.mean()); metric("median_detection_latency_cycles", la.median(), lb.median())
    metric("p95_detection_latency_cycles", la.quantile(.95), lb.quantile(.95))
    ca = fc.apply(lambda r: r.adaptive_latency_cycles if r.adaptive_detected else mend - r.injected_cycle, axis=1)
    cb = fc.apply(lambda r: r.baseline_latency_cycles if r.baseline_detected else mend - r.injected_cycle, axis=1)
    metric("censored_mean_latency_cycles(undetected=mission_end)", ca.mean(), cb.mean())
    metric("total_test_cycles", A.test_cycles.sum(), B.test_cycles.sum())
    metric("mission_interruption_cycles", A.interruption_cycles.sum(), B.interruption_cycles.sum())
    metric("test_overhead_pct_of_mission", 100 * A.test_cycles.sum() / mend, 100 * B.test_cycles.sum() / mend)
    metric("interruption_overhead_pct", 100 * A.interruption_cycles.sum() / mend, 100 * B.interruption_cycles.sum() / mend)
    for c, nm in (("n_full_scan", "full_scans"), ("n_partial_scan", "partial_scans"), ("n_mbist", "mbist_runs"), ("n_online", "online_tests")):
        metric(nm, A[c].sum(), B[c].sum())
    for b in BNAMES:
        metric(f"tests_on_{b}", ((A.selected_block == b) & (A.test_cycles > 0)).sum(), ((B.selected_block.isin([b, "ALL"])) & (B.test_cycles > 0)).sum())
    metric("coverage_per_Mcycle", fc.adaptive_detected.mean() / (A.test_cycles.sum() / 1e6), fc.baseline_detected.mean() / (B.test_cycles.sum() / 1e6))
    for st in ("IDLE", "ACTIVE", "DEGRADED"):
        metric(f"detections_while_{st}", (fc.adaptive_state_at_detection == st).sum(), (fc.baseline_state_at_detection == st).sum())
    for st in ("IDLE", "ACTIVE", "DEGRADED"):
        metric(f"ticks_in_{st}", (A.state == st).sum(), (B.state == st).sum())
    for tt in ("FULL_SCAN", "PARTIAL_SCAN", "MBIST", "ONLINE"):
        metric(f"detections_by_{tt}", (fc.adaptive_test_type == tt).sum(), (fc.baseline_test_type == tt).sum())
    metric("test_duration_mean_cycles_per_decision", A[A.test_cycles > 0].test_cycles.mean(), B[B.test_cycles > 0].test_cycles.mean())
    metric("faults_detected_only_by_adaptive", ((fc.adaptive_detected == 1) & (fc.baseline_detected == 0)).sum(), "")
    metric("faults_detected_only_by_baseline", "", ((fc.adaptive_detected == 0) & (fc.baseline_detected == 1)).sum())
    metric("faster_detection_adaptive_vs_baseline(both detected)", ((fc.adaptive_latency_cycles < fc.baseline_latency_cycles)).sum(), "")
    pd.DataFrame(rows).to_csv(RESULTS + "/baseline_vs_adaptive.csv", index=False)
    print(pd.DataFrame(rows).round(3).to_string(index=False))
if __name__ == "__main__": main()
