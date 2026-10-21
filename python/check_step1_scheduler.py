"""Step-1 directed tests + RTL/Python trace equivalence for the scheduler correctness refinements (Fix A DEGRADED recovery,
Fix B persistent idle sweep, Fix C starvation).  Plain-script style like check_rtl_equiv.py: prints PASS/FAIL per test, exit code 0 iff all pass.
Writes the log to results_step1/step1_directed_tests.txt (new output dir; shipped results/ untouched)."""
import sys, csv, random, os
from step1_lib import *

OUT = os.environ.get("STEP1_OUT", ROOT + "/results_step1"); os.makedirs(OUT, exist_ok=True)   # Step-2A: STEP1_OUT lets reruns avoid overwriting results_step1
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

def thresh_tick(act_b, th, rate=175, rsh=16):
    S = 0
    for t in range(100000):
        S += act_b; a = min(255, (S * rate) >> rsh)
        if (a >> 1) >= th: return t
HOT = [0, 200, 0, 0, 0]                      # only motor is stressed -> clean, independent threshold-crossing prediction

# ------------------------------------------------------------------ T1 v1 preserved
@T("T01 v1 configuration: every Step-1 switch defaults OFF and decisions equal the shipped scheduler_results.csv")
def _():
    p = Params(); A((p.recov_en, p.sweep_persist, p.starve_en) == (0, 0, 0), "default switches not off")
    ship = list(csv.DictReader(open(RESULTS + "/scheduler_results.csv")))
    for mode, tag in ((0, "adaptive"), (1, "baseline_N20")):
        rows = [r for r in ship if r["mode"] == tag]; m = Manager(Params(mode=mode)); stats = load_stats(); tr = mission.generate()
        for x, r in zip(tr, rows):
            d = m.step(x["mission_active"], x["act"], x["urg"], [0] * NB)
            sel = "-" if not d["valid"] else ("ALL" if d["blk"] == ALLBLK else BNAMES[d["blk"]])
            types = "+".join(dict.fromkeys(c[0] for c in components(d["blk"], d["tset"], stats))) if d["valid"] else ""
            A((SNAMES[d["state"]], sel, types, RSN[d["reason"]]) == (r["state"], r["selected_block"], r["test_types"], r["reason"]), f"{tag} tick {x['tick']}")
            for b in range(NB): A(d["prio"][b] == int(r[f"prio_{BNAMES[b]}"]) and d["aging"][b] == int(r[f"aging_{BNAMES[b]}"]), f"{tag} tick {x['tick']} prio/aging")

# ------------------------------------------------------------------ T2 threshold
@T("T02 aging threshold crossed: DEGRADED flag set at the predicted tick (not before), DEGRADED state one tick later; same entry rule as v1")
def _():
    t0 = thresh_tick(200, 64); tr = make_trace(300, lambda t: 0, act=HOT)
    for p in (Params(), refined()):
        log, _ = run_closed_loop(p, tr)
        A(first(log, lambda d: d["degmask"] & 2) == t0, f"flag tick {first(log, lambda d: d['degmask'] & 2)} != {t0}")
        A(log[t0 - 1]["degmask"] == 0 and log[t0 - 1]["state"] != ST_DEG)
        A(log[t0]["state"] != ST_DEG and log[t0 + 1]["state"] == ST_DEG, "state-monitor uses previous-tick flags")

# ------------------------------------------------------------------ T3 aging monotone / not reset
@T("T03 aging remains high: aging trace is identical to v1 (monotone, never reset) in refined runs incl. recovery")
def _():
    tr = mission.generate(); v1, _ = run_closed_loop(Params(), tr); rf, _ = run_closed_loop(refined(), tr)
    A([d["aging"] for d in v1] == [d["aging"] for d in rf], "aging differs from v1")
    for b in range(NB): A(all(rf[i]["aging"][b] <= rf[i + 1]["aging"][b] for i in range(len(rf) - 1)), "aging decreased")
    tr = make_trace(500, lambda t: 0, act=HOT); log, _ = run_closed_loop(refined(), tr)
    rec = first(log, lambda d: d["ackv"] & 2); A(rec is not None, "no recovery in scenario")
    A(log[rec]["aging"][1] >= log[rec - 1]["aging"][1] and (log[rec]["aging"][1] >> 1) >= 64, "aging fell / below threshold at recovery")

