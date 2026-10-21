"""docs/RESULTS_SUMMARY.md generated from results/*.csv (no hand-typed numbers)."""
import pandas as pd, json
from common import *
def md(df, fmt="{:.4g}"):
    cols = list(df.columns); out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows(): out.append("| " + " | ".join(fmt.format(v) if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)
def main():
    R = RESULTS; L = ["# Results summary (auto-generated from results/*.csv)\n"]
    st = json.load(open(R + "/atpg_stats.json"))
    a = pd.DataFrame([dict(block=k, state_bits=v["L"], faults_collapsed=v["faults_collapsed"], faults_uncollapsed=v["faults_uncollapsed"], patterns=v["patterns"],
        patterns_partial=v["patterns_partial"], atpg_aborted=v["atpg_aborted"], atpg_untestable=v["atpg_untestable"], fault_coverage=v["fault_coverage"],
        full_scan_cycles=v["full_scan_cycles"], partial_scan_cycles=v["partial_scan_cycles"]) for k, v in st.items() if k != "_meta"])
    L += ["## ATPG / scan (per block)\n", md(a), "\n## Coverage per test mechanism\n", md(pd.read_csv(R + "/coverage.csv")),
          "\n## Baseline vs adaptive\n", md(pd.read_csv(R + "/baseline_vs_adaptive.csv")),
          "\n## Baseline period sweep\n", md(pd.read_csv(R + "/baseline_period_sweep.csv")[["config", "fault_coverage", "mean_detection_latency_cycles", "censored_mean_latency_cycles", "total_test_cycles", "mission_interruption_cycles", "coverage_per_mcycle"]]),
          "\n## Weight sensitivity\n", md(pd.read_csv(R + "/weight_sensitivity.csv")),
          "\n## Synthesis (Yosys generic cells; timing/power NOT evaluated)\n", md(pd.read_csv(R + "/synthesis.csv")),
          "\n## MBIST fault classes (RTL simulation)\n", md(pd.read_csv(R + "/mbist_fault_coverage.csv"))]
    open(ROOT + "/docs/RESULTS_SUMMARY.md", "w").write("\n".join(L) + "\n"); print("written")
if __name__ == "__main__": main()
