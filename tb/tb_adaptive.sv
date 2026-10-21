// Adaptive scheduler scenario: IDLE sweep (full suite, criticality/priority order) -> ACTIVE (lightweight online only,
// every 2nd tick) -> fault events on block 1 raise fault history -> DEGRADED (partial scan + diagnostics on block 1, every tick).
`timescale 1ns/1ps
module tb_adaptive;
  reg clk = 0, rst_n = 0, tick = 0, ma = 0; reg [39:0] act = 0, urg = 0; reg [4:0] rf = 0; always #5 clk = ~clk;
  wire [1:0] state; wire dv; wire [2:0] blk, reason; wire [4:0] tset, dm; wire [79:0] prio; wire [39:0] h, ag, fl;
  reliability_manager dut (.clk(clk), .rst_n(rst_n), .tick(tick), .mode(1'b0), .mission_active(ma), .act_in(act), .urg_in(urg), .res_fail(rf), .res_cls(20'd0),
    .weights(20'h11111), .state(state), .dec_valid(dv), .dec_blk(blk), .dec_tset(tset), .dec_reason(reason), .prio(prio), .health(h), .aging(ag), .faults(fl), .degmask(dm));
  integer t, errors = 0, seen_blk, mask_seen, n_online = 0, n_deg = 0, first_deg = -1; reg [4:0] seen;
  task step; begin @(negedge clk); #1; $display("t=%3d state=%0d valid=%0d blk=%0d tset=%b reason=%0d prio=%0d,%0d,%0d,%0d,%0d dm=%b", t, state, dv, blk, tset, reason,
      prio[15:0], prio[31:16], prio[47:32], prio[63:48], prio[79:64], dm); end endtask
  initial begin
    repeat (3) @(negedge clk); rst_n = 1; seen = 0;
    for (t = 0; t < 8; t = t + 1) begin   // IDLE
      ma = 0; act = {5{8'd5}}; urg = 0; step;
      if (t < 5) begin
        if (!(state == 0 && dv && tset[0] && tset[4] && !tset[3] && !seen[blk] && (blk != 4 || tset[2]))) begin errors = errors + 1; $display("FAIL: idle sweep"); end
        seen[blk] = 1;
      end
      tick = 1; @(negedge clk); tick = 0;
    end
    if (seen != 5'b11111) begin errors = errors + 1; $display("FAIL: idle sweep did not cover all blocks"); end
    for (t = 8; t < 24; t = t + 1) begin  // ACTIVE
      ma = 1; act = {8'd35, 8'd80, 8'd110, 8'd150, 8'd40}; urg = {5{8'd128}}; step;
      if (t >= 10) begin
        if (state != 1) begin errors = errors + 1; $display("FAIL: expected ACTIVE"); end
        if (dv) begin n_online = n_online + 1; if (tset != 5'b01000) begin errors = errors + 1; $display("FAIL: ACTIVE must run online test only"); end end
      end
      tick = 1; @(negedge clk); tick = 0;
    end
    if (n_online < 5 || n_online > 8) begin errors = errors + 1; $display("FAIL: online test frequency %0d", n_online); end
    for (t = 24; t < 40; t = t + 1) begin  // fault events on block 1 -> fault history -> DEGRADED
      ma = 1; rf = (t < 28) ? 5'b00010 : 5'b00000; step;
      if (state == 2 && first_deg < 0) first_deg = t;
      if (state == 2 && dv) begin n_deg = n_deg + 1; if (!(tset == 5'b10010 && dm[blk])) begin errors = errors + 1; $display("FAIL: DEGRADED decision"); end end
      tick = 1; @(negedge clk); tick = 0;
    end
    if (first_deg < 0 || first_deg > 30 || n_deg < 8) begin errors = errors + 1; $display("FAIL: DEGRADED not entered/sustained (first=%0d n=%0d)", first_deg, n_deg); end
    if (errors == 0) $display("tb_adaptive PASS (online decisions=%0d, first DEGRADED tick=%0d, degraded decisions=%0d)", n_online, first_deg, n_deg); else $display("tb_adaptive FAIL errors=%0d", errors);
    $finish;
  end
endmodule