# ------------------------------------------------------------------ T4/T5/T6 fault, recovery, re-entry
FAULT = {0: (50, 150)}                                              # safety block: persistent fault in ticks 50..149, then healthy
@T("T04 unresolved safety fault: flag + unresolved bit persist while diagnostics fail (even beyond fault-history decay timers); no recovery without evidence")
def _():
    tr = make_trace(400, lambda t: 0); p = Params(recov_en=1)
    log, _ = run_closed_loop(p, tr, {0: (50, 10 ** 6)})
    f0 = first(log, lambda d: d["degmask"] & 1); A(f0 is not None and f0 < 60, "fault not flagged")
    for d in log[f0:]: A(d["degmask"] & 1 and d["unres"] & 1 and d["okc"][0] == 0, f"cleared/ok-count>0 at tick {d['tick']}")
    A(len(log) - f0 > 3 * p.fh_decay, "scenario shorter than 3 decay periods")
    # flagged-but-silent control: v1 has no clearing path at all either; refined must not clear on time alone
    A(all(d["state"] == ST_DEG for d in log[f0 + 1:]), "left DEGRADED while fault unresolved")

@T("T05 successful recovery diagnostic: recovery exactly when recov_n consecutive passing DIAGs follow the last failure; aging not reset; ack recorded")
def _():
    p = Params(recov_en=1); tr = make_trace(400, lambda t: 0); log, _ = run_closed_loop(p, tr, FAULT)
    passes = [d["tick"] for d in log if d["valid"] and d["tset"] & DIAG and d["blk"] == 0 and d["tick"] >= FAULT[0][1]]
    A(len(passes) >= p.recov_n, "no passing diagnostics")
    rec = first(log, lambda d: d["ackv"] & 1); A(rec == passes[p.recov_n - 1] + 1, f"recovered at {rec}, expected {passes[p.recov_n - 1] + 1}")
    A(log[rec - 1]["degmask"] & 1 and not log[rec]["degmask"] & 1)
    for d in log[rec - p.recov_n: rec]: A(d["okc"][0] >= 1 or d["tick"] == rec - p.recov_n)
    A(log[rec]["state"] == ST_DEG and log[rec + 1]["state"] != ST_DEG, "DEGRADED exit timing: mask cleared at tick rec, state leaves DEGRADED at rec+1 (prev-tick flags)")
    A(log[rec]["ack"][0] == (log[rec]["aging"][0] >> 1) + log[rec]["faults"][0] if (log[rec]["aging"][0] >> 1) + log[rec]["faults"][0] < 256 else True)

@T("T06 re-entry: aging-based re-entry at max(deg_th, ack+margin); failure-based re-entry immediate")
def _():
    p = Params(recov_en=1); tr = make_trace(600, lambda t: 0, act=HOT); log, _ = run_closed_loop(p, tr)
    rec = first(log, lambda d: d["ackv"] & 2); ack = log[rec]["ack"][1]; thr = max(p.deg_th, ack + p.reentry_margin)
    S = lambda t: 200 * (t + 1); unh = lambda t: min(255, (S(t) * p.rate) >> p.rshift) >> 1
    pred = next(t for t in range(rec + 1, 600) if unh(t) >= thr); got = first(log[rec + 1:], lambda d: d["degmask"] & 2) + rec + 1
    A(got == pred, f"re-entry at {got}, predicted {pred}"); A(all(not d["degmask"] & 2 for d in log[rec:pred]))
    A(unh(pred - 1) < thr, "re-entered before threshold")
    # failure re-entry (open loop): a single failed test on the recovered block flags it at that very tick
    fe = {rec + 3: 2}; py = python_trace(p, tr, fe)
    A(py[rec + 2]["degmask"] & 2 == 0 and py[rec + 3]["degmask"] & 2, "failure did not re-flag immediately")
    A(py[rec + 3]["okc"][1] == 0 and py[rec + 3]["unres"] & 2, "evidence counters not reset by failure")

# ------------------------------------------------------------------ T7 sweep persistence, T8 partial scans
SHORT = lambda t: 0 if (t % 6) < 3 else 1
@T("T07 repeated IDLE/ACTIVE transitions: sweep progress persists across ACTIVE, unfinished work resumes, no duplicate accounting")
def _():
    tr = make_trace(240, SHORT); v1, _ = run_closed_loop(Params(), tr); rf, _ = run_closed_loop(Params(sweep_persist=1), tr)
    A(sum(d["sweep"] == FULLMASK for d in v1) == 0, "v1 unexpectedly completes sweeps in short windows")
    A(sum(d["sweep"] == FULLMASK for d in rf) > 0, "refined never completes a sweep")
    for i in range(1, len(rf)):                                      # progress never lost except by completed-sweep re-arm
        a, b = rf[i - 1]["sweep"], rf[i]["sweep"]
        if rf[i]["state"] == ST_ACTIVE: A(b == a or a == FULLMASK, f"sweep lost across ACTIVE at tick {i}")
    seen = set()                                                     # duplicate accounting: one FULL per block per sweep
    for d in rf:
        if d["valid"] and d["reason"] == 1:
            if d["sweep"] == (1 << d["blk"]): seen = set()
            A(d["blk"] not in seen, f"duplicate completion for block {d['blk']} at {d['tick']}"); seen.add(d["blk"])
    f1, _, _ = block_counts(v1); f2, _, _ = block_counts(rf); A(min(f2) > min(f1), f"min full scans v1 {f1} refined {f2}")

