// Rule-based Health Manager: fault history (recent, decaying), staleness since last passing test,
// health term, fault term, degraded flags.  Does NOT make scheduling decisions.
// Step-1 (REC_EN=1): per-block sticky DEGRADED flag with evidence-based recovery (REC_N consecutive passing DIAG decisions)
// and re-entry hysteresis.  REC_EN=0 reproduces v1 exactly (degmask = unh >= DEG_TH).
module health_manager #(parameter FP = 32, FH_INC = 1, FH_DECAY = 64, STALE_K = 4, DEG_TH = 64,
                        REC_EN = 0, REC_N = 3, MARGIN = 16, EVID_EN = 0, ARISK_DEG = 0, OBS_EN = 0) (
  input  wire clk, rst_n, tick,
  input  wire [39:0] aging_n,
  input  wire [4:0]  res_fail,        // previous test on block b failed
  input  wire [19:0] res_cls,         // Step-3: per block 4-bit failing-test-class mask {ONLINE,MBIST,PARTIAL,FULL}; 0 = unknown (treated as needing FULL).  Used only if OBS_EN=1
  input  wire [4:0]  last_tset,       // Step-3: test set of the previous decision ([0]=FULL [1]=PARTIAL ...)
  input  wire        last_valid,
  input  wire        last_diag,       // previous decision included DIAG
  input  wire [2:0]  last_blk,
  output reg  [39:0] health_n,        // Health_i term of Eq.(2)
  output reg  [39:0] faults_n,        // Faults_i term of Eq.(2)
  output reg  [4:0]  degmask_n,
  output wire [4:0]  degmask_q,
  output reg  [4:0]  unres_n,         // unresolved-fault evidence (set by failed test, cleared only by a passing DIAG; OBS_EN=1: only by a passing DIAG whose depth dominates the failing test)
  output reg  [4:0]  nf_n,            // Step-3 (OBS_EN=1): outstanding evidence needs a FULL-depth diagnostic to be cleared (always 0 if OBS_EN=0)
  output reg  [39:0] okc_n, ack_n,    // consecutive passing DIAGs / unh at last clearance
  output reg  [4:0]  ackv_n,
  // Step-2A health-evidence separation (observation; EVID_EN=0 -> arisk_n still valid, dfault_n/aflag_n are 0)
  output reg  [4:0]  arisk_n,         // aging risk: (aging>>1) >= DEG_TH  (pure aging estimate, monotone)
  output reg  [4:0]  dfault_n,        // diagnostic-fault flag: set by a failed test, cleared by REC_N consecutive passing DIAGs
  output reg  [4:0]  aflag_n          // aging-risk escalation flag (ARISK_DEG=1 only): enters DEGRADED without fault evidence
);
  reg [39:0] fh, since, okc, ack; reg [4:0] ackv, dflag, aflag, unres, nf; reg [3:0] cls; reg need, dom; reg [7:0] dcnt; reg [4:0] dq; assign degmask_q = dq;
  reg [7:0] dcnt_n; reg decay; reg [39:0] fh_n, since_n;
  reg [15:0] f, s, a, fp, unh, stl, hl, thr, oc; reg [7:0] ackb; reg passb, df, af; reg [15:0] a2; integer b;
  always @* begin
    dcnt_n = dcnt + 8'd1; decay = (dcnt_n >= FH_DECAY); if (decay) dcnt_n = 8'd0;
    for (b = 0; b < 5; b = b + 1) begin
      f = {8'd0, fh[8*b +: 8]};
      if (decay && f > 0) f = f - 16'd1;
      if (res_fail[b]) f = (f + FH_INC > 255) ? 16'd255 : f + FH_INC;
      fh_n[8*b +: 8] = f[7:0];
      s = {8'd0, since[8*b +: 8]};
      if (last_valid && last_blk == b && !res_fail[b]) s = 16'd0; else s = (s + 1 > 255) ? 16'd255 : s + 1;
      since_n[8*b +: 8] = s[7:0];
      fp = f * FP; if (fp > 255) fp = 16'd255;
      a = {8'd0, aging_n[8*b +: 8]};
      unh = (a >> 1) + fp; if (unh > 255) unh = 16'd255;
      stl = s * STALE_K; if (stl > 255) stl = 16'd255;
      hl = unh + stl; if (hl > 255) hl = 16'd255;
      faults_n[8*b +: 8] = fp[7:0]; health_n[8*b +: 8] = hl[7:0];
      // ---- Step-1 evidence / flag logic
      passb = (last_valid && last_diag && last_blk == b && !res_fail[b]);
      oc = {8'd0, okc[8*b +: 8]}; ackb = ack[8*b +: 8];
      unres_n[b] = unres[b]; nf_n[b] = nf[b];
      cls = res_cls[4*b +: 4];
      need = ((cls & 4'b1101) != 4'd0);        // anything other than a PARTIAL-only failure needs FULL depth
      dom  = !OBS_EN || last_tset[0] || (!nf[b] && last_tset[1]); // a passing diagnostic dominates iff FULL, or PARTIAL while the evidence is PARTIAL-class
      if (res_fail[b]) begin oc = 16'd0; unres_n[b] = 1'b1; nf_n[b] = OBS_EN ? ((unres[b] ? nf[b] : 1'b0) | need) : 1'b0; end
      else if (passb && dom) begin oc = (oc + 1 > 255) ? 16'd255 : oc + 1; unres_n[b] = 1'b0; nf_n[b] = 1'b0; end
      ack_n[8*b +: 8] = ackb; ackv_n[b] = ackv[b];
      a2 = {1'b0, a[15:1]};
      arisk_n[b] = (a2 >= DEG_TH);
      dfault_n[b] = 1'b0; aflag_n[b] = 1'b0;
      if (EVID_EN) begin
        thr = ackv[b] ? ({8'd0, ackb} + MARGIN) : DEG_TH;
        if (thr < DEG_TH) thr = DEG_TH;
        df = dflag[b]; af = aflag[b];
        if (res_fail[b]) df = 1'b1;
        else if (df | af) begin
          if (oc >= REC_N) begin if (af) begin ack_n[8*b +: 8] = a2[7:0]; ackv_n[b] = 1'b1; end df = 1'b0; af = 1'b0; oc = 16'd0; end
        end else if (ARISK_DEG && a2 >= thr) begin af = 1'b1; oc = 16'd0; end
        dfault_n[b] = df; aflag_n[b] = af; degmask_n[b] = df | af;
      end else if (REC_EN) begin
        thr = ackv[b] ? (ackb + MARGIN) : DEG_TH;   // 16-bit, may exceed 255 (saturated block re-enters only on a new failure)
        if (thr < DEG_TH) thr = DEG_TH;
        df = dflag[b];
        if (res_fail[b]) df = 1'b1;
        else if (dflag[b]) begin
          if (oc >= REC_N) begin df = 1'b0; ack_n[8*b +: 8] = unh[7:0]; ackv_n[b] = 1'b1; oc = 16'd0; end
        end else if (unh >= thr) begin df = 1'b1; oc = 16'd0; end
        degmask_n[b] = df;
      end else begin
        df = dflag[b];
        degmask_n[b] = (unh >= DEG_TH);
      end
      okc_n[8*b +: 8] = oc[7:0];
    end
  end
  always @(posedge clk) begin
    if (!rst_n) begin fh <= 40'd0; since <= 40'd0; dcnt <= 8'd0; dq <= 5'd0; okc <= 40'd0; ack <= 40'd0; ackv <= 5'd0; dflag <= 5'd0; aflag <= 5'd0; unres <= 5'd0; nf <= 5'd0; end
    else if (tick) begin fh <= fh_n; since <= since_n; dcnt <= dcnt_n; dq <= degmask_n; okc <= okc_n; ack <= ack_n; ackv <= ackv_n;
                         dflag <= EVID_EN ? dfault_n : (REC_EN ? degmask_n : dflag); aflag <= aflag_n; unres <= unres_n; nf <= nf_n; end
  end
endmodule
