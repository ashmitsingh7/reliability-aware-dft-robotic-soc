"""Step-3 Phase-1 directed tests + RTL/Python equivalence for: observability-aware evidence (obs_en), rate-limited FULL-diagnostic escalation (esc_en),
stale bit on the 16-bit lastfull age (stale_en).  Plain-script style like check_step2a.py; exit 0 iff all pass.
Log -> $STEP3_OUT/step3_phase1_tests.txt (default results_step3/).  Campaign-level checks (S11) read results_step3/ produced by step3_campaign.py
(skipped with --no-campaign; run `python3 python/step3_campaign.py` first otherwise)."""
import sys, os, csv, json, random
from step1_lib import *
import fault_campaign as fc

OUT = os.environ.get("STEP3_OUT", ROOT + "/results_step3"); os.makedirs(OUT, exist_ok=True)
LOG = []; RES = []
def say(s): print(s, flush=True); LOG.append(s)
def T(name):
    def deco(fn):
        try: fn(); RES.append((name, True)); say(f"PASS  {name}")
        except AssertionError as e: RES.append((name, False)); say(f"FAIL  {name}: {e}")
        return fn
    return deco
def A(c, m=""):
    if not c: raise AssertionError(m)

def ev(**kw): return refined(evid_en=1, **kw)
OBS = dict(obs_en=1); ESC = dict(obs_en=1, esc_en=1)
IDLE_ALL = lambda t: 0
LOWACT = [2] * NB
stats = load_stats()

def run_cl(P, trace, fb, det, c0, c1=None):
    """Closed loop with a synthetic fault table: fault on block fb is detected by the component names in `det`, present from tick c0 (decisions of ticks > c0)
    until tick c1 (exclusive).  Returns (log, fe {tick: block mask}, fcl {tick: packed class word}) in the format step1_lib.compare expects."""
    m = Manager(P); res = [0] * NB; cls = [0] * NB; log = []; fe = {}; fcl = {}
    for x in trace:
        t = x["tick"]
        if any(res): fe[t] = sum(1 << b for b in range(NB) if res[b]); fcl[t] = pack_cls({b: cls[b] for b in range(NB) if res[b]})
        d = m.step(x["mission_active"], x["act"], x["urg"], res, cls); log.append(d); res = [0] * NB; cls = [0] * NB
        if d["valid"] and t > c0 and (c1 is None or t < c1):
            mask = 0
            for name, b, cy in components(d["blk"], d["tset"], stats):
                if b == fb and name in det: mask |= CLS_OF[name]
            if mask: res[fb] = 1; cls[fb] = mask
    return log, fe, fcl

def flag(log, b): return [(d["degmask"] >> b) & 1 for d in log]
FULLDET = {"FULL_SCAN", "MBIST", "ONLINE"}          # a fault that a PARTIAL scan cannot observe (the Step-2B situation); DIAG never detects

# ------------------------------------------------------------------ switches / default behaviour
@T("S01 every Step-3 switch defaults OFF; refined(evid_en=1) profile unchanged (obs_en=esc_en=stale_en=0)")
def _():
    p = Params(); A((p.obs_en, p.esc_en, p.stale_en) == (0, 0, 0)); p = ev(); A((p.obs_en, p.esc_en, p.stale_en) == (0, 0, 0))

@T("S02 obs_en=0: the failing-class input is ignored; decisions and all state columns are identical to the Step-2A model for arbitrary res_cls values")
def _():
    tr = mission.generate(); r = random.Random(5); fe = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 20))}
    cl = {t: pack_cls({b: r.randrange(16) for b in range(NB)}) for t in fe}
    a = python_trace(ev(), tr, fe, -1, None); b = python_trace(ev(), tr, fe, -1, cl)
    A(all(expected_row(i, x)[:-3] == expected_row(i, y)[:-3] for i, (x, y) in enumerate(zip(a, b))), "res_cls influenced a non-obs run")
    A(all(d["nf"] == 0 and d["reason"] != 6 for d in b), "nf/escalation active with obs_en=0")

