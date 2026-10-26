"""Yosys (generic gate mapping, no liberty/PDK) cell/flop counts.  Reports ONLY measured counts.
Timing / power / PPA: NOT EVALUATED (no technology library, no STA/power flow in this repo)."""
import re, subprocess, shutil, csv, sys
from common import *
Y = shutil.which("yosys") or shutil.which("yowasp-yosys")
CELL_RE = re.compile(r"^\s+(?:(\$_\w+_)\s+(\d+)|(\d+)\s+(\$_\w+_))\s*$", re.M)
def parse_cells(text, tag):
    cells = {}
    for m in CELL_RE.finditer(text):
        name, count = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        cells[name] = int(count)
    if not cells: raise RuntimeError(f"{tag}: synthesis statistics parser found no cells")
    return cells
SRC = {"scan_ff": "dft/scan_ff.sv", "scan_chain": "dft/scan_chain.sv"}
def synth(files, top, tag):
    fl = " ".join(f"{RTL}/{f}" for f in files)
    scr = (f"read_verilog -sv -I{RTL}/dft -I{RTL}/reliability {fl}; hierarchy -top {top}; proc; flatten; opt -nodffe -nosdff; techmap; opt -nodffe -nosdff; "
           f"dfflegalize -cell $_DFF_P_ 01; abc -g AND,NAND,OR,NOR,XOR,XNOR; opt_clean -purge; tee -o {BUILD}/syn_{tag}.txt stat")
    r = subprocess.run([Y, "-q", "-p", scr], capture_output=True, text=True, cwd=ROOT)
    if r.returncode: print(tag, "FAILED", r.stdout[-400:], r.stderr[-400:]); return None
    t = open(f"{BUILD}/syn_{tag}.txt").read(); cells = parse_cells(t, tag)
    ff = sum(v for k, v in cells.items() if "DFF" in k); tot = sum(cells.values())
    return dict(module=tag, total_cells=tot, flip_flops=ff, combinational_cells=tot - ff)
def main():
    rows = []
    for b in BLOCKS:   # scan-enabled block vs scan-tied-off netlist (scan_en=0)
        f = ["dft/scan_ff.sv", "dft/scan_chain.sv", f"dut/{b['mod']}.sv"]
        r = synth(f, b["mod"], b["name"] + "_with_scan")
        s = open(f"{BUILD}/{b['name']}.stat").read(); cells = parse_cells(s, b["name"])
        ff = sum(v for k, v in cells.items() if "DFF" in k); tot = sum(cells.values())
        rows.append(r); rows.append(dict(module=b["name"] + "_functional_only(scan tied off)", total_cells=tot, flip_flops=ff, combinational_cells=tot - ff))
    items = [("robotic_soc_core(5 blocks+wrappers+scan chains+FI hooks)", ["common/fault_injector.sv", "dft/scan_ff.sv", "dft/scan_chain.sv"] + [f"dut/{b['mod']}.sv" for b in BLOCKS] + ["dut/robotic_soc_core.sv"], "robotic_soc_core"),
             ("mbist_controller", ["dft/mbist_controller.sv"], "mbist_controller"),
             ("online_test(checker only; shadow copy NOT included)", ["dft/online_test.sv"], "online_test"),
             ("test_controller", ["dft/test_controller.sv"], "test_controller"),
             ("reliability_manager(state mon+aging+health+priority+scheduler)", [f"reliability/{m}.sv" for m in ("state_monitor", "aging_model", "health_manager", "priority_engine", "test_scheduler", "reliability_manager")], "reliability_manager"),
             ("scan_test_bank(pattern ROMs synthesised as logic)", ["dft/atpg_interface.sv"], "scan_test_bank")]
    for name, files, top in items:
        r = synth(files, top, top)
        if r: r["module"] = name; rows.append(r)
    rows = [r for r in rows if r]
    with open(RESULTS + "/synthesis.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["module", "total_cells", "flip_flops", "combinational_cells"]); w.writeheader(); w.writerows(rows)
    for r in rows: print(r)
if __name__ == "__main__": main()
