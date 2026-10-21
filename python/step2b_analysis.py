"""Step-2B analysis: flag-clearance lifecycle, per-block observability, missed-fault root cause, latency comparison.
Read-only w.r.t. Step-2A artifacts: re-simulates with the UNCHANGED Step-2A models/detection tables and writes only to results_step2b/.
Usage: python3 step2b_analysis.py [--out DIR]"""
import os, sys, csv, json, argparse, collections
import fault_campaign as fc
import step2a_campaign as s2a
from step1_lib import *

RES2A = ROOT + "/results_step2a"
TEST_NAMES = ("FULL_SCAN", "PARTIAL_SCAN", "MBIST", "ONLINE")

def capable(row, P):
    """Test types that can observe this fault under the implemented detection tables (ONLINE: which of the 4 mask slots)."""
    cap = []
    if row["detect_full"]: cap.append("FULL_SCAN")
    if row["detect_partial"]: cap.append("PARTIAL_SCAN")
    if row["detect_mbist"]: cap.append("MBIST")
    if row["detect_online_mask"]: cap.append("ONLINE")
    return cap

def trace_episode(P, trace, stats, row, c0):
    """Instrumented replica of step2a_campaign.episode(): identical manager stepping and result feedback; additionally logs, for every
    tick after injection, what was executed on the faulty block and what the diagnostic result was."""
    m = Manager(P); res = [0] * NB; fb = row["bidx"]; ev = []; first = None
    for x in trace:
        d = m.step(x["mission_active"], x["act"], x["urg"], res); res = [0] * NB
        start = x["tick"] * EPOCH_CYCLES; comps = components(d["blk"], d["tset"], stats) if d["valid"] else []
        pre = dict(dfault=d["dfault"] >> fb & 1, unres=d["unres"] >> fb & 1, okc=d["okc"][fb], degmask=d["degmask"] >> fb & 1)
        if not d["valid"] or start <= c0:
            if start > c0: ev.append(dict(tick=d["tick"], state=SNAMES[d["state"]], sel=None, **pre))
            continue
        fail_comps = []; mine = []
        for name, b, cy in comps:
            if b == fb:
                mine.append((name, int(bool(fc.detects(row, name, d["tick"], P)))))
                if fc.detects(row, name, d["tick"], P): fail_comps.append(name)
        any_fail = any(test_fails(row, name, b, d["tick"], P) for name, b, cy in comps)
        if any_fail and first is None: first = d["tick"]
        if any_fail: res[fb] = 1
        ev.append(dict(tick=d["tick"], state=SNAMES[d["state"]], sel=d["blk"], tset=d["tset"], reason=d["reason"], comps_on_fault_block=mine, result="FAIL" if any_fail else "PASS", **pre))
    return ev, first

def test_fails(row, name, b, tick, P): return b == row["bidx"] and bool(fc.detects(row, name, tick, P))

# ============================================================================ flag-clearance cases
def lifecycle(P, trace, stats, rows, i, inj, e2a):
    row = rows[i]; c0 = inj[i]; ev, first = trace_episode(P, trace, stats, row, c0); fb = row["bidx"]
    flag_set = [x["tick"] for k, x in enumerate(ev) if x["degmask"] and (k == 0 or not ev[k - 1]["degmask"])]
    flag_clr = [x["tick"] for k, x in enumerate(ev) if (not x["degmask"]) and k and ev[k - 1]["degmask"]]
    flagged = e2a["flagged_tick"]; cleared = e2a["cleared_tick"]
    assert str(flag_set[0]) == str(flagged) and str(flag_clr[0]) == str(cleared), f"{row['fault_id']}: instrumented trace disagrees with Step-2A episode row"
    f0, c_ = int(flagged), int(cleared)
    diags = [x for x in ev if x.get("sel") is not None and f0 <= x["tick"] < c_ and x.get("comps_on_fault_block") and any(n == "DIAG" for n, _ in x["comps_on_fault_block"])]
    unres_clr = next((x["tick"] for x in ev if x["tick"] > f0 and x["unres"] == 0 and x.get("sel") is not None and ev[ev.index(x) - 1]["unres"] == 1), None)
    later_fail = [x["tick"] for x in ev if x.get("result") == "FAIL" and x["tick"] >= c_]
    src = [x for x in ev if x.get("result") == "FAIL"][0]
    src_tests = [n for n, f in src["comps_on_fault_block"] if f]
    blind = all(all(f == 0 for n, f in x["comps_on_fault_block"]) for x in diags) and all(x["result"] == "PASS" for x in diags)
    return ev, dict(first_fail_tick=src["tick"], first_fail_tests="+".join(src_tests), flag_set_ticks=flag_set, flag_clear_ticks=flag_clr,
                    diag_ticks=[x["tick"] for x in diags], diag_tests=sorted({"+".join(n for n, _ in x["comps_on_fault_block"]) for x in diags}),
                    diag_results=[x["result"] for x in diags], okc_trace=[x["okc"] for x in diags], unres_cleared_tick=unres_clr,
                    later_fail_ticks=later_fail, all_diags_blind=blind)

