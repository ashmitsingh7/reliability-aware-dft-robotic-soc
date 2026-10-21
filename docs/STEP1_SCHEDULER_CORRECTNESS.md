# Step 1 - Scheduler correctness refinement (audit, design, validation)
Scope: Fix A (DEGRADED lock-in), Fix B (persistent IDLE sweep), Fix C (starvation). **Not** Step 2 (adaptive priority) or Step 3 (multi-seed). Paper untouched.
All new behaviour is behind switches that default to OFF; with them OFF the v1 outputs are byte-identical (see Validation). Parameter values below are
**implementation assumptions, not tuned** and do not model physical aging recovery.

## 1. Root cause (confirmed from source and the shipped decision log)
* `health_manager.sv` / `Manager.step`: `degmask[b] = (aging[b]/2 + faults[b]) >= DEG_TH`, recomputed every tick. `aging` is `min(255, cumulative_stress*RATE>>16)` and is
  monotone by construction; only a fault-history term can fall (decays 1 per 64 ticks) and it was never raised in the mission. A passing test only resets the *staleness* term (`since`),
  which is not part of `unh`. So once `aging/2 >= 64` the flag can never clear: the *aging estimate* and the *health/DEGRADED decision* were the same quantity.
* `state_monitor.sv`: `degmask != 0` forces DEGRADED, and leaves it only when the mask is zero -> permanent. Shipped log: motor aging/2 reaches 64 at tick 448, DEGRADED from 449 to 599 (151 ticks).
* `test_scheduler.sv` DEGRADED branch: only `PARTIAL|DIAG` on flagged blocks (146 motor, 5 encoder partial scans). No full scan for any block after ticks 439-443 (157+ ticks), although 40-44 mission-idle ticks occurred.
* Sweep bookkeeping: `sweep` mask and `gap` are cleared on every ACTIVE or DEGRADED tick (v1 code), so an unfinished sweep restarts from the top. On the *original* mission the IDLE windows (6-20 ticks) are long enough that
  18 sweeps still complete before tick 449, so Fix B is **not** what causes the 449-599 starvation there; it is demonstrated on a short-window trace (T07).

## 2. State variables (Python == RTL)
| Python `Manager` | RTL | Meaning |
|---|---|---|
| `aging[b]`, `stress[b]` | `aging_model.stress`, `aging_n` | cumulative aging estimate - **unchanged, never reset** |
| `unh[b]`, `faults[b]`, `health[b]` | `health_manager` locals / `faults_n`, `health_n` | health assessment (unchanged formula) |
| `st` | `state_monitor.state` | operating mode IDLE/ACTIVE/DEGRADED (unchanged logic; uses previous-tick flags) |
| `dflag[b]` (new) | `health_manager.dflag` | sticky DEGRADED flag per block (REC_EN=1) |
| `okc[b]` (new) | `okc` | consecutive passing DIAG decisions on the block since last failure/entry |
| `unres[b]` (new) | `unres` | unresolved-fault evidence: set by a failed test, cleared **only** by a passing DIAG |
| `ack[b]`, `ackv[b]` (new) | `ack`, `ackv` | health level `unh` at last clearance (hysteresis anchor) |
| `last_diag` (new) | `test_scheduler.last_diag` | previous decision contained DIAG |
| `sweep`, `gap` | `sweep`, `gap` | idle-sweep bitmask / re-arm counter (persistence changes only when they are cleared) |
| `lastfull[b]` (new) | `lastfull` (16 bit) | tick of last completed FULL scan of the block (0 = none since reset) |
| `fair` (new) | `fair` | DEGRADED ticks since last fairness slot |
| `overdue` mask (new) | `dbg_overdue` | `t - lastfull[b] >= overdue_ticks` |
New RTL ports (outputs only, plus `mission_active`/`unres_n`/`last_diag` internal wiring) are additive; existing testbenches are unmodified. Switches live in `rtl/reliability/rel_refine_params.svh` (default all 0).

## 3. Fix A - DEGRADED entry and recovery (`recov_en`)
Separated concepts: *aging estimate* (monotone, untouched) / *health assessment* (`unh`) / *operating mode* (state monitor) / *recovery eligibility* (`dflag`, `okc`, `unres`, `ack`).
* **Entry:** `unh >= deg_th` (64) for a never-cleared block - identical to v1. A failed test on the block flags it immediately (direct fault evidence).
* **Recovery evidence:** `recov_n` (3) **consecutive** passing DIAG decisions on that block (PARTIAL+DIAG in DEGRADED, FULL+DIAG in an idle sweep), with no failure in between. A timer alone never clears a flag (fault-history decay does not clear `dflag`/`unres`).
* **Recovery action:** clear `dflag`, record `ack = unh`. Aging is not touched.
* **Hysteresis / re-entry:** after clearance the block re-enters when `unh >= max(deg_th, ack + reentry_margin)` (margin 16) or on any new failure. If `ack + margin > 255` the block can re-enter only through a failure (saturation limitation).
* **Mode timing:** unchanged pipeline - flag at tick t, DEGRADED from t+1; flags clear at tick r, state leaves DEGRADED at r+1.
* Persistent fault: every diagnostic fails, `okc` stays 0, flag + `unres` stay set indefinitely (T04, T09).
* Assumption/limitation: in this simulation a diagnostic passes whenever no fault is injected, so an aging-only flag clears after `recov_n` diagnostics. That says nothing about physical aging recovery.

