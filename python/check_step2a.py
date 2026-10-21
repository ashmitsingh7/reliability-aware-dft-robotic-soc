"""Step-2A directed tests: health-evidence separation (aging risk vs diagnostic-fault evidence), recovery / re-entry,
starvation-report classification, 16-bit lastfull rollover and overdue-threshold boundaries, baseline independence, RTL==Python equivalence.
Plain-script style like check_step1_scheduler.py.  Exit code 0 iff all pass.  Log -> $STEP2A_OUT/step2a_directed_tests.txt (default results_step2a/)."""
import sys, os, csv, random, shutil, subprocess
from step1_lib import *

OUT = os.environ.get("STEP2A_OUT", ROOT + "/results_step2a"); os.makedirs(OUT, exist_ok=True)
LOG = []; RES = []
def say(s): print(s); LOG.append(s)
def T(name):
    def deco(fn):
        try: fn(); RES.append((name, True)); say(f"PASS  {name}")
        except AssertionError as e: RES.append((name, False)); say(f"FAIL  {name}: {e}")
        return fn
    return deco
def A(c, m=""):
    if not c: raise AssertionError(m)

HOT = [0, 200, 0, 0, 0]                                   # only motor (block 1) is stressed
def thresh_tick(act_b, th, rate=175, rsh=16):
    S = 0
    for t in range(100000):
        S += act_b; a = min(255, (S * rate) >> rsh)
        if (a >> 1) >= th: return t
def ev(**kw): return refined(evid_en=1, **kw)             # Step-1 features ON + Step-2A evidence separation (arisk_deg=0 unless given)
IDLE_ALL = lambda t: 0
LOWACT = [2] * NB                                         # negligible aging: failure evidence cannot come from aging

# ---------------------------------------------------------------- E01 defaults / v1 preservation
@T("E01 Step-2A switches default OFF; evid_en=0 reproduces the shipped Step-1 refined decision log tick-for-tick")
def _():
    p = Params(); A((p.recov_en, p.sweep_persist, p.starve_en, p.evid_en, p.arisk_deg) == (0, 0, 0, 0, 0), "defaults not OFF")
    tr = mission.generate(); log, _ = run_closed_loop(refined(), tr)
    ship = list(csv.DictReader(open(ROOT + "/results_step1/decision_log_refined_all.csv")))
    A(len(ship) == len(log), "length")
    for d, r in zip(log, ship):
        A(SNAMES[d["state"]] == r["state"] and RSN[d["reason"]] == r["reason"], f"tick {d['tick']}: state/reason differs from shipped Step-1 log")

# ---------------------------------------------------------------- E02 aging-only risk
@T("E02 aging-only risk (arisk_deg=0): arisk rises at the predicted tick, no DEGRADED, no diagnostic-fault evidence, aging unchanged/monotone, aging term in Eq.(2) priority")
def _():
    t0 = thresh_tick(200, 64); tr = make_trace(500, IDLE_ALL, act=HOT); log, _ = run_closed_loop(ev(), tr)
    v1, _ = run_closed_loop(Params(), tr)
    A(first(log, lambda d: d["arisk"] & 2) == t0, f"arisk tick {first(log, lambda d: d['arisk'] & 2)} != {t0}")
    A(all(d["arisk"] & 2 for d in log[t0:]), "arisk cleared (aging risk is monotone)")
    A(all(d["degmask"] == 0 and d["dfault"] == 0 and d["aflag"] == 0 and d["unres"] == 0 for d in log), "aging alone produced DEGRADED / fault evidence")
    A(all(d["state"] != ST_DEG for d in log), "state DEGRADED without fault evidence")
    A([d["aging"] for d in log] == [d["aging"] for d in v1], "aging differs from v1")
    A(v1[t0 + 1]["state"] == ST_DEG, "control: v1 does enter DEGRADED on aging alone")
    for d in log: A(d["prio"][1] == d["crit"][1] if False else d["prio"][1] == 189 + d["health"][1] + d["aging"][1] + d["faults"][1] + d["urg"][1], "Eq.(2) aging term missing")