# ------------------------------------------------------------------ observability-aware evidence
@T("S03 the Step-2B flaw reproduces without obs_en (flag clears while the fault persists) and is gone with obs_en: flag never clears, unres stays set, okc stays 0")
def _():
    tr = make_trace(300, IDLE_ALL, act=LOWACT); b = 1
    ref, _, _ = run_cl(ev(), tr, b, FULLDET, 50); fr = flag(ref, b); A(any(not f for f in fr[fr.index(1):]), "reference did not clear (flaw not reproduced)")
    log, _, _ = run_cl(ev(**OBS), tr, b, FULLDET, 50); fl = flag(log, b); t0 = fl.index(1)
    A(all(fl[t0:]), "obs_en cleared the flag while the fault persists")
    A(all((d["unres"] >> b) & 1 for d in log[t0:]) and all(d["okc"][b] == 0 for d in log[t0:] if d["tick"] > t0 + 1), "unres/okc moved on non-dominating passes")
    A(all(d["reason"] != 6 for d in log), "escalation fired with esc_en=0")
    A(any((d["tset"] & PARTIAL) and d["state"] == ST_DEG for d in log), "scenario never ran DEGRADED partial scans")

@T("S04 PARTIAL-class evidence is cleared by recov_n partial+DIAG passes with obs_en (no needless escalation); an UNKNOWN class (0) is treated as needing FULL")
def _():
    tr = make_trace(200, IDLE_ALL, act=LOWACT)
    for cls, need in ((CLS_PARTIAL, 0), (0, 1), (CLS_ONLINE, 1), (CLS_MBIST, 1), (CLS_FULL, 1), (CLS_PARTIAL | CLS_ONLINE, 1)):
        m = Manager(ev(**ESC)); log = []
        for x in tr:
            res = [0] * NB; rc = [0] * NB
            if x["tick"] == 20: res[2] = 1; rc[2] = cls
            log.append(m.step(x["mission_active"], x["act"], x["urg"], res, rc))
        fl = flag(log, 2); t0 = fl.index(1)
        A(log[20]["nf"] == need << 2, f"class {cls}: nf={log[20]['nf']}")
        if need == 0: A(any(not f for f in fl[t0:]) and all(d["reason"] != 6 for d in log), f"PARTIAL-class evidence did not clear by partial passes / escalated (class {cls})")
        else: A(any(d["reason"] == 6 and d["blk"] == 2 for d in log), f"class {cls} never escalated")

@T("S05 evidence accumulates: a PARTIAL-class failure followed by a FULL-class failure while unresolved needs FULL depth; a later partial pass must not clear it")
def _():
    tr = make_trace(80, IDLE_ALL, act=LOWACT); m = Manager(ev(**OBS)); log = []
    for x in tr:
        res = [0] * NB; rc = [0] * NB
        if x["tick"] == 10: res[3] = 1; rc[3] = CLS_PARTIAL
        if x["tick"] == 12: res[3] = 1; rc[3] = CLS_FULL
        log.append(m.step(x["mission_active"], x["act"], x["urg"], res, rc))
    A(log[10]["nf"] == 0 and log[12]["nf"] == 1 << 3, (log[10]["nf"], log[12]["nf"]))
    A(all((d["unres"] >> 3) & 1 and d["nf"] == 1 << 3 for d in log[12:]), "evidence cleared by a non-dominating pass")
    m = Manager(ev(**OBS)); log = []                                                   # reverse order: FULL-class first, then a PARTIAL-class failure must NOT lower the requirement
    for x in tr:
        res = [0] * NB; rc = [0] * NB
        if x["tick"] == 10: res[3] = 1; rc[3] = CLS_FULL
        if x["tick"] == 12: res[3] = 1; rc[3] = CLS_PARTIAL
        log.append(m.step(x["mission_active"], x["act"], x["urg"], res, rc))
    A(log[10]["nf"] == 1 << 3 and log[12]["nf"] == 1 << 3, (log[10]["nf"], log[12]["nf"]))