@T("T08 partial scans never satisfy full-scan bookkeeping (no sweep bit, no last-full update, no overdue relief)")
def _():
    p = Params(recov_en=1, sweep_persist=1); tr = make_trace(400, lambda t: 0, act=HOT); log, _ = run_closed_loop(p, tr)
    deg = [d for d in log if d["valid"] and d["reason"] == 3]; A(len(deg) > 0, "no DEGRADED partial scans occurred")
    for d in deg:
        A(d["tset"] & PARTIAL and not d["tset"] & FULL)
        prev = log[d["tick"] - 1]
        A(d["lastfull"] == prev["lastfull"], f"last-full tick changed by partial scan at {d['tick']}")
        # sweep bits may only change through the (v1-identical) re-arm of an already COMPLETED sweep; a partial scan never sets a bit
        A(d["sweep"] == prev["sweep"] or (prev["sweep"] == FULLMASK and d["sweep"] == 0), f"sweep bit set by partial scan at {d['tick']}")
    f, pt, _ = block_counts(log); A(pt[1] == len(deg) and pt[1] > 0)

# ------------------------------------------------------------------ T9/T10/T11 starvation
@T("T09 repeated DEGRADED ticks with unresolved safety fault: diagnostic stays prioritized; fairness never preempts; withholding is reported")
def _():
    p = refined(); tr = make_trace(500, lambda t: 0); log, _ = run_closed_loop(p, tr, {0: (50, 10 ** 6)})
    f0 = first(log, lambda d: d["degmask"] & 1)
    for d in log[f0 + 1:]:
        A(d["valid"] and d["reason"] == 3 and d["blk"] == 0, f"tick {d['tick']} not the safety diagnostic ({d['reason']},{d['blk']})")
    rep = starvation_report(log, tr, p); bad = [r for r in rep if r["overdue"]]
    A(bad and all(r["classification"] == "WITHHELD_BY_UNRESOLVED_DIAGNOSTIC" for r in bad if r["block"] != "safety") , str(rep))

@T("T10 long mission with eligible windows: unaffected blocks keep receiving full scans in DEGRADED; waiting bound holds")
def _():
    p = refined(recov_en=0); tr = make_trace(900, lambda t: 0, act=HOT); log, _ = run_closed_loop(p, tr)
    f = first(log, lambda d: d["degmask"] & 2); A(f is not None)
    bound = p.overdue_ticks + (NB - 1) * (p.fair_gap + 1)
    for b in (0, 2, 3, 4):
        ticks = [d["tick"] for d in log if d["valid"] and d["tset"] & FULL and d["blk"] == b] + [len(log)]
        ticks = [t for t in ticks if t >= f - 1] ; A(len(ticks) > 1, f"block {b} got no full scan after DEGRADED entry")
        gaps = [y - x for x, y in zip([f - 1] + ticks[:-1], ticks)]
        A(max(gaps[:-1] or [0]) <= bound, f"block {b} gap {max(gaps[:-1])} > bound {bound}")
    for d in log:
        if d["reason"] == 5: A(d["mission_active"] == 0 and d["state"] == ST_DEG and d["tset"] & FULL and not d["tset"] & PARTIAL)
    A(sum(d["reason"] == 5 for d in log) > 0, "no fairness slot used")
    v1log, _ = run_closed_loop(Params(), tr); fv, _, _ = block_counts(v1log); fr, _, _ = block_counts(log)
    A(fr[0] > fv[0] and fr[4] > fv[4], f"v1 {fv} refined {fr}")
    A(all(r["classification"] == "OK" for r in starvation_report(log, tr, p) if r["block"] != "motor"))

@T("T11 mission without eligible test windows: starvation reported explicitly; no full scan is forced into ACTIVE")
def _():
    p = refined(); tr = make_trace(400, lambda t: 1, act=HOT); log, _ = run_closed_loop(p, tr)
    A(all(not (d["valid"] and d["tset"] & FULL) for d in log[3:]), "full scan executed in an all-ACTIVE mission")
    rep = starvation_report(log, tr, p); A(all(r["classification"] == "STARVED_NO_ELIGIBLE_WINDOW" and r["eligible_windows_since"] == 0 for r in rep), str(rep))
    A(all(log[-1]["overdue"] >> b & 1 for b in range(NB)), "overdue mask not raised")

