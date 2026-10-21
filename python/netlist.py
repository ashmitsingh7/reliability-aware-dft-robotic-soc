"""Gate-level netlist (from Yosys JSON), compiled bit-parallel simulation, SCOAP, fault collapsing.
Independent implementation; concepts (SCOAP, equivalence collapsing, word-parallel fault simulation) are textbook
and were cross-checked against ideas in zilindev/Digital-Circuit-Fault-Simulator-ATPG and jack-mil/atpg-toolkit
(cited as conceptual reference; repositories cloned but code not reviewed in depth, nothing copied)."""
import json, re
from common import *

OPS = {'$_AND_': 'AND', '$_NAND_': 'NAND', '$_OR_': 'OR', '$_NOR_': 'NOR',
       '$_XOR_': 'XOR', '$_XNOR_': 'XNOR', '$_NOT_': 'NOT'}

class Netlist:
    def __init__(self, blk):
        self.blk = blk
        data = json.load(open(os.path.join(BUILD, blk["name"] + ".json")))
        mod = data["modules"]["nl_" + blk["name"]]
        ids = {}; self.nn = 0; self.const = {}
        def new():
            self.nn += 1; return self.nn - 1
        def net(b):
            if b in ("0", "x"): return self.const.setdefault(0, new())
            if b == "1": return self.const.setdefault(1, new())
            if b not in ids: ids[b] = new()
            return ids[b]
        self.pis = [net(b) for b in mod["ports"]["pi"]["bits"]]
        self.pos = [net(b) for b in mod["ports"]["po"]["bits"]]
        self.gates_raw = []; ffs = []
        for cname, c in mod["cells"].items():
            t = c["type"]; cn = c["connections"]
            if t in OPS:
                ins = [net(cn[p][0]) for p in ("A", "B") if p in cn]
                self.gates_raw.append((OPS[t], net(cn["Y"][0]), ins))
            elif t == "$_DFF_P_":
                ffs.append((net(cn["Q"][0]), net(cn["D"][0])))
            else:
                raise RuntimeError("unexpected cell " + t)
        qmap = {q: d for q, d in ffs}
        self.qs = [net(b) for b in mod["ports"]["sq"]["bits"]]
        assert len(set(self.qs)) == blk["ns"] == len(ffs), "FF merge/removal detected"
        self.ds = [qmap[q] for q in self.qs]
        # names
        self.names = {}
        order = sorted(mod["netnames"].items(), key=lambda kv: ('.' in kv[0], len(kv[0])))
        for k, v in order:
            if v.get("hide_name"): continue
            for i, b in enumerate(v["bits"]):
                if isinstance(b, int) and b in ids:
                    self.names.setdefault(ids[b], k if len(v["bits"]) == 1 else f"{k}[{i}]")
        self._topo()
        self.N = self.nn
        self._compile()
        self._fanout()

    def _topo(self):
        drv = {o: (op, o, ins) for op, o, ins in self.gates_raw}
        src = set(self.pis) | set(self.qs) | set(self.const.values())
        done = set(src); order = []
        for o in list(drv):
            stack = [o]
            while stack:
                x = stack[-1]
                if x in done: stack.pop(); continue
                op, _, ins = drv[x]
                pend = [i for i in ins if i not in done]
                if pend: stack.extend(pend)
                else: done.add(x); order.append((op, x, ins)); stack.pop()
        self.gates = order
        self.driver = {o: (op, ins) for op, o, ins in order}

    def _compile(self):
        L = ["def sim(pi, q, A, O, ALL):"]
        for i, n in enumerate(self.pis): L.append(f" v{n}=(pi[{i}]&A[{n}])|O[{n}]")
        for i, n in enumerate(self.qs): L.append(f" v{n}=(q[{i}]&A[{n}])|O[{n}]")
        for v, n in self.const.items(): L.append(f" v{n}={'ALL' if v else '0'}")
        for op, o, ins in self.gates:
            a = f"v{ins[0]}"; b = f"v{ins[1]}" if len(ins) > 1 else None
            e = {"AND": f"{a}&{b}", "NAND": f"({a}&{b})^ALL", "OR": f"{a}|{b}", "NOR": f"({a}|{b})^ALL",
                 "XOR": f"{a}^{b}", "XNOR": f"({a}^{b})^ALL", "NOT": f"{a}^ALL"}[op]
            L.append(f" v{o}=(({e})&A[{o}])|O[{o}]")
        L.append(" return [" + ",".join(f"v{n}" for n in self.pos) + "],[" + ",".join(f"v{n}" for n in self.ds) + "]")
        ns = {}; exec("\n".join(L), ns); self.sim = ns["sim"]
        self.A1 = [1] * self.nn; self.O0 = [0] * self.nn

    def _fanout(self):
        fo = [0] * self.nn
        for op, o, ins in self.gates:
            for i in ins: fo[i] += 1
        for n in self.pos: fo[n] += 1
        for n in self.ds: fo[n] += 1
        self.fo = fo
        self.pseudo_in = list(self.pis) + list(self.qs)
        self.outs = list(self.pos) + list(self.ds)

    def good(self, pi_bits, q_bits):
        return self.sim(pi_bits, q_bits, self.A1, self.O0, 1)

    # ---------- fault list ----------
    def fault_sites(self):
        cs = set(self.const.values())
        return [n for n in range(self.nn) if n not in cs and self.fo[n] > 0]

    def collapse(self):
        """Structural equivalence collapsing on fanout-free stems.  Returns (reps, classes)."""
        sites = self.fault_sites()
        par = {(n, v): (n, v) for n in sites for v in (0, 1)}
        def find(x):
            while par[x] != x: par[x] = par[par[x]]; x = par[x]
            return x
        def uni(a, b):
            if a in par and b in par: par[find(a)] = find(b)
        for op, o, ins in self.gates:
            for x in ins:
                if self.fo[x] != 1: continue
                if op == "AND":  uni((x, 0), (o, 0))
                elif op == "NAND": uni((x, 0), (o, 1))
                elif op == "OR":   uni((x, 1), (o, 1))
                elif op == "NOR":  uni((x, 1), (o, 0))
                elif op == "NOT":  uni((x, 0), (o, 1)); uni((x, 1), (o, 0))
        classes = {}
        for f in par: classes.setdefault(find(f), []).append(f)
        reps = sorted(classes)  # representative = root
        return reps, {r: len(classes[r]) for r in reps}, len(par)

    # ---------- SCOAP ----------
    def scoap(self):
        INF = 10**9
        cc0 = [INF] * self.nn; cc1 = [INF] * self.nn
        for n in self.pseudo_in: cc0[n] = cc1[n] = 1
        for v, n in self.const.items():
            cc0[n] = 1 if v == 0 else INF; cc1[n] = 1 if v == 1 else INF
        for op, o, ins in self.gates:
            a = ins[0]; b = ins[1] if len(ins) > 1 else None
            if op == "AND":  cc1[o] = cc1[a] + cc1[b] + 1; cc0[o] = min(cc0[a], cc0[b]) + 1
            elif op == "NAND": cc0[o] = cc1[a] + cc1[b] + 1; cc1[o] = min(cc0[a], cc0[b]) + 1
            elif op == "OR":  cc0[o] = cc0[a] + cc0[b] + 1; cc1[o] = min(cc1[a], cc1[b]) + 1
            elif op == "NOR": cc1[o] = cc0[a] + cc0[b] + 1; cc0[o] = min(cc1[a], cc1[b]) + 1
            elif op == "XOR": cc0[o] = min(cc0[a] + cc0[b], cc1[a] + cc1[b]) + 1; cc1[o] = min(cc0[a] + cc1[b], cc1[a] + cc0[b]) + 1
            elif op == "XNOR": cc1[o] = min(cc0[a] + cc0[b], cc1[a] + cc1[b]) + 1; cc0[o] = min(cc0[a] + cc1[b], cc1[a] + cc0[b]) + 1
            elif op == "NOT": cc0[o] = cc1[a] + 1; cc1[o] = cc0[a] + 1
        co = [INF] * self.nn
        for n in self.outs: co[n] = 0
        for op, o, ins in reversed(self.gates):
            if co[o] >= INF: continue
            for k, x in enumerate(ins):
                y = ins[1 - k] if len(ins) > 1 else None
                if op in ("AND", "NAND"): c = co[o] + cc1[y] + 1
                elif op in ("OR", "NOR"): c = co[o] + cc0[y] + 1
                elif op in ("XOR", "XNOR"): c = co[o] + min(cc0[y], cc1[y]) + 1
                else: c = co[o] + 1
                co[x] = min(co[x], c)
        self.cc0, self.cc1, self.co = cc0, cc1, co
        return cc0, cc1, co

    # ---------- fault-parallel (bit k of every net value == machine with fault k) ----------
    def masks(self, faults):
        F = len(faults); ALL = (1 << F) - 1
        A = [ALL] * self.nn; O = [0] * self.nn
        for k, (n, sa) in enumerate(faults):
            if sa == 0: A[n] &= ~(1 << k)
            else: O[n] |= (1 << k)
        return A, O, ALL

    def fsim_comb(self, pattern, faults, masks=None):
        """pattern=(pi_bits, q_bits) -> int bitmask of detected faults (full-scan: observe POs and FF.D)."""
        A, O, ALL = masks or self.masks(faults)
        pi, q = pattern
        gpo, gd = self.good(pi, q)
        po, d = self.sim([ALL if b else 0 for b in pi], [ALL if b else 0 for b in q], A, O, ALL)
        det = 0
        for v, g in zip(po + d, gpo + gd): det |= v ^ (ALL if g else 0)
        return det & ALL

    def fsim_seq(self, pi_seq, faults, obs=None, check=None):
        """Sequential fault-parallel simulation from the all-zero (reset) state.
        obs: list of PO indices compared; check: per-cycle bool list (compare only on flagged cycles)."""
        A, O, ALL = self.masks(faults)
        gq = [0] * len(self.qs); fq = [0] * len(self.qs)
        det = 0; first = {}
        obs = list(range(len(self.pos))) if obs is None else obs
        for t, pi in enumerate(pi_seq):
            gpo, gd = self.sim(pi, gq, self.A1, self.O0, 1)
            po, d = self.sim([ALL if b else 0 for b in pi], fq, A, O, ALL)
            if check is None or check[t]:
                for j in obs:
                    det |= po[j] ^ (ALL if gpo[j] else 0)
            gq = gd; fq = d
        return det & ALL

    def fsim_serial(self, pi_seq, fault, obs=None):
        """Reference serial single-fault simulation (used to cross-check the parallel simulator)."""
        return self.fsim_seq(pi_seq, [fault], obs) & 1

def name_of(nl, n): return nl.names.get(n, f"n{n}")