## 4. Fix B - persistent sweep (`sweep_persist`)
`sweep`/`gap` are no longer cleared on ACTIVE/DEGRADED, except that a **completed** sweep is re-armed exactly as v1 did (`sweep=0, gap=sweep_gap`). Block order (argmax Eq.2 priority over blocks not yet swept) and test semantics are unchanged.
A sweep bit is set only by an IDLE-state FULL+DIAG decision (completion is tick-atomic in this model: every test fits one tick, asserted in the campaign). Partial scans (DEGRADED) never set a bit or `lastfull`.

## 5. Fix C - starvation (`starve_en`) and the exact guarantee
* Tracking: `lastfull[b]`, `overdue[b]` (overdue after `overdue_ticks` = 150 ticks without a completed full scan).
* Mechanism (smallest consistent with the architecture): in DEGRADED, on a tick where the **mission is genuinely idle** (`mission_active=0`, i.e. a tick where IDLE rules would allow a full scan), if `fair >= fair_gap` (4), **no flagged block has unresolved-fault evidence** (`degmask & unres == 0`), and an overdue **unflagged** block exists, run FULL+DIAG(+MBIST for regfile) on the highest-priority such block (reason 5). Otherwise the v1 DEGRADED diagnostic runs.
* Never changed: ACTIVE state (ONLINE only), the DEGRADED diagnostic on flagged blocks while an unresolved fault exists, one decision per tick, no concurrency, no new priority weights.
* **Guarantee (conditional):** if the mission is mission-idle on every tick, and no flagged block holds unresolved-fault evidence, an unflagged block waits at most `overdue_ticks + (NB-1)*(fair_gap+1)` = 170 ticks between full scans (asserted in T10). With `mission_active=1` throughout, nothing can be scheduled and the block is reported `STARVED_NO_ELIGIBLE_WINDOW` (T11). While an unresolved safety fault exists, overdue blocks are reported `WITHHELD_BY_UNRESOLVED_SAFETY_DIAGNOSTIC` (T09). No unconditional bound is claimed.
* Pre-existing behaviour kept: the IDLE-state decision can still issue a full scan on the first ACTIVE tick because of the 2-tick debounce (3 such ticks in v1, 3 refined). Not changed in this step.

## 6. Validation (actual results, this environment)
* Tooling: iverilog 12.0 installed; **Yosys unavailable/not run** (synthesis flow `make synth` not executed, area of the added registers not measured).
* Baseline: git repo created from the shipped tree (`v1-baseline` tag), checksums in `step1_baseline/v1_sha256.txt`; shipped regression reproduced before any change (all PASS).
* Existing regression after changes: `results_step1/existing_regression_after_changes.log` - netlist/RTL equivalence PASS, RTL/Python v1 equivalence PASS (adaptive + baseline, 600 ticks, 0 mismatches), tb_soc/scan/mbist/adaptive/baseline/fault_injection/full_system PASS. (tb_full_system prints two intentional injected "partial scan FAIL" lines.)
* v1 bit-identity: `fault_campaign.csv`, `scheduler_results.csv`, `baseline_period_sweep.csv` regenerated by the modified code into `results_step1/v1_campaign_rerun/` are **byte-identical** (`cmp`) to the shipped files; the literal-stepping verification of 200 faults x 2 modes reports 0 mismatches. 45 shipped result/build artifacts and 32 untouched source files pass `sha256sum -c`; the RTL decision dumps of v1 (adaptive + baseline) are byte-identical before and after the RTL edit.
* New directed tests: `python/check_step1_scheduler.py` (13 tests T01-T13; 13/13 pass), log in `results_step1/step1_directed_tests.txt`.
* RTL == Python: 19 scenarios, 10,540 ticks, 48 columns per tick (decision, priorities, health, aging, faults and every new state variable), including mid-run reset, baseline mode, and non-default parameter variants: 0 mismatches.
* Defects found and fixed during testing (documented, not hidden): (i) re-entry threshold clamped to 255 caused flapping after a saturated-fault recovery -> clamp removed; (ii) two of my test expectations were off by one tick / ignored the v1-identical re-arm of a completed sweep.

## 7. Original mission, v1 vs refined (all features on) - `results_step1/`
| | v1 | refined |
|---|---|---|
| ticks IDLE / ACTIVE / DEGRADED | 136 / 313 / 151 | 174 / 414 / 12 |
| DEGRADED ticks in 449-599 | 151 | 12 (449-452, 515-518, 531-534) |
| partial scans (motor / encoder) | 146 / 5 | 6 / 3 |
| full scans per block (safety, motor, enc, comm, regfile) | 20, 20, 20, 20, 18 | 22, 22, 22, 22, 22 |
| full scans inside ticks 449-599 (each block) | 0 | 4 |
| last full-scan tick (safety, motor, enc, comm, regfile) | 441, 439, 440, 442, 443 | 579, 577, 578, 580, 581 |
| block recovery events / fairness slots used | 0 / 0 | 3 (motor 452, encoder 518, motor 534) / 0 |
| mission-interruption cycles | 67,690 | 13,435 |
Timeline (refined): motor flagged at tick 448 (state DEGRADED 449), three passing PARTIAL+DIAG at 449-451, flag cleared at 452, ACTIVE at 453 with ack=65 and aging still 130 and rising; encoder flagged 514 / cleared 518; motor re-enters at 530 once `unh >= 81` (= ack 65 + 16) and clears at 534.
Fairness slots were not needed on this mission (recovery ends DEGRADED quickly); the fairness path is exercised by T10 and the RTL equivalence scenarios. Fault coverage was **not** recomputed and no coverage claim is made.