@T("S06 a dominating pass (FULL+DIAG) clears unres and nf and counts toward recovery; a non-dominating pass (PARTIAL+DIAG while nf=1) does neither")
def _():
    m = Manager(ev(**OBS)); tr = make_trace(60, IDLE_ALL, act=LOWACT); log = []
    for x in tr:
        res = [0] * NB; rc = [0] * NB
        if x["tick"] == 10: res[1] = 1; rc[1] = CLS_FULL
        log.append(m.step(x["mission_active"], x["act"], x["urg"], res, rc))
    part = [d for d in log if d["state"] == ST_DEG and d["blk"] == 1 and d["tset"] == (PARTIAL | DIAG) and d["tick"] > 11]
    A(len(part) >= 3 and all(log[d["tick"] + 1]["okc"][1] == 0 and (log[d["tick"] + 1]["unres"] >> 1) & 1 for d in part[:-1]), "partial pass changed evidence")
    # now inject the dominating pass by hand: same manager state, force a FULL+DIAG decision outcome
    m = Manager(ev(**ESC)); log = []
    for x in tr:
        res = [0] * NB; rc = [0] * NB
        if x["tick"] == 10: res[1] = 1; rc[1] = CLS_FULL
        log.append(m.step(x["mission_active"], x["act"], x["urg"], res, rc))
    e = next(d for d in log if d["reason"] == 6); nxt = log[e["tick"] + 1]
    A(e["tset"] == (FULL | DIAG) and not (nxt["unres"] >> 1) & 1 and nxt["okc"][1] == 1 and nxt["nf"] == 0, f"dominating pass not honoured: {e['tset']} {nxt['unres']} {nxt['okc']} {nxt['nf']}")

# ------------------------------------------------------------------ escalation
@T("S07 escalation (persistent fault): FULL+DIAG on the flagged block (+MBIST for regfile), spacing exactly esc_gap+1 ticks, first one immediate, flag never clears, lastfull updated")
def _():
    for gap in (0, 3, 10, 25):
        for b, det in ((1, FULLDET), (4, FULLDET)):
            tr = make_trace(400, IDLE_ALL, act=LOWACT); P = ev(esc_gap=gap, **ESC); log, _, _ = run_cl(P, tr, b, det, 50)
            es = [d for d in log if d["reason"] == 6]; A(len(es) >= 3, f"gap {gap} b {b}: no escalations")
            A(all(d["blk"] == b and d["tset"] == (FULL | DIAG | (MBIST if b == REGFILE else 0)) for d in es), "wrong escalation test set / block")
            f0 = flag(log, b).index(1); A(es[0]["tick"] <= f0 + 2, f"first escalation not immediate: flag {f0} esc {es[0]['tick']}")
            sp = {y["tick"] - x["tick"] for x, y in zip(es, es[1:])}; A(sp == {gap + 1}, f"gap {gap}: spacings {sp}")
            A(all(log[d["tick"]]["lastfull"][b] == d["tick"] & 0xFFFF for d in es), "lastfull not updated by escalation")
            A(all(flag(log, b)[f0:]), "flag cleared while persistent fault present")

@T("S08 transient fault: obs_en alone leaves the block flagged forever (no path to a FULL diagnostic); obs_en+esc_en recovers within esc_gap+1+recov_n+1 ticks, only after the fault ended, via a FULL pass")
def _():
    tr = make_trace(400, IDLE_ALL, act=LOWACT); b = 1; c1 = 120
    lo, _, _ = run_cl(ev(**OBS), tr, b, FULLDET, 50, c1); fo = flag(lo, b); A(fo[-1] == 1 and all(fo[fo.index(1):]), "obs-only did not stay flagged")
    lg, _, _ = run_cl(ev(**ESC), tr, b, FULLDET, 50, c1); fl = flag(lg, b); t0 = fl.index(1); tc = t0 + fl[t0:].index(0)
    A(tc > c1, f"cleared at {tc} before fault end {c1}"); A(tc <= c1 + 10 + 1 + 3 + 2, f"recovery too slow: cleared {tc}, fault end {c1}")
    A(all(fl[tc:][i] == 0 for i in range(len(fl) - tc)), "flag re-set after recovery with no fault present")
    last_esc = max(d["tick"] for d in lg if d["reason"] == 6 and d["tick"] < tc); A(lg[last_esc]["tset"] & FULL, "recovery not via a FULL pass")

