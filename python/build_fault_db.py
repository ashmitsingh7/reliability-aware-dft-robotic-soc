"""Builds the fault database: for every collapsed stuck-at fault of every block, determines (by real fault
simulation on the Yosys gate-level netlist) which test mechanism detects it.
  detect_full    : full ATPG pattern set through full scan
  detect_partial : first ceil(PARTIAL_FRAC*P) coverage-ordered patterns ("partial scan")
  detect_mbist   : March C- through the register-file MBIST port (regfile only)
  detect_online  : bit k set if functional window k (lightweight concurrent shadow-compare) exposes the fault
Also exports the scan-pattern ROMs consumed by the RTL testbenches (rtl atpg_interface)."""
import csv, json, math, time
from atpg import *
from fault_simulator import selftest
import workload

def pack(bits): return sum(b << i for i, b in enumerate(bits))

def main():
    os.makedirs(RESULTS + "/rom", exist_ok=True)
    rows = []; stats = {}; gid = 0
    for bi, b in enumerate(BLOCKS):
        t0 = time.time(); nl = Netlist(b)
        assert selftest(nl) == 0, "parallel/serial fault simulators disagree"
        r = generate(nl, seed=11 + bi, limit=2000)
        faults, P, F = r["faults"], len(r["patterns"]), r["F"]
        Pp = math.ceil(PARTIAL_FRAC * P)
        part = 0
        for d in r["dets"][:Pp]: part |= d
        # MBIST (regfile)
        mb = None
        if bi == REGFILE:
            seq = workload.mbist_sequence()
            # sanity: fault-free read data equals expected
            q = [0] * b["ns"]
            for pi, chk, exp in seq:
                po, d = nl.good(pi, q)
                if chk: assert sum(bit << i for i, bit in enumerate(po[:8])) == exp, "MBIST golden mismatch"
                q = d
            mb = nl.fsim_seq([s[0] for s in seq], faults, obs=list(range(8)), check=[s[1] for s in seq])
        # online windows
        onl = [nl.fsim_seq(w, faults) for w in workload.windows(b["name"])]
        cc0, cc1, co = nl.scoap()
        for k, (net, sa) in enumerate(faults):
            gid += 1
            om = sum(((onl[w] >> k) & 1) << w for w in range(ONLINE_K))
            rows.append(dict(fault_id=f"F{gid:05d}", block=b["name"], net=name_of(nl, net), fault_type=f"SA{sa}",
                             criticality=b["crit"], class_size=r["classes"][faults[k]],
                             atpg_status=r["status"][k], detect_full=int((r["cov_mask"] >> k) & 1),
                             detect_partial=int((part >> k) & 1), detect_mbist=(int((mb >> k) & 1) if mb is not None else 0),
                             detect_online_mask=om, scoap_co=co[net]))
        # ROM export
        L, NI, NO = b["ns"], b["ni"], b["no"]
        words = []
        for pi, q in r["patterns"]:
            po, d = nl.good(pi, q)
            w = pack(q) | pack(pi) << L | pack(d) << (L + NI) | pack(po) << (2 * L + NI)
            words.append(w)
        hw = (2 * L + NI + NO + 3) // 4
        open(f"{RESULTS}/rom/{b['name']}.mem", "w").write("\n".join(f"{w:0{hw}x}" for w in words) + "\n")
        pen = sum(1 for k in range(F) if r["status"][k] == "detected")
        stats[b["name"]] = dict(L=L, NI=NI, NO=NO, gates=len(nl.gates), nets=nl.N, faults_uncollapsed=r["total_uncollapsed"],
            faults_collapsed=F, patterns=P, patterns_partial=Pp,
            full_scan_cycles=P * (L + 1) + L, partial_scan_cycles=Pp * (L + 1) + L, diag_cycles=2 * L,
            atpg_detected=pen, atpg_untestable=sum(1 for v in r["status"].values() if v == "untestable"),
            atpg_aborted=sum(1 for v in r["status"].values() if v == "aborted"),
            fault_coverage=pen / F, test_coverage=pen / max(1, F - sum(1 for v in r["status"].values() if v == "untestable")),
            mbist_cycles=mbist_cycles() if bi == REGFILE else 0, online_window=ONLINE_WINDOW,
            scoap_max_cc=max(max(cc0[n], cc1[n]) for n in nl.fault_sites() if cc0[n] < 10**8 and cc1[n] < 10**8),
            scoap_mean_co=sum(co[n] for n in nl.fault_sites() if co[n] < 10**8) / len(nl.fault_sites()))
        print(f"{b['name']:8s} F={F:5d} P={P:3d} Ppart={Pp:3d} cov={pen/F:.4f} untest={stats[b['name']]['atpg_untestable']} "
              f"abort={stats[b['name']]['atpg_aborted']}  {time.time()-t0:.1f}s")
    with open(RESULTS + "/fault_db.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    stats["_meta"] = dict(epoch_cycles=EPOCH_CYCLES, partial_frac=PARTIAL_FRAC, online_window=ONLINE_WINDOW,
                          online_k=ONLINE_K, mbist_words=MBIST_WORDS)
    json.dump(stats, open(RESULTS + "/atpg_stats.json", "w"), indent=1)
    print("faults in database:", len(rows))
if __name__ == "__main__": main()
