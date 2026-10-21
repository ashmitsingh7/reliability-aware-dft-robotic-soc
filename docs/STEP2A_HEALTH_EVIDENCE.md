# Step 2A - Health-evidence separation, audit findings, and semantics
Scope: Step 2A only. No priority-weight tuning, no new scheduling policy. All Step-2A switches default OFF (`evid_en=0`, `arisk_deg=0`); with them OFF the v1 and Step-1 behaviour is unchanged (v1 campaign CSVs byte-identical, see STEP2A_METHODOLOGY.md).

## 1. What was wrong (confirmed in source)
1. **Aging used as diagnostic evidence.** `unh = min(255, aging/2 + fault_penalty)` drove the DEGRADED flag, so an aging-only flag looked like a failed diagnostic. Step 1 made it recoverable but still through the same flag (`dflag`), and "recovery" by passing diagnostics read as if it cleared a fault.
2. **Passing diagnostic != physical recovery.** In this behavioural model a diagnostic passes whenever no fault is injected. That says nothing about NBTI/HCI recovery. Aging is never reset.
3. **Starvation report used one global condition** (any flagged block with unresolved evidence) for every overdue block.
4. **16-bit `lastfull` rollover defect (RTL only).** v1/Step-1 RTL computed `tcnt(32b) - lastfull(16b)`; after tick 65535 a freshly scanned block looked ~65,536 ticks old, i.e. falsely overdue. The Python model had unbounded integers and could not show it. The 600-tick and 900-tick tests cannot reach it.
5. **`--verify` of the v1 campaign is vacuous for feedback**: `full_sim()` feeds zero results and returns at first detection.

## 2. Signals and transitions changed (smallest change)
| Concept | Python (`Manager`) | RTL | Meaning |
|---|---|---|---|
| aging risk | `arisk[b]` = `(aging[b]>>1) >= deg_th` | `dbg_arisk` | pure aging estimate vs threshold; monotone; never cleared; never resets aging; influences scheduling only through the unchanged Eq.(2) aging term |
| diagnostic fault | `dfl[b]` / `dfault` | `dbg_dfault` | set by a failed test (`res_fail`), cleared only by `recov_n` consecutive passing DIAG decisions |
| aging escalation | `afl[b]` / `aflag` | `dbg_aflag` | only if `arisk_deg=1`: aging may force DEGRADED without fault evidence; enters at `max(deg_th, ack+margin)` on the aging-only value, cleared by the same pass rule; ack stores `aging>>1` |
| unresolved evidence | `unres[b]` (unchanged) | `dbg_unres` | set by failed test, cleared by passing DIAG; never set by aging |
| operating state | unchanged | unchanged | DEGRADED iff any `degmask` bit at previous tick (flag at t, state at t+1) |
| fairness cause | `fcause` | `dbg_fcause` | recorded by the scheduler each DEGRADED tick (below) |

`degmask = dfault | (arisk_deg ? aflag : 0)` when `evid_en=1`. Event ordering inside a tick is identical to Step 1: failure sets `dfault`; else if flagged and `okc >= recov_n` clear both flags (aflag clearing records ack); else aging entry. A failure during recovery resets `okc`.

Recovery policy (diagnostic status only): N consecutive passing DIAG decisions on the block with no failure between. Time alone never clears a flag. Recovery does not clear `arisk`, does not reset aging, and does not mean physical recovery. A failed diagnostic is the only way to establish unresolved fault evidence. With `arisk_deg=0` an aging-only block is never DEGRADED (aging still raises its Eq.(2) priority). With `arisk_deg=1` and fault-free traces, decisions equal Step-1 recovery exactly (test E03).

Semantic impact: `evid_en=1, arisk_deg=0` removes aging-only DEGRADED periods (original mission: DEGRADED ticks 12 -> 0). This materially changes scheduling relative to Step 1, so it is a separate named profile, not the default and not the "corrected adaptive reference" (that is Step-1 all three).

## 3. Fairness cause (`fcause`) - decision-log evidence for starvation
0 not DEGRADED; 1 mission active (no eligible window); 2 `starve_en` off; 3 `fair_gap` not elapsed; 5 no overdue unflagged candidate; 4 window + gap + candidate exist but an unresolved diagnostic on a flagged block took the slot; 6 granted. `starvation_report()` reports "withheld by diagnostic" only if >=1 tick since the block's last full scan was a mission-idle window, the block was an overdue unflagged candidate, and `fcause==4`; it names the withholding blocks, flags the block's own unresolved state separately, and labels trace-only logs "inferred".

## 4. Counter semantics (audited)
- `lastfull` = 16-bit stamp of the tick of the last completed FULL scan decision (set at the decision tick, same tick in RTL `tcnt` and Python `t`). Pass/fail outcome is not part of it (outcome goes to `unres`). Partial scans never touch it or the sweep bits (T08, E12).
- Age = `(t - lastfull) mod 2^16` in both RTL and Python; overdue iff age >= `overdue_ticks`. Boundary: overdue at exactly `lastfull + overdue_ticks` (E13).
- `lastfull == 0` means "scanned at tick 0 or never since reset"; both give overdue at t=150. Harmless but indistinguishable.
- Documented horizon: a block unscanned for more than 65,535 ticks aliases (overdue clears at 65,536 for 150 ticks). Tested (E18), not fixed (needs one more state bit; out of scope).
- Baseline mode: `(tcnt+1) % BASE_N` with 32-bit `tcnt` would drift at 2^32 ticks (irrelevant at this scale).
