"""Step-3 Phase-1 closed-loop campaign: does observability-aware evidence (obs_en) remove the premature flag clearances found in Step 2B, and
what does the escalation path (esc_en) cost?  Same DUT, same mission trace (seed 2024), same 2,515 faults, same injection draw (seed 4242),
same unchanged detection tables as Steps 1-2B.  One fault per episode.  Nothing about Eq.(2) weights, baselines or the fault database is touched.

Two closed-loop episode types per profile (separate files, never mixed with the first-detection replay):
  persistent : fault present from its injection cycle until the end of the mission (the Step-2A/2B experiment).  Any flag clearance here is premature.
  transient  : fault present for TRANSIENT_TICKS scheduler ticks after injection and then removed.  Measures whether a flagged block can still recover
               (this is what the obs-only profile cannot do without an escalation path) and how long that takes.
Each decision's result is fed back as res_fail on the next tick; res_cls carries the class(es) of the failing component(s) of that decision on the
faulty block (FULL=1 PARTIAL=2 MBIST=4 ONLINE=8).  A component fails iff the detection table says it detects the fault (fc.detects, unchanged).

Usage: python3 step3_campaign.py [--out DIR] [--profiles a,b] [--episodes N]    (default out = results_step3)"""
import os, sys, csv, json, argparse, random, hashlib, subprocess
import fault_campaign as fc
from step1_lib import *
from step2a_campaign import INJ_SEED, cfg_json, sha

TRANSIENT_TICKS = 60                      # ASSUMPTION: transient episode keeps the fault for 60 ticks (~10% of the mission), then it disappears
PROFILES = {
    "s2a_all3_evid": refined(evid_en=1),                                           # Step-2A reference (reproduces the 117 premature clearances)
    "s3_obs":        refined(evid_en=1, obs_en=1, fair_unres_en=1),                  # + observability-aware evidence + healthy-block fairness exemption
    "s3_obs_esc":    refined(evid_en=1, obs_en=1, esc_en=1, fair_unres_en=1),        # + rate-limited FULL-diagnostic escalation (esc_gap=10) + fairness exemption
    "s3_obs_esc_stale": refined(evid_en=1, obs_en=1, esc_en=1, stale_en=1, fair_unres_en=1), # + stale bit + fairness exemption
}

def episode(P, trace, stats, row, c0, c1=None):
    m = Manager(P); res = [0] * NB; cls = [0] * NB; fb = row["bidx"]; first = None
    flagged_at = None; cleared_at = None; flag_sets = 0; prev_flag = 0
    ndiag = 0; nfail = 0; deg_ticks = 0; tot = 0; intr = 0; n_esc = 0; esc_intr = 0; esc_cyc = 0; esc_ticks = []; log_last = None
    full_scan_counts = [0] * NB; max_ticks_since_full = [0] * NB; healthy_full_scan_delay_after_flag = [None] * NB
    for x in trace:
        d = m.step(x["mission_active"], x["act"], x["urg"], res, cls); res = [0] * NB; cls = [0] * NB; log_last = d
        for b in range(NB): max_ticks_since_full[b] = max(max_ticks_since_full[b], (d["tick"] - d["lastfull"][b]) & 0xFFFF)
        if d["valid"] and d["tset"] & FULL:
            for b in (range(NB) if d["blk"] == ALLBLK else [d["blk"]]): full_scan_counts[b] += 1
        start = x["tick"] * EPOCH_CYCLES; comps = components(d["blk"], d["tset"], stats) if d["valid"] else []
        cyc = sum(c[2] for c in comps); tot += cyc; mis = sum(c[2] for c in comps if c[0] != "ONLINE") if x["mission_active"] else 0; intr += mis
        if d["state"] == ST_DEG: deg_ticks += 1
        if d["reason"] == 6: n_esc += 1; esc_cyc += cyc; esc_intr += mis; esc_ticks.append(d["tick"])
        flag = (d["degmask"] >> fb) & 1
        if flag and not prev_flag: flag_sets += 1
        if flagged_at is None and flag: flagged_at = d["tick"]
        elif flagged_at is not None and cleared_at is None and not flag: cleared_at = d["tick"]
        prev_flag = flag
        if flagged_at is not None and d["valid"] and d["tset"] & FULL:
            for b in (range(NB) if d["blk"] == ALLBLK else [d["blk"]]):
                if b != fb and healthy_full_scan_delay_after_flag[b] is None: healthy_full_scan_delay_after_flag[b] = d["tick"] - flagged_at
        if not d["valid"] or start <= c0 or (c1 is not None and start >= c1): continue
        fail = False; mask = 0; t_in = 0
        for name, b, cy in comps:
            t_in += cy
            if b == fb and fc.detects(row, name, d["tick"], P):
                fail = True; mask |= CLS_OF[name]
                if first is None: first = (start + t_in, name, d["tick"], d["state"])
        if d["blk"] == fb and d["tset"] & DIAG and first is not None: ndiag += 1
        if fail: nfail += 1; res[fb] = 1; cls[fb] = mask
    end_tick = None if c1 is None else (c1 + EPOCH_CYCLES - 1) // EPOCH_CYCLES        # first tick whose start is >= c1 (fault already gone)
    present_at_clear = cleared_at is not None and (end_tick is None or cleared_at < end_tick)
    return dict(det=int(first is not None), det_cycle=first[0] if first else None, det_test=first[1] if first else "", det_tick=first[2] if first else None,
                flagged_tick=flagged_at, cleared_tick=cleared_at, flag_set_events=flag_sets,
                cleared_while_fault_present=int(present_at_clear), recovered_after_fault_ended=int(cleared_at is not None and not present_at_clear),
                recovery_latency_ticks=(cleared_at - end_tick) if (cleared_at is not None and not present_at_clear and end_tick is not None) else None,
                flagged_at_end=int(bool((log_last["degmask"] >> fb) & 1)), fail_reports=nfail, diag_decisions_on_fault_block=ndiag, degraded_ticks=deg_ticks,
                escalations=n_esc, escalation_cycles=esc_cyc, escalation_interruption_cycles=esc_intr, first_escalation_tick=esc_ticks[0] if esc_ticks else None,
                total_test_cycles=tot, interruption_cycles=intr, state_end=log_last["state"],
                full_scan_counts=full_scan_counts, max_ticks_since_full=max_ticks_since_full,
                healthy_full_scan_delay_after_flag=healthy_full_scan_delay_after_flag)

