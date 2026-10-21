// Step-1 trace testbench: like tb_scheduler.sv (untouched) but also dumps the Step-1 internal state every tick and
// supports a mid-run synchronous reset (+rst_at=<tick>).  +trace=<mem> +out=<csv> +mode=<0|1> +ticks=<n>
// Columns: tick,state,valid,blk,tset,reason,degmask, prio[5],health[5],aging[5],faults[5],
//          unres,okc[5],ackv,ack[5],sweep,gap,fair,lastfull[5],overdue,arisk,dfault,aflag,fcause,nf,esc,lfstale   (all post-tick values, same as the Python dict)
// Trace word: bit0 mission_active, [40:1] act, [80:41] urg, [85:81] res_fail, [105:86] res_cls (4 bits/block)
`timescale 1ns/1ps
module tb_scheduler_step1;
  reg clk = 0, rst_n = 0, tick = 0, mode = 0, mission_active = 0; reg [39:0] act = 0, urg = 0; reg [4:0] res_fail = 0; reg [19:0] res_cls = 0;
  wire [1:0] state; wire dv; wire [2:0] blk, reason; wire [4:0] tset, degmask; wire [79:0] prio; wire [39:0] health, aging, faults;
  wire [4:0] d_unres, d_ackv, d_sweep, d_overdue; wire [39:0] d_okc, d_ack; wire [7:0] d_gap, d_fair; wire [79:0] d_lf; wire [4:0] d_arisk, d_dfault, d_aflag; wire [2:0] d_fcause; wire [4:0] d_nf, d_lfs; wire [7:0] d_esc;
  reliability_manager dut(.clk(clk), .rst_n(rst_n), .tick(tick), .mode(mode), .mission_active(mission_active), .act_in(act), .urg_in(urg),
     .res_fail(res_fail), .res_cls(res_cls), .weights({4'd1,4'd1,4'd1,4'd1,4'd1}), .state(state), .dec_valid(dv), .dec_blk(blk), .dec_tset(tset),
     .dec_reason(reason), .prio(prio), .health(health), .aging(aging), .faults(faults), .degmask(degmask),
     .dbg_unres(d_unres), .dbg_ackv(d_ackv), .dbg_sweep(d_sweep), .dbg_overdue(d_overdue), .dbg_okc(d_okc), .dbg_ack(d_ack),
     .dbg_gap(d_gap), .dbg_fair(d_fair), .dbg_lastfull(d_lf),
     .dbg_arisk(d_arisk), .dbg_dfault(d_dfault), .dbg_aflag(d_aflag), .dbg_fcause(d_fcause), .dbg_nf(d_nf), .dbg_lfstale(d_lfs), .dbg_esc(d_esc));
  always #5 clk = ~clk;
  reg [111:0] mem [0:131071]; reg [1023:0] tracef, outf; integer n, t, fd, m, rst_at, i;
  initial begin
    if (!$value$plusargs("trace=%s", tracef)) tracef = "results/mission_trace.mem";
    if (!$value$plusargs("out=%s", outf)) outf = "build/rtl_step1.csv";
    if (!$value$plusargs("mode=%d", m)) m = 0;
    if (!$value$plusargs("ticks=%d", n)) n = 600;
    if (!$value$plusargs("rst_at=%d", rst_at)) rst_at = -1;
    mode = m[0]; $readmemh(tracef, mem); fd = $fopen(outf, "w");
    repeat (3) @(negedge clk); rst_n = 1;
    for (t = 0; t < n; t = t + 1) begin
      @(negedge clk);
      if (t == rst_at) begin rst_n = 0; @(negedge clk); @(negedge clk); rst_n = 1; @(negedge clk); end
      mission_active = mem[t][0]; act = mem[t][40:1]; urg = mem[t][80:41]; res_fail = mem[t][85:81]; res_cls = mem[t][105:86];
      #1;
      $fwrite(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d", t, state, dv, blk, tset, reason, degmask);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", prio[16*i +: 16]);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", health[8*i +: 8]);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", aging[8*i +: 8]);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", faults[8*i +: 8]);
      $fwrite(fd, ",%0d", d_unres);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", d_okc[8*i +: 8]);
      $fwrite(fd, ",%0d", d_ackv);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", d_ack[8*i +: 8]);
      $fwrite(fd, ",%0d,%0d,%0d", d_sweep, d_gap, d_fair);
      for (i = 0; i < 5; i = i + 1) $fwrite(fd, ",%0d", d_lf[16*i +: 16]);
      $fwrite(fd, ",%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n", d_overdue, d_arisk, d_dfault, d_aflag, d_fcause, d_nf, d_esc, d_lfs);
      tick = 1; @(negedge clk); tick = 0;
    end
    $fclose(fd); $display("tb_scheduler_step1 done (%0d ticks, mode=%0d)", n, mode); $finish;
  end
endmodule