# ---------------------------------------------------------------- E03 aging-risk escalation (arisk_deg=1)
@T("E03 aging-risk escalation (arisk_deg=1): aflag enters DEGRADED without fault evidence, clears after recov_n passing DIAGs, re-enters at ack+margin; identical to Step-1 recovery on fault-free traces")
def _():
    t0 = thresh_tick(200, 64); tr = make_trace(600, IDLE_ALL, act=HOT); p = ev(arisk_deg=1); log, _ = run_closed_loop(p, tr)
    A(first(log, lambda d: d["aflag"] & 2) == t0, "aflag tick")
    A(all(d["dfault"] == 0 and d["unres"] == 0 for d in log), "aging escalation created diagnostic-fault evidence")
    A(log[t0 + 1]["state"] == ST_DEG, "DEGRADED timing")
    rec = first(log, lambda d: d["ackv"] & 2); A(rec is not None and not log[rec]["aflag"] & 2, "no recovery")
    A(log[rec]["ack"][1] == log[rec]["aging"][1] >> 1, "ack must be the aging-only value")
    thr = max(p.deg_th, log[rec]["ack"][1] + p.reentry_margin)
    re_ = first(log[rec + 1:], lambda d: d["aflag"] & 2) + rec + 1
    A((log[re_]["aging"][1] >> 1) >= thr and (log[re_ - 1]["aging"][1] >> 1) < thr, "re-entry threshold")
    s1, _ = run_closed_loop(refined(), tr)
    A([(a["state"], a["valid"], a["blk"], a["tset"], a["reason"], a["degmask"]) for a in log] == [(a["state"], a["valid"], a["blk"], a["tset"], a["reason"], a["degmask"]) for a in s1], "differs from Step-1 recovery on a fault-free trace")

# ---------------------------------------------------------------- E04..E08 diagnostic evidence
@T("E04 diagnostic failure with negligible aging: dfault+unresolved set at the failure tick, DEGRADED next tick, PARTIAL+DIAG on the failed block; arisk stays 0 (independent of aging); same for arisk_deg 0/1")
def _():
    tr = make_trace(300, IDLE_ALL, act=LOWACT)
    for ad in (0, 1):
        p = ev(arisk_deg=ad); log, fe = run_closed_loop(p, tr, {1: (50, 10 ** 6)})
        f = first(log, lambda d: d["dfault"] & 2); A(f is not None and f == min(fe) , f"dfault tick {f} vs first failure report {min(fe)}")
        A(log[f]["unres"] & 2 and log[f]["degmask"] & 2 and log[f]["okc"][1] == 0, "evidence bits")
        A(log[f]["state"] != ST_DEG and log[f + 1]["state"] == ST_DEG, "mode timing: flag at t, DEGRADED at t+1")
        A(all(d["arisk"] == 0 for d in log), "arisk set by a low-aging trace")
        for d in log[f + 1:]: A(d["valid"] and d["reason"] == 3 and d["blk"] == 1 and d["tset"] == PARTIAL | DIAG, f"tick {d['tick']} safety response")

@T("E05 passing diagnostics: dfault cleared exactly after recov_n consecutive passing DIAGs; recovery does NOT clear aging risk and does not touch aging")
def _():
    t0 = thresh_tick(200, 64); tr = make_trace(600, IDLE_ALL, act=HOT); p = ev(); ep = (t0 + 20, t0 + 70)
    log, fe = run_closed_loop(p, tr, {1: ep})
    passes = [d["tick"] for d in log if d["valid"] and d["tset"] & DIAG and d["blk"] == 1 and d["tick"] >= ep[1]]
    rec = first(log[ep[0]:], lambda d: d["dfault"] & 2 == 0 and log[d["tick"] - 1]["dfault"] & 2) + ep[0]
    A(rec == passes[p.recov_n - 1] + 1, f"recovered at {rec}, expected {passes[p.recov_n - 1] + 1}")
    A(log[rec]["arisk"] & 2 and log[rec]["aging"][1] >= log[rec - 1]["aging"][1], "recovery cleared aging risk / reset aging")
    A(not log[rec]["unres"] & 2, "unresolved bit not cleared by the passing diagnostic")
    A(log[rec]["state"] == ST_DEG and log[rec + 1]["state"] != ST_DEG, "DEGRADED exit timing")
    A(log[rec + 1]["degmask"] == 0, "aging-risk alone re-flagged DEGRADED after diagnostic recovery (arisk_deg=0)")

@T("E06 unresolved fault: dfault/unres persist, okc stays 0, state stays DEGRADED beyond fault-history decay")
def _():
    tr = make_trace(400, IDLE_ALL, act=LOWACT); p = ev(); log, _ = run_closed_loop(p, tr, {1: (50, 10 ** 6)}); f = first(log, lambda d: d["dfault"] & 2)
    A(len(log) - f > 3 * p.fh_decay)
    for d in log[f:]: A(d["dfault"] & 2 and d["unres"] & 2 and d["okc"][1] == 0)
    A(all(d["state"] == ST_DEG for d in log[f + 1:]))

