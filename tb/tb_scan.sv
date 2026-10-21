// Scan testbench: shift-in, capture, shift-out of real ATPG patterns on every block; chain integrity (flush);
// negative test with injected state faults.  Expected responses come from the independent Python gate-level model.
`timescale 1ns/1ps
module tb_scan;
  reg clk = 0, rst_n = 0; always #5 clk = ~clk;
  `include "dft_params.svh"
  reg [4:0] start = 0, partial = 0; wire [4:0] busy, done, fail, tm, sen, sin, sout; wire [30:0] tpi; wire [73:0] po_flat;
  wire [31:0] c0, c1, c2, c3, c4;
  reg fi_en = 0; reg [2:0] fi_blk = 0; reg [1:0] fi_reg = 0; reg [7:0] fi_bit = 0; reg fi_val = 0;
  reg [4:0] ftm = 0, fsen = 0, fsin = 0;
  robotic_soc_core core (.clk(clk), .rst_n(rst_n), .rxd(1'b1), .enc_a(1'b0), .enc_b(1'b0), .estop(1'b0), .cur_sense(4'd0), .rd_addr(4'd0),
    .pwm(), .motor_en(), .brake(), .fsm_state(), .rdata(), .tm(tm | ftm), .scan_en(sen | fsen), .scan_in(sin | fsin), .scan_out(sout), .tpi(tpi),
    .mb_en(1'b0), .mb_we(1'b0), .mb_addr(4'd0), .mb_wdata(8'd0), .po_flat(po_flat), .fi_en(fi_en), .fi_blk(fi_blk), .fi_reg(fi_reg), .fi_bit(fi_bit), .fi_val(fi_val));
  scan_test_bank bank (.clk(clk), .rst_n(rst_n), .start(start), .partial(partial), .busy(busy), .done(done), .fail(fail), .tm(tm), .scan_en(sen), .scan_in(sin),
    .tpi(tpi), .scan_out(sout), .po_flat(po_flat), .cycles0(c0), .cycles1(c1), .cycles2(c2), .cycles3(c3), .cycles4(c4));
  integer errors = 0, b, k, L, NPb, NPPb, exp, got; reg [31:0] cy;
  integer Ls [0:4]; integer NPs [0:4]; integer NPPs [0:4];
  task run_scan(input integer blk, input p, output reg f, output reg [31:0] cycles);
    begin
      partial = p ? (5'd1 << blk) : 5'd0; start = 5'd1 << blk; @(negedge clk); start = 0;
      while (!done[blk]) @(negedge clk);
      f = fail[blk];
      cycles = (blk == 0) ? c0 : (blk == 1) ? c1 : (blk == 2) ? c2 : (blk == 3) ? c3 : c4;
    end
  endtask
  // chain-integrity flush: stream a pseudo-random sequence, expect it L cycles later at scan_out
  reg [255:0] hist; reg [15:0] lfsr; reg ok_flush; integer n;
  task flush(input integer blk, input integer len);
    begin
      lfsr = 16'hACE1 + blk; hist = 0; ok_flush = 1; ftm = 5'd1 << blk; fsen = 5'd1 << blk;
      for (n = 0; n < len + 40; n = n + 1) begin
        lfsr = {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
        fsin = lfsr[0] ? (5'd1 << blk) : 5'd0; hist = {hist[254:0], lfsr[0]};
        @(negedge clk);
        if (n >= len && sout[blk] !== hist[len-1]) ok_flush = 0;
      end
      ftm = 0; fsen = 0; fsin = 0;
    end
  endtask
  reg f; 
  initial begin
    Ls[0]=9; Ls[1]=24; Ls[2]=31; Ls[3]=27; Ls[4]=128;
    NPs[0]=NP0; NPs[1]=NP1; NPs[2]=NP2; NPs[3]=NP3; NPs[4]=NP4; NPPs[0]=NPP0; NPPs[1]=NPP1; NPPs[2]=NPP2; NPPs[3]=NPP3; NPPs[4]=NPP4;
    repeat (3) @(negedge clk); rst_n = 1; @(negedge clk);
    for (b = 0; b < 5; b = b + 1) begin
      flush(b, Ls[b]);
      if (!ok_flush) begin errors = errors + 1; $display("FAIL: chain integrity block %0d", b); end
      run_scan(b, 0, f, cy);
      exp = NPs[b] * (Ls[b] + 1) + Ls[b];
      $display("block %0d full scan: patterns=%0d chain=%0d cycles=%0d (expected %0d) fail=%0d flush_ok=%0d", b, NPs[b], Ls[b], cy, exp, f, ok_flush);
      if (f || cy != exp) begin errors = errors + 1; $display("FAIL: fault-free full scan block %0d", b); end
      run_scan(b, 1, f, cy); exp = NPPs[b] * (Ls[b] + 1) + Ls[b];
      $display("block %0d partial scan: patterns=%0d cycles=%0d (expected %0d) fail=%0d", b, NPPs[b], cy, exp, f);
      if (f || cy != exp) begin errors = errors + 1; $display("FAIL: fault-free partial scan block %0d", b); end
    end
    // negative tests: stuck-at on a state bit, a PI and a PO of each block must be caught by full scan
    for (b = 0; b < 5; b = b + 1) for (k = 0; k < 3; k = k + 1) begin
      fi_en = 1; fi_blk = b; fi_reg = k; fi_bit = (k == 0) ? Ls[b] / 2 : 1; fi_val = (b + k) % 2;
      run_scan(b, 0, f, cy);
      $display("injected block %0d region %0d bit %0d SA%0d -> scan fail=%0d", b, k, fi_bit, fi_val, f);
      if (!f) begin errors = errors + 1; $display("FAIL: injected fault not caught by scan"); end
      fi_en = 0;
    end
    if (errors == 0) $display("tb_scan PASS"); else $display("tb_scan FAIL errors=%0d", errors);
    $finish;
  end
endmodule
