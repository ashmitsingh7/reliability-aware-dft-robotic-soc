"""Check every quantitative / configuration claim made in the paper's Section X ("Implementation of the Reliability-Aware DFT Architecture")
against the artifacts in this repository.  Reads committed results only (results_step3/campaign_summary.json, results/fault_db.csv,
results/mission_trace.csv) plus the model defaults; it does not regenerate anything.

Usage: python3 python/check_paper_claims.py        -> results_paper/paper_claims_check.txt, exit status 1 if any claim fails.
The claim IDs (P01..) are the ones used in docs/PAPER_TRACEABILITY.md, section "Paper Section X claims".
"""
import os, sys, json, csv, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
from common import BNAMES, NB, EPOCH_CYCLES
from reliability_model import Params, ST_IDLE, ST_ACTIVE, ST_DEG, ONLINE
from step1_lib import refined
import mission

S = json.load(open(ROOT + "/results_step3/campaign_summary.json"))
PR = S["profiles"]; REF, OBS, ESC, STALE = (PR[k] for k in ("s2a_all3_evid", "s3_obs", "s3_obs_esc", "s3_obs_esc_stale"))
out, fails = [], 0
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def check(cid, text, ok, detail=""):
    global fails
    fails += (not ok); out.append(f"{'PASS' if ok else 'FAIL'}  {cid}  {text}" + (f"   [{detail}]" if detail else ""))

# ---- architecture / configuration claims
check("P01", "five functional blocks: safety FSM, motor controller, encoder interface, communication interface, register file",
      sorted(BNAMES) == sorted(["safety", "motor", "encoder", "comm", "regfile"]), str(BNAMES))
check("P02", "Eq.(2) weights all unity in every reported profile", all(list(p["config"]["w"]) == [1] * 5 for p in PR.values()),
      str({k: p["config"]["w"] for k, p in PR.items()}))
d = Params()
check("P03", "obs_en, esc_en, stale_en are disabled by default", (d.obs_en, d.esc_en, d.stale_en) == (0, 0, 0), f"{(d.obs_en, d.esc_en, d.stale_en)}")
check("P04", "escalation interval is 10 scheduler ticks (esc_gap)", d.esc_gap == 10 and all(p["config"]["esc_gap"] == 10 for p in PR.values()))
# ---- experimental setup claims
tr = list(csv.DictReader(open(ROOT + "/results/mission_trace.csv")))
check("P05", "600-tick synthetic mission trace", len(tr) == 600 and S["meta"]["mission_ticks"] == 600, f"{len(tr)} rows")
check("P06", "20,000 modeled cycles per tick", EPOCH_CYCLES == 20000)
rows = list(csv.DictReader(open(ROOT + "/results/fault_db.csv")))
check("P07", "collapsed fault database containing 2,515 faults", len(rows) == 2515 and S["meta"]["faults"] == 2515, f"{len(rows)} rows")
check("P07b", "committed fault_db / atpg_stats / mission_trace are the ones the campaign ran on (sha256 match campaign meta)",
      all(sha(ROOT + "/results/" + f) == S["meta"][k] for f, k in (("fault_db.csv", "fault_db_sha256"), ("atpg_stats.json", "atpg_stats_sha256"), ("mission_trace.csv", "mission_trace_sha256"))))
