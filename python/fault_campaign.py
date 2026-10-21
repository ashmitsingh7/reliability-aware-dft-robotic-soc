"""Automated fault campaign: baseline (fixed schedule) vs adaptive (reliability-aware) on the SAME DUT, SAME
mission trace, SAME faults and SAME injection times.
Per fault: reset manager -> inject at cycle c0 -> run scheduler -> record first detecting test.
Efficiency note: before the first detection the Reliability Manager's inputs are identical to the fault-free run
(a test that passes produces no event), so the fault-free decision log is reused for the scan over decisions.
--verify N re-runs N faults by literally stepping the manager with feedback and asserts identical outcomes."""
import csv, random, argparse, copy, sys
from reliability_model import *
import mission

def load_db():
    rows = list(csv.DictReader(open(RESULTS + "/fault_db.csv")))
    for r in rows:
        for k in ("criticality", "class_size", "detect_full", "detect_partial", "detect_mbist", "detect_online_mask", "scoap_co"):
            r[k] = int(r[k])
        r["bidx"] = BNAMES.index(r["block"])
    return rows

def timeline(params, trace, stats):
    """Fault-free run -> per-tick decision log with executed components."""
    m = Manager(params); log = []
    for x in trace:
        d = m.step(x["mission_active"], x["act"], x["urg"], [0] * NB)
        d["comps"] = components(d["blk"], d["tset"], stats) if d["valid"] else []
        d["crit"] = list(params.crit_term); d["phase"] = x["phase"]
        log.append(d)
    return log

