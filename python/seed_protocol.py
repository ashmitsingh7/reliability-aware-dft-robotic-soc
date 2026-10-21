"""Seed protocol (Phase 0 of the paper-evaluation plan).  Nothing tuned on data that is reported.

DEVELOPMENT seeds: every design / parameter decision (weights, esc_gap, sweep_gap, overdue limit, Phase-3 candidates) may look at these only.
  mission seed 2024 / injection seed 4242 are the seeds used by Steps 1-3 so far; they are development seeds (already seen, no claim rests on them alone).
  Additional development seeds: DEV_MISSION = 1000..1019; the injection seed of mission seed s is INJ(s) = 7*s + 1.
SEALED evaluation seeds: EVAL_MISSION = 20 seeds derived by a fixed public rule from the label below.  They are NOT to be used in any design
  decision.  The final evaluation reads them through eval_seeds(), which refuses to run unless PAPER_FINAL=1 and records the first (and only intended)
  run in results_final/EVAL_RUN_ONCE.json.  A second run requires PAPER_FINAL_FORCE=1 and is logged as a re-run in the same file (the paper must
  then say so).  The rule is deterministic, so the seeds are fixed now even though no script has used them yet.
"""
import os, json, hashlib, time
from common import ROOT

DEV_FIXED = dict(mission=2024, injection=4242)
DEV_MISSION = list(range(1000, 1020))
def inj_seed(mission_seed): return 7 * mission_seed + 1
LABEL = "paper-eval-v1"
def _derive(i): return int(hashlib.sha256(f"{LABEL}:{i}".encode()).hexdigest()[:8], 16) % (2 ** 31)
EVAL_RULE = f"seed_i = int(sha256('{LABEL}:'+i).hex[:8],16) % 2**31 for i in 0..19"
MARK = os.path.join(ROOT, "results_final", "EVAL_RUN_ONCE.json")

def dev_seeds(): return [(s, inj_seed(s)) for s in DEV_MISSION]

def eval_seeds():
    if os.environ.get("PAPER_FINAL") != "1": raise RuntimeError("sealed evaluation seeds are only available with PAPER_FINAL=1 (see docs/SEED_PROTOCOL.md)")
    prior = json.load(open(MARK)) if os.path.exists(MARK) else None
    if prior and os.environ.get("PAPER_FINAL_FORCE") != "1": raise RuntimeError(f"sealed evaluation already run at {prior['first_run_utc']}; set PAPER_FINAL_FORCE=1 to re-run (logged as a re-run)")
    os.makedirs(os.path.dirname(MARK), exist_ok=True)
    rec = prior or dict(first_run_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), rule=EVAL_RULE, reruns=[])
    if prior: rec["reruns"].append(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(rec, open(MARK, "w"), indent=1)
    return [(_derive(i), inj_seed(_derive(i))) for i in range(20)]

if __name__ == "__main__":
    print("development fixed:", DEV_FIXED); print("development seeds:", dev_seeds()[:3], "... (20)"); print("sealed rule:", EVAL_RULE, "(values not printed; PAPER_FINAL=1 required)")
