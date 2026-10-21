"""Step-2A campaign runner.  Explicit, reproducible profiles; two SEPARATE experiments.  Does not modify fault_campaign.py (v1 methodology
is reproduced by importing its functions unchanged).  Nothing here changes weights, fault database, detection tables or injection times.

Experiment 1 (first-detection, fault-free schedule replay): per fault, first detecting test that STARTS after the injection cycle in the
  per-profile fault-free schedule.  Exact for a single fault per episode in this behavioural model, because before the first detection every
  test of the injected block passes and a passing test produces no manager event (res_fail is only ever raised by a detection), so the
  manager inputs are identical to the fault-free run.  It is NOT a closed-loop experiment and says nothing about the scheduler's response
  after a detection.
Experiment 2 (closed-loop diagnostic response, --closed-loop): sequential single-PERSISTENT-fault episodes.  For every fault: reset the manager,
  inject at the same cycle as Experiment 1, keep the fault present until the end of the mission, feed each decision's pass/fail (any executed
  component of that decision on the faulty block that detects the fault per the unchanged detection tables) back as res_fail on the next
  tick, and record the scheduler's response.  One fault per episode (no simultaneous multi-fault episodes are modelled).
Usage: python3 step2a_campaign.py [--out DIR] [--verify N] [--closed-loop] [--episodes N]"""
import os, sys, csv, json, argparse, random, hashlib, subprocess
from dataclasses import asdict
import fault_campaign as fc
from step1_lib import *

INJ_SEED = 4242            # the original v1 injection seed (fault_campaign.injections default) - never changed
PROFILES = {
    "v1_adaptive":             Params(mode=0),                                                    # original v1: Eq.(2) adaptive, all Step-1/2A switches OFF
    "fixed_N5":                Params(mode=1, base_n=5),
    "fixed_N10":               Params(mode=1, base_n=10),
    "fixed_N20":               Params(mode=1, base_n=20),                                         # PRINCIPAL baseline (chosen before results were seen)
    "fixed_N40":               Params(mode=1, base_n=40),
    "fixed_N80":               Params(mode=1, base_n=80),
    "s1_recovery_only":        Params(mode=0, recov_en=1),                                        # Eq.(2) + Step-1 Fix A only
    "s1_all3":                 refined(),                                                         # Eq.(2) + Step-1 Fix A+B+C (the 'corrected adaptive reference')
    "s2a_all3_evid":           refined(evid_en=1),                                                # + health-evidence separation, arisk_deg=0 (aging risk never forces DEGRADED)
    "s2a_all3_evid_aflag":     refined(evid_en=1, arisk_deg=1),                                   # + health-evidence separation, aging-risk escalation allowed
}
MAIN = ["v1_adaptive", "fixed_N20", "s1_recovery_only", "s1_all3"]
def cfg_json(p): return {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(p).items()}

def sha(path): return hashlib.sha256(open(path, "rb").read()).hexdigest()

def decision_rows(name, P, log, stats):
    rows = fc.log_rows(name, log, stats)
    for r, d in zip(rows, log):
        r.update(degmask=d["degmask"], arisk=d["arisk"], dfault=d["dfault"], aflag=d["aflag"], unres=d["unres"], fcause=d["fcause"], overdue_mask=d["overdue"],
                 sweep=d["sweep"], tset=d["tset"], blk=d["blk"], valid=d["valid"])
        for b in range(NB): r[f"lastfull_{BNAMES[b]}"] = d["lastfull"][b]
    return rows

def full_scan_stats(log, trace, P, M):
    """Independent of Manager.lastfull: derived from decisions only (baseline's ALL-block decisions count for every block)."""
    full, part, last = block_counts(log); T = M - 1
    per = {}
    for b in range(NB):
        ticks = [d["tick"] for d in log if d["valid"] and d["tset"] & FULL and (d["blk"] == b or d["blk"] == ALLBLK)]
        gaps = [y - x for x, y in zip(ticks, ticks[1:])]
        since = T - ticks[-1] if ticks else None
        per[BNAMES[b]] = dict(full_scans=len(ticks), last_full_tick=ticks[-1] if ticks else None, ticks_since_last_full=since if since is not None else T + 1,
                              max_gap_between_full_scans=max(gaps) if gaps else None, overdue_at_end=int((since if since is not None else T + 1) >= P.overdue_ticks))
    return per

