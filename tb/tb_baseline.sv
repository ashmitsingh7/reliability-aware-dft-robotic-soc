// Baseline (fixed periodic schedule) checks: FULL_SCAN+MBIST of ALL blocks exactly every BASE_N ticks, regardless of
// system state / health / mission.
`timescale 1ns/1ps
module tb_baseline;
  reg clk = 0, rst_n = 0, tick = 0, ma = 0; reg [39:0] act = 0, urg = 0; reg [4:0] rf = 0; always #5 clk = ~clk;
  wire [1:0] state; wire dv; wire [2:0] blk, reason; wire [4:0] tset, dm; wire [79:0] prio; wire [39:0] h, ag, fl;
  reliability_manager dut (.clk(clk), .rst_n(rst_n), .tick(tick), .mode(1'b1), .mission_active(ma), .act_in(act), .urg_in(urg), .res_fail(rf), .res_cls(20'd0),
    .weights(20'h11111), .state(state), .dec_valid(dv), .dec_blk(blk), .dec_tset(tset), .dec_reason(reason), .prio(prio), .health(h), .aging(ag), .faults(fl), .degmask(dm));
  integer t, errors = 0, ndec = 0; reg [31:0] r;
  initial begin
    repeat (3) @(negedge clk); rst_n = 1;
    for (t = 0; t < 100; t = t + 1) begin
      @(negedge clk); r = $random; ma = r[0]; act = {5{r[15:8]}}; urg = {5{r[23:16]}}; rf = r[28:24]; #1;
      if (((t + 1) % 20) == 0) begin
        if (!(dv && blk == 3'd7 && tset == 5'b00101 && reason == 3'd4)) begin errors = errors + 1; $display("FAIL: expected periodic decision at tick %0d", t); end
        ndec = ndec + 1;
      end else if (dv) begin errors = errors + 1; $display("FAIL: unexpected decision at tick %0d", t); end
      tick = 1; @(negedge clk); tick = 0;
    end
    if (ndec != 5) errors = errors + 1;
    if (errors == 0) $display("tb_baseline PASS (%0d periodic full-suite decisions, state-independent)", ndec); else $display("tb_baseline FAIL errors=%0d", errors);
    $finish;
  end
endmodule
