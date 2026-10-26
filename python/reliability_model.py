"""Bit-exact Python reference model of the Reliability Manager (State Monitor + Aging + Health Manager +
Priority Engine + Scheduler).  The RTL in rtl/reliability/ implements the identical integer semantics and is
checked against this model (python/check_rtl_equiv.py).  Paper elements: Eq.(2), Algorithm 1, Fig. 1/2.
Everything marked 'ASSUMPTION' is NOT specified in the paper."""
from dataclasses import dataclass, field
import json
from common import *

FULL, PARTIAL, MBIST, ONLINE, DIAG = 1, 2, 4, 8, 16
TNAMES = {FULL: "FULL_SCAN", PARTIAL: "PARTIAL_SCAN", MBIST: "MBIST", ONLINE: "ONLINE", DIAG: "DIAG"}
ST_IDLE, ST_ACTIVE, ST_DEG = 0, 1, 2
SNAMES = ["IDLE", "ACTIVE", "DEGRADED"]
RSN = ["none", "idle_sweep_full_suite", "active_online_argmax", "degraded_flagged_block", "baseline_fixed_period", "degraded_idle_fairness", "degraded_escalated_full_diag"]
CLS_FULL, CLS_PARTIAL, CLS_MBIST, CLS_ONLINE = 1, 2, 4, 8     # Step-3 failing-test-class bits (res_cls)
CLS_OF = {"FULL_SCAN": CLS_FULL, "PARTIAL_SCAN": CLS_PARTIAL, "MBIST": CLS_MBIST, "ONLINE": CLS_ONLINE}
ALLBLK = 7

@dataclass
class Params:
    w: tuple = (1, 1, 1, 1, 1)                      # Eq.(2) weights w1..w5 (neutral default - NOT tuned)
    crit_term: tuple = tuple(b["crit"] * 63 for b in BLOCKS)   # ASSUMPTION: tier*63 -> 0..255 scale
    rate: int = 175; rshift: int = 16                # ASSUMPTION: behavioural aging scale (aging = stress*rate>>16, sat 255)
    fp: int = 32                                     # ASSUMPTION: fault-history -> penalty scale
    fh_inc: int = 1; fh_decay: int = 64              # ASSUMPTION: fault history decays by 1 every 64 ticks ("recent")
    stale_k: int = 4                                 # ASSUMPTION: health confidence decays 4/tick since last passing test
    deg_th: int = 64                                 # ASSUMPTION: DEGRADED when aging/2 + fault penalty >= 64
    deb: int = 2                                     # ASSUMPTION: 2-tick debounce on IDLE<->ACTIVE
    active_period: int = 2                           # ASSUMPTION: online test every 2nd ACTIVE tick
    sweep_gap: int = 10                              # ASSUMPTION: idle sweeps re-armed after 10 ticks
    base_n: int = 20                                 # baseline: full scan+MBIST of all blocks every 20 ticks
    mode: int = 0                                    # 0 adaptive, 1 fixed baseline
    # ---- Step-1 correctness refinements.  ALL DEFAULT TO 0/OFF => bit-identical to v1.  Values below are ASSUMPTIONS, not tuned.
    recov_en: int = 0                                # Fix A: per-block sticky DEGRADED flag with evidence-based recovery + hysteresis
    recov_n: int = 3                                 # consecutive passing DIAG decisions on a flagged block needed to clear its flag
    reentry_margin: int = 16                         # re-entry needs unh >= max(deg_th, unh_at_clearance + margin)
    sweep_persist: int = 0                           # Fix B: keep idle-sweep progress across IDLE->ACTIVE/DEGRADED
    starve_en: int = 0                               # Fix C: overdue-block fairness slot in DEGRADED during a genuine mission-idle tick
    overdue_ticks: int = 150                         # a block is overdue if no completed full scan for this many ticks
    fair_gap: int = 4                                # min DEGRADED ticks between fairness slots
    # ---- Step-2A health-evidence separation.  DEFAULT OFF => bit-identical to Step 1 / v1.  Values are ASSUMPTIONS, not tuned.
    evid_en: int = 0                                 # aging risk (arisk) and diagnostic-fault evidence (dfault) are separate per-block states
    arisk_deg: int = 0                               # evid_en only: 1 = an aging-risk block may also force DEGRADED via an *aging* flag (aflag); 0 = only diagnostic faults do
    # ---- Step-3 Phase-1 correctness fixes.  ALL DEFAULT OFF => bit-identical to Step 2A.  Values are ASSUMPTIONS, not tuned.
    obs_en: int = 0                                  # observability-aware evidence: a passing diagnostic clears unres/okc only if its depth dominates the failing test class
    esc_en: int = 0                                  # (needs obs_en) escalate a flagged block whose evidence needs FULL depth to a FULL+DIAG decision, rate-limited
    esc_gap: int = 10                                # min DEGRADED ticks between escalations (first one is immediate after reset)
    stale_en: int = 0                                # per-block stale bit on the 16-bit lastfull age: removes aliasing beyond 65,535 ticks
    fair_unres_en: int = 0                           # permit an overdue, unflagged block's fairness FULL+DIAG even during mission-active DEGRADED ticks while another flagged block retains unresolved evidence

