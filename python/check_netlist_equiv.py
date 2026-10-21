"""Co-simulation check: RTL (iverilog) vs Yosys gate-level netlist model (Python) on random vectors."""
import random, subprocess, os, sys
from netlist import *
def run(nvec=600, seed=1):
    ok = True
    for b in BLOCKS:
        rnd = random.Random(seed + b["ns"])
        vecs = [rnd.getrandbits(b["ni"]) for _ in range(nvec)]
        open(f"{BUILD}/eq_{b['name']}.mem", "w").write("\n".join(f"{v:x}" for v in vecs) + "\n")
        tb = f"""`timescale 1ns/1ps
module eq_tb; reg clk=0, rst_n=0; reg [{b['ni']-1}:0] pi=0; wire [{b['no']-1}:0] po; integer t, fd; reg [{b['ni']-1}:0] mem [0:{nvec-1}];
 {b['mod']} dut(.clk(clk),.rst_n(rst_n),.scan_en(1'b0),.scan_in(1'b0),.scan_out(),.state_q(),.pi(pi),.po(po),.fi_s0({b['ns']}'d0),.fi_s1({b['ns']}'d0));
 always #5 clk=~clk;
 initial begin $readmemh("{BUILD}/eq_{b['name']}.mem", mem); fd=$fopen("{BUILD}/eq_{b['name']}.out","w");
  repeat(2) @(negedge clk); rst_n=1;
  for (t=0;t<{nvec};t=t+1) begin pi=mem[t]; #1 $fdisplay(fd,"%h",po); @(negedge clk); end
  $fclose(fd); $finish; end
endmodule
"""
        open(f"{BUILD}/eq_{b['name']}.sv", "w").write(tb)
        r = subprocess.run(["iverilog", "-g2012", "-o", f"{BUILD}/eq_{b['name']}.vvp", f"{BUILD}/eq_{b['name']}.sv",
                            f"{RTL}/dft/scan_ff.sv", f"{RTL}/dft/scan_chain.sv", f"{RTL}/dut/{b['mod']}.sv"], capture_output=True, text=True)
        if r.returncode: print(r.stderr); sys.exit(1)
        subprocess.run(["vvp", f"{BUILD}/eq_{b['name']}.vvp"], capture_output=True)
        outs = [int(x, 16) for x in open(f"{BUILD}/eq_{b['name']}.out").read().split()]
        nl = Netlist(b); q = [0] * b["ns"]; bad = 0
        for t, v in enumerate(vecs):
            po, d = nl.good([(v >> i) & 1 for i in range(b["ni"])], q)
            exp = sum(bit << i for i, bit in enumerate(po))
            if exp != outs[t]: bad += 1
            q = d
        print(f"{b['name']:8s} cycles={nvec} mismatches={bad}"); ok &= (bad == 0)
    print("NETLIST/RTL EQUIVALENCE:", "PASS" if ok else "FAIL"); return ok
if __name__ == "__main__": sys.exit(0 if run() else 1)
