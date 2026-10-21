"""Fault-simulation front end: serial (reference) and bit-parallel (production) simulators, fault dropping,
coverage.  The compiled engine lives in netlist.py."""
from netlist import *

def serial_comb(nl, pattern, fault):
    """One fault at a time, scalar simulation (reference model)."""
    A, O, ALL = nl.masks([fault]); return nl.fsim_comb(pattern, [fault], (A, O, ALL)) & 1

def parallel_comb(nl, pattern, faults):
    return nl.fsim_comb(pattern, faults)

def fault_dropping_run(nl, patterns, faults):
    """Apply patterns in order; faults detected by a pattern are dropped (not re-simulated).
    Returns (detected_mask, per-pattern new-detection counts)."""
    rem = list(range(len(faults))); det = 0; counts = []
    for p in patterns:
        sub = [faults[i] for i in rem]
        d = nl.fsim_comb(p, sub); new = 0; keep = []
        for j, i in enumerate(rem):
            if (d >> j) & 1: det |= 1 << i; new += 1
            else: keep.append(i)
        rem = keep; counts.append(new)
    return det, counts

def coverage(mask, n): return bin(mask).count("1") / n if n else 1.0

def selftest(nl, n=40, seed=3):
    """Cross-check parallel vs serial simulators on random faults/patterns."""
    import random
    rnd = random.Random(seed); reps, _, _ = nl.collapse()
    sample = rnd.sample(reps, min(n, len(reps)))
    bad = 0
    for _ in range(5):
        p = ([rnd.getrandbits(1) for _ in nl.pis], [rnd.getrandbits(1) for _ in nl.qs])
        par = nl.fsim_comb(p, sample)
        for k, f in enumerate(sample):
            if ((par >> k) & 1) != serial_comb(nl, p, f): bad += 1
    seq = [[rnd.getrandbits(1) for _ in nl.pis] for _ in range(60)]
    par = nl.fsim_seq(seq, sample)
    for k, f in enumerate(sample):
        if ((par >> k) & 1) != nl.fsim_serial(seq, f): bad += 1
    return bad