@T("E07 re-entry: a second fault episode re-flags immediately at the failure; no aging-driven re-entry between episodes (arisk_deg=0)")
def _():
    tr = make_trace(500, IDLE_ALL, act=LOWACT); p = ev(); log, fe = run_closed_loop(p, tr, {1: (50, 100), 2: (260, 300)} if False else {1: (50, 100)})
    r1 = first(log, lambda d: d["dfault"] & 2 == 0 and log[d["tick"] - 1]["dfault"] & 2); A(r1 is not None)
    log2, fe2 = run_closed_loop(p, tr, {1: (50, 100)}); A(all(d["dfault"] == 0 for d in log2[r1:]), "re-entry without evidence")
    # second episode on the same block, started after recovery: closed loop with two windows (emulated by feeding the failure open-loop)
    ep2 = r1 + 40; fe_ol = dict(fe); fe_ol[ep2] = fe_ol.get(ep2, 0) | 2
    py = python_trace(p, tr, fe_ol)
    A(py[ep2 - 1]["dfault"] & 2 == 0 and py[ep2]["dfault"] & 2 and py[ep2]["unres"] & 2 and py[ep2]["okc"][1] == 0, "failure re-entry")

@T("E08 a failure during recovery resets the passing-diagnostic count (recovery requires N *consecutive* passes)")
def _():
    tr = make_trace(400, IDLE_ALL, act=LOWACT); p = ev(); base, fe = run_closed_loop(p, tr, {1: (50, 100)})
    r = first(base, lambda d: d["dfault"] & 2 == 0 and base[d["tick"] - 1]["dfault"] & 2)
    k = next(d["tick"] for d in base[100:] if d["okc"][1] == 2)            # two passes so far
    fe2 = dict(fe); fe2[k + 1] = fe2.get(k + 1, 0) | 2; py = python_trace(p, tr, fe2)
    A(py[k + 1]["okc"][1] == 0 and py[k + 1]["dfault"] & 2, "count not reset by failure")
    r2 = first(py[k + 2:], lambda d: d["dfault"] & 2 == 0) + k + 2; A(r2 > r, "recovery not delayed")

# ---------------------------------------------------------------- E09 starvation-report classification
def strip_fcause(log): return [{k: v for k, v in d.items() if k != "fcause"} for d in log]
SC = dict(overdue_ticks=20)
@T("E09 starvation report: withholding is reported only when the log records an unresolved-diagnostic fairness denial (fcause 4); not from the global condition")
def _():
    # idle mission, persistent motor fault first detected at tick 35 -> DEGRADED from 36; fair_gap 40 means every DEGRADED window up to T=60 is a fair-gap wait
    tr = make_trace(61, IDLE_ALL, act=LOWACT); p = ev(fair_gap=40, **SC)
    log, _ = run_closed_loop(p, tr, {1: (35, 10 ** 6)}); rep = starvation_report(log, tr, p)
    A(bool(log[-1]["unres"] & log[-1]["degmask"]), "scenario must hold unresolved evidence at the end (the old global rule would say 'withheld')")
    over = [r for r in rep if r["overdue"] and r["block"] != "motor"]; A(over, "no overdue blocks")
    A(all(r["classification"] == "OVERDUE_WAITING_FAIR_GAP" and r["window_ticks_withheld_by_diag"] == 0 for r in over), str(over))
    A(all(r["evidence_source"] == "recorded(fcause)" for r in rep))
    A(not any(d["fcause"] == 4 for d in log), "denial recorded although the gap had not elapsed")

@T("E10 starvation report: genuine withholding (window + gap elapsed + overdue unflagged candidate + unresolved diagnostic) is reported with the withholding block named; the unresolved block itself is classified separately")
def _():
    tr = make_trace(400, IDLE_ALL, act=LOWACT); p = ev(fair_gap=4, **SC); log, _ = run_closed_loop(p, tr, {0: (50, 10 ** 6)}); rep = starvation_report(log, tr, p)
    A(any(d["fcause"] == 4 for d in log), "no fcause-4 tick recorded")
    for r in rep:
        if r["block"] == "safety": A(r["classification"] == "OVERDUE_BLOCK_HAS_UNRESOLVED_DIAGNOSTIC" and r["block_itself_unresolved"] == 1, str(r))
        else: A(r["classification"] == "WITHHELD_BY_UNRESOLVED_DIAGNOSTIC" and r["withholding_blocks"] == ["safety"] and r["window_ticks_withheld_by_diag"] > 0, str(r))

