"""Step-2B characterization / invariant tests.  NOTE: Step 2B found no implementation defect (see docs/STEP2B_ROOT_CAUSE_REPORT.md), so these are
CHARACTERIZATION tests that pin the confirmed findings to the raw artifacts and the implemented detection tables; they are not bug-fix regressions.
Reads results_step2a/ + results_step2b/ + results/ only.  Exit 0 iff all pass."""
import os, sys, csv, json, collections, hashlib
import fault_campaign as fc
from step1_lib import *
R2A = ROOT + "/results_step2a"; R2B = os.environ.get("STEP2B_OUT", ROOT + "/results_step2b"); LOG = []; RES = []
def say(s): print(s); LOG.append(s)
def T(name):
    def deco(fn):
        try: fn(); RES.append(True); say("PASS  " + name)
        except AssertionError as e: RES.append(False); say(f"FAIL  {name}: {e}")
        return fn
    return deco
def A(c, m=""):
    if not c: raise AssertionError(m)
rows = fc.load_db(); idx = {r["fault_id"]: i for i, r in enumerate(rows)}; P = Params()
eps = list(csv.DictReader(open(R2A + "/profiles/s2a_all3_evid/closed_loop_episodes.csv")))

@T("B01 DIAG component has no detection table: it never detects any fault; a PARTIAL+DIAG decision fails for a fault iff detect_partial=1")
def _():
    for r in rows:
        A(fc.detects(r, "DIAG", 0, P) == 0)
        A(bool(fc.detects(r, "PARTIAL_SCAN", 0, P)) == bool(r["detect_partial"]))

@T("B02 over all 2451 flagged episodes (evidence profile): flag cleared while fault persists  <=>  detect_partial == 0 (117 vs 0 exceptions)")
def _():
    n = collections.Counter()
    for e in eps:
        if e["flagged_tick"] in ("", "None"): continue
        n[(rows[idx[e["fault_id"]]]["detect_partial"], e["cleared_while_fault_persists"])] += 1
    A(dict(n) == {(1, "0"): 2334, (0, "1"): 117}, str(dict(n)))

@T("B03 every flagged-and-cleared case is a diagnostic that cannot observe the fault: detect_full=1, detect_partial=0, diag decisions all PARTIAL_SCAN+DIAG and all PASS; unresolved bit clears after the first pass")
def _():
    c = list(csv.DictReader(open(R2B + "/flag_clearance_cases.csv"))); A(len(c) == 117)
    for x in c:
        A(x["detect_partial"] == "0" and x["detect_full"] == "1" and x["diag_selected_tests"] == "PARTIAL_SCAN+DIAG" and set(x["diag_results"].split("|")) == {"PASS"}, x["fault_id"])
        A(int(x["unresolved_bit_cleared_tick"]) == int(x["diag_ticks"].split("|")[0]) + 1, x["fault_id"])
        A(x["python_clear_tick_replayed_from_fe"] == x["flag_clear_tick"] and x["rtl_equals_python_on_episode"] in ("1", ""), x["fault_id"])
    A(set(x["fault_id"] for x in c) == set(e["fault_id"] for e in eps if e["cleared_while_fault_persists"] == "1"))

@T("B04 partial-blind but detectable faults = 119 = 117 flagged-and-cleared + 2 injected too late to be detected")
def _():
    blind = [r for r in rows if not r["detect_partial"] and (r["detect_full"] or r["detect_mbist"] or r["detect_online_mask"])]; A(len(blind) == 119)
    und = [e for e in eps if rows[idx[e["fault_id"]]]["detect_partial"] == 0 and e["det"] == "0" and rows[idx[e["fault_id"]]]["detect_full"]]; A(len(und) == 2)

@T("B05 coverage gap vs N=20 is entirely injections in the last 18 ticks: 62 N20-only faults, all injected at tick >= 581, none with a capable adaptive test after injection; every injection before tick 581 is detected by all profiles (except 2 undetectable faults)")
def _():
    m = list(csv.DictReader(open(R2B + "/missed_faults.csv"))); n20 = [x for x in m if x["N20_detected"] == "1"]; A(len(n20) == 62)
    A(min(int(x["injection_tick"]) for x in n20) == 581 and all(int(x["adaptive_capable_tests_executed_after_injection"]) == 0 for x in m))
    A(all(x["category"] in ("NO_MISSION_IDLE_WINDOW_BEFORE_MISSION_END", "IDLE_WINDOW_PRESENT_BUT_SWEEP_REARM_GAP_NOT_ELAPSED") for x in n20))
    lat = list(csv.DictReader(open(R2B + "/detection_latency_comparison.csv")))
    for x in lat:
        if int(x["injection_tick"]) < 581 and rows[idx[x["fault_id"]]]["detect_full"]: A(x["s2a_evid_detected"] == "1" and x["s1_all3_detected"] == "1", x["fault_id"])
    A(collections.Counter(x["population"] for x in lat) == {"both": 2451, "N20_only": 62, "neither": 2})

@T("B06 raw-log check: N=20 detects all 62 with the FULL_SCAN at tick 599 (the last tick of the mission); the adaptive run has no later full scan of those blocks than tick 581")
def _():
    m = [x for x in csv.DictReader(open(R2B + "/missed_faults.csv")) if x["N20_detected"] == "1"]
    A(set(x["N20_detection_tick"] for x in m) == {"599"}, str(set(x["N20_detection_tick"] for x in m)))
    raw = list(csv.DictReader(open(R2A + "/profiles/s2a_all3_evid/decision_log.csv")))
    last = max(int(r["tick"]) for r in raw if int(r["valid"]) and int(r["tset"]) & FULL); A(last <= 581, last)

@T("B07 protected artifacts unchanged since the Step-2B pre-edit checksum list (results/, results_step1/, results_step2a/, rtl/, tb/, docs/ and pre-existing python/)")
def _():
    bad = []
    for line in open(R2B + "/baseline_evidence/pre_edit_sha256.txt"):
        h, p = line.rstrip("\n").split("  ", 1)
        if p.startswith("python/step2b") or p.startswith("python/check_step2b"): continue
        if not os.path.exists(os.path.join(ROOT, p)) or hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() != h: bad.append(p)
    A(not bad, str(bad[:5]))

if __name__ == "__main__":
    n = sum(RES); say(f"\nSTEP-2B CHARACTERIZATION TESTS: {n}/{len(RES)} passed"); open(R2B + "/step2b_tests.txt", "w").write("\n".join(LOG) + "\n"); sys.exit(0 if n == len(RES) else 1)