def run_profile(name, P, rows, inj, trace, stats, outdir, idx, kind):
    c1s = {"persistent": lambda c0: None, "transient": lambda c0: c0 + TRANSIENT_TICKS * EPOCH_CYCLES}[kind]
    L = fc.timeline(P, trace, stats); out = []
    for i in idx:
        e = episode(P, trace, stats, rows[i], inj[i], c1s(inj[i])); out.append((i, e))
        r = fc.first_detection(rows[i], inj[i], L, P)                      # fault-free replay of the SAME profile
        c1 = c1s(inj[i]); inwin = r[0] and (c1 is None or r[1] <= c1)      # a transient fault is only detectable if the replay detection falls inside its window
        exp = (r[0], r[1], r[2]) if inwin else (0, None, "")
        assert (e["det"], e["det_cycle"], e["det_test"]) == exp, f"{name}/{kind}: closed-loop first detection != replay, fault index {i}"
    pdir = os.path.join(outdir, "profiles", name); os.makedirs(pdir, exist_ok=True); keys = list(out[0][1])
    with open(f"{pdir}/{kind}_episodes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["fault_id", "block", "criticality", "injected_cycle", "detect_partial", "detect_full"] + keys)
        for i, e in out: w.writerow([rows[i]["fault_id"], rows[i]["block"], rows[i]["criticality"], inj[i], rows[i]["detect_partial"], rows[i]["detect_full"]] + [e[k] for k in keys])
    n = len(out); fl = [e for _, e in out if e["flagged_tick"] is not None]; det = [e for _, e in out if e["det"]]
    mean = lambda xs: (sum(xs) / len(xs)) if xs else None; lat = sorted(e["recovery_latency_ticks"] for e in fl if e["recovery_latency_ticks"] is not None)
    s = dict(kind=kind, episodes=n, detected=len(det), flagged=len(fl), cleared_while_fault_present=sum(e["cleared_while_fault_present"] for e in fl),
             recovered_after_fault_ended=sum(e["recovered_after_fault_ended"] for e in fl), flagged_at_end=sum(e["flagged_at_end"] for e in fl),
             mean_flag_set_events=mean([e["flag_set_events"] for e in fl]), max_flag_set_events=max([e["flag_set_events"] for e in fl], default=0),
             recovery_latency_ticks_median=lat[len(lat) // 2] if lat else None, recovery_latency_ticks_max=lat[-1] if lat else None,
             mean_degraded_ticks_flagged=mean([e["degraded_ticks"] for e in fl]), mean_escalations_flagged=mean([e["escalations"] for e in fl]),
             mean_total_test_cycles=mean([e["total_test_cycles"] for _, e in out]), mean_interruption_cycles=mean([e["interruption_cycles"] for _, e in out]),
             mean_interruption_cycles_flagged=mean([e["interruption_cycles"] for e in fl]), mean_escalation_interruption_cycles_flagged=mean([e["escalation_interruption_cycles"] for e in fl]),
             episodes_ending_in_DEGRADED=sum(1 for _, e in out if e["state_end"] == ST_DEG),
             per_block={BNAMES[b]: dict(episodes=sum(1 for i, _ in out if rows[i]["bidx"] == b), flagged=sum(1 for i, e in out if rows[i]["bidx"] == b and e["flagged_tick"] is not None),
                                        cleared_while_fault_present=sum(e["cleared_while_fault_present"] for i, e in out if rows[i]["bidx"] == b and e["flagged_tick"] is not None),
                                        flagged_at_end=sum(e["flagged_at_end"] for i, e in out if rows[i]["bidx"] == b and e["flagged_tick"] is not None),
                                        mean_full_scan_count=mean([e["full_scan_counts"][b] for _, e in out]),
                                        mean_max_ticks_since_full=mean([e["max_ticks_since_full"][b] for _, e in out]),
                                        max_ticks_since_full=max(e["max_ticks_since_full"][b] for _, e in out),
                                        healthy_full_scan_missing_after_flag=sum(1 for i, e in out if rows[i]["bidx"] != b and e["flagged_tick"] is not None and e["healthy_full_scan_delay_after_flag"][b] is None),
                                        mean_healthy_full_scan_delay_after_flag=mean([e["healthy_full_scan_delay_after_flag"][b] for i, e in out if rows[i]["bidx"] != b and e["flagged_tick"] is not None and e["healthy_full_scan_delay_after_flag"][b] is not None]),
                                        max_healthy_full_scan_delay_after_flag=max([e["healthy_full_scan_delay_after_flag"][b] for i, e in out if rows[i]["bidx"] != b and e["flagged_tick"] is not None and e["healthy_full_scan_delay_after_flag"][b] is not None], default=None)) for b in range(NB)})
    return s

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=os.path.join(ROOT, "results_step3")); ap.add_argument("--profiles", default="")
    ap.add_argument("--episodes", type=int, default=0); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    stats = load_stats(); rows = fc.load_db(); trace = mission.generate(); M = len(trace); inj = fc.injections(rows, M, INJ_SEED)
    idx = list(range(len(rows))) if not a.episodes else sorted(random.Random(99).sample(range(len(rows)), a.episodes))
    names = a.profiles.split(",") if a.profiles else list(PROFILES)
    summ = {"meta": dict(faults=len(rows), episodes=len(idx), mission_ticks=M, injection_seed=INJ_SEED, mission_seed=2024, transient_ticks=TRANSIENT_TICKS,
                         fault_db_sha256=sha(RESULTS + "/fault_db.csv"), atpg_stats_sha256=sha(RESULTS + "/atpg_stats.json"), mission_trace_sha256=sha(RESULTS + "/mission_trace.csv"),
                         git_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
                         git_status=subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout,
                         tool_versions=dict(python=subprocess.run([sys.executable, "--version"], capture_output=True, text=True).stderr.strip() or subprocess.run([sys.executable, "--version"], capture_output=True, text=True).stdout.strip(), iverilog=(subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout + subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stderr).splitlines()[0] if (subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout + subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stderr).splitlines() else "unavailable", yosys=subprocess.run(["yosys", "-V"], capture_output=True, text=True).stdout.strip() or "unavailable"), argv=sys.argv[1:]),
            "note": "single mission trace, single injection seed: development-seed result only, no multi-seed claim", "profiles": {}}
    for nme in names:
        P = PROFILES[nme]; summ["profiles"][nme] = dict(config=cfg_json(P))
        for kind in ("persistent", "transient"):
            s = run_profile(nme, P, rows, inj, trace, stats, a.out, idx, kind); summ["profiles"][nme][kind] = s
            print(f"{nme:18s} {kind:10s} episodes {s['episodes']} flagged {s['flagged']:5d} cleared-while-fault-present {s['cleared_while_fault_present']:4d} recovered-after-end {s['recovered_after_fault_ended']:5d} "
                  f"flagged-at-end {s['flagged_at_end']:5d} mean-intr {s['mean_interruption_cycles']:.0f} mean-esc/flagged {s['mean_escalations_flagged']}", flush=True)
    with open(os.path.join(a.out, "fairness_metrics.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["profile", "kind", "block", "fault_coverage", "mean_interruption_cycles", "mean_interruption_cycles_flagged", "mean_full_scan_count", "mean_max_ticks_since_full", "max_ticks_since_full", "healthy_full_scan_missing_after_flag", "mean_healthy_full_scan_delay_after_flag", "max_healthy_full_scan_delay_after_flag"])
        for nme, profile in summ["profiles"].items():
            for kind in ("persistent", "transient"):
                q = profile[kind]
                for b in range(NB):
                    pb = q["per_block"][BNAMES[b]]
                    w.writerow([nme, kind, BNAMES[b], q["detected"] / q["episodes"], q["mean_interruption_cycles"], q["mean_interruption_cycles_flagged"], pb["mean_full_scan_count"], pb["mean_max_ticks_since_full"], pb["max_ticks_since_full"], pb["healthy_full_scan_missing_after_flag"], pb["mean_healthy_full_scan_delay_after_flag"], pb["max_healthy_full_scan_delay_after_flag"]])
    json.dump(summ, open(a.out + "/campaign_summary.json", "w"), indent=1, default=str)

if __name__ == "__main__": main()