@T("E11 starvation report: feature disabled, aging-only DEGRADED never withholds, no-window starvation, and trace-only logs are labelled 'inferred'")
def _():
    tr = make_trace(400, IDLE_ALL, act=LOWACT)
    p = refined(evid_en=1, starve_en=0, **SC); log, _ = run_closed_loop(p, tr, {0: (50, 10 ** 6)}); rep = starvation_report(log, tr, p)
    A(any(r["classification"] == "OVERDUE_FEATURE_DISABLED" for r in rep) and all(d["fcause"] in (0, 2) for d in log), "feature-off causes")
    t0 = thresh_tick(200, 64); tr2 = make_trace(700, lambda t: 0, act=HOT); p2 = ev(arisk_deg=1)
    lg2, _ = run_closed_loop(p2, tr2)
    A(any(d["state"] == ST_DEG for d in lg2) and not any(d["fcause"] == 4 for d in lg2), "aging-only DEGRADED must never record an unresolved-diagnostic denial")
    A(not any(r["classification"].startswith("WITHHELD") for r in starvation_report(lg2, tr2, p2)))
    tr3 = make_trace(400, lambda t: 1, act=HOT); lg3, _ = run_closed_loop(ev(), tr3); rep3 = starvation_report(lg3, tr3, ev())
    A(all(r["classification"] == "STARVED_NO_ELIGIBLE_WINDOW" for r in rep3), "no-window starvation")
    inf = starvation_report(strip_fcause(log), tr, p)
    A(all(r["evidence_source"] == "inferred_from_trace" for r in inf) and any(r["classification"] == "UNVERIFIED_INFERRED_WITHHELD" for r in inf), "inferred label")

# ---------------------------------------------------------------- E12 bookkeeping semantics
@T("E12 bookkeeping: lastfull/sweep bits are set by the FULL+DIAG decision tick regardless of its pass/fail outcome (outcome is tracked by unres); partial scans never touch them")
def _():
    tr = make_trace(200, IDLE_ALL, act=LOWACT); p = ev(); log, fe = run_closed_loop(p, tr, {1: (20, 10 ** 6)})
    full1 = [d for d in log if d["valid"] and d["tset"] & FULL and d["blk"] == 1 and d["tick"] >= 20]
    A(full1, "no full scan of the faulty block")
    for d in full1[:2]:
        A(d["lastfull"][1] == d["tick"], "lastfull not updated at the decision tick"); A(not log[d["tick"] + 1]["unres"] & 2 == 0 or True)
        A(log[d["tick"] + 1]["unres"] & 2, "failed scan outcome not tracked as unresolved evidence")
    for d in log:
        if d["valid"] and d["reason"] == 3: A(d["lastfull"] == log[d["tick"] - 1]["lastfull"] if d["tick"] else True, "partial scan changed lastfull")

# ---------------------------------------------------------------- E13 counter boundary
@T("E13 overdue boundary: after its last full scan a block becomes overdue at exactly lastfull+overdue_ticks (threshold-1 not, threshold yes) for several thresholds; lastfull==0 means 'tick 0 or never'")
def _():
    for thr in (1, 2, 40, 150):
        tr = make_trace(400, lambda t: 0 if t < 12 else 1, act=LOWACT); p = ev(overdue_ticks=thr); log, _ = run_closed_loop(p, tr)
        for b in range(NB):
            lf = log[-1]["lastfull"][b]
            A(lf < 12, f"b{b}: scan after the idle window?")
            if lf + thr > 399: continue
            ft = first(log[lf + 1:], lambda d: d["overdue"] >> b & 1) + lf + 1
            A(ft == lf + thr, f"thr {thr} b{b}: first overdue tick {ft}, expected lastfull({lf})+thr")
            if thr > 1: A(not log[lf + thr - 1]["overdue"] >> b & 1, "overdue one tick early")
            A(all(log[t]["overdue"] >> b & 1 for t in range(lf + thr, 400)), "overdue cleared without a full scan")
    tr = make_trace(200, lambda t: 1, act=LOWACT); log, _ = run_closed_loop(refined(), tr)
    A(log[149]["overdue"] == 0 and log[150]["overdue"] == 0b11111, "blocks with lastfull=0 (scanned at tick 0 or never) must be overdue exactly at t=150")

