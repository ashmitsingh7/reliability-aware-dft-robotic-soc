"""RTL Reliability Manager vs Python reference model, adaptive and baseline, on the mission trace plus injected
test-failure events (exercises fault history / DEGRADED paths)."""
import subprocess, sys, random, csv
from reliability_model import *; import mission
def main():
    tr = mission.generate(); r = random.Random(77)
    fe = {t: 1 << r.randrange(NB) for t in sorted(r.sample(range(30, 580), 14))}
    mission.write(tr, None, BUILD + "/stress_trace.mem", fe)
    srcs = [f"{RTL}/reliability/{m}.sv" for m in ("state_monitor", "aging_model", "health_manager", "priority_engine", "test_scheduler", "reliability_manager")]
    r_ = subprocess.run(["iverilog", "-g2012", "-I", RTL + "/reliability", "-o", BUILD + "/tb_sched.vvp", ROOT + "/tb/tb_scheduler.sv"] + srcs, capture_output=True, text=True)
    if r_.returncode: print(r_.stderr); return False
    ok = True
    for mode in (0, 1):
        out = f"{BUILD}/rtl_dec_mode{mode}.csv"
        o = subprocess.run(["vvp", BUILD + "/tb_sched.vvp", f"+trace={BUILD}/stress_trace.mem", f"+out={out}", f"+mode={mode}", "+ticks=600"], capture_output=True, text=True)
        print(o.stdout.strip().splitlines()[-1])
        rtl = [list(map(int, l.split(","))) for l in open(out)]
        m = Manager(Params(mode=mode)); bad = 0
        for x in tr:
            res = [(fe.get(x["tick"], 0) >> b) & 1 for b in range(NB)]
            d = m.step(x["mission_active"], x["act"], x["urg"], res)
            exp = [d["tick"], d["state"], d["valid"], d["blk"], d["tset"], d["reason"], d["degmask"]] + d["prio"] + d["health"] + d["aging"] + d["faults"]
            if exp != rtl[x["tick"]]:
                bad += 1
                if bad == 1: print("first mismatch tick", x["tick"], "\n exp", exp, "\n rtl", rtl[x["tick"]])
        print(f"mode {mode}: {len(tr)} ticks compared, mismatches = {bad}"); ok &= bad == 0
    print("RTL vs PYTHON MODEL:", "PASS" if ok else "FAIL"); return ok
if __name__ == "__main__": sys.exit(0 if main() else 1)
