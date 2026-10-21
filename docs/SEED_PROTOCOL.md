# Seed protocol (Phase 0)

Purpose: nothing that is reported in the paper may have been tuned on the data it is reported on.

| Set | Seeds | Allowed use |
|---|---|---|
| Fixed development (Steps 1-3 so far) | mission 2024, injection 4242 | All design work. Already seen; no paper claim rests on it alone. |
| Development pool | mission 1000..1019, injection = 7*s+1 | Parameter choices: Eq.(2) weights, `esc_gap`, `sweep_gap`, overdue limit, Phase-3 candidates, sensitivity sweeps. |
| Sealed evaluation | 20 seeds from a fixed public rule (`python/seed_protocol.py`) | One run at the end (Phase 5), through `eval_seeds()`. |

Mechanics (`python/seed_protocol.py`): `eval_seeds()` raises unless `PAPER_FINAL=1`, writes `results_final/EVAL_RUN_ONCE.json` on first use and refuses a second use unless `PAPER_FINAL_FORCE=1` (logged as a re-run, which the paper must then state). The seeds are fixed by the rule now; no script has used them yet. This is a discipline aid, not a security boundary: the rule is public in the repo.

Phase-1 status: every Step-3 number (`results_step3/`) uses the fixed development seeds only (mission 2024, injection 4242). No multi-seed claim is made anywhere in Phase 1.
