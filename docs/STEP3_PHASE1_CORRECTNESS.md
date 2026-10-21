# Step 3, Phase 1 - correctness fixes (obs_en, esc_en, stale_en)
Branch `step3-phase1` from Step 2B (`688e9a2`, tagged `paper-ref-v0`). All three switches are **OFF by default**: with them off the RTL and the Python model are bit-identical to Step 2A (Step 1: 13/13, Step 2A: 18/18 incl. >65,535-tick RTL equivalence, `check_rtl_equiv`: pass, `tb_adaptive`/`tb_baseline`/`tb_soc`/`tb_scan`/`tb_mbist`: pass).
Reproduce: `make campaign-step3 test-step3` (outputs in `results_step3/`). Seeds: fixed development seeds only (mission 2024, injection 4242); **no multi-seed claim** (`docs/SEED_PROTOCOL.md`). Eq.(2) weights, baselines, fault database and detection tables are untouched.

## What changed
1. **`obs_en` - observability-aware diagnostic evidence.** `res_fail` gets a companion `res_cls` (4 bits per block: FULL=1, PARTIAL=2, MBIST=4, ONLINE=8; 0 = unknown). A failure whose class is anything other than PARTIAL-only (including unknown) marks the evidence `nf` ("needs FULL depth"); `nf` accumulates while the evidence is unresolved. A passing DIAG decision clears `unres`/`nf` and counts toward `recov_n` only if it *dominates*: its test set contains FULL, or it contains PARTIAL and `nf`=0. Anything else is a non-informative pass (no change to `unres`, `okc`). The dominance rule rests on the implemented tables: FULL detects a superset of PARTIAL, MBIST and ONLINE for all 2,515 faults (checked: 0 exceptions). ONLINE and MBIST are therefore not treated as comparable with PARTIAL; they demand FULL.
2. **`esc_en` (needs `obs_en`) - escalation.** In DEGRADED, when the selected flagged block has `nf`=1 and at least `esc_gap` (=10, an assumption, not tuned) DEGRADED ticks have passed since the last escalation (first one immediate after reset), the decision is `FULL+DIAG` (+`MBIST` for regfile) instead of `PARTIAL+DIAG`; reason code 6; it refreshes `lastfull`. Escalation is allowed while the mission is active, as DEGRADED partial scans already are. **This is a scheduling-policy change** and must be presented as one in the paper.
3. **`stale_en` - stale bit.** Per block, set when the 16-bit modular age reaches 0xFFFF, cleared by the next full scan; `overdue = age>=T OR stale`. Removes the aliasing beyond 65,535 ticks documented in Step 2A. No effect within the 600-tick mission.
RTL: `health_manager` (+`res_cls`, `last_tset`, `nf_n`, `OBS_EN`), `test_scheduler` (+`nf_n`, `last_tset`, `OBS_EN/ESC_EN/ESC_GAP/STALE_EN`, `dbg_esc`, `dbg_lfstale`), `reliability_manager` (+`res_cls` input, `dbg_nf/esc/lfstale`). Existing instantiations tie `res_cls` to 0. Equivalence columns grew from 52 to 55.

## Result: Phase-1 success criterion
Closed-loop, one fault per episode, 2,515 faults, same injection draw as Steps 2A/2B (`results_step3/campaign_summary.json`):

| profile | flagged (persistent) | cleared while fault present | flag-set events per flagged episode (mean, max) | mean interruption cycles / episode (persistent) |
|---|---|---|---|---|
| Step-2A reference (`s2a_all3_evid`) | 2,451 | **117** | 2.0, 76 | 469,680 |
| `obs_en` | 2,451 | **0** | 1.0, 1 | 486,764 (+3.6%) |
| `obs_en`+`esc_en` | 2,451 | **0** | 1.0, 1 | 526,202 (+12.0%) |

The campaign's reference profile reproduces the Step-2A episodes exactly (flag tick, clear tick, first detection) for all 2,515 faults (test S14), so the 117 -> 0 comparison is like for like.

## Why escalation is needed (transient episodes, fault removed after 60 ticks)
| profile | flagged | recovered after fault ended | cleared while fault present | still flagged at end |
|---|---|---|---|---|
| reference | 2,440 | 2,174 | **112** | 155 |
| `obs_en` only | 2,440 | **0** | 0 | 2,440 |
| `obs_en`+`esc_en` | 2,440 | 2,267 (median 8, max 13 ticks after the fault ended) | 0 | 173 |
`obs_en` alone removes the false clearances but leaves every flagged block flagged forever, even after the fault is gone (the fairness slot is withheld while evidence is unresolved and DEGRADED only runs partial scans). Escalation restores recovery. The 173 not recovered are episodes whose fault was still present, or ended too late to recover, before the mission ended (test S15 asserts every flagged episode whose fault ended >= 30 ticks before the end recovered).

## Honest cost
Escalation adds 85,026 mission-interrupting cycles per flagged persistent episode (about 16% of that episode's interruption, 27.1 escalations on average, each a FULL scan of the flagged block while the fault persists and fails again). Overall +12.0% mean interruption vs the reference on this experiment, of which +3.6% comes from `obs_en` alone (the reference clears flags early and so stops running DEGRADED scans, which is the premature clearance being removed). `esc_gap` trades this cost against recovery speed; it has not been swept (Phase 4, development seeds). These are persistent-fault episodes in which every flagged block stays DEGRADED to the end of the mission (2,448 of 2,451 end in DEGRADED), which is the correct response to a permanent fault but not a typical mission.

## Tests (`make test-step3`, 18/18)
S01-S12 directed (defaults off, class ignored when off, flaw reproduced and removed, PARTIAL-class evidence still clears by partial passes, unknown class conservative, accumulation in both orders, dominating vs non-dominating pass, escalation spacing exactly `esc_gap`+1 and test set, transient recovery bound, preconditions, safety invariants, stale bit across the wrap, stale bit inert for regularly scanned blocks); S13-S16 campaign-level (117 -> 0, reference reproduces Step 2A, transient recovery, cost reported); S17 RTL==Python on 21 scenarios (285,300 ticks, 55 columns/tick, resets, baseline mode, 70k-tick horizon); S18 six injected RTL defects (no dominance check, no rate limit, unknown class not conservative, no accumulation, stale never set, no `lastfull` refresh) are each caught. The accumulation mutant was first *missed* by random traces and led to two added directed scenarios.
Also changed: the E17 mutation anchor in `check_step2a.py` (the age line it rewrites moved). **Step-2B test B07** ("protected artifacts unchanged since the Step-2B checksum list") now fails by design on this branch (it lists the RTL/Python files edited here); B01-B06 pass. Run B07 on `paper-ref-v0`.

## Limits
- Behavioural model: whether a physical partial scan misses these faults is outside it; the 4.7% partial-blind fraction is a property of the behavioural ATPG tables.
- Single mission trace and injection seed; one fault per episode; no simultaneous faults; `res_cls` is supplied by the testbench/campaign, not yet produced by a real test controller (RTL-in-the-loop is Phase 4).
- Yosys was not available in this session: area/flop cost of the new state (`nf` 5 b, `esc` 8 b, `lfstale` 5 b, `last_tset` 5 b, a few gates) is not measured. `make paper` was only dry-run (`make -n`), not executed end to end.
- Not done in Phase 1 by design: Phase 2 fair baselines/ablations, Phase 3 latency work, mission-end coverage metric.
