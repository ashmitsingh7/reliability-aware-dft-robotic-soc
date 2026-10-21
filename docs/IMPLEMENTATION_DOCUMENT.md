# Implementation document
All numerical results live in `results/*.csv` and are tabulated automatically in `docs/RESULTS_SUMMARY.md`; none are typed by hand here.

## 1. Project Overview
A runnable prototype that compares a fixed periodic DFT schedule with a state-, health-, aging-, fault-history-, criticality- and mission-aware adaptive schedule on the same small robotic-controller SoC and the same stuck-at fault campaign.
## 2. Research Problem
Conventional DFT optimises one manufacturing-time objective; a continuously operating robotic SoC needs runtime test decisions informed by aging, operating state and block criticality (paper Sec. I).
## 3. Paper Summary
The paper is a **survey** of (i) conventional SoC test architecture/scheduling, (ii) aging-aware monitoring, (iii) in-field/online test, (iv) criticality-/state-aware scheduling (HetSched), with a literature-gap matrix and a proposed Reliability Manager: State Monitor, rule-based Health Manager, Scheduler; Eq. (2); Algorithm 1 (Sec. IX). Its Section X describes this prototype and reports the Step-3 Phase-1 closed-loop results (single seed, behavioural model); see PAPER_TRACEABILITY.md for the claim-by-claim check.
## 4. Research Gap
No surveyed source fuses live aging/health, operating mode and block criticality into a *test*-scheduling decision for a robotic SoC with a genuine idle mode (paper Sec. XI). The paper calls this an "unexplored combination of mature components" and states the claim must be substantiated by its own fault-injection evaluation.
## 5. Proposed Architecture
Four layers (Fig. 1): DUT + Scan/ATPG/fault injection; STA-based aging-sensor placement (Layer B); Reliability Manager; online-test path.
## 6. Implemented Architecture
See ARCHITECTURE.md. Layers A, C, D implemented; Layer B (STA/sensor placement) **not** implemented - replaced by a behavioural aging abstraction.
## 7. Difference Between Paper and Prototype
The survey part of the paper (Sec. I-IX) lists no DUT internals, thresholds, mission model or test costs; all are assumptions here (PAPER_TRACEABILITY.md). Paper Sec. X reports only the Phase-1 numbers in `results_step3/`, and states that Layer B is not part of the prototype's evidence. Aging is behavioural. Online test is shadow-compare, not CBIST. Partial scan is a reduced pattern set.
## 8. DUT Architecture
Safety FSM (tier 4), Motor Controller (3), Encoder I/F (3), Comm I/F (2), Register File 16x8 (1); 219 flip-flops; wrappers + per-block chains; block order = criticality order (configurable in python/common.py).
## 9. DFT Architecture
Wrapper muxes, per-block scan chains, `scan_test_bank` pattern players fed from ATPG ROMs, `mbist_controller`, `online_test`, `test_controller`.
## 10. Scan Chain
Mux-D scan flops, MSB-first load; capture with PI applied, PO sampled; unload overlapped with next load; cycles = P(L+1)+L. `tb_scan` verifies flush integrity, shift/capture/shift-out with ATPG patterns and Python-model expected responses, and negative tests.
## 11. Fault Model
Single stuck-at SA0/SA1. Gate-level: net stems of the Yosys netlist. RTL: state bits, block PIs, block POs.
## 12. Fault Injection
RTL: `fi_mask` + OR/AND masks (tb_fault_injection: 710 faults, automated). Gate-level: fault-parallel masks in the compiled simulator (the campaign).
## 13. Fault Simulation
Serial reference (`fault_simulator.serial_comb`, `fsim_serial`), bit-parallel combinational and sequential simulators using Python big integers (bit k = machine with fault k), fault dropping in ATPG and `fault_dropping_run`. Parallel==serial checked.
## 14. ATPG
Random phase (96 patterns), PODEM with SCOAP-guided backtrace (3-valued good/faulty implication, backtrack limit), fault dropping, reverse-order compaction, greedy coverage ordering. FAN / D-algorithm **not** implemented. Redundant faults are reported only if PODEM exhausts the search; otherwise "aborted".
## 15. Fault Collapsing
Structural equivalence on fanout-free stems (AND/NAND/OR/NOR/NOT); no dominance collapsing. Ratio in RESULTS_SUMMARY.md.
## 16. MBIST
March C- (10N), address up/down generator, solid data generator, comparator, FSM; `tb_mbist` measures detection of SAF, TF, AF, CFin, CFid on a behavioural memory model and of all 256 state stuck-at faults of the real register file.
## 17. Online Testing
Time-multiplexed shadow compare of one selected block over 128 cycles; zero mission stall; shadow area excluded; detects only faults that propagate to block outputs during the window.
## 18. State Monitor
Registered state IDLE/ACTIVE/DEGRADED; DEGRADED if any block flagged by the Health Manager (previous tick); otherwise ACTIVE iff mission active, with 2-tick debounce.
## 19. Aging Model
`stress += activity` per tick; `aging = min(255, stress*175 >> 16)`. **Behavioural digital abstraction, not a transistor-level reliability model.** In the SoC, activity is measured by output-toggle counters (`activity_monitor`).
## 20. Health Manager
Rules: fault history +1 per failed test, -1 every 64 ticks; staleness +1/tick since last passing test; Faults = min(255, 32*history); unhealth = min(255, aging/2 + Faults); Health term = min(255, unhealth + 4*staleness); degraded flag = unhealth >= 64. No scheduling decisions inside.
## 21. Fault History
Per-block saturating counter with decay (recent history).
## 22. Criticality
Tier x 63 (252/189/189/126/63); configurable.
## 23. Priority Engine
Priority_i = w1 Crit + w2 Health + w3 Aging + w4 Faults + w5 Mission, terms 0..255, 4-bit weights, default (1,1,1,1,1) (neutral, untuned).
## 24. Adaptive Scheduler
Algorithm 1 with ASSUMPTION knobs: sweep gap 10, online period 2, partial = 50% patterns. Decisions logged per tick (results/scheduler_results.csv: state, priorities, selected block, test types, reason, health, aging, faults, criticality, urgency, cycles).
## 25. Test Controller
Executes FULL->PARTIAL->MBIST->ONLINE->DIAG for a block (or all blocks for the baseline), reports fail/cycles. Diagnostics are modelled as scan-flush cycle accounting.
## 26. Baseline Scheduler
MODE=1: full scan + MBIST of all blocks every N=20 ticks regardless of state.
## 27. Adaptive Scheduler
MODE=0 (same module, same Reliability Manager inputs).
## 28. Testbench Architecture
tb_soc, tb_scan, tb_mbist, tb_fault_injection (RTL campaign), tb_scheduler (trace dump), tb_baseline, tb_adaptive, tb_full_system; plus Python cross-checks (netlist<->RTL, RTL manager<->Python model).
## 29. Fault Campaign
python/fault_campaign.py; outputs fault_campaign.csv (+ scheduler_results.csv, baseline_period_sweep.csv). First-detection semantics; fault-free-schedule reuse verified by literal re-simulation of sampled faults.
## 30. Experimental Methodology
EXPERIMENTAL_METHODOLOGY.md.
## 31. Metrics
Coverage, detection latency (mean/median/p95/censored), test cycles, mission-interrupting cycles, overhead %, counts per test type and block, detections by state and by criticality, coverage per million test cycles.
## 32. Results
docs/RESULTS_SUMMARY.md (auto-generated from CSVs). Interpretation is limited by LIMITATIONS.md. The experiment as run does **not** show the adaptive scheduler improving coverage; it shows lower mission-interrupting test time, and faster detection for the faults it does detect, at lower coverage.
## 33. Weight Sensitivity
results/weight_sensitivity.csv: 11 weight vectors; no optimum claimed; w4 has no effect on first-detection metrics by construction.
## 34. Synthesis
results/synthesis.csv: Yosys generic cell/flop counts. Timing, power, PPA: **Not evaluated.**
## 35. Open-Source Reuse
OPEN_SOURCE_SOURCES.md: no code reused; five of nine reference repositories carry no license; no additional search was performed.
## 36. Original Contributions
**ORIGINAL RESEARCH CONTRIBUTION (of this prototype):** the integration of robotic-SoC context, runtime state awareness, aging/health awareness, fault-history awareness, criticality- and mission-aware prioritisation, adaptive selection of test type, adaptive test frequency, IDLE/ACTIVE/DEGRADED operation, and the comparison against fixed scheduling. Scan, ATPG, MBIST, fault simulation are established techniques and are not claimed as novel.
## 37. Limitations
LIMITATIONS.md.
## 38. Reproducibility
`make prep test fault-campaign analyze plots synth`; seeds fixed (ATPG 11+block index, mission 2024, injection 4242).
## 39. Future Work
Aging-driven fault arrival; transition/delay faults; flop-subset partial scan (cf. SCOAP/stress-aware selection); CBIST-style online test without a shadow copy; save/restore around destructive tests; multiple missions and injection draws with confidence intervals; STA-based sensor placement (paper Layer B); FAN/D-algorithm; timing/power evaluation with a PDK.
## 40. File-by-File Implementation Map
rtl/dut/* DUT; rtl/dft/* DFT; rtl/reliability/* Reliability Manager; rtl/common/fault_injector.sv; tb/*; python/build_netlists.py (Yosys), netlist.py (netlist, compiled simulator, SCOAP, collapsing), atpg.py (PODEM flow), fault_simulator.py, workload.py (functional windows, March C- sequence), build_fault_db.py, reliability_model.py (bit-exact manager model), mission.py, fault_campaign.py, weight_sensitivity.py, calculate_coverage.py, analyze_results.py, plot_results.py, run_synthesis.py, check_netlist_equiv.py, check_rtl_equiv.py, gen_rtl_params.py, make_results_summary.py.
