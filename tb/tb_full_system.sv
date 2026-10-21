// Integrated full-system test: robotic_soc (core + DFT engines + Reliability Manager + Test Controller) against a
// fault-free reference core (shadow for the online test).  Real scan/MBIST/online execution on RTL.
//  Phase A (fault-free): ACTIVE -> online tests only, no failures; then IDLE -> full suite on every block, all pass.
//  Phase B (RTL stuck-at injected in encoder state during ACTIVE): online test flags it -> fault history -> DEGRADED
//          -> partial scan on the encoder fails (confirmation).
// After every destructive (scan/MBIST) test the SoC pulses core_restore: functional core, reference core and stimulus re-initialise.
// Scheduler tick = EPOCH cycles (abstraction; full-system tick shortened vs the 20,000-cycle campaign tick so that sim is quick,
// but still longer than the longest test, see tb assertion).
`timescale 1ns/1ps
module tb_full_system;
  localparam EPOCH = 10000;
  reg clk = 0, rst_n = 0, run_en = 1; always #5 clk = ~clk;
  wire rxd, ea, eb, estop; wire [3:0] cur, rda;
  wire restore; wire core_rstn = rst_n & ~restore;
  stim_gen sg (.clk(clk), .rst_n(core_rstn), .run_en(run_en), .estop_en(1'b0), .rxd(rxd), .enc_a(ea), .enc_b(eb), .estop(estop), .cur(cur), .rd_addr(rda));
  reg [31:0] ecnt = 0; reg tick = 0;
  always @(posedge clk) begin if (!rst_n) begin ecnt <= 0; tick <= 0; end else begin ecnt <= (ecnt == EPOCH-1) ? 0 : ecnt + 1; tick <= (ecnt == EPOCH-2); end end
  reg fi_en = 0; reg [2:0] fi_blk = 0; reg [1:0] fi_reg = 0; reg [7:0] fi_bit = 0; reg fi_val = 0;
  wire [73:0] po_s, po_ref;
  robotic_soc_core ref_core (.clk(clk), .rst_n(core_rstn), .rxd(rxd), .enc_a(ea), .enc_b(eb), .estop(estop), .cur_sense(cur), .rd_addr(rda), .pwm(), .motor_en(), .brake(),
    .fsm_state(), .rdata(), .tm(5'd0), .scan_en(5'd0), .scan_in(5'd0), .scan_out(), .tpi(31'd0), .mb_en(1'b0), .mb_we(1'b0), .mb_addr(4'd0), .mb_wdata(8'd0),
    .po_flat(po_ref), .fi_en(1'b0), .fi_blk(3'd0), .fi_reg(2'd0), .fi_bit(8'd0), .fi_val(1'b0));
  wire [1:0] state; wire dv, tcb, tcd, tcf; wire [2:0] dblk, dreason, tcblk; wire [4:0] dtset, dm, rfq; wire [79:0] prio; wire [39:0] hl, ag, fl; wire [31:0] tcc;
  reg [39:0] urg = 0;
  robotic_soc soc (.clk(clk), .rst_n(rst_n), .rxd(rxd), .enc_a(ea), .enc_b(eb), .estop(estop), .cur_sense(cur), .rd_addr(rda), .pwm(), .motor_en(), .brake(), .fsm_state(), .rdata(),
    .tick(tick), .mode(1'b0), .urg_in(urg), .weights(20'h11111), .ref_po(po_ref), .po_flat(po_s),
    .fi_en(fi_en), .fi_blk(fi_blk), .fi_reg(fi_reg), .fi_bit(fi_bit), .fi_val(fi_val),
    .state(state), .dec_valid(dv), .dec_blk(dblk), .dec_tset(dtset), .dec_reason(dreason), .prio(prio), .health(hl), .aging(ag), .faults(fl), .degmask(dm),
    .core_restore(restore), .tc_busy(tcb), .tc_done(tcd), .tc_fail(tcf), .tc_blk(tcblk), .tc_cycles(tcc), .res_fail_q(rfq));
  integer errors = 0, tk = 0, fd, i; reg [4:0] last_ts; reg [2:0] last_bk; integer last_tick, max_cycles = 0;
  integer a_online = 0, a_full = 0, a_fail = 0, a_active = 0, a_idle = 0, b_online_fail = 0, b_deg = 0, b_partial_fail = 0, phase = 0, first_fail_tick = -1, first_deg_tick = -1, first_partial_fail_tick = -1;
  reg [4:0] a_full_seen = 0;
  initial begin fd = $fopen("results/rtl_full_system_log.csv", "w"); $fwrite(fd, "phase,tick,state,dec_valid,blk,tset,reason,prio0,prio1,prio2,prio3,prio4,tc_blk,tc_tset,tc_fail,tc_cycles\n"); end
  always @(posedge clk) if (rst_n) begin
    if (tick) begin
      tk = tk + 1;
      $fwrite(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,,,,\n", phase, tk, state, dv, dblk, dtset, dreason, prio[15:0], prio[31:16], prio[47:32], prio[63:48], prio[79:64]);
      if (dv) begin last_ts <= dtset; last_bk <= dblk; end
      if (state == 1) a_active = a_active + 1; if (state == 0) a_idle = a_idle + 1;
      if (tcb) begin errors = errors + 1; $display("FAIL: test still busy at next tick"); end
    end
    if (tcd) begin
      if (tcc > max_cycles) max_cycles = tcc;
      $fwrite(fd, "%0d,%0d,,,,,,,,,,,%0d,%0d,%0d,%0d\n", phase, tk, tcblk, last_ts, tcf, tcc);
      if (phase == 1) begin
        if (last_ts == 5'b01000) a_online = a_online + 1;
        if (last_ts[0]) begin a_full = a_full + 1; a_full_seen[tcblk] = 1; end
        if (tcf) a_fail = a_fail + 1;
      end else begin
        if (tcf && last_ts == 5'b01000) begin b_online_fail = b_online_fail + 1; if (first_fail_tick < 0) first_fail_tick = tk; $display("  [B] online test FAIL on block %0d at tick %0d", tcblk, tk); end
        if (tcf && last_ts[1]) begin b_partial_fail = b_partial_fail + 1; if (first_partial_fail_tick < 0) first_partial_fail_tick = tk; $display("  [B] partial scan FAIL on block %0d at tick %0d", tcblk, tk); end
      end
    end
    if (phase == 2 && state == 2 && first_deg_tick < 0) first_deg_tick = tk;
  end
  task do_reset; begin rst_n = 0; fi_en = 0; repeat (4) @(negedge clk); rst_n = 1; tk = 0; end endtask
  task wait_ticks(input integer n); integer q; begin for (q = 0; q < n; q = q + 1) begin @(posedge tick); end end endtask
  initial begin
    // ---------------- Phase A ----------------
    phase = 1; run_en = 1; urg = {5{8'd128}}; do_reset;
    wait_ticks(9);
    $display("Phase A (ACTIVE, fault-free): ticks in ACTIVE=%0d, online tests completed=%0d, failures=%0d", a_active, a_online, a_fail);
    if (a_online < 3 || a_fail != 0) begin errors = errors + 1; $display("FAIL: phase A ACTIVE"); end
    run_en = 0; urg = 0; a_online = 0; a_fail = 0;
    wait_ticks(14);
    $display("Phase A (IDLE, fault-free): ticks IDLE=%0d, full-scan decisions executed=%0d, blocks covered mask=%b, failures=%0d, longest test=%0d cycles", a_idle, a_full, a_full_seen, a_fail, max_cycles);
    if (a_full < 5 || a_full_seen != 5'b11111 || a_fail != 0) begin errors = errors + 1; $display("FAIL: phase A IDLE suite"); end
    // ---------------- Phase B ----------------
    phase = 2; run_en = 1; urg = {5{8'd128}}; do_reset;
    wait_ticks(3);
    fi_blk = 2; fi_reg = 0; fi_bit = 6; fi_val = 1; fi_en = 1;       // encoder state bit 6 (position[2]) stuck-at-1
    $display("Phase B: injected encoder state[6] SA1 at tick %0d", tk);
    wait_ticks(24);
    $display("Phase B: first online fail tick=%0d, first DEGRADED tick=%0d, first partial-scan fail tick=%0d (online fails=%0d, partial fails=%0d)", first_fail_tick, first_deg_tick, first_partial_fail_tick, b_online_fail, b_partial_fail);
    if (b_online_fail < 1) begin errors = errors + 1; $display("FAIL: online test never flagged injected fault"); end
    if (first_deg_tick < 0) begin errors = errors + 1; $display("FAIL: never entered DEGRADED"); end
    if (b_partial_fail < 1) begin errors = errors + 1; $display("FAIL: partial scan never confirmed fault"); end
    $fclose(fd);
    if (errors == 0) $display("tb_full_system PASS"); else $display("tb_full_system FAIL errors=%0d", errors);
    $finish;
  end
endmodule
