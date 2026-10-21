// Reliability Manager = State Monitor + Aging Model + Health Manager + Priority Engine + Test Scheduler.
// One evaluation per `tick` (scheduler epoch).  Outputs are combinational for the current tick.
module reliability_manager (
  input  wire clk, rst_n, tick, mode,           // mode 0 = adaptive, 1 = fixed baseline
  input  wire mission_active,
  input  wire [39:0] act_in, urg_in,
  input  wire [4:0]  res_fail,
  input  wire [19:0] res_cls,           // Step-3: per-block failing-test-class mask {ONLINE,MBIST,PARTIAL,FULL} (ignored unless OBS_EN=1; tie to 0)
  input  wire [19:0] weights,
  output wire [1:0]  state,
  output wire        dec_valid,
  output wire [2:0]  dec_blk,
  output wire [4:0]  dec_tset,
  output wire [2:0]  dec_reason,
  output wire [79:0] prio,
  output wire [39:0] health, aging, faults,
  output wire [4:0]  degmask,
  // Step-1 debug/observation (unconnected in v1 testbenches)
  output wire [4:0]  dbg_unres, dbg_ackv, dbg_sweep, dbg_overdue, output wire [39:0] dbg_okc, dbg_ack,
  output wire [7:0]  dbg_gap, dbg_fair, output wire [79:0] dbg_lastfull,
  // Step-2A observation
  output wire [4:0]  dbg_arisk, dbg_dfault, dbg_aflag, output wire [2:0] dbg_fcause,
  // Step-3 observation
  output wire [4:0]  dbg_nf, dbg_lfstale, output wire [7:0] dbg_esc
);
  `include "rel_params.svh"
  `include "rel_refine_params.svh"
  wire [1:0] state_q; wire [4:0] degmask_q; wire last_valid, last_diag; wire [2:0] last_blk; wire [4:0] last_tset;
  state_monitor #(.DEB(DEB_P)) u_sm (.clk(clk), .rst_n(rst_n), .tick(tick), .mission_active(mission_active),
      .deg_any(|degmask_q), .state_n(state), .state(state_q));
  aging_model #(.RATE(RATE_P), .RSHIFT(RSHIFT_P)) u_ag (.clk(clk), .rst_n(rst_n), .tick(tick), .act(act_in), .aging_n(aging));
  health_manager #(.FP(FP_P), .FH_INC(FH_INC_P), .FH_DECAY(FH_DECAY_P), .STALE_K(STALE_K_P), .DEG_TH(DEG_TH_P),
      .REC_EN(REC_EN_P), .REC_N(REC_N_P), .MARGIN(MARGIN_P), .EVID_EN(EVID_EN_P), .ARISK_DEG(ARISK_DEG_P), .OBS_EN(OBS_EN_P)) u_hm (
      .clk(clk), .rst_n(rst_n), .tick(tick), .aging_n(aging), .res_fail(res_fail), .res_cls(res_cls), .last_tset(last_tset), .last_valid(last_valid), .last_diag(last_diag), .last_blk(last_blk), .nf_n(dbg_nf),
      .unres_n(dbg_unres), .okc_n(dbg_okc), .ack_n(dbg_ack), .ackv_n(dbg_ackv), .arisk_n(dbg_arisk), .dfault_n(dbg_dfault), .aflag_n(dbg_aflag),
      .health_n(health), .faults_n(faults), .degmask_n(degmask), .degmask_q(degmask_q));
  priority_engine #(.CRIT(CRIT_TERMS)) u_pe (.health(health), .aging(aging), .faults(faults), .urg(urg_in), .w(weights), .prio(prio));
  test_scheduler #(.ACTIVE_PERIOD(ACTIVE_PERIOD_P), .SWEEP_GAP(SWEEP_GAP_P), .BASE_N(BASE_N_P),
      .SWEEP_PERSIST(SWEEP_PERSIST_P), .STARVE_EN(STARVE_EN_P), .OVERDUE_T(OVERDUE_T_P), .FAIR_GAP(FAIR_GAP_P),
      .OBS_EN(OBS_EN_P), .ESC_EN(ESC_EN_P), .ESC_GAP(ESC_GAP_P), .STALE_EN(STALE_EN_P)) u_ts (
      .clk(clk), .rst_n(rst_n), .tick(tick), .mode(mode), .mission_active(mission_active), .state_n(state), .prio(prio), .degmask_n(degmask), .unres_n(dbg_unres), .nf_n(dbg_nf), .last_diag(last_diag), .last_tset(last_tset), .dbg_esc(dbg_esc), .dbg_lfstale(dbg_lfstale),
      .dbg_sweep(dbg_sweep), .dbg_gap(dbg_gap), .dbg_fair(dbg_fair), .dbg_lastfull(dbg_lastfull), .dbg_overdue(dbg_overdue), .dbg_fcause(dbg_fcause),
      .dec_valid(dec_valid), .dec_blk(dec_blk), .dec_tset(dec_tset), .dec_reason(dec_reason), .last_valid(last_valid), .last_blk(last_blk));
endmodule