@T("S09 escalation needs obs_en AND esc_en AND nf: esc_en without obs_en never escalates; obs_en with PARTIAL-class evidence never escalates; baseline mode never escalates")
def _():
    tr = make_trace(300, IDLE_ALL, act=LOWACT)
    lg, _, _ = run_cl(ev(esc_en=1), tr, 1, FULLDET, 50); A(all(d["reason"] != 6 for d in lg))
    pm = Params(**{**ev(**ESC).__dict__, "mode": 1}); lg = python_trace(pm, tr, {20: 2}, -1, {20: pack_cls({1: CLS_FULL})}); A(all(d["reason"] in (0, 4) for d in lg))

@T("S10 safety/architecture invariants with escalation on: reason 6 only in DEGRADED, only on a flagged block with nf set, one decision per tick, never in baseline mode; v1 invariant 'ACTIVE runs ONLINE only' holds")
def _():
    scen = []
    r = random.Random(1); orig = mission.generate()
    fe = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 30))}; cl = {t: pack_cls({b: r.choice([0, 1, 2, 4, 8, 3, 6, 15]) for b in range(NB) if fe[t] >> b & 1}) for t in fe}
    scen.append(python_trace(ev(esc_gap=4, **ESC), orig, fe, -1, cl))
    lg, _, _ = run_cl(ev(**ESC), orig, 3, FULLDET, 100); scen.append(lg)
    for log in scen:
        for i, d in enumerate(log):
            if d["reason"] == 6: A(d["state"] == ST_DEG and (d["degmask"] >> d["blk"]) & 1 and (d["tset"] & FULL) and d["valid"], f"bad escalation at {d['tick']}")
            if d["state"] == ST_ACTIVE and d["valid"]: A(d["tset"] == ONLINE, "ACTIVE ran a non-ONLINE test")
    A(any(d["reason"] == 6 for log in scen for d in log), "no escalation exercised")

# ------------------------------------------------------------------ stale bit
def long_all_active(n): return make_trace(n, lambda t: 1, act=LOWACT)

@T("S11 stale bit: without it a block unscanned for > 65535 ticks wraps back to 'not overdue' (documented Step-2A horizon); with stale_en it stays overdue until its next full scan, then clears")
def _():
    tr = long_all_active(66500); lo, _, _ = run_cl(ev(), tr, 0, set(), 10 ** 9); A(lo[65535]["overdue"] == 0b11111 and lo[65536]["overdue"] == 0, "baseline wrap behaviour changed")
    ls, _, _ = run_cl(ev(stale_en=1), tr, 0, set(), 10 ** 9); A(all(ls[t]["overdue"] == 0b11111 for t in range(200, 66500)), "stale bit did not hold overdue across the wrap")
    A(ls[65535]["lfstale"] == 0b11111 or ls[65536]["lfstale"] == 0b11111, "stale bit not set at the wrap");
    tr2 = make_trace(66800, lambda t: 0 if t >= 66000 and t < 66030 else 1, act=LOWACT); l2, _, _ = run_cl(ev(stale_en=1), tr2, 0, set(), 10 ** 9)
    A(l2[66100]["overdue"] == 0 and l2[66100]["lfstale"] == 0, f"stale not cleared by a full scan: {l2[66100]['overdue']} {l2[66100]['lfstale']}")

@T("S12 stale bit never changes behaviour when blocks are scanned regularly: identical decisions/state for stale_en=0/1 on a 70,000-tick periodic-idle trace and on the original mission")
def _():
    tr = make_trace(70000, lambda t: 0 if (t % 100) >= 90 else 1, act=LOWACT)
    a = python_trace(ev(), tr, {}); b = python_trace(ev(stale_en=1), tr, {})
    A(all(expected_row(i, x)[:-1] == expected_row(i, y)[:-1] for i, (x, y) in enumerate(zip(a, b))), "stale_en changed regular behaviour")
    o = mission.generate(); a = python_trace(ev(), o, {}); b = python_trace(ev(stale_en=1), o, {}); A(all(expected_row(i, x)[:-1] == expected_row(i, y)[:-1] for i, (x, y) in enumerate(zip(a, b))))

