# Experimental methodology
**Pipeline.** RTL (SystemVerilog) -> Yosys (techmap + abc to AND/NAND/OR/NOR/XOR/XNOR/NOT + D flops) -> Python netlist model (verified cycle-exact vs RTL in Icarus on 600 random vectors per block)
-> collapsed stuck-at fault list -> PODEM ATPG (+random phase, fault dropping, compaction, greedy coverage ordering) -> per-fault detection table (fault_db.csv):
detect_full, detect_partial, detect_mbist (March C- sequence through the register-file port, fault-parallel sequential simulation), detect_online_mask (4 functional windows, lock-step compare of all block outputs).
**Parallel simulator validation:** serial single-fault results equal bit-parallel results on random samples (selftest in build_fault_db.py).

**Scheduler campaign (python/fault_campaign.py).** 600 ticks x 20,000 cycles; synthetic mission (IDLE/ACTIVE-normal/ACTIVE-critical). For each of the 2,515 collapsed faults: random injection cycle (seed 4242, identical for both schedulers);
the manager (bit-exact Python model of the RTL, checked equal on 600 ticks in both modes) decides each tick; a test detects the fault if it starts after injection, targets the faulty block and the fault-db row says that test type detects it.
Metrics: coverage, detection latency (detection cycle = tick start + cycles into the test), test cycles (all blocks, from injection to detection, and over the whole mission), mission-interrupting cycles (scan-type tests during mission-active ticks; online tests count 0), counts per test type / block, detections by system state, coverage per million test cycles.
**Baseline:** full scan + MBIST of every block every N=20 ticks, state-independent (N chosen before running); N in {5,10,20,40,80} swept in baseline_period_sweep.csv.
**Test cost model:** full scan = P(L+1)+L cycles (verified exactly in tb_scan); MBIST = 10N = 160 (verified); online = 128 cycles; diag = 2L (flush length).
**Weights:** default all 1 (neutral, untuned). Ten other weight vectors in weight_sensitivity.csv; no optimum is claimed.
**Reproduce:** `make prep test fault-campaign analyze plots synth`.
