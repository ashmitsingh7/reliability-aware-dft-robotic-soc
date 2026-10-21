"""RTL -> gate-level netlist (Yosys, open-source).  Scan/reset tied inactive so the netlist is the functional
logic that scan-ATPG sees (full-scan => combinational frame with PPI=FF.Q, PPO=FF.D)."""
import os, subprocess, sys, shutil
from common import *

def run_yosys(script):
    exe = shutil.which("yosys") or shutil.which("yowasp-yosys")
    return subprocess.run([exe, "-q", "-p", script], capture_output=True, text=True)

def build():
    os.makedirs(BUILD, exist_ok=True)
    for b in BLOCKS:
        m = b["mod"]
        wrap = f"""module nl_{b['name']}(input clk, input [{b['ni']-1}:0] pi, output [{b['no']-1}:0] po, output [{b['ns']-1}:0] sq);
  {m} u(.clk(clk), .rst_n(1'b1), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(sq),
        .pi(pi), .po(po), .fi_s0({b['ns']}'d0), .fi_s1({b['ns']}'d0));
endmodule
"""
        wp = os.path.join(BUILD, f"nl_{b['name']}.sv"); open(wp, "w").write(wrap)
        js = os.path.join(BUILD, f"{b['name']}.json")
        script = (f"read_verilog -sv {RTL}/dft/scan_ff.sv {RTL}/dft/scan_chain.sv {RTL}/dut/{m}.sv {wp}; "
                  f"hierarchy -top nl_{b['name']}; proc; flatten; opt -nodffe -nosdff; techmap; opt -nodffe -nosdff; "
                  f"dfflegalize -cell $_DFF_P_ 01; abc -g AND,NAND,OR,NOR,XOR,XNOR; opt_clean -purge; "
                  f"tee -o {BUILD}/{b['name']}.stat stat; write_json {js}")
        r = run_yosys(script)
        if r.returncode != 0 or not os.path.exists(js):
            print(r.stdout[-2000:], r.stderr[-2000:]); sys.exit(1)
        print("synthesised", b["name"])
if __name__ == "__main__":
    build()