def block_coverage(rows, results):
    out = {}
    for b in range(NB):
        sel = [rs for rw, rs in zip(rows, results) if rw["bidx"] == b]
        out[BNAMES[b]] = dict(faults=len(sel), detected=sum(r["det"] for r in sel), coverage=sum(r["det"] for r in sel) / len(sel))
    return out

def exp1_profile(name, P, rows, inj, trace, stats, outdir, M):
    log = fc.timeline(P, trace, stats)
    for d in log: assert all(c[2] <= EPOCH_CYCLES for c in d["comps"]) and sum(c[2] for c in d["comps"]) <= EPOCH_CYCLES, "test exceeds one tick"
    LR = decision_rows(name, P, log, stats)
    res = []
    for r, c0 in zip(rows, inj):
        a = fc.first_detection(r, c0, log, P); res.append(dict(det=a[0], cyc=a[1], name=a[2], state=a[3], cum=a[4], inj=c0))
    s = fc.summarize(rows, res, LR, M)
    s["profile"] = name; s["config"] = cfg_json(P); s["injection_seed"] = INJ_SEED; s["experiment"] = "1_first_detection_fault_free_schedule_replay"
    s["coverage_by_block"] = block_coverage(rows, res)
    s["state_occupancy_ticks"] = {SNAMES[i]: sum(1 for d in log if d["state"] == i) for i in range(3)}
    s["full_scans_by_block"] = full_scan_stats(log, trace, P, M)
    s["overdue_blocks_at_end"] = [b for b, v in s["full_scans_by_block"].items() if v["overdue_at_end"]]
    s["mean_censored_latency_definition"] = "(detection cycle, or end of mission = %d cycles if undetected) - injection cycle, averaged over ALL faults" % (M * EPOCH_CYCLES)
    s["ever_detectable_faults"] = sum(1 for r in rows if r["detect_full"] or r["detect_mbist"] or r["detect_online_mask"] or r["detect_partial"])
    if P.mode == 0: s["starvation_report_end_of_mission"] = starvation_report(log, trace, P, M - 1)
    else: s["starvation_report_end_of_mission"] = "n/a: fixed-period baseline does not keep scheduler lastfull; see full_scans_by_block (derived from decisions)"
    pdir = os.path.join(outdir, "profiles", name); os.makedirs(pdir, exist_ok=True)
    with open(pdir + "/decision_log.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(LR[0])); w.writeheader(); w.writerows(LR)
    with open(pdir + "/fault_results.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["fault_id", "block", "criticality", "injected_cycle", "detected", "detection_cycle", "latency_cycles", "test", "state_at_detection", "cum_test_cycles"])
        for r, x in zip(rows, res): w.writerow([r["fault_id"], r["block"], r["criticality"], x["inj"], x["det"], x["cyc"] if x["det"] else "", (x["cyc"] - x["inj"]) if x["det"] else "", x["name"], SNAMES[x["state"]] if x["det"] else "", x["cum"]])
    return log, res, s

# ------------------------------------------------------------------ Experiment 2
def test_fails(row, name, b, tick, P):
    return b == row["bidx"] and bool(fc.detects(row, name, tick, P))

def episode(P, trace, stats, row, c0):
    """Single persistent fault from cycle c0 to end of mission; decision results fed back as res_fail on the next tick."""
    m = Manager(P); res = [0] * NB; fb = row["bidx"]; first = None; rep = []; flagged_at = None; cleared_at = None; ndiag = 0; nfail = 0
    deg_ticks = 0; tot = 0; intr = 0; other_full = 0; log = []
    for x in trace:
        d = m.step(x["mission_active"], x["act"], x["urg"], res); res = [0] * NB; log.append(d)
        start = x["tick"] * EPOCH_CYCLES; comps = components(d["blk"], d["tset"], stats) if d["valid"] else []
        cyc = sum(c[2] for c in comps); tot += cyc; intr += 0 if not x["mission_active"] else sum(c[2] for c in comps if c[0] != "ONLINE")
        if d["state"] == ST_DEG: deg_ticks += 1
        if flagged_at is not None and d["valid"] and d["tset"] & FULL and d["blk"] != fb and d["blk"] != ALLBLK and d["tick"] > flagged_at: other_full += 1
        if flagged_at is not None and cleared_at is None and not (d["degmask"] >> fb & 1): cleared_at = d["tick"]
        if flagged_at is None and (d["degmask"] >> fb & 1): flagged_at = d["tick"]
        if not d["valid"] or start <= c0: continue
        fail = False; t_in = 0
        for name, b, cy in comps:
            t_in += cy
            if test_fails(row, name, b, d["tick"], P):
                fail = True
                if first is None: first = (start + t_in, name, d["tick"], d["state"])
        if d["valid"] and d["blk"] == fb and d["tset"] & DIAG and first is not None: ndiag += 1
        if fail and P.mode == 0: res[fb] = 1; nfail += 1
        elif fail: nfail += 1
    T = len(trace) - 1; lf_other = [d for d in [log[-1]]][0]
    return dict(det=int(first is not None), det_cycle=first[0] if first else None, det_test=first[1] if first else "", det_tick=first[2] if first else None,
                flagged_tick=flagged_at, cleared_while_fault_persists=int(cleared_at is not None and flagged_at is not None), cleared_tick=cleared_at,
                fail_reports=nfail, diag_decisions_on_fault_block_after_detection=ndiag, degraded_ticks=deg_ticks, other_block_full_scans_after_flag=other_full,
                total_test_cycles=tot, interruption_cycles=intr, overdue_mask_end=log[-1]["overdue"], unres_end=log[-1]["unres"],
                dfault_end=log[-1]["dfault"], degmask_end=log[-1]["degmask"], state_end=log[-1]["state"])

def exp2_profile(name, P, rows, inj, trace, stats, outdir, replay, idx):
    out = []
    for i in idx:
        e = episode(P, trace, stats, rows[i], inj[i]); out.append((i, e))
        r1 = replay[i]
        assert (e["det"], e["det_cycle"], e["det_test"]) == (r1["det"], r1["cyc"], r1["name"]), f"{name}: closed-loop first detection differs from replay for fault index {i}"
    pdir = os.path.join(outdir, "profiles", name); os.makedirs(pdir, exist_ok=True)
    keys = list(out[0][1])
    with open(pdir + "/closed_loop_episodes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["fault_id", "block", "criticality", "injected_cycle"] + keys)
        for i, e in out: w.writerow([rows[i]["fault_id"], rows[i]["block"], rows[i]["criticality"], inj[i]] + [e[k] for k in keys])
    det = [e for _, e in out if e["det"]]; n = len(out); mean = lambda xs: (sum(xs) / len(xs)) if xs else None
    agg = dict(experiment="2_closed_loop_sequential_single_persistent_fault_episodes", episodes=n, detected=len(det),
               flagged=sum(1 for _, e in out if e["flagged_tick"] is not None),
               cleared_while_fault_persists=sum(e["cleared_while_fault_persists"] for _, e in out),
               false_clearance_rate_of_flagged=(sum(e["cleared_while_fault_persists"] for _, e in out) / max(1, sum(1 for _, e in out if e["flagged_tick"] is not None))),
               mean_degraded_ticks_detected=mean([e["degraded_ticks"] for e in det]), mean_diag_decisions_after_detection=mean([e["diag_decisions_on_fault_block_after_detection"] for e in det]),
               mean_other_block_full_scans_after_flag=mean([e["other_block_full_scans_after_flag"] for e in det]),
               mean_total_test_cycles=mean([e["total_test_cycles"] for _, e in out]), mean_interruption_cycles=mean([e["interruption_cycles"] for _, e in out]),
               episodes_with_overdue_blocks_at_end=sum(1 for _, e in out if e["overdue_mask_end"]),
               episodes_ending_in_DEGRADED=sum(1 for _, e in out if e["state_end"] == ST_DEG),
               per_block={BNAMES[b]: dict(episodes=sum(1 for i, _ in out if rows[i]["bidx"] == b),
                                          cleared_while_fault_persists=sum(e["cleared_while_fault_persists"] for i, e in out if rows[i]["bidx"] == b),
                                          flagged=sum(1 for i, e in out if rows[i]["bidx"] == b and e["flagged_tick"] is not None)) for b in range(NB)})
    return agg

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=os.path.join(ROOT, "results_step2a")); ap.add_argument("--verify", type=int, default=200)
    ap.add_argument("--closed-loop", action="store_true"); ap.add_argument("--episodes", type=int, default=0, help="0 = all faults"); ap.add_argument("--profiles", default="")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    stats = load_stats(); rows = fc.load_db(); trace = mission.generate(); M = len(trace); inj = fc.injections(rows, M, INJ_SEED)
    names = a.profiles.split(",") if a.profiles else list(PROFILES)
    summ = {"meta": dict(faults=len(rows), mission_ticks=M, epoch_cycles=EPOCH_CYCLES, injection_seed=INJ_SEED, mission_seed=2024,
                         fault_db_sha256=sha(RESULTS + "/fault_db.csv"), atpg_stats_sha256=sha(RESULTS + "/atpg_stats.json"), mission_trace_sha256=sha(RESULTS + "/mission_trace.csv"),
                         git_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(), argv=sys.argv[1:]), "profiles": {}}
    replay = {}
    for nme in names:
        P = PROFILES[nme]; log, res, s = exp1_profile(nme, P, rows, inj, trace, stats, a.out, M); replay[nme] = res; summ["profiles"][nme] = s
        print(f"{nme:22s} cov {s['fault_coverage']:.4f}  tot_cyc {s['total_test_cycles']:>9d}  interrupt {s['mission_interruption_cycles']:>9d}  mean_lat {s['mean_detection_latency_cycles']:.0f}")
        if a.verify:                    # literal stepping (fault_campaign.full_sim) for a random sample - same sample as v1's --verify
            rnd = random.Random(5); idx = rnd.sample(range(len(rows)), min(a.verify, len(rows))); bad = 0
            for i in idx:
                f = fc.full_sim(P, trace, stats, rows[i], inj[i]); e = res[i]
                if (f[0], f[1], f[2], f[4]) != (e["det"], e["cyc"], e["name"], e["cum"]): bad += 1
            s["verify_full_sim_mismatches"] = bad; s["verify_sample"] = len(idx); assert bad == 0
    if a.closed_loop:
        rnd = random.Random(99); idx = list(range(len(rows))) if not a.episodes else sorted(rnd.sample(range(len(rows)), a.episodes))
        for nme in names:
            summ["profiles"][nme]["closed_loop"] = exp2_profile(nme, PROFILES[nme], rows, inj, trace, stats, a.out, replay[nme], idx)
            c = summ["profiles"][nme]["closed_loop"]; print(f"  closed-loop {nme:22s} episodes {c['episodes']} flagged {c['flagged']} cleared-while-persisting {c['cleared_while_fault_persists']}")
    json.dump(summ, open(a.out + "/campaign_summary.json", "w"), indent=1, default=str)
    cols = ["profile", "faults", "detected", "fault_coverage", "coverage_crit4", "coverage_crit3", "coverage_crit2", "coverage_crit1", "mean_detection_latency_cycles",
            "median_detection_latency_cycles", "p95_detection_latency_cycles", "censored_mean_latency_cycles", "total_test_cycles", "mission_interruption_cycles",
            "full_scans", "partial_scans", "mbist_runs", "online_tests", "detected_in_IDLE", "detected_in_ACTIVE", "detected_in_DEGRADED"]
    with open(a.out + "/comparison_table.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols + ["ticks_IDLE", "ticks_ACTIVE", "ticks_DEGRADED", "overdue_blocks_at_end"])
        for nme in names:
            s = summ["profiles"][nme]; w.writerow([s.get(c, nme if c == "profile" else "") for c in cols] + [s["state_occupancy_ticks"][k] for k in SNAMES] + ["|".join(s["overdue_blocks_at_end"])])

if __name__ == "__main__": main()
