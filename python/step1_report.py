"""Step-1 validation report generator: original mission, v1 vs refined (features individually and all ON).
Writes ONLY to results_step1/ (shipped results/ is never touched).  No fault-coverage claims are made here."""
import csv, json, os
from step1_lib import *
OUT = ROOT + "/results_step1"; os.makedirs(OUT, exist_ok=True)
tr = mission.generate(); stats = load_stats()
CFG = {"v1_default": Params(), "persist_only": Params(sweep_persist=1), "recovery_only": Params(recov_en=1),
       "starvation_only": Params(starve_en=1), "refined_all": refined()}
def inter(d):   # same definition as fault_campaign.log_rows: non-ONLINE test cycles on mission-active ticks
    if not d["valid"] or not d["mission_active"]: return 0
    return sum(c[2] for c in components(d["blk"], d["tset"], stats) if c[0] != "ONLINE")
logs = {k: run_closed_loop(p, tr)[0] for k, p in CFG.items()}
summ = {}
for k, lg in logs.items():
    f, pt, last = block_counts(lg); mt = mode_time(lg); rep = starvation_report(lg, tr, CFG[k])
    first_deg = first(lg, lambda d: d["state"] == ST_DEG)
    summ[k] = dict(mode_ticks=mt, first_degraded_tick=first_deg, degraded_ticks_449_599=sum(1 for d in lg[449:600] if d["state"] == ST_DEG),
                   full_scans={BNAMES[b]: f[b] for b in range(NB)}, partial_scans={BNAMES[b]: pt[b] for b in range(NB)},
                   last_full_scan_tick={BNAMES[b]: (lg[-1]["lastfull"][b] if f[b] else None) for b in range(NB)},
                   full_scans_in_449_599={BNAMES[b]: sum(1 for d in lg[449:600] if d["valid"] and d["tset"] & FULL and d["blk"] == b) for b in range(NB)},
                   fairness_slots=sum(1 for d in lg if d["reason"] == 5), sweep_completions=sum(1 for i, d in enumerate(lg) if d["sweep"] == FULLMASK and (i == 0 or lg[i - 1]["sweep"] != FULLMASK)),
                   recoveries=sum(bin(lg[i - 1]["degmask"] & ~lg[i]["degmask"]).count("1") for i in range(1, len(lg))) if CFG[k].recov_en else 0,   # flag 1->0 events
                   mission_interruption_cycles=sum(inter(d) for d in lg), total_test_cycles=sum(sum(c[2] for c in components(d["blk"], d["tset"], stats)) for d in lg if d["valid"]),
                   full_scans_on_mission_active_ticks=sum(1 for d in lg if d["valid"] and d["tset"] & FULL and d["mission_active"]),
                   starvation_end_of_mission=rep)
    with open(f"{OUT}/decision_log_{k}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["tick", "phase", "mission_active", "state", "valid", "block", "tests", "reason", "degmask", "sweep", "lastfull_" + "_".join(BNAMES), "overdue_mask", "okc", "unres"] + [f"aging_{n}" for n in BNAMES])
        for d, x in zip(lg, tr):
            w.writerow([d["tick"], x["phase"], d["mission_active"], SNAMES[d["state"]], d["valid"], "-" if not d["valid"] else ("ALL" if d["blk"] == ALLBLK else BNAMES[d["blk"]]),
                        "+".join(dict.fromkeys(c[0] for c in components(d["blk"], d["tset"], stats))) if d["valid"] else "", RSN[d["reason"]], d["degmask"], d["sweep"],
                        "/".join(map(str, d["lastfull"])), d["overdue"], "/".join(map(str, d["okc"])), d["unres"]] + d["aging"])
json.dump(summ, open(f"{OUT}/step1_mission_summary.json", "w"), indent=1)
# ticks 449..599 side by side + transitions
v1, rf = logs["v1_default"], logs["refined_all"]
with open(f"{OUT}/ticks_449_599_comparison.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["tick", "phase", "mission_active", "v1_state", "v1_block", "v1_tests", "ref_state", "ref_block", "ref_tests", "ref_reason", "ref_degmask", "ref_okc_motor", "ref_ack_motor", "aging_motor"])
    desc = lambda d: ("-", "") if not d["valid"] else (("ALL" if d["blk"] == ALLBLK else BNAMES[d["blk"]]), "+".join(dict.fromkeys(c[0] for c in components(d["blk"], d["tset"], stats))))
    for t in range(449, 600): 
        a, b = v1[t], rf[t]; w.writerow([t, tr[t]["phase"], tr[t]["mission_active"], SNAMES[a["state"]], *desc(a), SNAMES[b["state"]], *desc(b), RSN[b["reason"]], b["degmask"], b["okc"][1], b["ack"][1], b["aging"][1]])
with open(f"{OUT}/state_transitions_refined_all.txt", "w") as fh:
    prev = None
    for d, x in zip(rf, tr):
        key = (d["state"], d["degmask"])
        if key != prev: fh.write(f"tick {d['tick']:3d}: state={SNAMES[d['state']]:8s} degmask={d['degmask']:05b} ackv={d['ackv']:05b} phase={x['phase']}\n")
        prev = key
print(json.dumps({k: {kk: v[kk] for kk in ("mode_ticks", "degraded_ticks_449_599", "full_scans", "partial_scans", "fairness_slots", "sweep_completions", "mission_interruption_cycles", "full_scans_on_mission_active_ticks")} for k, v in summ.items()}, indent=1))
