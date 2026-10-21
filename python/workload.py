"""Mission-like functional stimulus (block primary inputs) for the online-test windows.
Implementation assumption: these generators are synthetic robotic workloads, not captured traces."""
import random
from common import *

def _bits(v, n): return [(v >> i) & 1 for i in range(n)]
def _pack(**f):  # f: name=(value,lsb,width)
    v = 0
    for val, lsb, w in f.values(): v |= (val & ((1 << w) - 1)) << lsb
    return v

def gen(name, W, seed):
    r = random.Random(seed); out = []
    if name == "safety":
        burst = {"estop": 0, "oc": 0, "cf": 0, "ef": 0}; stopped = 0
        for t in range(W):
            for k, p in (("estop", .01), ("oc", .012), ("cf", .03), ("ef", .03)):
                if burst[k] > 0: burst[k] -= 1
                elif r.random() < p: burst[k] = r.randint(1, 6)
            clr = 1 if r.random() < .12 else 0
            run = 1 if r.random() < .93 else 0
            out.append(_pack(a=(burst["estop"] > 0, 0, 1), b=(burst["oc"] > 0, 1, 1), c=(burst["cf"] > 0, 2, 1),
                             d=(burst["ef"] > 0, 3, 1), e=(clr, 4, 1), f=(run, 5, 1)))
    elif name == "motor":
        sp = r.randint(40, 220); spd = 0; cb = 0
        for t in range(W):
            if t % 32 == 0: sp = r.randint(40, 220)
            spd = max(0, min(63, sp // 4 + r.randint(-4, 4)))
            if cb > 0: cb -= 1; cur = r.randint(13, 15)
            else:
                cur = r.randint(0, 9)
                if r.random() < .02: cb = r.randint(1, 3)
            en = 1; brake = 1 if r.random() < .03 else 0
            out.append(_pack(en=(en, 0, 1), br=(brake, 1, 1), sp=(sp, 2, 8), sd=(spd, 10, 6), cu=(cur, 16, 4)))
    elif name == "encoder":
        code = [0b00, 0b01, 0b11, 0b10]; idx = 0; dr = 1; hold = 0; rem = 0
        for t in range(W):
            if rem == 0: dr = r.choice([1, 1, -1]); rem = r.randint(8, 40)
            rem -= 1
            if hold == 0:
                if r.random() < .015: idx = (idx + 2) % 4       # invalid double transition
                else: idx = (idx + dr) % 4
                hold = r.randint(1, 3)
            else: hold -= 1
            c = code[idx]
            out.append(_pack(a=((c >> 1) & 1, 0, 1), b=(c & 1, 1, 1), clr=(1 if (t == 0 or r.random() < .004) else 0, 2, 1)))
    elif name == "comm":
        t = 0
        while t < W:
            gap = r.randint(2, 14)
            for _ in range(gap):
                if t < W: out.append(_pack(rx=(1, 0, 1), cl=(1 if r.random() < .03 else 0, 1, 1))); t += 1
            frame = [0] + [r.getrandbits(1) for _ in range(12)] + [0 if r.random() < .04 else 1]
            for b in frame:
                if t < W: out.append(_pack(rx=(b, 0, 1), cl=(0, 1, 1))); t += 1
    elif name == "regfile":
        for t in range(W):
            we = 1 if r.random() < .3 else 0
            out.append(_pack(ra=(r.randint(0, 15), 0, 4), wd=(r.getrandbits(8), 4, 8), wa=(r.randint(0, 15), 12, 4), we=(we, 16, 1)))
    return [_bits(v, [b for b in BLOCKS if b["name"] == name][0]["ni"]) for v in out]

def windows(name, W=ONLINE_WINDOW, K=ONLINE_K, base_seed=100):
    return [gen(name, W, base_seed + 17 * k + len(name)) for k in range(K)]

def mbist_sequence():
    """March C- (10N): {up/down(w0); up(r0,w1); up(r1,w0); down(r0,w1); down(r1,w0); any(r0)} via the regfile MBIST port.
    Returns list of (pi_bits, check, expected_rdata).  Solid 0x00/0xFF data background."""
    seq = []
    def op(kind, a, d):
        v = _pack(wd=(d, 17, 8), ad=(a, 25, 4), we=(1 if kind == "w" else 0, 29, 1), en=(1, 30, 1))
        seq.append((_bits(v, 31), kind == "r", d))
    N = MBIST_WORDS
    for a in range(N): op("w", a, 0x00)
    for a in range(N): op("r", a, 0x00); op("w", a, 0xFF)
    for a in range(N): op("r", a, 0xFF); op("w", a, 0x00)
    for a in reversed(range(N)): op("r", a, 0x00); op("w", a, 0xFF)
    for a in reversed(range(N)): op("r", a, 0xFF); op("w", a, 0x00)
    for a in range(N): op("r", a, 0x00)
    return seq