def run_cases(P, trace, stats, rows, inj, outdir, do_rtl=True):
    idx = {r["fault_id"]: k for k, r in enumerate(rows)}
    eps = list(csv.DictReader(open(RES2A + "/profiles/s2a_all3_evid/closed_loop_episodes.csv")))
    cl = [e for e in eps if e["cleared_while_fault_persists"] == "1"]; out = []; trows = []
    vvp = None
    if do_rtl: vvp = build_rtl("s2b_evid", P)
    for e in cl:
        i = idx[e["fault_id"]]; r = rows[i]; ev, L = lifecycle(P, trace, stats, rows, i, inj, e)
        # RTL / Python cross-check: replay the exact res_fail stream through python_trace and (optionally) the RTL
        fe = {}
        for x in ev:
            if x.get("result") == "FAIL": fe[x["tick"] + 1] = fe.get(x["tick"] + 1, 0) | (1 << r["bidx"])
        py = python_trace(P, trace, fe); fb = r["bidx"]
        py_clear = next(t for t in range(1, len(py)) if (py[t - 1]["degmask"] >> fb & 1) and not (py[t]["degmask"] >> fb & 1))
        rtl_ok = ""
        if do_rtl:
            n, bad, msg = compare(P, trace, fe, "s2b_case", 0, -1, vvp=vvp); rtl_ok = int(bad == 0)
        cause = "PARTIAL_SCAN_NON_OBSERVING" if (L["all_diags_blind"] and r["detect_partial"] == 0) else "UNCLASSIFIED"
        out.append(dict(fault_id=r["fault_id"], block=r["block"], net=r["net"], fault_type=r["fault_type"], criticality=r["criticality"], atpg_status=r["atpg_status"],
                        injection_tick=inj[i] // EPOCH_CYCLES, injection_cycle=inj[i], detect_full=r["detect_full"], detect_partial=r["detect_partial"], detect_mbist=r["detect_mbist"],
                        detect_online_mask=r["detect_online_mask"], flagging_failed_tick=L["first_fail_tick"], flagging_tests=L["first_fail_tests"],
                        flag_set_tick=L["flag_set_ticks"][0], diag_ticks="|".join(map(str, L["diag_ticks"])), diag_selected_tests="|".join(L["diag_tests"]),
                        diag_results="|".join(L["diag_results"]), okc_during_diags="|".join(map(str, L["okc_trace"])), unresolved_bit_cleared_tick=L["unres_cleared_tick"],
                        flag_clear_tick=L["flag_clear_ticks"][0], flag_cycles_set=len(L["flag_set_ticks"]), flag_cycles_cleared=len(L["flag_clear_ticks"]),
                        refail_after_first_clear_tick=(L["later_fail_ticks"][0] if L["later_fail_ticks"] else ""), n_later_fail_reports=len(L["later_fail_ticks"]),
                        detected_by_first_detection_campaign=e["det"], python_clear_tick_replayed_from_fe=py_clear, rtl_equals_python_on_episode=rtl_ok,
                        fault_persists_through_mission=1, root_cause_class=cause,
                        raw_log_ref="flag_clearance_traces.csv?fault_id=%s ; mission=results/mission_trace.csv ; episode=results_step2a/profiles/s2a_all3_evid/closed_loop_episodes.csv" % r["fault_id"]))
        for x in ev:
            trows.append(dict(fault_id=r["fault_id"], tick=x["tick"], state=x["state"], selected_block=x.get("sel", ""), tset=x.get("tset", ""), reason=x.get("reason", ""),
                              comps_on_fault_block="+".join(f"{n}:{'DET' if f else 'no-det'}" for n, f in x.get("comps_on_fault_block", [])), result=x.get("result", ""),
                              dfault_before=x["dfault"], unres_before=x["unres"], okc_before=x["okc"], degmask_before=x["degmask"]))
    with open(outdir + "/flag_clearance_cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    with open(outdir + "/flag_clearance_traces.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trows[0])); w.writeheader(); w.writerows(trows)
    return out, eps

