# Paper traceability
Source: A. Singh, "Reliability-Aware Design-for-Test Architectures for Autonomous Robotic SoCs: A Survey of Conventional, Aging-Aware, and
Adaptive Runtime Testing" (`paper/paper.tex`, `paper/paper.pdf`). The paper is a **survey plus one implementation section**. Sections I-IX (survey) specify concretely
only: the four-layer stack (Sec. IX, Fig. 1), Eq. (2), Algorithm 1, the IDLE/ACTIVE/DEGRADED behaviour table, the DUT block list, a fixed-schedule baseline
(Fig. 2) and a fault-injection evaluation plan. **Section X ("Implementation of the Reliability-Aware DFT Architecture") is this repository**: its configuration and
result claims are asserted one by one by `make check-paper-claims` (table at the end of this file). Everything below marked ASSUMPTION is not in the paper.

| Paper element | Paper description | Implementation | File | Status |
|---|---|---|---|---|
| Architecture (Fig. 1) | DUT + DFT primitives + Test Controller + Reliability Manager (State Monitor, rule-based Health Manager, Scheduler) | same structure | rtl/dut/robotic_soc.sv | IMPLEMENTED |
| DUT | Motor Ctrl, Comm I/F, Reg File, Safety FSM, Encoder I/F | five small synthesizable blocks. Internal designs are ASSUMPTIONS | rtl/dut/*.sv | IMPLEMENTED |
| Layer A: Scan/ATPG/fault injection | conventional primitives | scan chains, PODEM, fault sim, RTL + gate-level stuck-at injection | rtl/dft, python/atpg.py, python/fault_simulator.py | IMPLEMENTED |
| Fault model | stuck-at (and transition-delay) named for conventional DFT | stuck-at SA0/SA1 at gate-level stems; RTL stuck-at at state/PI/PO | python/netlist.py, rtl/common/fault_injector.sv | PARTIAL (no transition/soft/intermittent) |
| Scan | scan insertion | mux-D scan flops, per-block chains, wrapper | rtl/dft/scan_ff.sv, scan_chain.sv | IMPLEMENTED |
| ATPG | stuck-at ATPG | PODEM + random phase + compaction | python/atpg.py | IMPLEMENTED (no FAN/D-alg) |
| MBIST | MBIST | March C- controller | rtl/dft/mbist_controller.sv | IMPLEMENTED |
| Online test | lightweight concurrent test (Sec. V, CBIST principle) | selective shadow-compare window; ASSUMPTION (not CBIST) | rtl/dft/online_test.sv | IMPLEMENTED (shadow area excluded) |
| State Monitor | IDLE/ACTIVE/DEGRADED | debounced monitor of mission activity + degraded flags (debounce is ASSUMPTION) | rtl/reliability/state_monitor.sv | IMPLEMENTED |
| Aging | aging/health signal from sensors (Layer B) | behavioural activity-accumulation abstraction, NOT NBTI/HCI; Layer B STA/sensor placement NOT implemented | rtl/reliability/aging_model.sv | PARTIAL |
| Health Manager | rule-based | fault history (decaying), staleness, health term, degraded flags (rules are ASSUMPTIONS) | rtl/reliability/health_manager.sv | IMPLEMENTED |
| Criticality | per-block fixed tier | tiers 4/3/3/2/1 (ASSUMPTION), configurable | python/common.py | IMPLEMENTED |
| Priority (Eq. 2) | w1 Crit + w2 Health + w3 Aging + w4 Faults + w5 Mission | exact form, 0..255 terms, 4-bit weights; default weights all 1 (untuned) | rtl/reliability/priority_engine.sv | IMPLEMENTED |
| Mission term | mission urgency / interruptibility | synthetic per-block reliance profile; "higher = test sooner" is an ASSUMPTION | python/mission.py | IMPLEMENTED |
| Scheduler (Alg. 1) | IDLE full scan+MBIST+diag in criticality order; ACTIVE online on argmax; DEGRADED higher frequency, partial scan, extra diag | as specified; periods/sweeps are ASSUMPTIONS | rtl/reliability/test_scheduler.sv | IMPLEMENTED |
| Test Controller | executes decisions | sequences scan/MBIST/online/diag | rtl/dft/test_controller.sv | IMPLEMENTED (diag = cycle accounting) |
| Baseline | fixed schedule, full scan as scheduled | full scan + MBIST of all blocks every N ticks | MODE=1 in test_scheduler.sv, python/reliability_model.py | IMPLEMENTED |
| Adaptive mode | state-adaptive schedule | MODE=0 | same | IMPLEMENTED |
| Evaluation | fault-injection campaign vs fixed baseline; sensitivity of weights | python/fault_campaign.py, weight_sensitivity.py | python/ | IMPLEMENTED |
| ML/RL | explicitly out of scope | none | - | not applicable |

## Paper Section X claims -> evidence (`make check-paper-claims`, output `results_paper/paper_claims_check.txt`)
Profile names in the repo: paper "reference profile" = `s2a_all3_evid`; "observability alone" = `s3_obs`; "observability plus escalation" = `s3_obs_esc`; `s3_obs_esc_stale` is a sanity profile (stale bit inert within 600 ticks).
| ID | Paper claim (Sec. X) | Evidence | Check |
|---|---|---|---|
| P01 | five blocks: safety FSM, motor controller, encoder, comm, register file | `python/common.py` BLOCKS, `rtl/dut/*.sv` | automatic |
| P02 | Eq.(2) weights all unity in reported experiments | `config.w` of every profile in `results_step3/campaign_summary.json` | automatic |
| P03 | `obs_en`, `esc_en`, `stale_en` disabled by default | `Params` in `python/reliability_model.py` (RTL parameters default 0) | automatic |
| P04 | escalation interval 10 ticks (assumption, not optimized) | `esc_gap=10`; never swept (`docs/STEP3_PHASE1_CORRECTNESS.md`) | automatic |
| P05-P06 | 600-tick trace, 20,000 cycles per tick | `results/mission_trace.csv`, `EPOCH_CYCLES` in `python/common.py` | automatic |
| P07/P07b | collapsed fault database of 2,515 faults; committed inputs are the ones the campaign used | `results/fault_db.csv` + sha256 in campaign meta | automatic |
| P08-P10 | seeds 2024 / 4242; transient faults removed after 60 ticks; one fault per episode | campaign meta | automatic |
| P11-P13 | 2,451/2,515 flagged; 117 premature clearances in reference; 0 with `obs_en` | `persistent` block of each profile | automatic |
| P14-P17 | transient: obs alone recovers 0/2,440; obs+esc recovers 2,267; 173 not recovered; zero premature clearances | `transient` block of each profile | automatic |
| P18-P19 | mean interruption 469,680 / 486,764 / 526,202 cycles; +3.6% / +12.0% | `mean_interruption_cycles` (persistent) | automatic |
| P20-P21 | Table IV reference-transient row (2,174 / 112 / 155); `stale_en` changes nothing in 600 ticks | `transient` block, `s3_obs_esc_stale` | automatic |
| P22-P23 | ACTIVE = lightweight online test only; IDLE = full-depth tests | fault-free run of the model over the mission trace | automatic |
| P24 | directed + RTL==Python + mutation tests 18/18 | `results_step3/step3_phase1_tests.txt` (`make test-step3`) | automatic (log) |
| - | PODEM stuck-at ATPG, March C- MBIST controller, scan chains, shadow-compare online test | `python/atpg.py`, `rtl/dft/mbist_controller.sv`, `rtl/dft/scan_chain.sv`, `rtl/dft/online_test.sv` | `make test` (needs iverilog) |
| - | NOT claimed / not implemented: calibrated NBTI/HCI aging, silicon power/timing/area, multi-seed, matched fixed-vs-adaptive comparison, Layer B (STA ranking, sensor placement) | `docs/LIMITATIONS.md` 1-2, 10, 12; `IMPLEMENTATION_STATUS.md` | n/a |

Wording note: Sec. X says that in ACTIVE the scheduler "favors lightweight online tests and scheduled testing". In the model ACTIVE issues the lightweight online test **only** (every `active_period`=2nd ACTIVE tick, argmax of Eq. (2)); no scan or MBIST is scheduled in ACTIVE (check P22, directed test S10). This matches Algorithm 1 (Sec. IX).