def load_stats():
    return json.load(open(RESULTS + "/atpg_stats.json"))

def components(dec_blk, tset, stats):
    """Ordered (test, block, cycles) executed for one decision."""
    out = []
    blks = range(NB) if dec_blk == ALLBLK else [dec_blk]
    for b in blks:
        s = stats[BNAMES[b]]
        if tset & FULL:    out.append(("FULL_SCAN", b, s["full_scan_cycles"]))
        if tset & PARTIAL: out.append(("PARTIAL_SCAN", b, s["partial_scan_cycles"]))
        if tset & MBIST and b == REGFILE: out.append(("MBIST", b, s["mbist_cycles"]))
        if tset & ONLINE:  out.append(("ONLINE", b, ONLINE_WINDOW))
        if tset & DIAG:    out.append(("DIAG", b, s["diag_cycles"]))
    return out

class Manager:
    def __init__(self, p: Params):
        self.p = p; self.t = 0
        self.st = ST_IDLE; self.dbc = 0
        self.stress = [0] * NB; self.aging = [0] * NB
        self.fh = [0] * NB; self.since = [0] * NB; self.dcnt = 0
        self.degmask = 0; self.sweep = 0; self.gap = p.sweep_gap; self.ap = 0
        self.last_valid = 0; self.last_blk = 0
        # Step-1 state (bookkeeping is always maintained; it only influences decisions when the matching feature flag is on)
        self.last_diag = 0
        self.dflag = [0] * NB; self.ack = [0] * NB; self.ackv = [0] * NB; self.okc = [0] * NB; self.unres = [0] * NB
        self.lastfull = [0] * NB; self.fair = 0
        self.nf = [0] * NB; self.last_tset = 0; self.esc = p.esc_gap; self.lfstale = [0] * NB   # Step-3
        self.dfl = [0] * NB; self.afl = [0] * NB     # Step-2A: diagnostic-fault flag / aging-risk-escalation flag (evid_en only)

    def step(self, mission_active, act, urg, res_fail, res_cls=None):
        p = self.p; t = self.t; self.t += 1
        res_cls = res_cls or [0] * NB
        # 1. State Monitor (uses health-manager degraded flags from previous tick)
        if self.degmask != 0: self.st = ST_DEG; self.dbc = 0
        else:
            raw = ST_ACTIVE if mission_active else ST_IDLE
            if self.st == ST_DEG: self.st = raw; self.dbc = 0
            elif raw == self.st: self.dbc = 0
            elif self.dbc + 1 >= p.deb: self.st = raw; self.dbc = 0
            else: self.dbc += 1
        # 2. Aging model (behavioural digital abstraction)
        for b in range(NB):
            self.stress[b] += act[b]
            self.aging[b] = min(255, (self.stress[b] * p.rate) >> p.rshift)
        # 3. Health manager: fault history, staleness, health terms, degraded flags
        self.dcnt += 1
        if self.dcnt >= p.fh_decay:
            self.dcnt = 0
            self.fh = [max(0, x - 1) for x in self.fh]
        for b in range(NB):
            if res_fail[b]: self.fh[b] = min(255, self.fh[b] + p.fh_inc)
            if self.last_valid and self.last_blk == b and not res_fail[b]: self.since[b] = 0
            else: self.since[b] = min(255, self.since[b] + 1)
        faults = [min(255, self.fh[b] * p.fp) for b in range(NB)]
        unh = [min(255, (self.aging[b] >> 1) + faults[b]) for b in range(NB)]
        health = [min(255, unh[b] + min(255, self.since[b] * p.stale_k)) for b in range(NB)]
        # Step-1 evidence tracking (fault / diagnostic outcome) -- no effect on v1 outputs unless p.recov_en
        for b in range(NB):
            pass_b = bool(self.last_valid and self.last_diag and self.last_blk == b and not res_fail[b])
            if res_fail[b]:
                if p.obs_en:    # anything other than a PARTIAL-only failure (incl. unknown class 0) needs FULL depth to be cleared; evidence accumulates while unresolved
                    need = int(res_cls[b] == 0 or (res_cls[b] & ~CLS_PARTIAL & 0xF) != 0); self.nf[b] = (self.nf[b] if self.unres[b] else 0) | need
                self.okc[b] = 0; self.unres[b] = 1
            elif pass_b:
                dom = (not p.obs_en) or bool(self.last_tset & FULL) or (not self.nf[b] and bool(self.last_tset & PARTIAL))
                if dom: self.okc[b] = min(255, self.okc[b] + 1); self.unres[b] = 0; self.nf[b] = 0
        arisk = [int((self.aging[b] >> 1) >= p.deg_th) for b in range(NB)]    # aging risk: pure aging estimate vs threshold (monotone; never cleared, never reset)
        if p.evid_en:
            # Step-2A: dfault (failed-diagnostic evidence) and aflag (aging-risk escalation) are distinct.  Same entry/recovery timing as Step 1.
            for b in range(NB):
                a2 = self.aging[b] >> 1
                thr = p.deg_th if not self.ackv[b] else max(p.deg_th, self.ack[b] + p.reentry_margin)
                df, af = self.dfl[b], self.afl[b]
                if res_fail[b]: df = 1                                              # failed test = diagnostic-fault evidence
                elif df or af:
                    if self.okc[b] >= p.recov_n:                                    # recovery of DIAGNOSTIC status only; aging untouched
                        if af: self.ack[b] = a2; self.ackv[b] = 1
                        df = 0; af = 0; self.okc[b] = 0
                elif p.arisk_deg and a2 >= thr: af = 1; self.okc[b] = 0           # aging-risk escalation (no fault evidence)
                self.dfl[b], self.afl[b] = df, af
            self.degmask = sum((1 << b) for b in range(NB) if self.dfl[b] or (p.arisk_deg and self.afl[b]))
        elif p.recov_en:
            for b in range(NB):
                thr = p.deg_th if not self.ackv[b] else max(p.deg_th, self.ack[b] + p.reentry_margin)   # may exceed 255: saturated block re-enters only on new failure evidence
                if res_fail[b]: self.dflag[b] = 1                                   # a failed test is direct fault evidence
                elif self.dflag[b]:
                    if self.okc[b] >= p.recov_n:                                    # recovery: N consecutive passing diagnostics
                        self.dflag[b] = 0; self.ack[b] = unh[b]; self.ackv[b] = 1; self.okc[b] = 0
                elif unh[b] >= thr: self.dflag[b] = 1; self.okc[b] = 0              # (re-)entry
            self.degmask = sum((1 << b) for b in range(NB) if self.dflag[b])
        else:
            self.degmask = sum((1 << b) for b in range(NB) if unh[b] >= p.deg_th)
        # 4. Priority engine  (Eq. 2)
        prio = [p.w[0] * p.crit_term[b] + p.w[1] * health[b] + p.w[2] * self.aging[b] + p.w[3] * faults[b] + p.w[4] * urg[b]
                for b in range(NB)]
        # 5. Scheduler (Algorithm 1)
        age = [(t - self.lastfull[b]) & 0xFFFF for b in range(NB)]
        overdue = sum((1 << b) for b in range(NB) if age[b] >= p.overdue_ticks or (p.stale_en and self.lfstale[b]))   # 16-bit modular age (matches RTL lastfull) + Step-3 stale bit
        lf_upd = [0] * NB; esc_in = self.esc
        valid, blk, tset, reason = 0, 0, 0, 0; fcause = 0
        def argmax(cands):
            best = cands[0]
            for b in cands[1:]:
                if prio[b] > prio[best]: best = b
            return best
        if p.mode == 1:
            if (t + 1) % p.base_n == 0: valid, blk, tset, reason = 1, ALLBLK, FULL | MBIST, 4
        elif self.st == ST_IDLE:
            self.ap = 0
            if self.sweep == (1 << NB) - 1:
                if self.gap >= p.sweep_gap: self.sweep = 0; self.gap = 0
                else: self.gap += 1
            if self.sweep != (1 << NB) - 1:
                blk = argmax([b for b in range(NB) if not (self.sweep >> b) & 1])
                tset = FULL | DIAG | (MBIST if blk == REGFILE else 0); valid = 1; reason = 1
                self.sweep |= 1 << blk
                self.lastfull[blk] = t & 0xFFFF  # full scan completes within its tick in this model
                lf_upd[blk] = 1
        elif self.st == ST_ACTIVE:
            if p.sweep_persist:
                if self.sweep == (1 << NB) - 1: self.sweep = 0; self.gap = p.sweep_gap   # completed sweep: re-arm (as v1)
            else: self.sweep = 0; self.gap = p.sweep_gap
            if self.ap == 0:
                blk = argmax(list(range(NB))); tset = ONLINE; valid = 1; reason = 2; self.ap = p.active_period - 1
            else: self.ap -= 1
        else:
            if p.sweep_persist:
                if self.sweep == (1 << NB) - 1: self.sweep = 0; self.gap = p.sweep_gap
            else: self.sweep = 0; self.gap = p.sweep_gap
            self.ap = 0
            cand = overdue & ~self.degmask & ((1 << NB) - 1)
            unres_flagged = sum((1 << b) for b in range(NB) if self.unres[b]) & self.degmask
            # fairness-slot decision cause, recorded directly by the scheduler (Step-2A):
            # 1 mission active (no eligible window)  2 starve_en off  3 fair_gap not elapsed  5 no overdue unflagged candidate
            # 4 window+gap+candidate exist but an unresolved diagnostic fault on a flagged block withholds the slot; 6 granted.
            # fair_unres_en is the narrow Step-3 exemption: it never clears or changes the flagged block's evidence,
            # but stops that evidence from globally withholding a healthy block's overdue full scan.
            if mission_active and not (p.fair_unres_en and unres_flagged != 0): fcause = 1
            elif not p.starve_en: fcause = 2
            elif self.fair < p.fair_gap and not (p.fair_unres_en and unres_flagged != 0): fcause = 3
            elif cand == 0: fcause = 5
            elif unres_flagged != 0 and not p.fair_unres_en: fcause = 4
            else: fcause = 6
            if p.starve_en and (not mission_active or (p.fair_unres_en and unres_flagged != 0)) and (self.fair >= p.fair_gap or (p.fair_unres_en and unres_flagged != 0)) and (p.fair_unres_en or unres_flagged == 0) and cand != 0:
                blk = argmax([b for b in range(NB) if (cand >> b) & 1])
                tset = FULL | DIAG | (MBIST if blk == REGFILE else 0); valid = 1; reason = 5
                self.fair = 0; self.lastfull[blk] = t & 0xFFFF; lf_upd[blk] = 1
            else:
                self.fair = min(255, self.fair + 1); self.esc = min(255, self.esc + 1)
                if self.degmask != 0:
                    blk = argmax([b for b in range(NB) if (self.degmask >> b) & 1]); valid = 1
                    if p.obs_en and p.esc_en and self.nf[blk] and esc_in >= p.esc_gap:     # Step-3 escalation: partial scans cannot clear this evidence
                        tset = FULL | DIAG | (MBIST if blk == REGFILE else 0); reason = 6; self.esc = 0; self.lastfull[blk] = t & 0xFFFF; lf_upd[blk] = 1
                    else: tset = PARTIAL | DIAG; reason = 3
        if p.stale_en:
            for b in range(NB): self.lfstale[b] = 0 if lf_upd[b] else (1 if (self.lfstale[b] or age[b] == 0xFFFF) else 0)
        self.last_tset = tset if (valid and p.mode == 0) else 0
        self.last_valid = valid and p.mode == 0; self.last_blk = blk; self.last_diag = int(bool(valid and (tset & DIAG)) and p.mode == 0)
        return dict(tick=t, state=self.st, valid=valid, blk=blk, tset=tset, reason=reason, prio=prio,
                    health=health, aging=list(self.aging), faults=faults, degmask=self.degmask, urg=list(urg),
                    mission_active=int(mission_active),
                    dflag=self.degmask if p.recov_en else 0, unres=sum((1 << b) for b in range(NB) if self.unres[b]), okc=list(self.okc),
                    ackv=sum((1 << b) for b in range(NB) if self.ackv[b]), ack=list(self.ack), sweep=self.sweep, gap=self.gap,
                    fair=self.fair, lastfull=list(self.lastfull), overdue=overdue,
                    arisk=sum((1 << b) << 0 for b in range(NB) if arisk[b]), dfault=sum((1 << b) for b in range(NB) if p.evid_en and self.dfl[b]),
                    aflag=sum((1 << b) for b in range(NB) if p.evid_en and self.afl[b]), fcause=fcause,
                    nf=sum((1 << b) for b in range(NB) if self.nf[b]), esc=self.esc, lfstale=sum((1 << b) for b in range(NB) if self.lfstale[b]))

def rtl_header(p: Params, stats):
    """Generate rtl/reliability/rel_params.svh so RTL uses exactly the Python parameters."""
    L = ["// AUTO-GENERATED by python/reliability_model.py - do not edit",
         f"localparam NB_P = {NB};"]
    for i, k in enumerate(("W1", "W2", "W3", "W4", "W5")): L.append(f"localparam [3:0] DEF_{k} = 4'd{p.w[i]};")
    L.append("localparam [39:0] CRIT_TERMS = {" + ", ".join(f"8'd{c}" for c in reversed(p.crit_term)) + "};")
    for k in ("rate", "rshift", "fp", "fh_inc", "fh_decay", "stale_k", "deg_th", "deb", "active_period", "sweep_gap", "base_n"):
        L.append(f"localparam {k.upper()}_P = {getattr(p, k)};")
    return "\n".join(L) + "\n"