# ============================================================================ observability
def observability(rows, outdir):
    by = collections.defaultdict(list)
    for r in rows: by[(r["block"], r["fault_type"])].append(r)
    for r in rows: by[(r["block"], "ALL")].append(r)
    out = []; stats = load_stats()
    for (b, ft), rs in sorted(by.items(), key=lambda kv: (BNAMES.index(kv[0][0]), kv[0][1])):
        n = len(rs); c = lambda f: sum(1 for r in rs if f(r))
        any_ = lambda r: r["detect_full"] or r["detect_partial"] or r["detect_mbist"] or r["detect_online_mask"]
        out.append(dict(block=b, fault_type=ft, faults=n, atpg_status_detected=c(lambda r: r["atpg_status"] == "detected"),
                        detectable_full=c(lambda r: r["detect_full"]), detectable_partial=c(lambda r: r["detect_partial"]), detectable_mbist=c(lambda r: r["detect_mbist"]),
                        detectable_online_any_slot=c(lambda r: r["detect_online_mask"]), detectable_by_any_test=c(any_), undetectable_by_all=c(lambda r: not any_(r)),
                        full_only=c(lambda r: r["detect_full"] and not r["detect_partial"] and not r["detect_mbist"] and not r["detect_online_mask"]),
                        partial_blind_but_detectable_elsewhere=c(lambda r: not r["detect_partial"] and any_(r)),
                        partial_subset_of_full_violations=c(lambda r: r["detect_partial"] and not r["detect_full"]),
                        online_slot_counts="|".join(str(c(lambda r, s=s: r["detect_online_mask"] >> s & 1)) for s in range(ONLINE_K)),
                        partial_pass_is_valid_absence_evidence_fraction=round(c(lambda r: r["detect_partial"]) / n, 4),
                        DIAG_has_detection_table=0, full_scan_cycles=stats[b]["full_scan_cycles"], partial_scan_cycles=stats[b]["partial_scan_cycles"],
                        mbist_cycles=stats[b]["mbist_cycles"] if b == "regfile" else "n/a", diag_cycles=stats[b]["diag_cycles"]))
    with open(outdir + "/per_block_test_observability.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    return out

# ============================================================================ missed faults / latency
def rle(seq):
    out = []
    for s in seq:
        if out and out[-1][0] == s: out[-1][1] += 1
        else: out.append([s, 1])
    return "|".join(f"{a}x{b}" for a, b in out)

def load_results(name):
    return {r["fault_id"]: r for r in csv.DictReader(open(f"{RES2A}/profiles/{name}/fault_results.csv"))}

def missed_faults(P, trace, stats, rows, inj, outdir, ref="fixed_N20", prof="s2a_all3_evid"):
    M = len(trace); log = fc.timeline(P, trace, stats); fr = load_results(ref); ar = load_results(prof)
    # cross-check the re-simulated schedule against the raw Step-2A decision log
    raw = list(csv.DictReader(open(f"{RES2A}/profiles/{prof}/decision_log.csv"))); assert len(raw) == len(log)
    assert all(SNAMES[d["state"]] == r["state"] and int(d["valid"]) == int(r["valid"]) and int(d["tset"]) == int(r["tset"]) for d, r in zip(log, raw)), "re-simulated schedule != raw Step-2A log"
    gaps = {}
    for b in range(NB):
        t = [d["tick"] for d in log if d["valid"] and d["tset"] & FULL and d["blk"] == b]; g = [y - x for x, y in zip(t, t[1:])]
        gaps[BNAMES[b]] = dict(full_scan_ticks=t, max_gap=max(g), mean_gap=sum(g) / len(g))
    out = []; idx = {r["fault_id"]: k for k, r in enumerate(rows)}
    for fid, a in ar.items():
        f = fr[fid]
        if not (f["detected"] == "1" and a["detected"] == "0") and not (f["detected"] == "0" and a["detected"] == "0"): continue
        i = idx[fid]; r = rows[i]; fb = r["bidx"]; c0 = inj[i]; t0 = c0 // EPOCH_CYCLES; bn = r["block"]
        after = [d for d in log if d["valid"] and d["tick"] * EPOCH_CYCLES > c0]
        cnt = collections.Counter(); capable_n = 0
        for d in after:
            for name, b, cy in d["comps"]:
                if b == fb:
                    cnt[name] += 1
                    if fc.detects(r, name, d["tick"], P): capable_n += 1
        tail = [d for d in log if d["tick"] * EPOCH_CYCLES > c0]
        lf_before = max([t for t in gaps[bn]["full_scan_ticks"] if t * EPOCH_CYCLES <= c0] or [-1])
        windows = sum(1 for d in tail if not trace[d["tick"]]["mission_active"]); fc4 = sum(1 for d in tail if d["fcause"] == 4)
        cap = capable(r, P); ticks_to_end = M - 1 - t0
        idle_tk = [d for d in tail if d["state"] == ST_IDLE]; idle_t = len(idle_tk); idle_nodec = sum(1 for d in idle_tk if not d["valid"])
        idle_other = sum(1 for d in idle_tk if d["valid"] and d["blk"] != fb and d["tset"] & FULL)
        if not cap: cat = "UNDETECTABLE_UNDER_IMPLEMENTED_MODEL"
        elif capable_n: cat = "BOOKKEEPING_ERROR_capable_test_ran"
        elif fc4: cat = "WITHHELD_BY_UNRESOLVED_DIAGNOSTIC"
        elif windows == 0: cat = "NO_MISSION_IDLE_WINDOW_BEFORE_MISSION_END"
        elif idle_nodec == idle_t: cat = "IDLE_WINDOW_PRESENT_BUT_SWEEP_REARM_GAP_NOT_ELAPSED"
        elif idle_other: cat = "IDLE_SWEEP_SERVED_OTHER_BLOCKS_FIRST"
        else: cat = "ELIGIBLE_BUT_NOT_SELECTED"
        out.append(dict(fault_id=fid, block=bn, fault_type=r["fault_type"], criticality=r["criticality"], injection_tick=t0, ticks_from_injection_to_mission_end=ticks_to_end,
                        detect_full=r["detect_full"], detect_partial=r["detect_partial"], detect_mbist=r["detect_mbist"], detect_online_mask=r["detect_online_mask"],
                        capable_test_types="+".join(cap), N20_detected=f["detected"], N20_detection_cycle=f["detection_cycle"], N20_detection_tick=(int(f["detection_cycle"]) // EPOCH_CYCLES if f["detected"] == "1" else ""),
                        N20_test=f["test"], adaptive_tests_on_block_after_injection="|".join(f"{k}:{v}" for k, v in sorted(cnt.items())) or "none",
                        adaptive_capable_tests_executed_after_injection=capable_n, adaptive_last_full_scan_tick_before_injection=lf_before,
                        ticks_since_last_full_scan_at_injection=t0 - lf_before if lf_before >= 0 else "never", adaptive_block_max_gap_between_full_scans=gaps[bn]["max_gap"],
                        adaptive_block_mean_gap=round(gaps[bn]["mean_gap"], 1), adaptive_last_full_scan_tick_in_mission=gaps[bn]["full_scan_ticks"][-1],
                        state_sequence_after_injection=rle(SNAMES[d["state"]] for d in tail), mission_idle_windows_after_injection=windows, ticks_with_unresolved_diag_withholding=fc4,
                        idle_ticks_after_injection=idle_t, idle_ticks_with_no_decision=idle_nodec, idle_ticks_full_scan_other_block=idle_other, sweep_rearm_gap_param=P.sweep_gap,
                        horizon_consistent_ticks_to_end_le_block_max_gap=int(ticks_to_end <= gaps[bn]["max_gap"]),
                        category=cat, raw_log_ref=f"results_step2a/profiles/{prof}/decision_log.csv ticks {t0+1}-{M-1}; results_step2a/profiles/{ref}/decision_log.csv"))
    out.sort(key=lambda x: (x["category"], x["injection_tick"]))
    with open(outdir + "/missed_faults.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    return out, gaps

def latency_comparison(rows, inj, outdir, M):
    fr = load_results("fixed_N20"); a1 = load_results("s1_all3"); a2 = load_results("s2a_all3_evid"); out = []
    for r, c0 in zip(rows, inj):
        fid = r["fault_id"]; x = fr[fid]; y = a2[fid]; z = a1[fid]
        lat = lambda q: int(q["latency_cycles"]) if q["detected"] == "1" else ""
        both = x["detected"] == "1" and y["detected"] == "1"
        out.append(dict(fault_id=fid, block=r["block"], fault_type=r["fault_type"], criticality=r["criticality"], injection_tick=c0 // EPOCH_CYCLES, injection_cycle=c0,
                        N20_detected=x["detected"], N20_latency=lat(x), N20_test=x["test"], s1_all3_detected=z["detected"], s1_all3_latency=lat(z), s1_all3_test=z["test"],
                        s2a_evid_detected=y["detected"], s2a_evid_latency=lat(y), s2a_evid_test=y["test"],
                        delta_s2a_minus_N20=(int(y["latency_cycles"]) - int(x["latency_cycles"])) if both else "",
                        population=("both" if both else "N20_only" if x["detected"] == "1" else "adaptive_only" if y["detected"] == "1" else "neither"),
                        N20_censored_latency=lat(x) if x["detected"] == "1" else M * EPOCH_CYCLES - c0, s2a_evid_censored_latency=lat(y) if y["detected"] == "1" else M * EPOCH_CYCLES - c0))
    with open(outdir + "/detection_latency_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    return out

def pct(xs, q): xs = sorted(xs); return xs[int(q * (len(xs) - 1))]
def stat(xs): return dict(n=len(xs), mean=sum(xs) / len(xs), median=pct(xs, .5), p95=pct(xs, .95)) if xs else dict(n=0)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=ROOT + "/results_step2b"); ap.add_argument("--no-rtl", action="store_true"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); stats = load_stats(); rows = fc.load_db(); trace = mission.generate(); M = len(trace); inj = fc.injections(rows, M, s2a.INJ_SEED)
    P = s2a.PROFILES["s2a_all3_evid"]
    cases, eps = run_cases(P, trace, stats, rows, inj, a.out, not a.no_rtl)
    obs = observability(rows, a.out); miss, gaps = missed_faults(P, trace, stats, rows, inj, a.out); lat = latency_comparison(rows, inj, a.out, M)
    idx = {r["fault_id"]: k for k, r in enumerate(rows)}
    # ---- flagged-population cross-tab: clearance vs detect_partial
    tab = collections.Counter()
    for e in eps:
        if e["flagged_tick"] in ("", "None"): continue
        r = rows[idx[e["fault_id"]]]; tab[f"detect_partial={r['detect_partial']},cleared_while_persisting={e['cleared_while_fault_persists']}"] += 1
    # ---- coverage vs injection time (first-detection replay)
    fr = load_results("fixed_N20"); ar = load_results("s2a_all3_evid"); s1r = load_results("s1_all3")
    def cov_by_t(res, lo, hi):
        ids = [r["fault_id"] for r, c0 in zip(rows, inj) if lo <= c0 // EPOCH_CYCLES < hi]; return (sum(1 for i in ids if res[i]["detected"] == "1"), len(ids))
    curve = {}
    for lo, hi in ((0, 100), (100, 200), (200, 300), (300, 400), (400, 500), (500, 560), (560, 581), (581, 600)):
        curve[f"{lo}-{hi-1}"] = dict(N20=cov_by_t(fr, lo, hi), s1_all3=cov_by_t(s1r, lo, hi), s2a_evid=cov_by_t(ar, lo, hi))
    both = [r for r in lat if r["population"] == "both"]; g = lambda k: [int(r[k]) for r in both]
    summary = dict(
        meta=dict(branch="step2b-root-cause", injection_seed=s2a.INJ_SEED, single_seed=True, faults=len(rows), mission_ticks=M, step2a_commit="43c3a9e",
                  note="first-detection campaign = fault-free schedule replay; flag-clearance = closed-loop single-persistent-fault episodes; denominators never mixed"),
        flag_clearance=dict(cases=len(cases), reported_in_step2a=117, by_root_cause=dict(collections.Counter(c["root_cause_class"] for c in cases)),
                            by_block=dict(collections.Counter(c["block"] for c in cases)), by_flagging_test=dict(collections.Counter(c["flagging_tests"] for c in cases)),
                            all_detect_partial_zero=all(c["detect_partial"] == 0 for c in cases), all_detect_full_one=all(c["detect_full"] == 1 for c in cases),
                            diag_selected_tests=dict(collections.Counter(c["diag_selected_tests"] for c in cases)),
                            all_diag_results_pass=all(set(c["diag_results"].split("|")) == {"PASS"} for c in cases),
                            unresolved_bit_cleared_after_one_pass=sum(1 for c in cases if c["unresolved_bit_cleared_tick"] is not None and c["diag_ticks"] and int(c["unresolved_bit_cleared_tick"]) == int(c["diag_ticks"].split("|")[0]) + 1),
                            re_failed_later=sum(1 for c in cases if c["n_later_fail_reports"] > 0), flap_cases_multiple_flag_cycles=sum(1 for c in cases if c["flag_cycles_set"] > 1),
                            python_replay_clear_tick_equals_episode=all(c["python_clear_tick_replayed_from_fe"] == c["flag_clear_tick"] for c in cases),
                            rtl_equals_python_on_episode=("not run" if a.no_rtl else f"{sum(c['rtl_equals_python_on_episode'] for c in cases)}/{len(cases)}"),
                            flagged_population_crosstab_all_2451_flagged_episodes=dict(tab),
                            DIAG_component_has_no_detection_table=True),
        missed_by_adaptive_detected_by_N20=dict(count=sum(1 for m in miss if m["N20_detected"] == "1"), by_category=dict(collections.Counter(m["category"] for m in miss)),
                            by_block=dict(collections.Counter(m["block"] for m in miss if m["N20_detected"] == "1")),
                            injection_tick_min=min(m["injection_tick"] for m in miss if m["N20_detected"] == "1"), injection_tick_max=max(m["injection_tick"] for m in miss if m["N20_detected"] == "1"),
                            all_N20_detections_by=dict(collections.Counter(m["N20_test"] for m in miss if m["N20_detected"] == "1")),
                            adaptive_block_gap_between_full_scans={b: dict(max=v["max_gap"], mean=round(v["mean_gap"], 1), last_full_scan_tick=v["full_scan_ticks"][-1]) for b, v in gaps.items()}),
        coverage_vs_injection_tick_detected_over_total=curve,
        latency_both_detected=dict(population=len(both), N20=stat(g("N20_latency")), s1_all3=stat(g("s1_all3_latency")), s2a_evid=stat(g("s2a_evid_latency")),
                                   delta_mean=sum(g("s2a_evid_latency")) / len(both) - sum(g("N20_latency")) / len(both)),
        populations=dict(collections.Counter(r["population"] for r in lat)),
        observability=[o for o in obs if o["fault_type"] == "ALL"])
    json.dump(summary, open(a.out + "/root_cause_summary.json", "w"), indent=1, default=str)
    print(json.dumps({k: summary[k] for k in ("flag_clearance", "missed_by_adaptive_detected_by_N20", "coverage_vs_injection_tick_detected_over_total", "latency_both_detected", "populations")}, indent=1, default=str))

if __name__ == "__main__": main()
