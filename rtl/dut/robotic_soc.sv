// Integrated prototype: SoC core + DFT engines (scan/ATPG player, MBIST, online test, test controller)
// + Reliability Manager (State Monitor, Aging, Health, Priority, Scheduler) = paper Fig.1 stack.
// ref_po: outputs of a reference (shadow) copy of the core, supplied by the environment for the online test.
`include "../reliability/rel_refine_params.svh"
module robotic_soc #(parameter FAIR_UNRES_EN = FAIR_UNRES_EN_P) (
  input  wire clk, rst_n,
  input  wire rxd, enc_a, enc_b, estop,
  input  wire [3:0] cur_sense, rd_addr,
  output wire pwm, motor_en, brake, output wire [2:0] fsm_state, output wire [7:0] rdata,
  // reliability manager configuration / environment
  input  wire tick, mode,
  input  wire [39:0] urg_in, input wire [19:0] weights,
  input  wire [73:0] ref_po, output wire [73:0] po_flat,
  // fault injection
  input  wire fi_en, input wire [2:0] fi_blk, input wire [1:0] fi_reg, input wire [7:0] fi_bit, input wire fi_val,
  // observability
  output wire [1:0] state, output wire dec_valid, output wire [2:0] dec_blk, output wire [4:0] dec_tset, output wire [2:0] dec_reason,
  output wire [79:0] prio, output wire [39:0] health, aging, faults, output wire [4:0] degmask,
  output wire core_restore, output wire tc_busy, tc_done, tc_fail, tc_accepted, tc_overrun, output wire [2:0] tc_blk, output wire [31:0] tc_cycles, output wire [19:0] tc_cls, output wire [4:0] res_fail_q, output wire [19:0] res_cls_q
);
  wire [4:0] tm, scan_en, scan_in, scan_out, s_start, s_partial, s_busy, s_done, s_fail; wire [30:0] tpi;
  wire [31:0] c0, c1, c2, c3, c4;
  wire mb_start, mb_busy, mb_done, mb_fail, mb_en, mb_we; wire [3:0] mb_addr, mb_fa; wire [7:0] mb_wdata;
  wire on_start, on_busy, on_done, on_fail; wire [2:0] on_sel; wire [15:0] on_fm;
  // Scan/MBIST tests overwrite functional state (no save/restore hardware in this prototype).  ASSUMPTION: after a
  // destructive test the functional core is re-initialised (core-only reset); DFT engines and the Reliability Manager are not.
  reg restore_q; reg [4:0] cur_ts; assign core_restore = restore_q;
  wire core_rst_n = rst_n & ~restore_q;
  robotic_soc_core core (.clk(clk), .rst_n(core_rst_n), .rxd(rxd), .enc_a(enc_a), .enc_b(enc_b), .estop(estop), .cur_sense(cur_sense), .rd_addr(rd_addr),
      .pwm(pwm), .motor_en(motor_en), .brake(brake), .fsm_state(fsm_state), .rdata(rdata),
      .tm(tm), .scan_en(scan_en), .scan_in(scan_in), .scan_out(scan_out), .tpi(tpi),
      .mb_en(mb_en), .mb_we(mb_we), .mb_addr(mb_addr), .mb_wdata(mb_wdata), .po_flat(po_flat),
      .fi_en(fi_en), .fi_blk(fi_blk), .fi_reg(fi_reg), .fi_bit(fi_bit), .fi_val(fi_val));
  scan_test_bank bank (.clk(clk), .rst_n(rst_n), .start(s_start), .partial(s_partial), .busy(s_busy), .done(s_done), .fail(s_fail),
      .tm(tm), .scan_en(scan_en), .scan_in(scan_in), .tpi(tpi), .scan_out(scan_out), .po_flat(po_flat),
      .cycles0(c0), .cycles1(c1), .cycles2(c2), .cycles3(c3), .cycles4(c4));
  mbist_controller #(.AW(4), .DW(8)) mbist (.clk(clk), .rst_n(rst_n), .start(mb_start), .busy(mb_busy), .done(mb_done), .fail(mb_fail),
      .mem_en(mb_en), .mem_we(mb_we), .mem_addr(mb_addr), .mem_wdata(mb_wdata), .mem_rdata(rdata), .fail_addr(mb_fa));
  online_test #(.WINDOW(128)) onl (.clk(clk), .rst_n(rst_n), .start(on_start), .sel(on_sel), .dut_po(po_flat), .ref_po(ref_po),
      .busy(on_busy), .done(on_done), .fail(on_fail), .first_mismatch_cycle(on_fm));
  // reliability manager
  wire [39:0] act; reg [4:0] res_fail_r; reg [19:0] res_cls_r;
  activity_monitor #(.SHIFT(2)) am (.clk(clk), .rst_n(rst_n), .tick(tick), .po_flat(po_flat), .act(act));
  reliability_manager #(.FAIR_UNRES_EN(FAIR_UNRES_EN)) rm (.clk(clk), .rst_n(rst_n), .tick(tick), .mode(mode), .mission_active(motor_en), .act_in(act), .urg_in(urg_in),
      .res_fail(res_fail_r), .res_cls(res_cls_r), .weights(weights), .state(state), .dec_valid(dec_valid), .dec_blk(dec_blk), .dec_tset(dec_tset),
      .dec_reason(dec_reason), .prio(prio), .health(health), .aging(aging), .faults(faults), .degmask(degmask));
  test_controller tc (.clk(clk), .rst_n(rst_n), .go(tick & dec_valid), .blk(dec_blk), .tset(dec_tset), .busy(tc_busy), .done(tc_done), .accepted(tc_accepted), .overrun(tc_overrun), .done_cls(tc_cls),
      .fail(tc_fail), .done_blk(tc_blk), .cycles(tc_cycles), .scan_start(s_start), .scan_partial(s_partial), .scan_done(s_done), .scan_fail(s_fail),
      .mb_start(mb_start), .mb_done(mb_done), .mb_fail(mb_fail), .on_start(on_start), .on_done(on_done), .on_fail(on_fail), .on_sel(on_sel));
  // test result -> Health Manager (consumed at the next tick)
  assign res_fail_q = res_fail_r;
  always @(posedge clk) begin
    if (!rst_n) begin restore_q <= 0; cur_ts <= 0; end
    else begin
      if (tick & dec_valid) cur_ts <= dec_tset;
      restore_q <= tc_done & (cur_ts[0] | cur_ts[1] | cur_ts[2]);
    end
  end
  always @(posedge clk) begin
    if (!rst_n) begin res_fail_r <= 0; res_cls_r <= 0; end
    else begin
      if (tick) begin res_fail_r <= 0; res_cls_r <= 0; end
      if (tc_done) begin res_fail_r <= tc_fail ? ((tc_blk == 3'd7) ? 5'b11111 : (5'd1 << tc_blk)) : 5'd0; res_cls_r <= tc_cls; end
    end
  end
  assign res_cls_q = res_cls_r;
endmodule
