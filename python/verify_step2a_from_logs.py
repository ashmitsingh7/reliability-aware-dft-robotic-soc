"""Independent verification of campaign statistics from RAW artifacts only: per-profile decision_log.csv (the per-tick log), results/fault_db.csv,
results/atpg_stats.json.  Does NOT import reliability_model / fault_campaign: test cycle costs, component ordering and detection rules are
re-implemented here from the documented semantics, and every statistic is recomputed and compared with campaign_summary.json and
profiles/*/fault_results.csv.  Exit 0 iff all match."""
import csv, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = sys.argv[1] if len(sys.argv) > 1 else ROOT + "/results_step2a"
EPOCH = 20000; ONLINE_WINDOW = 128; ONLINE_K = 4; BN = ["safety", "motor", "encoder", "comm", "regfile"]
stats = json.load(open(ROOT + "/results/atpg_stats.json"))
db = list(csv.DictReader(open(ROOT + "/results/fault_db.csv")))
for r in db:
    for k in ("criticality", "detect_full", "detect_partial", "detect_mbist", "detect_online_mask"): r[k] = int(r[k])
    r["b"] = BN.index(r["block"])
summ = json.load(open(OUT + "/campaign_summary.json"))
M = summ["meta"]["mission_ticks"]; inj = []
rr = random.Random(summ["meta"]["injection_seed"])
for _ in db:
    t0 = rr.randint(0, M - 2); inj.append(t0 * EPOCH + rr.randrange(EPOCH))
bad = 0
def chk(cond, msg):
    global bad
    if not cond: bad += 1; print("MISMATCH", msg)

def comps(row):
    """Ordered executed components from one logged decision (types are the unique test names of the decision)."""
    if not int(row["valid"]): return []
    types = row["test_types"].split("+") if row["test_types"] else []; blk = int(row["blk"]); out = []
    for b in (range(5) if blk == 7 else [blk]):
        s = stats[BN[b]]
        if "FULL_SCAN" in types: out.append(("FULL_SCAN", b, s["full_scan_cycles"]))
        if "PARTIAL_SCAN" in types: out.append(("PARTIAL_SCAN", b, s["partial_scan_cycles"]))
        if "MBIST" in types and b == 4: out.append(("MBIST", b, s["mbist_cycles"]))
        if "ONLINE" in types: out.append(("ONLINE", b, ONLINE_WINDOW))
        if "DIAG" in types: out.append(("DIAG", b, s["diag_cycles"]))
    return out

def det(r, name, tick, period):
    return {"FULL_SCAN": r["detect_full"], "PARTIAL_SCAN": r["detect_partial"], "MBIST": r["detect_mbist"]}.get(name, (r["detect_online_mask"] >> ((tick // period) % ONLINE_K)) & 1 if name == "ONLINE" else 0)

for name, s in summ["profiles"].items():
    rows = list(csv.DictReader(open(f"{OUT}/profiles/{name}/decision_log.csv"))); P = s["config"]; period = P["active_period"]
    chk(len(rows) == M, f"{name}: log length")
    tot = intr = 0; cnt = dict(FULL_SCAN=0, PARTIAL_SCAN=0, MBIST=0, ONLINE=0); occ = {"IDLE": 0, "ACTIVE": 0, "DEGRADED": 0}; per_comp = []
    for r in rows:
        cs = comps(r); cyc = sum(c[2] for c in cs); tot += cyc
        ma = int(r["mission_active"]); intr += 0 if not ma else sum(c[2] for c in cs if c[0] != "ONLINE")
        chk(cyc == int(r["test_cycles"]), f"{name}: tick {r['tick']} test_cycles {cyc} vs {r['test_cycles']}")
        for c in cs:
            if c[0] in cnt: cnt[c[0]] += 1
        occ[r["state"]] += 1; per_comp.append((int(r["tick"]), cs))
    chk(tot == s["total_test_cycles"], f"{name}: total cycles {tot} vs {s['total_test_cycles']}")
    chk(intr == s["mission_interruption_cycles"], f"{name}: interruption {intr} vs {s['mission_interruption_cycles']}")
    chk((cnt["FULL_SCAN"], cnt["PARTIAL_SCAN"], cnt["MBIST"], cnt["ONLINE"]) == (s["full_scans"], s["partial_scans"], s["mbist_runs"], s["online_tests"]), f"{name}: scan counts {cnt}")
    chk(occ == s["state_occupancy_ticks"], f"{name}: occupancy {occ}")
    # first detection recomputed from the raw per-tick log
    lat = []; cens = []; nd = 0; bb = {b: [0, 0] for b in BN}; tier = {c: [0, 0] for c in (1, 2, 3, 4)}; fr = list(csv.DictReader(open(f"{OUT}/profiles/{name}/fault_results.csv")))
    for r, c0, x in zip(db, inj, fr):
        hit = None
        for tick, cs in per_comp:
            start = tick * EPOCH
            if not cs or start <= c0: continue
            t_in = 0
            for nm, b, cy in cs:
                t_in += cy
                if b == r["b"] and det(r, nm, tick, period): hit = (start + t_in, nm); break
            if hit: break
        bb[r["block"]][1] += 1; tier[r["criticality"]][1] += 1
        if hit: nd += 1; lat.append(hit[0] - c0); bb[r["block"]][0] += 1; tier[r["criticality"]][0] += 1
        cens.append((hit[0] if hit else M * EPOCH) - c0)
        chk((int(x["detected"]) == 1) == bool(hit) and (not hit or int(x["detection_cycle"]) == hit[0]), f"{name}: fault {r['fault_id']} detection differs from fault_results.csv")
    lat.sort()
    chk(nd == s["detected"], f"{name}: detected {nd} vs {s['detected']}")
    chk(abs(sum(lat) / len(lat) - s["mean_detection_latency_cycles"]) < 1e-6, f"{name}: mean latency")
    chk(lat[len(lat) // 2] == s["median_detection_latency_cycles"] and lat[int(.95 * (len(lat) - 1))] == s["p95_detection_latency_cycles"], f"{name}: median/p95")
    chk(abs(sum(cens) / len(cens) - s["censored_mean_latency_cycles"]) < 1e-6, f"{name}: censored latency")
    for b in BN: chk(abs(bb[b][0] / bb[b][1] - s["coverage_by_block"][b]["coverage"]) < 1e-12, f"{name}: block coverage {b}")
    for c in (1, 2, 3, 4): chk(abs(tier[c][0] / tier[c][1] - s[f"coverage_crit{c}"]) < 1e-12, f"{name}: tier coverage {c}")
    print(f"{name:22s} recomputed from raw log: coverage {nd/len(db):.4f} total {tot} interruption {intr} full/partial/mbist/online {cnt['FULL_SCAN']}/{cnt['PARTIAL_SCAN']}/{cnt['MBIST']}/{cnt['ONLINE']}")
print("INDEPENDENT VERIFICATION:", "PASS" if bad == 0 else f"FAIL ({bad} mismatches)"); sys.exit(0 if bad == 0 else 1)