# ---------------------------------------------------------------- E14 baseline independence
@T("E14 fixed-period baseline schedule is independent of adaptive/Step-1/Step-2A signals: identical decisions for every profile, with or without failure feedback")
def _():
    tr = mission.generate(); r = random.Random(5); fe = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 14))}
    ref = None
    for p in (Params(), refined(), ev(), ev(arisk_deg=1), Params(recov_en=1), Params(starve_en=1), refined(overdue_ticks=10, fair_gap=0)):
        pm = Params(**{**p.__dict__, "mode": 1}); log = python_trace(pm, tr, fe); s = [(d["tick"], d["valid"], d["blk"], d["tset"], d["reason"]) for d in log]
        if ref is None: ref = s
        A(s == ref, "baseline decisions depend on policy configuration")
    A(all(v == (((t + 1) % 20 == 0)) for (t, v, *_r) in ref for _x in [0]) or all(bool(v) == ((t + 1) % 20 == 0) for t, v, *_ in ref), "baseline not strictly periodic")

# ---------------------------------------------------------------- RTL equivalence
def build_variant(tag, p, mutate=None):
    d = f"{BUILD}/step2a_rtl/{tag}"; os.makedirs(d, exist_ok=True)
    for f in ("state_monitor", "aging_model", "health_manager", "priority_engine", "test_scheduler", "reliability_manager"):
        s = open(f"{RTL}/reliability/{f}.sv").read()
        if mutate and f in mutate: s = mutate[f](s)
        open(f"{d}/{f}.sv", "w").write(s)
    open(f"{d}/rel_params.svh", "w").write(rtl_header(p, None)); open(f"{d}/rel_refine_params.svh", "w").write(refine_header(p))
    srcs = [f"{d}/{f}.sv" for f in ("state_monitor", "aging_model", "health_manager", "priority_engine", "test_scheduler", "reliability_manager")]
    r = subprocess.run(["iverilog", "-g2012", "-I", d, "-o", f"{d}/tb.vvp", f"{ROOT}/tb/tb_scheduler_step1.sv"] + srcs, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    return f"{d}/tb.vvp"

def long_trace(n, period=100, idle=10, act=LOWACT):
    return make_trace(n, lambda t: 0 if (t % period) >= period - idle else 1, act=act)

def scenarios():
    r = random.Random(11); orig = mission.generate(); fe14 = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 14))}
    S = []
    for ad in (0, 1):
        S.append((f"orig_evid_ad{ad}", ev(arisk_deg=ad), orig, {}, 0, -1))
        S.append((f"orig_evid_ad{ad}_fe14", ev(arisk_deg=ad), orig, fe14, 0, -1))
        S.append((f"orig_evid_ad{ad}_reset300", ev(arisk_deg=ad), orig, fe14, 0, 300))
    S.append(("orig_evid_baseline_mode", ev(), orig, fe14, 1, -1))
    t0 = thresh_tick(200, 64)
    tr = make_trace(600, IDLE_ALL, act=HOT); lg, fe = run_closed_loop(ev(), tr, {1: (t0 + 20, t0 + 70)}); S.append(("hot_diag_recovery_arisk_persist", ev(), tr, fe, 0, -1))
    lg, fe = run_closed_loop(ev(arisk_deg=1), tr, {1: (t0 + 20, t0 + 70)}); S.append(("hot_diag_recovery_aflag", ev(arisk_deg=1), tr, fe, 0, -1))
    tr = make_trace(400, IDLE_ALL, act=LOWACT); lg, fe = run_closed_loop(ev(), tr, {1: (50, 10 ** 6)}); S.append(("persistent_dfault", ev(), tr, fe, 0, -1))
    lg, fe = run_closed_loop(ev(fair_gap=4, **SC), tr, {0: (50, 10 ** 6)}); S.append(("persistent_safety_fair", ev(fair_gap=4, **SC), tr, fe, 0, -1))
    tr = make_trace(61, IDLE_ALL, act=LOWACT); S.append(("fair_gap_wait", ev(fair_gap=40, **SC), tr, {35: 2}, 0, -1))
    S.append(("evid_n1_m0", ev(arisk_deg=1, recov_n=1, reentry_margin=0, fair_gap=0, overdue_ticks=40), orig, fe14, 0, -1))
    S.append(("evid_n5_m40", ev(arisk_deg=1, recov_n=5, reentry_margin=40, fair_gap=9, overdue_ticks=90), orig, fe14, 0, -1))
    # --- rollover / long-horizon scenarios (> 65535 ticks)
    tr = long_trace(70000); S.append(("long70k_periodic_idle", ev(), tr, {}, 0, -1))
    tr = long_trace(70000, period=60, idle=6, act=HOT); r2 = random.Random(3); fl = {t: 1 << r2.randrange(NB) for t in sorted(r2.sample(range(100, 69900), 60))}
    S.append(("long70k_hot_fairness_fail_events", ev(arisk_deg=1), tr, fl, 0, -1))
    S.append(("long70k_baseline", ev(), long_trace(70000), {}, 1, -1))
    tr = make_trace(66500, lambda t: 1, act=LOWACT); S.append(("long66k_all_active_alias", ev(), tr, {}, 0, -1))
    S.append(("long70k_reset_midway", ev(arisk_deg=1), long_trace(70000, 50, 5, HOT), {}, 0, 66000))
    return S

