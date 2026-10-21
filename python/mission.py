"""Synthetic robotic mission profile (per scheduler tick).  Implementation assumption: the paper gives no
mission model; this generator provides IDLE/ACTIVE phases, per-block switching-activity and a mission-urgency term."""
import random, csv
from common import *
M_TICKS = 600
REL_CRIT = [255, 230, 200, 120, 80]      # block reliance during a critical manoeuvre (safety, motor, enc, comm, regfile)
REL_NORM = [128, 115, 100, 60, 40]
REL_PRE  = [200, 180, 160, 90, 60]       # pre-mission readiness (last 5 idle ticks before a critical manoeuvre)

def generate(seed=2024, M=M_TICKS):
    r = random.Random(seed); phases = [("IDLE", 8)]
    while sum(l for _, l in phases) < M + 80:
        phases.append((("ACTIVE_CRIT" if r.random() < .3 else "ACTIVE_NORM"), r.randint(15, 50)))
        phases.append(("IDLE", r.randint(6, 20)))
    seq = []
    for i, (k, l) in enumerate(phases):
        nxt = phases[i + 1][0] if i + 1 < len(phases) else "IDLE"
        for j in range(l): seq.append((k, nxt, l - j))
    tr = []
    for t in range(M):
        k, nxt, left = seq[t]
        if k == "IDLE":
            act = [15, 5, 8, 20, 5]; urg = REL_PRE[:] if (nxt == "ACTIVE_CRIT" and left <= 5) else [0] * NB
            act = [max(0, min(255, a + r.randint(-3, 3))) for a in act]
        else:
            crit = k == "ACTIVE_CRIT"
            base = [40, 190, 160, 80, 35] if crit else [40, 140, 110, 80, 35]
            sp = [10, 30, 25, 15, 10]
            act = [max(0, min(255, b + r.randint(-s, s))) for b, s in zip(base, sp)]
            urg = (REL_CRIT if crit else REL_NORM)[:]
        tr.append(dict(tick=t, phase=k, mission_active=int(k != "IDLE"), act=act, urg=urg))
    return tr

def write(tr, path_csv=None, path_mem=None, fail_events=None, fail_classes=None):
    if path_csv:
        with open(path_csv, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["tick", "phase", "mission_active"] + [f"act_{n}" for n in BNAMES] + [f"urg_{n}" for n in BNAMES])
            for x in tr: w.writerow([x["tick"], x["phase"], x["mission_active"]] + x["act"] + x["urg"])
    if path_mem:
        fe = fail_events or {}
        with open(path_mem, "w") as f:
            for x in tr:
                v = x["mission_active"]
                for b in range(NB): v |= x["act"][b] << (1 + 8 * b)
                for b in range(NB): v |= x["urg"][b] << (41 + 8 * b)
                v |= fe.get(x["tick"], 0) << 81
                if fail_classes is not None:               # Step-3: 112-bit trace word, failing-class mask 4 bits/block at [105:86]
                    v |= fail_classes.get(x["tick"], 0) << 86
                    f.write(f"{v:028x}\n")
                else: f.write(f"{v:022x}\n")
if __name__ == "__main__":
    tr = generate(); write(tr, RESULTS + "/mission_trace.csv", RESULTS + "/mission_trace.mem")
    a = sum(x["mission_active"] for x in tr); print("ticks", len(tr), "active share %.2f" % (a / len(tr)))