check("P08", "development seeds: 2024 (mission), 4242 (fault injection)", (S["meta"]["mission_seed"], S["meta"]["injection_seed"]) == (2024, 4242))
check("P09", "transient faults are removed after 60 ticks", S["meta"]["transient_ticks"] == 60)
check("P10", "one injected fault per episode (episodes == faults)", all(p[k]["episodes"] == 2515 for p in PR.values() for k in ("persistent", "transient")))
# ---- reported results
P = lambda r: r["persistent"]; T = lambda r: r["transient"]
check("P11", "2,451 of 2,515 persistent episodes raised a flag under the reference profile", (P(REF)["flagged"], P(REF)["episodes"]) == (2451, 2515))
check("P12", "reference cleared flags while the fault was present in 117 flagged episodes", P(REF)["cleared_while_fault_present"] == 117)
check("P13", "obs_en reduces that count to zero", P(OBS)["cleared_while_fault_present"] == 0 and P(OBS)["flagged"] == 2451)
check("P14", "obs_en alone: none of the 2,440 flagged transient episodes recovered", (T(OBS)["flagged"], T(OBS)["recovered_after_fault_ended"]) == (2440, 0))
check("P15", "obs_en+esc_en: zero premature clearances (persistent and transient)", P(ESC)["cleared_while_fault_present"] == 0 and T(ESC)["cleared_while_fault_present"] == 0)
check("P16", "obs_en+esc_en: recovery in 2,267 of the 2,440 flagged transient episodes", (T(ESC)["recovered_after_fault_ended"], T(ESC)["flagged"]) == (2267, 2440))
check("P17", "remaining 173 transient episodes ended without recovery", T(ESC)["flagged_at_end"] == 173 and 2440 - 2267 == 173)
m = [round(x["persistent"]["mean_interruption_cycles"]) for x in (REF, OBS, ESC)]
check("P18", "mean mission-interruption cycles (persistent): 469,680 / 486,764 / 526,202", m == [469680, 486764, 526202], str(m))
pc = [100 * (m[i] / m[0] - 1) for i in (1, 2)]
check("P19", "increases of approximately 3.6% and 12.0% vs the reference", [round(x, 1) for x in pc] == [3.6, 12.0], f"{pc[0]:.2f}%, {pc[1]:.2f}%")
check("P20", "Table IV transient reference row (2,174 recovered / 112 premature / 155 at end)",
      (T(REF)["recovered_after_fault_ended"], T(REF)["cleared_while_fault_present"], T(REF)["flagged_at_end"]) == (2174, 112, 155))
check("P21", "stale_en profile does not change any reported result within the 600-tick mission",
      all(P(STALE)[k] == P(ESC)[k] and T(STALE)[k] == T(ESC)[k] for k in ("flagged", "cleared_while_fault_present", "recovered_after_fault_ended", "flagged_at_end", "mean_interruption_cycles")))
# ---- state-dependent behaviour (fault-free run of the adaptive scheduler over the mission trace)
Mgr = sys.modules["reliability_model"].Manager
trace = mission.generate(); m_ = Mgr(refined(evid_en=1, obs_en=1, esc_en=1)); res = [0] * NB; seen = {ST_IDLE: set(), ST_ACTIVE: set(), ST_DEG: set()}
for x in trace:
    dd = m_.step(x["mission_active"], x["act"], x["urg"], res, [0] * NB)
    if dd["valid"]: seen[dd["state"]].add(dd["tset"])
check("P22", "ACTIVE state issues only the lightweight online test (Algorithm 1) in the fault-free mission", seen[ST_ACTIVE] <= {ONLINE}, str(sorted(seen[ST_ACTIVE])))
check("P23", "IDLE state issues full-depth tests (FULL bit set on every IDLE decision)", all(t & 1 for t in seen[ST_IDLE]), str(sorted(seen[ST_IDLE])))
# ---- test-suite evidence
tl = ROOT + "/results_step3/step3_phase1_tests.txt"
last = [l for l in open(tl) if "PHASE-1 TESTS" in l]
check("P24", "Step-3 Phase-1 test log reports 18/18 passed", bool(last) and "18/18" in last[-1], last[-1].strip() if last else "log missing")

os.makedirs(ROOT + "/results_paper", exist_ok=True)
hdr = f"Paper Section X claim check ({len(out)} claims, {fails} failing)\n" + "\n".join(out) + "\n"
open(ROOT + "/results_paper/paper_claims_check.txt", "w").write(hdr); print(hdr)
sys.exit(1 if fails else 0)
