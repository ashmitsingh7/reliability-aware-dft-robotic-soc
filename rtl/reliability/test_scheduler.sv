// Adaptive Test Scheduler (paper Algorithm 1) and fixed-schedule baseline (MODE input).
// tset bits: [0]=FULL_SCAN [1]=PARTIAL_SCAN [2]=MBIST [3]=ONLINE [4]=DIAG.  blk==7 means "all blocks" (baseline).
// reason: 0 none, 1 idle sweep, 2 active online argmax, 3 degraded flagged block, 4 baseline period, 5 degraded idle fairness,
//         6 (Step-3, OBS_EN&ESC_EN) degraded flagged block escalated to a FULL diagnostic, rate-limited by ESC_GAP.
module test_scheduler #(parameter ACTIVE_PERIOD = 2, SWEEP_GAP = 10, BASE_N = 20,
                        SWEEP_PERSIST = 0, STARVE_EN = 0, OVERDUE_T = 150, FAIR_GAP = 4,
                        OBS_EN = 0, ESC_EN = 0, ESC_GAP = 10, STALE_EN = 0) (
  input  wire clk, rst_n, tick, mode, mission_active,
  input  wire [1:0]  state_n,
  input  wire [79:0] prio,
  input  wire [4:0]  degmask_n, unres_n, nf_n,
  output reg         dec_valid,
  output reg  [2:0]  dec_blk,
  output reg  [4:0]  dec_tset,
  output reg  [2:0]  dec_reason,
  output reg         last_valid,
  output reg  [2:0]  last_blk,
  output reg         last_diag,
  output reg  [4:0]  last_tset,       // Step-3: test set of the previous (adaptive) decision, 0 if none
  // Step-1 next-state observation (post-tick values, same convention as the Python model's returned dict)
  output wire [4:0]  dbg_sweep, output wire [7:0] dbg_gap, dbg_fair, output wire [79:0] dbg_lastfull, output reg [4:0] dbg_overdue,
  output reg  [2:0]  dbg_fcause,    // Step-2A: fairness-slot decision cause recorded by the scheduler (see docs)
  output wire [7:0]  dbg_esc, output wire [4:0] dbg_lfstale   // Step-3 observation (post-tick values)
);
  reg [4:0] sweep, sweep_n, sweep_t; reg [7:0] gap, gap_n, ap, ap_n; reg [31:0] tcnt;
  reg [79:0] lastfull, lastfull_n; reg [7:0] fair, fair_n; reg [4:0] cand; integer k; reg [15:0] agek;
  reg [7:0] esc, esc_n; reg [4:0] lfs, lfs_n, lf_upd; reg [4:0] age_wrap;
  assign dbg_esc = esc_n; assign dbg_lfstale = lfs_n;
  assign dbg_sweep = sweep_n; assign dbg_gap = gap_n; assign dbg_fair = fair_n; assign dbg_lastfull = lastfull_n;
  function [2:0] argmax(input [79:0] pr, input [4:0] cand);
    integer i; reg [15:0] bp; reg found;
    begin
      argmax = 3'd0; found = 1'b0; bp = 16'd0;
      for (i = 0; i < 5; i = i + 1)
        if (cand[i]) begin
          if (!found || pr[16*i +: 16] > bp) begin argmax = i[2:0]; bp = pr[16*i +: 16]; found = 1'b1; end
        end
    end
  endfunction
  always @* begin
    dec_valid = 0; dec_blk = 0; dec_tset = 0; dec_reason = 0;
    sweep_n = sweep; gap_n = gap; ap_n = ap; sweep_t = sweep; lastfull_n = lastfull; fair_n = fair;
    dbg_fcause = 3'd0; esc_n = esc; lf_upd = 5'd0;
    // Step-2A: 16-bit MODULAR age (tcnt[15:0] - lastfull), identical to the Python model; v1 compared 32-bit tcnt against 16-bit lastfull (false 'overdue' after tick 65535)
    // Step-3 (STALE_EN=1): a per-block stale bit is set when the age reaches 0xFFFF and cleared by the next full scan, so the age can no longer alias below OVERDUE_T.
    for (k = 0; k < 5; k = k + 1) begin
      agek = tcnt[15:0] - lastfull[16*k +: 16]; dbg_overdue[k] = (agek >= OVERDUE_T) | (STALE_EN & lfs[k]); age_wrap[k] = (agek == 16'hFFFF);
    end
    if (mode) begin
      if (((tcnt + 1) % BASE_N) == 0) begin dec_valid = 1; dec_blk = 3'd7; dec_tset = 5'b00101; dec_reason = 3'd4; end
    end else if (state_n == 2'd0) begin
      ap_n = 0;
      if (sweep == 5'b11111) begin
        if (gap >= SWEEP_GAP) begin sweep_t = 0; gap_n = 0; end else gap_n = gap + 1;
      end
      if (sweep_t != 5'b11111) begin
        dec_blk = argmax(prio, ~sweep_t); dec_valid = 1; dec_reason = 3'd1;
        dec_tset = 5'b10001 | ((dec_blk == 3'd4) ? 5'b00100 : 5'b00000);
        sweep_t[dec_blk] = 1'b1; lastfull_n[16*dec_blk +: 16] = tcnt[15:0]; lf_upd[dec_blk] = 1'b1;
      end
      sweep_n = sweep_t;
    end else if (state_n == 2'd1) begin
      if (SWEEP_PERSIST) begin if (sweep == 5'b11111) begin sweep_n = 0; gap_n = SWEEP_GAP; end end
      else begin sweep_n = 0; gap_n = SWEEP_GAP; end
      if (ap == 0) begin dec_blk = argmax(prio, 5'b11111); dec_tset = 5'b01000; dec_valid = 1; dec_reason = 3'd2; ap_n = ACTIVE_PERIOD - 1; end
      else ap_n = ap - 1;
    end else begin
      if (SWEEP_PERSIST) begin if (sweep == 5'b11111) begin sweep_n = 0; gap_n = SWEEP_GAP; end end
      else begin sweep_n = 0; gap_n = SWEEP_GAP; end
      ap_n = 0;
      cand = dbg_overdue & ~degmask_n;
      if (mission_active) dbg_fcause = 3'd1;
      else if (!STARVE_EN) dbg_fcause = 3'd2;
      else if (fair < FAIR_GAP) dbg_fcause = 3'd3;
      else if (cand == 5'd0) dbg_fcause = 3'd5;
      else if ((degmask_n & unres_n) != 5'd0) dbg_fcause = 3'd4;
      else dbg_fcause = 3'd6;
      if (STARVE_EN && !mission_active && fair >= FAIR_GAP && ((degmask_n & unres_n) == 5'd0) && cand != 5'd0) begin
        dec_blk = argmax(prio, cand); dec_valid = 1; dec_reason = 3'd5; fair_n = 8'd0;
        dec_tset = 5'b10001 | ((dec_blk == 3'd4) ? 5'b00100 : 5'b00000);
        lastfull_n[16*dec_blk +: 16] = tcnt[15:0]; lf_upd[dec_blk] = 1'b1;
      end else begin
        fair_n = (fair == 8'd255) ? 8'd255 : fair + 8'd1; esc_n = (esc == 8'd255) ? 8'd255 : esc + 8'd1;
        if (degmask_n != 0) begin
          dec_blk = argmax(prio, degmask_n); dec_valid = 1;
          if (OBS_EN && ESC_EN && nf_n[dec_blk] && esc >= ESC_GAP) begin   // Step-3 escalation: partial scans cannot clear this evidence
            dec_tset = 5'b10001 | ((dec_blk == 3'd4) ? 5'b00100 : 5'b00000); dec_reason = 3'd6; esc_n = 8'd0;
            lastfull_n[16*dec_blk +: 16] = tcnt[15:0]; lf_upd[dec_blk] = 1'b1;
          end else begin dec_tset = 5'b10010; dec_reason = 3'd3; end
        end
      end
    end
  end
  integer kk;
  always @* begin lfs_n = lfs; for (kk = 0; kk < 5; kk = kk + 1) if (lf_upd[kk]) lfs_n[kk] = 1'b0; else if (STALE_EN && age_wrap[kk]) lfs_n[kk] = 1'b1; end
  always @(posedge clk) begin
    if (!rst_n) begin sweep <= 0; gap <= SWEEP_GAP; ap <= 0; tcnt <= 0; last_valid <= 0; last_blk <= 0; last_diag <= 0; last_tset <= 0; lastfull <= 0; fair <= 0; esc <= ESC_GAP; lfs <= 0; end
    else if (tick) begin
      sweep <= sweep_n; gap <= gap_n; ap <= ap_n; tcnt <= tcnt + 1;
      last_valid <= dec_valid & ~mode; last_blk <= dec_blk; last_diag <= dec_valid & dec_tset[4] & ~mode; last_tset <= (dec_valid & ~mode) ? dec_tset : 5'd0;
      lastfull <= lastfull_n; fair <= fair_n; esc <= esc_n; lfs <= lfs_n;
    end
  end
endmodule