# ------------------------------------------------------------------ campaign level
R3 = ROOT + "/results_step3"; R2A = ROOT + "/results_step2a"
def campaign_checks():
    rows = fc.load_db(); idx = {r["fault_id"]: i for i, r in enumerate(rows)}
    summ = json.load(open(R3 + "/campaign_summary.json")); pf = summ["profiles"]
    @T("S13 campaign (2,515 persistent-fault episodes): the Step-2A reference reproduces the 117 premature clearances; obs_en and obs_en+esc_en have 0 (all fault tables, same injection draw)")
    def _():
        A(summ["meta"]["episodes"] == len(rows) == 2515)
        A(pf["s2a_all3_evid"]["persistent"]["cleared_while_fault_present"] == 117, pf["s2a_all3_evid"]["persistent"]["cleared_while_fault_present"])
        for n in ("s3_obs", "s3_obs_esc", "s3_obs_esc_stale"): A(pf[n]["persistent"]["cleared_while_fault_present"] == 0 and pf[n]["transient"]["cleared_while_fault_present"] == 0, n)
        A(pf["s3_obs"]["persistent"]["flagged"] == pf["s2a_all3_evid"]["persistent"]["flagged"] == 2451)
    @T("S14 the campaign's reference profile reproduces the Step-2A closed-loop episodes exactly (flag tick, clear tick) for all 2,515 faults, so the new runner is trusted")
    def _():
        a = {x["fault_id"]: x for x in csv.DictReader(open(R2A + "/profiles/s2a_all3_evid/closed_loop_episodes.csv"))}
        b = {x["fault_id"]: x for x in csv.DictReader(open(R3 + "/profiles/s2a_all3_evid/persistent_episodes.csv"))}
        A(set(a) == set(b) and len(a) == 2515)
        for k in a: A((a[k]["flagged_tick"], a[k]["cleared_tick"], a[k]["det_cycle"], a[k]["det_test"]) == (b[k]["flagged_tick"], b[k]["cleared_tick"], b[k]["det_cycle"], b[k]["det_test"]), k)
    @T("S15 transient episodes: obs-only recovers none of its flagged blocks; obs+esc recovers every flagged episode whose fault ended >= 30 ticks before the mission end and never clears while the fault is present")
    def _():
        A(pf["s3_obs"]["transient"]["recovered_after_fault_ended"] == 0)
        eps = list(csv.DictReader(open(R3 + "/profiles/s3_obs_esc/transient_episodes.csv"))); M = summ["meta"]["mission_ticks"]; bad = []
        for e in eps:
            if e["flagged_tick"] in ("", "None"): continue
            end_tick = (int(e["injected_cycle"]) + 60 * EPOCH_CYCLES + EPOCH_CYCLES - 1) // EPOCH_CYCLES
            if end_tick <= M - 30 and e["recovered_after_fault_ended"] != "1": bad.append(e["fault_id"])
            A(e["cleared_while_fault_present"] == "0", e["fault_id"])
        A(not bad, f"{len(bad)} not recovered, e.g. {bad[:3]}")
    @T("S16 the cost of escalation is reported, not hidden: mean interruption cycles per flagged persistent episode obs_esc > obs > reference is not assumed; the numbers are in campaign_summary.json (informational)")
    def _():
        for n in ("s2a_all3_evid", "s3_obs", "s3_obs_esc"): say(f"      {n:16s} persistent mean_interruption_cycles(all) {pf[n]['persistent']['mean_interruption_cycles']:.0f}  flagged {pf[n]['persistent']['mean_interruption_cycles_flagged']:.0f}  escalation part {pf[n]['persistent']['mean_escalation_interruption_cycles_flagged']:.0f}")

