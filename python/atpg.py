"""Deterministic ATPG: PODEM (3-valued dual-machine implication, SCOAP-guided backtrace) preceded by a
random-pattern phase, with fault dropping, reverse-order compaction and coverage-greedy ordering.
Full-scan combinational frame: controllable = PI + FF.Q, observable = PO + FF.D.
Written independently; algorithmic reference: Goel's PODEM (1981) and jack-mil/atpg-toolkit (MIT) - cited as conceptual reference; repository cloned, code not reviewed in depth, nothing copied."""
import random
from netlist import *
X = 2
def _t(f): return [f(a, b) for a in range(3) for b in range(3)]
def _and(a, b): return 0 if (a == 0 or b == 0) else (1 if (a == 1 and b == 1) else 2)
def _or(a, b):  return 1 if (a == 1 or b == 1) else (0 if (a == 0 and b == 0) else 2)
def _xor(a, b): return 2 if (a == 2 or b == 2) else a ^ b
def _n(a): return 2 if a == 2 else 1 - a
T = {"AND": _t(_and), "NAND": _t(lambda a, b: _n(_and(a, b))), "OR": _t(_or), "NOR": _t(lambda a, b: _n(_or(a, b))),
     "XOR": _t(_xor), "XNOR": _t(lambda a, b: _n(_xor(a, b)))}
NOT3 = [1, 0, 2]

class Podem:
    def __init__(self, nl):
        self.nl = nl; nl.scoap(); self.inputs = set(nl.pseudo_in)
    def _sim(self, assign, fnet, sa):
        nl = self.nl; g = [X] * nl.N
        for v, n in nl.const.items(): g[n] = v
        for n, v in assign.items(): g[n] = v
        f = g[:]
        if fnet in self.inputs: f[fnet] = sa
        for op, o, ins in nl.gates:
            if op == "NOT": gv = NOT3[g[ins[0]]]; fv = NOT3[f[ins[0]]]
            else:
                t = T[op]; gv = t[g[ins[0]] * 3 + g[ins[1]]]; fv = t[f[ins[0]] * 3 + f[ins[1]]]
            g[o] = gv; f[o] = sa if o == fnet else fv
        return g, f
    def _detected(self, g, f):
        for o in self.nl.outs:
            if g[o] != X and f[o] != X and g[o] != f[o]: return True
        return False
    def _objective(self, g, f, fnet, sa):
        if g[fnet] == X: return (fnet, 1 - sa)
        if g[fnet] == sa: return None
        best = None
        for op, o, ins in self.nl.gates:
            if g[o] != X and f[o] != X: continue
            if not any(g[i] != X and f[i] != X and g[i] != f[i] for i in ins): continue
            xs = [i for i in ins if g[i] == X]
            if not xs: continue
            c = self.nl.co[o]
            if best is None or c < best[0]: best = (c, op, xs[0])
        if best is None: return None
        _, op, x = best
        return (x, 1 if op in ("AND", "NAND") else 0)
    def _backtrace(self, net, val, g):
        nl = self.nl
        while net not in self.inputs:
            op, ins = nl.driver[net]
            if op == "NOT": net, val = ins[0], 1 - val; continue
            cand = [i for i in ins if g[i] == X] or list(ins)
            if op in ("NAND", "NOR", "XNOR"): val = 1 - val
            if op in ("AND", "NAND"):      # AND-like: out=1 needs all 1 (hardest first), out=0 needs one 0 (easiest)
                net = (max if val == 1 else min)(cand, key=lambda i: (nl.cc1 if val == 1 else nl.cc0)[i])
            elif op in ("OR", "NOR"):
                net = (max if val == 0 else min)(cand, key=lambda i: (nl.cc0 if val == 0 else nl.cc1)[i])
            else:                           # XOR/XNOR(after inversion handled)
                net = cand[0]; other = [i for i in ins if i != net]
                ov = g[other[0]] if other and g[other[0]] != X else 0
                val = val ^ ov
        return net, val
    def run(self, fnet, sa, limit=120):
        assign = {}; stack = []; bt = 0
        while True:
            g, f = self._sim(assign, fnet, sa)
            if self._detected(g, f): return "detected", assign
            obj = self._objective(g, f, fnet, sa)
            if obj is not None:
                pi, v = self._backtrace(obj[0], obj[1], g)
                if pi in assign:             # no progress possible -> treat as conflict
                    obj = None
                else:
                    assign[pi] = v; stack.append([pi, v, False]); continue
            while stack:
                top = stack[-1]
                if not top[2]: top[2] = True; top[1] ^= 1; assign[top[0]] = top[1]; break
                del assign[top[0]]; stack.pop()
            else:
                return "untestable", None
            bt += 1
            if bt > limit: return "aborted", None

def popcount(x): return bin(x).count("1")

def generate(nl, seed=1, rpg=96, limit=120):
    rnd = random.Random(seed)
    reps, classes, total_uncollapsed = nl.collapse()
    faults = list(reps); F = len(faults)
    masks = nl.masks(faults); FULL = (1 << F) - 1
    pi_idx = {n: i for i, n in enumerate(nl.pis)}; q_idx = {n: i for i, n in enumerate(nl.qs)}
    rem = FULL; pats = []
    def rnd_pat(): return ([rnd.getrandbits(1) for _ in nl.pis], [rnd.getrandbits(1) for _ in nl.qs])
    for _ in range(rpg):
        p = rnd_pat(); d = nl.fsim_comb(p, faults, masks)
        if d & rem: pats.append(p); rem &= ~d
    status = {}
    pod = Podem(nl)
    for k in range(F):
        if not (rem >> k) & 1: continue
        res, assign = pod.run(faults[k][0], faults[k][1], limit)
        if res == "detected":
            pi = [rnd.getrandbits(1) for _ in nl.pis]; q = [rnd.getrandbits(1) for _ in nl.qs]
            for n, v in assign.items():
                if n in pi_idx: pi[pi_idx[n]] = v
                else: q[q_idx[n]] = v
            p = (pi, q); d = nl.fsim_comb(p, faults, masks)
            assert (d >> k) & 1, "PODEM pattern failed to detect its target"
            pats.append(p); rem &= ~d
        else:
            status[k] = res; rem &= ~(1 << k)
    # reverse-order compaction
    dets = [nl.fsim_comb(p, faults, masks) for p in pats]
    covered = 0; keep = []
    for i in reversed(range(len(pats))):
        if dets[i] & ~covered: keep.append(i); covered |= dets[i]
    keep.sort(); pats = [pats[i] for i in keep]; dets = [dets[i] for i in keep]
    # greedy coverage ordering (also used for partial scan)
    order = []; cov = 0; left = list(range(len(pats)))
    while left:
        j = max(left, key=lambda i: popcount(dets[i] & ~cov))
        if not (dets[j] & ~cov): break
        order.append(j); cov |= dets[j]; left.remove(j)
    pats = [pats[i] for i in order]; dets = [dets[i] for i in order]
    ok = {k for k in range(F) if (cov >> k) & 1}
    for k in range(F):
        status[k] = "detected" if k in ok else status.get(k, "undetected")
    return dict(faults=faults, classes=classes, total_uncollapsed=total_uncollapsed, patterns=pats, dets=dets,
                status=status, cov_mask=cov, F=F)
