// Trace-driven Reliability Manager testbench.  +trace=<mem> +out=<csv> +mode=<0|1> +ticks=<n>.
// Dumps every tick's decision; python/check_rtl_equiv.py compares the dump with the Python reference model.
// Also asserts the Algorithm-1 rules (state -> permitted test types) on every decision.
`timescale 1ns/1ps
module tb_scheduler;
  reg clk = 0, rst_n = 0, tick = 0, mode = 0, mission_active = 0; reg [39:0] act = 0, urg = 0; reg [4:0] res_fail = 0;
  wire [1:0] state; wire dv; wire [2:0] blk, reason; wire [4:0] tset, degmask; wire [79:0] prio; wire [39:0] health, aging, faults;
  reliability_manager dut(.clk(clk), .rst_n(rst_n), .tick(tick), .mode(mode), .mission_active(mission_active), .act_in(act), .urg_in(urg),
     .res_fail(res_fail), .res_cls(20'd0), .weights({4'd1,4'd1,4'd1,4'd1,4'd1}), .state(state), .dec_valid(dv), .dec_blk(blk), .dec_tset(tset),
     .dec_reason(reason), .prio(prio), .health(health), .aging(aging), .faults(faults), .degmask(degmask));
  always #5 clk = ~clk;
  reg [87:0] mem [0:4095]; reg [1023:0] tracef, outf; integer n, t, fd, m, errors = 0, i;
  initial begin
    if (!$value$plusargs("trace=%s", tracef)) tracef = "results/mission_trace.mem";
    if (!$value$plusargs("out=%s", outf)) outf = "build/rtl_decisions.csv";
    if (!$value$plusargs("mode=%d", m)) m = 0;
    if (!$value$plusargs("ticks=%d", n)) n = 600;
    mode = m[0]; $readmemh(tracef, mem); fd = $fopen(outf, "w");
    repeat (3) @(negedge clk); rst_n = 1;
    for (t = 0; t < n; t = t + 1) begin
      @(negedge clk);
      mission_active = mem[t][0]; act = mem[t][40:1]; urg = mem[t][80:41]; res_fail = mem[t][85:81];
      #1;
      $fwrite(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d", t, state, dv, blk, tset, reason, degmask);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", prio[16*i +: 16]);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", health[8*i +: 8]);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", aging[8*i +: 8]);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", faults[8*i +: 8]);
      $fwrite(fd, "\n");
      if (!mode && dv) begin   // Algorithm-1 rule checks
        if (state == 0 && !(tset[0] && tset[4] && !tset[3] && !tset[1])) errors = errors + 1;
        if (state == 1 && tset != 5'b01000) errors = errors + 1;
        if (state == 2 && tset != 5'b10010) errors = errors + 1;
        if (state == 2 && !degmask[blk]) errors = errors + 1;
      end
      tick = 1; @(negedge clk); tick = 0;
    end
    $fclose(fd);
    if (errors == 0) $display("tb_scheduler PASS (%0d ticks, mode=%0d)", n, mode); else $display("tb_scheduler FAIL errors=%0d", errors);
    $finish;
  end
endmodule