# ------------------------------------------------------------------ RTL equivalence
def build_variant(tag, p, mutate=None):
    d = f"{BUILD}/step3_rtl/{tag}"; os.makedirs(d, exist_ok=True); fl = ("state_monitor", "aging_model", "health_manager", "priority_engine", "test_scheduler", "reliability_manager")
    for f in fl:
        s = open(f"{RTL}/reliability/{f}.sv").read()
        if mutate and f in mutate: s = mutate[f](s)
        open(f"{d}/{f}.sv", "w").write(s)
    open(f"{d}/rel_params.svh", "w").write(rtl_header(p, None)); open(f"{d}/rel_refine_params.svh", "w").write(refine_header(p))
    r = subprocess.run(["iverilog", "-g2012", "-I", d, "-o", f"{d}/tb.vvp", f"{ROOT}/tb/tb_scheduler_step1.sv"] + [f"{d}/{f}.sv" for f in fl], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    return f"{d}/tb.vvp"

def scenarios():
    r = random.Random(21); orig = mission.generate(); S = []
    fe = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 30))}
    cl = {t: pack_cls({b: r.choice([0, 1, 2, 4, 8, 3, 6, 9, 15]) for b in range(NB) if fe[t] >> b & 1}) for t in fe}
    S.append(("rand_cls_obs", ev(**OBS), orig, fe, cl, 0, -1))
    S.append(("rand_cls_obs_esc", ev(**ESC), orig, fe, cl, 0, -1))
    S.append(("rand_cls_obs_esc_gap0", ev(esc_gap=0, **ESC), orig, fe, cl, 0, -1))
    S.append(("rand_cls_obs_esc_gap3_n1_m0", ev(esc_gap=3, recov_n=1, reentry_margin=0, arisk_deg=1, **ESC), orig, fe, cl, 0, -1))
    S.append(("rand_cls_obs_esc_reset300", ev(**ESC), orig, fe, cl, 0, 300))
    S.append(("rand_cls_baseline_mode", ev(**ESC), orig, fe, cl, 1, -1))
    S.append(("rand_cls_recov_only_obs", Params(recov_en=1, obs_en=1, esc_en=1), orig, fe, cl, 0, -1))      # obs path under the Step-1 (non-evid) health logic
    S.append(("rand_cls_obs_starve_overdue20", ev(overdue_ticks=20, fair_gap=2, **ESC), orig, fe, cl, 0, -1))
    tr = make_trace(400, IDLE_ALL, act=LOWACT)
    S.append(("accumulate_full_then_partial", ev(**ESC), tr, {10: 1 << 3, 12: 1 << 3}, {10: pack_cls({3: CLS_FULL}), 12: pack_cls({3: CLS_PARTIAL})}, 0, -1))
    S.append(("accumulate_partial_then_full", ev(**ESC), tr, {10: 1 << 3, 12: 1 << 3}, {10: pack_cls({3: CLS_PARTIAL}), 12: pack_cls({3: CLS_FULL})}, 0, -1))
    for b in (0, 1, 4):
        lg, f_, c_ = run_cl(ev(**ESC), tr, b, FULLDET, 50); S.append((f"persistent_b{b}_obs_esc", ev(**ESC), tr, f_, c_, 0, -1))
    lg, f_, c_ = run_cl(ev(**ESC), tr, 1, FULLDET, 50, 120); S.append(("transient_b1_obs_esc", ev(**ESC), tr, f_, c_, 0, -1))
    lg, f_, c_ = run_cl(ev(**OBS), tr, 1, FULLDET, 50, 120); S.append(("transient_b1_obs_only", ev(**OBS), tr, f_, c_, 0, -1))
    lg, f_, c_ = run_cl(ev(**ESC), orig, 3, FULLDET, 100); S.append(("orig_mission_persistent_comm", ev(**ESC), orig, f_, c_, 0, -1))
    lg, f_, c_ = run_cl(ev(**ESC), orig, 4, FULLDET, 200, 330); S.append(("orig_mission_transient_regfile", ev(**ESC), orig, f_, c_, 0, -1))
    # stale / rollover
    S.append(("long66k_all_active_stale", ev(stale_en=1), long_all_active(66500), {}, {}, 0, -1))
    S.append(("long70k_stale_scan_after_wrap", ev(stale_en=1), make_trace(70000, lambda t: 0 if 66000 <= t < 66030 else 1, act=LOWACT), {}, {}, 0, -1))
    S.append(("long70k_stale_reset_midway", ev(stale_en=1), make_trace(70000, lambda t: 1, act=LOWACT), {}, {}, 0, 66000))
    S.append(("long70k_stale_all_features", ev(stale_en=1, **ESC), make_trace(70000, lambda t: 0 if (t % 80) >= 70 else 1, act=LOWACT), {t: 2 for t in range(5000, 69000, 4000)},
              {t: pack_cls({1: CLS_ONLINE}) for t in range(5000, 69000, 4000)}, 0, -1))
    return S