def detects(row, name, tick, p):
    if name == "FULL_SCAN": return row["detect_full"]
    if name == "PARTIAL_SCAN": return row["detect_partial"]
    if name == "MBIST": return row["detect_mbist"]
    if name == "ONLINE": return (row["detect_online_mask"] >> ((tick // p.active_period) % ONLINE_K)) & 1
    return 0

def first_detection(row, inj_cycle, log, p):
    """Scan decisions that START after injection.  Returns (detected, det_cycle, test_name, state_at_det, cum_cycles)."""
    cum = 0
    for d in log:
        start = d["tick"] * EPOCH_CYCLES
        if not d["valid"] or start <= inj_cycle: continue
        t_in = 0
        for name, b, cy in d["comps"]:
            t_in += cy; cum += cy
            if b == row["bidx"] and detects(row, name, d["tick"], p):
                return 1, start + t_in, name, d["state"], cum
    return 0, None, "", None, cum

def full_sim(params, trace, stats, row, inj_cycle):
    """Literal 'reset DUT, inject, run scheduler' with feedback into the manager (verification path)."""
    m = Manager(params); res = [0] * NB; cum = 0
    for x in trace:
        d = m.step(x["mission_active"], x["act"], x["urg"], res); res = [0] * NB
        start = x["tick"] * EPOCH_CYCLES
        if not d["valid"] or start <= inj_cycle: continue
        t_in = 0
        for name, b, cy in components(d["blk"], d["tset"], stats):
            t_in += cy; cum += cy
            if b == row["bidx"] and detects(row, name, d["tick"], params):
                return 1, start + t_in, name, d["state"], cum
    return 0, None, "", None, cum

def injections(rows, M, seed=4242):
    r = random.Random(seed); out = []
    for _ in rows:
        t0 = r.randint(0, M - 2); out.append(t0 * EPOCH_CYCLES + r.randrange(EPOCH_CYCLES))
    return out

def log_rows(mode, log, stats):
    out = []
    for d in log:
        comps = d["comps"]; cyc = sum(c[2] for c in comps)
        intr = 0 if not d["mission_active"] else sum(c[2] for c in comps if c[0] != "ONLINE")
        sel = "-" if not d["valid"] else ("ALL" if d["blk"] == ALLBLK else BNAMES[d["blk"]])
        r = dict(mode=mode, tick=d["tick"], cycle=d["tick"] * EPOCH_CYCLES, state=SNAMES[d["state"]], phase=d["phase"],
                 mission_active=d["mission_active"], selected_block=sel,
                 test_types="+".join(dict.fromkeys(c[0] for c in comps)), reason=RSN[d["reason"]],
                 test_cycles=cyc, interruption_cycles=intr,
                 n_full_scan=sum(1 for c in comps if c[0] == "FULL_SCAN"), n_partial_scan=sum(1 for c in comps if c[0] == "PARTIAL_SCAN"),
                 n_mbist=sum(1 for c in comps if c[0] == "MBIST"), n_online=sum(1 for c in comps if c[0] == "ONLINE"))
        for k in ("prio", "health", "aging", "faults", "crit", "urg"):
            for b in range(NB): r[f"{k}_{BNAMES[b]}"] = d[k][b]
        out.append(r)
    return out

def summarize(rows, results, log, M):
    """results: list of dict(det, cyc, name, state, cum, inj)."""
    n = len(rows); det = [r for r in results if r["det"]]
    lat = sorted(r["cyc"] - r["inj"] for r in det)
    mission_end = M * EPOCH_CYCLES
    cens = [(r["cyc"] if r["det"] else mission_end) - r["inj"] for r in results]
    tot = sum(d["test_cycles"] for d in log); intr = sum(d["interruption_cycles"] for d in log)
    s = dict(faults=n, detected=len(det), fault_coverage=len(det) / n,
             mean_detection_latency_cycles=(sum(lat) / len(lat)) if lat else None,
             median_detection_latency_cycles=lat[len(lat) // 2] if lat else None,
             p95_detection_latency_cycles=lat[int(.95 * (len(lat) - 1))] if lat else None,
             censored_mean_latency_cycles=sum(cens) / n,
             total_test_cycles=tot, mission_interruption_cycles=intr,
             test_overhead_pct=100.0 * tot / mission_end, interruption_overhead_pct=100.0 * intr / mission_end,
             full_scans=sum(d["n_full_scan"] for d in log), partial_scans=sum(d["n_partial_scan"] for d in log),
             mbist_runs=sum(d["n_mbist"] for d in log), online_tests=sum(d["n_online"] for d in log),
             coverage_per_mcycle=(len(det) / n) / (tot / 1e6) if tot else None)
    for st in SNAMES: s[f"detected_in_{st}"] = sum(1 for r in det if SNAMES[r["state"]] == st)
    for c in (4, 3, 2, 1):
        sel = [(rw, rs) for rw, rs in zip(rows, results) if rw["criticality"] == c]
        s[f"coverage_crit{c}"] = sum(rs["det"] for _, rs in sel) / len(sel)
    for b in range(NB):
        s[f"tests_{BNAMES[b]}"] = sum(1 for d in log if d["selected_block"] in (BNAMES[b], "ALL") and d["test_cycles"] > 0)
    return s

def run(verify=0, out=RESULTS):
    stats = load_stats(); rows = load_db(); trace = mission.generate(); M = len(trace)
    inj = injections(rows, M)
    P_ad = Params(mode=0); P_bl = Params(mode=1)
    L_ad = timeline(P_ad, trace, stats); L_bl = timeline(P_bl, trace, stats)
    LR_ad = log_rows("adaptive", L_ad, stats); LR_bl = log_rows(f"baseline_N{P_bl.base_n}", L_bl, stats)
    for d in L_ad + L_bl:
        assert all(c[2] <= EPOCH_CYCLES for c in d["comps"]) and sum(c[2] for c in d["comps"]) <= EPOCH_CYCLES, "test exceeds one tick"
    state_at = {d["tick"]: d["state"] for d in L_ad}
    res_ad, res_bl = [], []
    for r, c0 in zip(rows, inj):
        a = first_detection(r, c0, L_ad, P_ad); b = first_detection(r, c0, L_bl, P_bl)
        res_ad.append(dict(det=a[0], cyc=a[1], name=a[2], state=a[3], cum=a[4], inj=c0))
        res_bl.append(dict(det=b[0], cyc=b[1], name=b[2], state=b[3], cum=b[4], inj=c0))
    if verify:
        rnd = random.Random(5); idx = rnd.sample(range(len(rows)), min(verify, len(rows))); bad = 0
        for i in idx:
            for P, res in ((P_ad, res_ad), (P_bl, res_bl)):
                f = full_sim(P, trace, stats, rows[i], inj[i]); e = res[i]
                if (f[0], f[1], f[2], f[4]) != (e["det"], e["cyc"], e["name"], e["cum"]): bad += 1
        print(f"verify: {len(idx)} faults x 2 modes re-run by literal manager stepping, mismatches = {bad}")
        assert bad == 0
    # fault_campaign.csv
    with open(out + "/fault_campaign.csv", "w", newline="") as f:
        cols = ["fault_id", "block", "net", "fault_type", "criticality", "injected_cycle", "system_state", "baseline_detected",
                "adaptive_detected", "baseline_detection_cycle", "adaptive_detection_cycle", "baseline_latency_cycles",
                "adaptive_latency_cycles", "baseline_test_type", "adaptive_test_type", "baseline_test_cycles",
                "adaptive_test_cycles", "baseline_state_at_detection", "adaptive_state_at_detection", "ever_detectable"]
        w = csv.writer(f); w.writerow(cols)
        for r, c0, a, b in zip(rows, inj, res_ad, res_bl):
            ever = int(r["detect_full"] or r["detect_mbist"] or r["detect_online_mask"] or r["detect_partial"])
            w.writerow([r["fault_id"], r["block"], r["net"], r["fault_type"], r["criticality"], c0, SNAMES[state_at[c0 // EPOCH_CYCLES]],
                        b["det"], a["det"], b["cyc"] if b["det"] else "", a["cyc"] if a["det"] else "",
                        (b["cyc"] - c0) if b["det"] else "", (a["cyc"] - c0) if a["det"] else "", b["name"], a["name"],
                        b["cum"], a["cum"], SNAMES[b["state"]] if b["det"] else "", SNAMES[a["state"]] if a["det"] else "", ever])
    LR = LR_ad + LR_bl
    with open(out + "/scheduler_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(LR[0])); w.writeheader(); w.writerows(LR)
    # baseline period sweep (summary only)
    sweep = []
    for N in (5, 10, 20, 40, 80):
        P = Params(mode=1, base_n=N); L = timeline(P, trace, stats); LRn = log_rows(f"baseline_N{N}", L, stats)
        rs = []
        for r, c0 in zip(rows, inj):
            b = first_detection(r, c0, L, P); rs.append(dict(det=b[0], cyc=b[1], name=b[2], state=b[3], cum=b[4], inj=c0))
        s = summarize(rows, rs, LRn, M); s["config"] = f"baseline_N{N}"; sweep.append(s)
    s = summarize(rows, res_ad, LR_ad, M); s["config"] = "adaptive_default"; sweep.insert(0, s)
    keys = ["config"] + [k for k in sweep[0] if k != "config"]
    with open(out + "/baseline_period_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(sweep)
    print("campaign complete: %d faults; adaptive cov %.4f, baseline(N=%d) cov %.4f" % (
        len(rows), sweep[0]["fault_coverage"], P_bl.base_n, sweep[3]["fault_coverage"]))
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--verify", type=int, default=0); a = ap.parse_args()
    run(a.verify)