@T("T12 safety/architecture invariants over all scenarios: ACTIVE state runs ONLINE only; fairness only on mission-idle ticks; one decision per tick")
def _():
    scen = [(refined(), mission.generate(), {}), (refined(), make_trace(240, SHORT), {}), (refined(recov_en=0), make_trace(900, lambda t: 0, act=HOT), {0: (50, 150)}),
            (refined(), mission.generate(), {1: (100, 10 ** 6)})]
    for p, tr, fl in scen:
        log, _ = run_closed_loop(p, tr, fl)
        for d in log:
            if d["valid"] and d["state"] == ST_ACTIVE: A(d["tset"] == ONLINE)
            if d["reason"] == 5: A(d["mission_active"] == 0)
            if d["state"] == ST_DEG and d["valid"] and d["reason"] == 3: A(d["degmask"] >> d["blk"] & 1 and d["tset"] == PARTIAL | DIAG)
    # interruption budget: refined mission-time test cycles never exceed what the same decision rules allow (no FULL in mission-active DEGRADED)
    log, _ = run_closed_loop(refined(), mission.generate())
    A(all(not (d["mission_active"] and d["state"] == ST_DEG and d["tset"] & FULL) for d in log if d["valid"]))

# ------------------------------------------------------------------ T13: RTL vs Python
def scenarios():
    r = random.Random(77); orig = mission.generate()
    fe14 = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 14))}
    S = []
    S.append(("orig_v1cfg", Params(), orig, {}, 0, -1))
    S.append(("orig_v1cfg_fe14", Params(), orig, fe14, 0, -1))
    S.append(("orig_baseline", Params(), orig, fe14, 1, -1))
    S.append(("orig_refined", refined(), orig, {}, 0, -1))
    S.append(("orig_refined_fe14", refined(), orig, fe14, 0, -1))
    S.append(("orig_refined_baseline_mode", refined(), orig, fe14, 1, -1))
    S.append(("orig_refined_reset300", refined(), orig, fe14, 0, 300))
    S.append(("orig_recov_only_fe14", Params(recov_en=1), orig, fe14, 0, -1))
    S.append(("orig_persist_only", Params(sweep_persist=1), orig, fe14, 0, -1))
    S.append(("orig_starve_only", Params(starve_en=1), orig, fe14, 0, -1))
    tr = make_trace(500, lambda t: 0, act=HOT); lg, fe = run_closed_loop(Params(recov_en=1), tr, FAULT); S.append(("recovery_closed_loop", Params(recov_en=1), tr, fe, 0, -1))
    tr = make_trace(600, lambda t: 0, act=HOT); lg, fe = run_closed_loop(Params(recov_en=1), tr); S.append(("recovery_reentry_aging", Params(recov_en=1), tr, fe, 0, -1))
    tr = make_trace(400, lambda t: 0); lg, fe = run_closed_loop(refined(), tr, {0: (50, 10 ** 6)}); S.append(("persistent_fault_refined", refined(), tr, fe, 0, -1))
    tr = make_trace(240, SHORT); S.append(("short_idle_persist", refined(), tr, {}, 0, -1))
    tr = make_trace(900, lambda t: 0, act=HOT); lg, fe = run_closed_loop(refined(recov_en=0), tr, FAULT); S.append(("fairness_long", refined(recov_en=0), tr, fe, 0, -1))
    tr = make_trace(400, lambda t: 1, act=HOT); S.append(("no_windows", refined(), tr, {}, 0, -1))
    tr = make_trace(300, lambda t: 0, act=HOT); S.append(("threshold_edge", refined(), tr, {}, 0, -1))
    # edge: threshold/margin/gap parameter variants (documented non-default values, exercise comparators)
    S.append(("orig_refined_n1_m0_gap0", refined(recov_n=1, reentry_margin=0, fair_gap=0, overdue_ticks=40), orig, fe14, 0, -1))
    S.append(("orig_refined_n5_m40_gap9", refined(recov_n=5, reentry_margin=40, fair_gap=9, overdue_ticks=90), orig, fe14, 0, -1))
    return S

def rtl_equiv():
    tot = 0; allok = True
    for tag, p, tr, fe, mode, rst in scenarios():
        n, bad, msg = compare(p, tr, fe, tag, mode, rst); tot += n
        say(f"  {'PASS' if bad == 0 else 'FAIL'}  RTL==Python  {tag:34s} ticks={n:4d} mismatches={bad} {msg}"); allok &= bad == 0
    RES.append(("T13 RTL vs Python full decision + internal-state traces", allok)); say(("PASS" if allok else "FAIL") + f"  T13 RTL vs Python full decision + internal-state traces ({tot} ticks, {len(COLS)} columns/tick)")

if __name__ == "__main__":
    if "--no-rtl" not in sys.argv: rtl_equiv()
    n = sum(1 for _, ok in RES if ok); say(f"\nSTEP-1 DIRECTED TESTS: {n}/{len(RES)} passed")
    open(OUT + "/step1_directed_tests.txt", "w").write("\n".join(LOG) + "\n"); sys.exit(0 if n == len(RES) else 1)