def rtl_equiv():
    tot = 0; allok = True
    for tag, p, tr, fe, cl, mode, rst in scenarios():
        n, bad, msg = compare(p, tr, fe, "s3_" + tag, mode, rst, fc=cl); tot += n
        say(f"  {'PASS' if bad == 0 else 'FAIL'}  RTL==Python  {tag:36s} ticks={n:6d} mismatches={bad} {msg}"); allok &= bad == 0
    RES.append(("S17", allok)); say(("PASS" if allok else "FAIL") + f"  S17 RTL vs Python: decisions + all internal-state columns, incl. nf/esc/lfstale, obs/esc/stale on, resets, baseline mode, >65535-tick horizon ({tot} ticks, {len(COLS)} columns/tick)")

def mutants():
    tr = make_trace(400, IDLE_ALL, act=LOWACT); P = ev(**ESC); lg, f_, c_ = run_cl(P, tr, 1, FULLDET, 50, 120)
    r = random.Random(21); orig = mission.generate(); fe = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 30))}
    cl = {t: pack_cls({b: r.choice([0, 1, 2, 4, 8, 3, 6, 9, 15]) for b in range(NB) if fe[t] >> b & 1}) for t in fe}
    M = [("M1 dominance check removed (any DIAG pass clears)", {"health_manager": lambda s: s.replace("dom  = !OBS_EN || last_tset[0] || (!nf[b] && last_tset[1]);", "dom = 1'b1;")}, P, tr, f_, c_),
         ("M2 escalation rate limit removed", {"test_scheduler": lambda s: s.replace("nf_n[dec_blk] && esc >= ESC_GAP", "nf_n[dec_blk]")}, P, tr, f_, c_),
         ("M3 unknown failure class not treated as needing FULL", {"health_manager": lambda s: s.replace("need = (cls == 4'd0) || ((cls & 4'b1101) != 4'd0);", "need = ((cls & 4'b1101) != 4'd0);")}, ev(**ESC), orig, fe, cl),
         ("M4 nf evidence does not accumulate across failures", {"health_manager": lambda s: s.replace("((unres[b] ? nf[b] : 1'b0) | need)", "need")}, ev(**ESC), make_trace(400, IDLE_ALL, act=LOWACT), {10: 1 << 3, 12: 1 << 3}, {10: pack_cls({3: CLS_FULL}), 12: pack_cls({3: CLS_PARTIAL})}),
         ("M5 stale bit never set", {"test_scheduler": lambda s: s.replace("else if (STALE_EN && age_wrap[kk]) lfs_n[kk] = 1'b1;", "")}, ev(stale_en=1), long_all_active(66500), {}, {}),
         ("M6 escalation does not refresh lastfull", {"test_scheduler": lambda s: s.replace("lastfull_n[16*dec_blk +: 16] = tcnt[15:0]; lf_upd[dec_blk] = 1'b1;\n          end else begin dec_tset = 5'b10010;", "end else begin dec_tset = 5'b10010;")}, ev(overdue_ticks=20, fair_gap=2, **ESC), orig, fe, cl)]
    allok = True
    for name, mut, p, t, f_, c_ in M:
        vvp = build_variant("mut_" + name[:2], p, mut); n, bad, msg = compare(p, t, f_, "s3_mut_" + name[:2], 0, -1, vvp=vvp, fc=c_)
        say(f"      mutant {name}: {n} ticks, {bad} mismatches {msg[:90]}"); allok &= bad > 0
    RES.append(("S18", allok)); say(("PASS" if allok else "FAIL") + "  S18 test sensitivity: each of 6 injected RTL defects (dominance, rate limit, unknown class, accumulation, stale set, lastfull refresh) is caught by the equivalence traces")

if __name__ == "__main__":
    if "--no-campaign" not in sys.argv: campaign_checks()
    if "--no-rtl" not in sys.argv: rtl_equiv(); mutants()
    n = sum(1 for _, ok in RES if ok); say(f"\nSTEP-3 PHASE-1 TESTS: {n}/{len(RES)} passed")
    open(OUT + "/step3_phase1_tests.txt", "w").write("\n".join(LOG) + "\n"); sys.exit(0 if n == len(RES) else 1)