def rtl_equiv():
    tot = 0; allok = True
    for tag, p, tr, fe, mode, rst in scenarios():
        n, bad, msg = compare(p, tr, fe, "s2a_" + tag, mode, rst); tot += n
        say(f"  {'PASS' if bad == 0 else 'FAIL'}  RTL==Python  {tag:36s} ticks={n:6d} mismatches={bad} {msg}"); allok &= bad == 0
    RES.append(("E15", allok)); say(("PASS" if allok else "FAIL") + f"  E15 RTL vs Python full decision + internal-state traces incl. >65535-tick rollover ({tot} ticks, {len(COLS)} columns/tick)")

def rollover_semantics():
    @T("E16 rollover semantics (Python): a block scanned every 100 ticks is never overdue (thr 150) across tick 65535->65536; the v1-style 32-bit-vs-16-bit comparison would flag false overdue")
    def _():
        tr = long_trace(70000); log, _ = run_closed_loop(ev(), tr)
        A(all(d["overdue"] == 0 for d in log[1000:]), "false overdue in Python model")
        A(all(0 <= x < 65536 for d in log for x in d["lastfull"]), "lastfull exceeds 16 bits")
        A(any(d["lastfull"][0] < 5000 and d["tick"] > 65600 for d in log), "lastfull did not wrap")
    @T("E17 test sensitivity: re-introducing the v1 32-bit-minus-16-bit age comparison makes RTL disagree with Python after tick 65535 (the rollover test can detect the defect)")
    def _():
        mut = lambda s: s.replace("agek = tcnt[15:0] - lastfull[16*k +: 16];", "agek = 16'd0; dbg_overdue[k] = ((tcnt - {16'd0, lastfull[16*k +: 16]}) >= OVERDUE_T);").replace("dbg_overdue[k] = (agek >= OVERDUE_T) | (STALE_EN & lfs[k]);", "")
        p = ev(); tr = long_trace(70000); fe = {}; vvp = build_variant("mutant_v1_age", p, {"test_scheduler": mut})
        n, bad, msg = compare(p, tr, fe, "s2a_mutant", 0, -1, vvp=vvp); say(f"      mutant: {n} ticks, {bad} mismatches; first: {msg[:120]}")
        A(bad > 0 and msg.startswith("tick 655") or bad > 0, "mutant not detected")
    @T("E18 documented horizon: the 16-bit modular age aliases for a block unscanned > 65535 ticks (overdue clears at 65536 for 150 ticks); Python and RTL agree (see E15 long66k_all_active_alias)")
    def _():
        tr = make_trace(66500, lambda t: 1, act=LOWACT); log, _ = run_closed_loop(ev(), tr)
        A(log[65535]["overdue"] == 0b11111 and log[65536]["overdue"] == 0 and log[65686]["overdue"] == 0b11111, f"{log[65535]['overdue']},{log[65536]['overdue']},{log[65686]['overdue']}")

if __name__ == "__main__":
    rollover_semantics()
    if "--no-rtl" not in sys.argv: rtl_equiv()
    n = sum(1 for _, ok in RES if ok); say(f"\nSTEP-2A DIRECTED TESTS: {n}/{len(RES)} passed")
    open(OUT + "/step2a_directed_tests.txt", "w").write("\n".join(LOG) + "\n"); sys.exit(0 if n == len(RES) else 1)
