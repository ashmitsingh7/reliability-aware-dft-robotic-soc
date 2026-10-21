# Implementation status
| Feature | Status | Reason | Workaround |
|---|---|---|---|
| Robotic SoC DUT (5 blocks, scan, wrappers, FI hooks) | IMPLEMENTED | - | - |
| Scan chain (shift/capture/shift-out, flush) | IMPLEMENTED | verified by tb_scan | - |
| Stuck-at fault model | IMPLEMENTED | stem faults at gate level; state/PI/PO at RTL | no branch faults |
| Transition-delay / delay-degradation / soft-error / intermittent faults | NOT IMPLEMENTED | out of prototype scope | stuck-at only |
| Serial and parallel fault simulation, fault dropping | IMPLEMENTED | - | - |
| Deductive fault simulation | NOT IMPLEMENTED | time | parallel simulator used |
| Fault collapsing | PARTIALLY IMPLEMENTED | equivalence only, fanout-free stems | no dominance |
| SCOAP | IMPLEMENTED | used to guide PODEM | - |
| PODEM ATPG | IMPLEMENTED | 2 motor faults aborted (not proven redundant) | - |
| FAN / D-algorithm | NOT IMPLEMENTED | PODEM sufficient | - |
| Partial scan | PARTIALLY IMPLEMENTED | implemented as 50% coverage-ordered pattern subset, not a flop subset | see LIMITATIONS |
| MBIST (March C-) | IMPLEMENTED | solid data background | - |
| Online test | PARTIALLY IMPLEMENTED | shadow-compare (not CBIST); shadow copy area not counted | - |
| State Monitor / Health Manager / Priority Engine / Scheduler / Test Controller | IMPLEMENTED | rules beyond Eq.(2)/Alg.1 are assumptions | - |
| Aging model | PARTIALLY IMPLEMENTED | behavioural abstraction only | paper Layer B (STA, sensor placement) NOT IMPLEMENTED |
| Fixed baseline vs adaptive on same DUT/faults | IMPLEMENTED | single mission / injection draw | - |
| Weight sensitivity | IMPLEMENTED | w4 cannot matter for first detection | - |
| Fault campaign CSVs, plots | IMPLEMENTED | - | - |
| Diagnostics (IDLE deep / DEGRADED extra) | PARTIALLY IMPLEMENTED | modelled as scan-flush cycle accounting | - |
| Full-system RTL integration test | IMPLEMENTED | requires an explicit core-restore after destructive tests (no save/restore HW) | - |
| Yosys synthesis | IMPLEMENTED | generic cell/flop counts only | Timing/power/PPA: Not evaluated |
| Verilator / Questa scripts | NOT IMPLEMENTED | not tested | Icarus only |
| JTAG | NOT IMPLEMENTED | out of scope | - |
| Additional GitHub/open-source search | NOT IMPLEMENTED | only the nine given repositories were cloned and license-checked | see OPEN_SOURCE_SOURCES.md |
| Reuse of third-party code | REFERENCE ONLY | nothing copied | - |
| Observability-aware diagnostic evidence (`obs_en`) | IMPLEMENTED (default OFF) | Step 3 Phase 1; removes the 117 premature clearances in the closed-loop campaign | see docs/STEP3_PHASE1_CORRECTNESS.md |
| Escalation to FULL diagnostic (`esc_en`) | IMPLEMENTED (default OFF) | scheduling-policy change; `esc_gap` not swept | needs `obs_en` |
| Stale bit on 16-bit lastfull age (`stale_en`) | IMPLEMENTED (default OFF) | removes >65,535-tick aliasing | - |
