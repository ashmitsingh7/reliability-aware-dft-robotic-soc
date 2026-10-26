# Step 2A final engineering report
Branch `step2a-health-evidence` (from Step 1 commit 5ce425b; `v1-baseline` = 5b6e57a). Environment: Ubuntu 24, Python 3.12, Icarus Verilog 12.0. Yosys 0.33 installed but **not run** (no synthesis/area result). Details: `baseline_evidence/environment.txt`.

## 1. Audit findings resolved
- Aging was conflated with diagnostic evidence: separated (`arisk` / `dfault` / `aflag`, switches `evid_en`, `arisk_deg`, default OFF). Aging never reset.
- RTL 16-bit `lastfull` rollover defect (false overdue after tick 65,535): fixed with 16-bit modular age in RTL and Python; a mutant re-introducing the old comparison is caught (first mismatch tick 65,592). Residual: aliasing beyond 65,535 ticks without a full scan (documented, tested).
- Starvation report no longer uses one global condition; classification rests on scheduler-recorded `fcause`.
- v1 `--verify` is vacuous for feedback (documented); Experiment 2 supplies the actual closed-loop check.
- Not defects, now documented: `lastfull` set at decision regardless of pass/fail; `lastfull==0` ambiguity.

## 2. Health-evidence semantics: see `docs/STEP2A_HEALTH_EVIDENCE.md`.

## 3. Files modified/added: `CHANGED_FILES.txt`; checksums `post_edit_sha256.txt` (pre-edit: `baseline_evidence/pre_edit_sha256.txt`). `results/` and `results_step1/` verified unchanged (only the 8 intended source files differ from the pre-edit list).

## 4. Test results (all actually executed)
| Check | Result |
|---|---|
| Step 1 directed tests (before edits) | 13/13 |
| Step 1 directed tests (after edits, 52 columns) | 13/13 (`step1_tests_rerun/`) |
| Step 2A directed tests E01-E18 incl. RTL==Python | 18/18; RTL equivalence 353,961 ticks, 0 mismatches (`step2a_directed_tests.txt`) |
| Existing regression, edited RTL (`existing_regression_after_edits.log`) | netlist equivalence PASS; RTL vs Python v1 (mode 0 and 1, 600 ticks) PASS; tb_soc, tb_adaptive, tb_baseline, tb_mbist, tb_scan, tb_fault_injection, tb_full_system PASS |
| Pre-edit regression in scratch copy | netlist/RTL-Python, tb_soc, tb_scan, tb_mbist, tb_adaptive, tb_baseline PASS; tb_fault_injection/tb_full_system were interrupted there (they pass on the edited tree) |
| Independent raw-log verification (`verify_step2a_from_logs.py`) | PASS for all 10 profiles (cycles, counts, occupancy, per-fault detection, coverage, latency, tiers) |
| Yosys | not executed |

## 5. Historical v1 reproduction
With Step-1/2A OFF, original mission/DB/seed: `fault_campaign.csv`, `scheduler_results.csv`, `baseline_period_sweep.csv` are byte-identical to shipped files, both on the unedited code (scratch) and the edited code (`v1_campaign_rerun/`). 200-fault literal-stepping check: 0 mismatches. v1: adaptive coverage 0.8231, N=20 0.9992.

## 6-8. Fixed baseline vs adaptive (Experiment 1; full tables in `RESULTS_TABLE.md`)
| profile | coverage | mean / median / p95 latency (cycles) | total test cyc | interruption cyc |
|---|---|---|---|---|
| v1 adaptive | 0.8231 | see table | 283,671 | 67,690 |
| fixed N=20 | 0.9992 | 206,504 / 207,876 / 382,402 | 290,280 | 222,548 |
| Step-1 all three (corrected reference) | 0.9746 | 343,846 / 267,088 / 886,900 | 253,151 | 13,435 |
| Step-2A evidence, arisk_deg=0 | 0.9746 | 348,667 / 268,036 / 902,502 | 250,156 | 9,544 |
Result: with Step 1 on, adaptive coverage rises from 0.8231 to 0.9746 and interruption falls ~94% vs N=20, but it does **not** match fixed N=20 coverage (0.9992, i.e. 0.9746 vs 0.9992) and detects later (mean 344k vs 207k cycles; p95 887k vs 382k). Total test cycles are 13% lower than N=20. N=40 also reaches 0.9992 with 145k total cycles but 126k interruption. The fixed baseline interrupts the mission far more; the two are not equal-cost, and the paper must state both axes. No superiority claim is supported. Per-block: adaptive coverage safety 0.968, motor 0.991, encoder 0.988, comm 0.981, regfile 0.964 (critical-tier-4 0.968 vs 1.0 fixed). At end of mission no block is overdue/starved in Step-1 profiles (22 full scans per block, 18-22 ticks since last full scan). Evidence profile with arisk_deg=0 has DEGRADED occupancy 0 ticks (vs 12) because aging alone no longer forces it; arisk_deg=1 equals s1_all3 exactly.

## Experiment 2 (closed-loop, sequential single persistent-fault episodes, 2,515 episodes/profile)
Closed-loop first detections equal the replay for all faults. Adaptive profiles: ~2,450 of 2,515 episodes flag the block; ~2,370 episodes end in DEGRADED and ~1,890 end with at least one other block overdue (a persistent unresolved fault keeps the manager in DEGRADED, with the fairness slot withheld). Flags cleared while the fault persisted: 275 (s1_all3, includes aging-flag clears) and 117 (evidence, arisk_deg=0, i.e. diagnostic false clearance because the partial-scan diagnostic cannot detect some faults). Mean interruption per episode ~4.6e5 cycles (DEGRADED partial scans run on mission-active ticks). These are model results, not an endorsement of the policy.

## 9. Remaining limitations: `docs/STEP2A_METHODOLOGY.md` (behavioural aging/fault models, single mission and seed, assumed thresholds, one-tick tests, no synthesis data, 16-bit age horizon, no multi-fault episodes).

## 10. Recommendation for the priority-policy redesign (Step 2B, not done here)
(1) Evaluate across multiple mission seeds/injection seeds before any claim. (2) Address the two measured weaknesses with the evidence-separated profile as the starting reference: late detection of low-priority blocks (p95) and coverage gap vs N=20, without raising interruption. (3) Decide the persistent-fault policy: after a confirmed unresolved fault the manager sits in DEGRADED and other blocks go overdue; define a bounded fairness policy. (4) Add a diagnostic that can see faults partial scans miss, so false clearance can be measured separately from aging escalation. (5) Run synthesis to cost the added state.

## Not claimed
Superiority over fixed-period, physical aging validation, silicon-level reliability.
