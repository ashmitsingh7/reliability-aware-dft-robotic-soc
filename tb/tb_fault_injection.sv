// Automated RTL fault-injection campaign: every stuck-at-0/1 on every state bit, block PI and block PO of the SoC core
// (RTL injection masks), 600-cycle mission workload, compared cycle-by-cycle with a fault-free golden core.
// Self-checks: fault-free control shows zero mismatches; campaign is non-trivial.  CSV: results/rtl_fault_injection.csv
`timescale 1ns/1ps
module tb_fault_injection;
  reg clk = 0, rst_n = 0; always #5 clk = ~clk;
  wire rxd, ea, eb, estop; wire [3:0] cur, rda;
  stim_gen sg (.clk(clk), .rst_n(rst_n), .run_en(1'b1), .estop_en(1'b1), .rxd(rxd), .enc_a(ea), .enc_b(eb), .estop(estop), .cur(cur), .rd_addr(rda));
  reg fi_en = 0; reg [2:0] fi_blk = 0; reg [1:0] fi_reg = 0; reg [7:0] fi_bit = 0; reg fi_val = 0;
  wire [73:0] po_g, po_f;
  robotic_soc_core golden (.clk(clk), .rst_n(rst_n), .rxd(rxd), .enc_a(ea), .enc_b(eb), .estop(estop), .cur_sense(cur), .rd_addr(rda), .pwm(), .motor_en(), .brake(),
    .fsm_state(), .rdata(), .tm(5'd0), .scan_en(5'd0), .scan_in(5'd0), .scan_out(), .tpi(31'd0), .mb_en(1'b0), .mb_we(1'b0), .mb_addr(4'd0), .mb_wdata(8'd0),
    .po_flat(po_g), .fi_en(1'b0), .fi_blk(3'd0), .fi_reg(2'd0), .fi_bit(8'd0), .fi_val(1'b0));
  robotic_soc_core faulty (.clk(clk), .rst_n(rst_n), .rxd(rxd), .enc_a(ea), .enc_b(eb), .estop(estop), .cur_sense(cur), .rd_addr(rda), .pwm(), .motor_en(), .brake(),
    .fsm_state(), .rdata(), .tm(5'd0), .scan_en(5'd0), .scan_in(5'd0), .scan_out(), .tpi(31'd0), .mb_en(1'b0), .mb_we(1'b0), .mb_addr(4'd0), .mb_wdata(8'd0),
    .po_flat(po_f), .fi_en(fi_en), .fi_blk(fi_blk), .fi_reg(fi_reg), .fi_bit(fi_bit), .fi_val(fi_val));
  integer widths [0:14]; integer errors = 0, b, r, bit_i, v, c, first, fd, total = 0, detected = 0, nbits;
  integer reg_tot [0:2]; integer reg_det [0:2]; integer blk_tot [0:4]; integer blk_det [0:4];
  task trial(input integer blk, input integer rg, input integer bt, input integer val, input en);
    begin
      fi_en = en; fi_blk = blk; fi_reg = rg; fi_bit = bt; fi_val = val;
      rst_n = 0; repeat (2) @(negedge clk); rst_n = 1; first = -1;
      for (c = 0; c < 600; c = c + 1) begin @(negedge clk); if (first < 0 && po_g !== po_f) first = c; end
    end
  endtask
  initial begin
    // widths[region*5 + block]
    widths[0]=9;  widths[1]=24; widths[2]=31; widths[3]=27; widths[4]=128;     // state
    widths[5]=6;  widths[6]=20; widths[7]=3;  widths[8]=2;  widths[9]=31;      // PI
    widths[10]=9; widths[11]=10; widths[12]=16; widths[13]=15; widths[14]=24;  // PO
    for (r = 0; r < 3; r = r + 1) begin reg_tot[r] = 0; reg_det[r] = 0; end
    for (b = 0; b < 5; b = b + 1) begin blk_tot[b] = 0; blk_det[b] = 0; end
    fd = $fopen("results/rtl_fault_injection.csv", "w"); $fwrite(fd, "block,region,bit,fault,detected,first_cycle\n");
    repeat (2) @(negedge clk);
    trial(0, 0, 0, 0, 0);  // fault-free control
    if (first >= 0) begin errors = errors + 1; $display("FAIL: golden vs fault-free-control mismatch at cycle %0d", first); end
    for (r = 0; r < 3; r = r + 1) for (b = 0; b < 5; b = b + 1) for (bit_i = 0; bit_i < widths[r*5+b]; bit_i = bit_i + 1) for (v = 0; v < 2; v = v + 1) begin
      trial(b, r, bit_i, v, 1); total = total + 1; reg_tot[r] = reg_tot[r] + 1; blk_tot[b] = blk_tot[b] + 1;
      if (first >= 0) begin detected = detected + 1; reg_det[r] = reg_det[r] + 1; blk_det[b] = blk_det[b] + 1; end
      $fwrite(fd, "%0d,%0d,%0d,SA%0d,%0d,%0d\n", b, r, bit_i, v, (first >= 0), first);
    end
    $fclose(fd);
    $display("RTL fault injection: %0d faults, %0d detected by 600-cycle workload compare (%0d%%)", total, detected, 100*detected/total);
    $display(" by region  state %0d/%0d  PI %0d/%0d  PO %0d/%0d", reg_det[0], reg_tot[0], reg_det[1], reg_tot[1], reg_det[2], reg_tot[2]);
    $display(" by block   safety %0d/%0d motor %0d/%0d encoder %0d/%0d comm %0d/%0d regfile %0d/%0d", blk_det[0], blk_tot[0], blk_det[1], blk_tot[1], blk_det[2], blk_tot[2], blk_det[3], blk_tot[3], blk_det[4], blk_tot[4]);
    if (total != 710 || detected < total / 2) begin errors = errors + 1; $display("FAIL: campaign size/detection sanity"); end
    if (errors == 0) $display("tb_fault_injection PASS"); else $display("tb_fault_injection FAIL errors=%0d", errors);
    $finish;
  end
endmodule
