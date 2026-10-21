// MBIST testbench.  (1) fault-free memory passes with exactly 10N cycles; (2) behavioural memory-fault model:
// SAF0/SAF1, TF(up/down), AF(alias), CFin, CFid inter-word, CFin intra-word; (3) every stuck-at on the 128 state bits
// of the real register_file RTL (RTL injection masks).  Results printed and written to results/mbist_fault_coverage.csv.
`timescale 1ns/1ps
module faulty_mem (input clk, we, input [3:0] addr, input [7:0] wdata, output [7:0] rdata,
                   input [3:0] ftype, input [3:0] fa, input [2:0] fb, input [3:0] fv, input [2:0] fvb, input init_load, input [127:0] init_val);
  // ftype: 0 none, 1 SAF0, 2 SAF1, 3 TF-up, 4 TF-down, 5 AF alias(fa -> fv), 6 CFin(aggressor up), 7 CFid(up -> victim=1), 8 CFid(down -> victim=0)
  reg [7:0] m [0:15]; integer i;
  wire [3:0] ea = (ftype == 5 && addr == fa) ? fv : addr;
  reg [7:0] rd;
  always @* begin
    rd = m[ea];
    if (ftype == 1 && ea == fa) rd[fb] = 1'b0;
    if (ftype == 2 && ea == fa) rd[fb] = 1'b1;
  end
  assign rdata = rd;
  reg [7:0] old, nw; reg aggup, aggdn;
  always @(posedge clk) begin
    if (init_load) for (i = 0; i < 16; i = i + 1) m[i] <= init_val[8*i +: 8];
    else if (we) begin
      old = m[ea]; nw = wdata;
      if (ftype == 1 && ea == fa) nw[fb] = 1'b0;
      if (ftype == 2 && ea == fa) nw[fb] = 1'b1;
      if (ftype == 3 && ea == fa && !old[fb] && wdata[fb]) nw[fb] = 1'b0;
      if (ftype == 4 && ea == fa && old[fb] && !wdata[fb]) nw[fb] = 1'b1;
      m[ea] <= nw;
      aggup = (ea == fa) && !old[fb] && nw[fb]; aggdn = (ea == fa) && old[fb] && !nw[fb];
      if (ftype == 6 && aggup && !(fa == fv && fb == fvb)) begin if (fa == fv) nw[fvb] = ~nw[fvb]; else m[fv][fvb] <= ~m[fv][fvb]; m[ea] <= nw; end
      if (ftype == 7 && aggup && !(fa == fv && fb == fvb)) begin if (fa == fv) nw[fvb] = 1'b1; else m[fv][fvb] <= 1'b1; m[ea] <= nw; end
      if (ftype == 8 && aggdn && !(fa == fv && fb == fvb)) begin if (fa == fv) nw[fvb] = 1'b0; else m[fv][fvb] <= 1'b0; m[ea] <= nw; end
    end
  end
endmodule

module tb_mbist;
  reg clk = 0, rst_n = 0, start = 0; always #5 clk = ~clk;
  wire busy, done, fail, mem_en, mem_we; wire [3:0] addr, fail_addr; wire [7:0] wdata, rdata;
  reg [3:0] ftype = 0, fa = 0, fv = 0; reg [2:0] fb = 0, fvb = 0; reg il = 0; reg [127:0] iv = 0;
  mbist_controller mb (.clk(clk), .rst_n(rst_n), .start(start), .busy(busy), .done(done), .fail(fail), .mem_en(mem_en), .mem_we(mem_we),
                       .mem_addr(addr), .mem_wdata(wdata), .mem_rdata(rdata), .fail_addr(fail_addr));
  faulty_mem mem (.clk(clk), .we(mem_we), .addr(addr), .wdata(wdata), .rdata(rdata), .ftype(ftype), .fa(fa), .fb(fb), .fv(fv), .fvb(fvb), .init_load(il), .init_val(iv));
  integer errors = 0, cyc, det, tot, t, a, b, c, d, seed = 7, fdout; integer cls_det [0:15]; integer cls_tot [0:15];
  task run_mbist(output integer cycles, output reg failed);
    begin
      il = 1; iv = {$random(seed), $random(seed), $random(seed), $random(seed)}; @(negedge clk); il = 0;
      start = 1; @(negedge clk); start = 0; cycles = 0;
      while (!done) begin @(negedge clk); cycles = cycles + 1; end
      failed = fail;
    end
  endtask
  // register-file section
  reg [127:0] s0, s1; wire [30:0] rf_pi; wire [23:0] rf_po; reg rf_sen = 0;
  assign rf_pi = {mem_en_r, mem_we_r, addr_r, wdata_r, 1'b0, 4'd0, 8'd0, 4'd0};
  wire mem_en_r, mem_we_r; wire [3:0] addr_r; wire [7:0] wdata_r;
  wire rbusy, rdone, rfail, rfa_dummy; wire [3:0] rfaddr;
  mbist_controller mb2 (.clk(clk), .rst_n(rst_n), .start(start2), .busy(rbusy), .done(rdone), .fail(rfail), .mem_en(mem_en_r), .mem_we(mem_we_r),
                        .mem_addr(addr_r), .mem_wdata(wdata_r), .mem_rdata(rf_po[7:0]), .fail_addr(rfaddr));
  reg start2 = 0;
  register_file rf (.clk(clk), .rst_n(rst_n), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(), .pi(rf_pi), .po(rf_po), .fi_s0(s0), .fi_s1(s1));
  reg f1; integer rfdet, cycles2;
  initial begin
    for (t = 0; t < 16; t = t + 1) begin cls_det[t] = 0; cls_tot[t] = 0; end
    fdout = $fopen("results/mbist_fault_coverage.csv", "w"); $fwrite(fdout, "fault_class,injected,detected\n");
    repeat (3) @(negedge clk); rst_n = 1;
    // (1) fault-free
    run_mbist(cyc, f1);
    if (f1) begin errors = errors + 1; $display("FAIL: fault-free memory failed MBIST"); end
    $display("MBIST fault-free: cycles after start = %0d (10N = 160 operations), fail=%0d", cyc, f1);
    if (cyc < 160 || cyc > 163) begin errors = errors + 1; $display("FAIL: unexpected MBIST cycle count"); end
    // (2) memory fault classes
    for (a = 0; a < 16; a = a + 1) for (b = 0; b < 8; b = b + 1) for (t = 1; t <= 4; t = t + 1) begin
      ftype = t; fa = a; fb = b; run_mbist(cyc, f1); cls_tot[t] = cls_tot[t] + 1; if (f1) cls_det[t] = cls_det[t] + 1; end
    for (a = 0; a < 16; a = a + 1) for (b = 0; b < 16; b = b + 1) if (a != b) begin ftype = 5; fa = a; fv = b; run_mbist(cyc, f1); cls_tot[5] = cls_tot[5] + 1; if (f1) cls_det[5] = cls_det[5] + 1; end
    for (a = 0; a < 16; a = a + 1) for (b = 0; b < 16; b = b + 1) if (a != b) for (t = 6; t <= 8; t = t + 1) begin
      ftype = t; fa = a; fb = (a + b) % 8; fv = b; fvb = (a * 3 + b) % 8; run_mbist(cyc, f1); cls_tot[t] = cls_tot[t] + 1; if (f1) cls_det[t] = cls_det[t] + 1; end
    for (a = 0; a < 16; a = a + 1) for (b = 0; b < 7; b = b + 1) begin   // intra-word CFin: bit b aggressor, bit b+1 victim
      ftype = 6; fa = a; fb = b; fv = a; fvb = b + 1; run_mbist(cyc, f1); cls_tot[9] = cls_tot[9] + 1; if (f1) cls_det[9] = cls_det[9] + 1; end
    ftype = 0;
    $display("class        injected detected");
    $display("SAF0         %5d %5d", cls_tot[1], cls_det[1]); $display("SAF1         %5d %5d", cls_tot[2], cls_det[2]);
    $display("TF-up        %5d %5d", cls_tot[3], cls_det[3]); $display("TF-down      %5d %5d", cls_tot[4], cls_det[4]);
    $display("AF(alias)    %5d %5d", cls_tot[5], cls_det[5]); $display("CFin inter   %5d %5d", cls_tot[6], cls_det[6]);
    $display("CFid up->1   %5d %5d", cls_tot[7], cls_det[7]); $display("CFid dn->0   %5d %5d", cls_tot[8], cls_det[8]);
    $display("CFin intra-word (solid background) %5d %5d", cls_tot[9], cls_det[9]);
    $fwrite(fdout, "SAF0,%0d,%0d\nSAF1,%0d,%0d\nTF_up,%0d,%0d\nTF_down,%0d,%0d\nAF_alias,%0d,%0d\nCFin_inter_word,%0d,%0d\nCFid_up_to_1,%0d,%0d\nCFid_down_to_0,%0d,%0d\nCFin_intra_word,%0d,%0d\n",
      cls_tot[1],cls_det[1],cls_tot[2],cls_det[2],cls_tot[3],cls_det[3],cls_tot[4],cls_det[4],cls_tot[5],cls_det[5],cls_tot[6],cls_det[6],cls_tot[7],cls_det[7],cls_tot[8],cls_det[8],cls_tot[9],cls_det[9]);
    for (t = 1; t <= 8; t = t + 1) if (cls_det[t] != cls_tot[t]) begin errors = errors + 1; $display("FAIL: class %0d not fully detected", t); end
    // (3) real register_file RTL: stuck-at on each of the 128 state bits
    rfdet = 0;
    for (a = 0; a < 128; a = a + 1) for (b = 0; b < 2; b = b + 1) begin
      s0 = 0; s1 = 0; if (b) s1[a] = 1'b1; else s0[a] = 1'b1;
      rst_n = 0; repeat (2) @(negedge clk); rst_n = 1; @(negedge clk);
      start2 = 1; @(negedge clk); start2 = 0; while (!rdone) @(negedge clk);
      if (rfail) rfdet = rfdet + 1; else begin errors = errors + 1; $display("FAIL: RF state bit %0d SA%0d escaped MBIST", a, b); end
    end
    s0 = 0; s1 = 0; rst_n = 0; repeat (2) @(negedge clk); rst_n = 1; @(negedge clk);
    start2 = 1; @(negedge clk); start2 = 0; while (!rdone) @(negedge clk);
    if (rfail) begin errors = errors + 1; $display("FAIL: fault-free register_file failed MBIST"); end
    $display("register_file RTL: %0d / 256 state-bit stuck-at faults detected by MBIST", rfdet);
    $fwrite(fdout, "RF_state_SA,256,%0d\n", rfdet); $fclose(fdout);
    if (errors == 0) $display("tb_mbist PASS"); else $display("tb_mbist FAIL errors=%0d", errors);
    $finish;
  end
endmodule
