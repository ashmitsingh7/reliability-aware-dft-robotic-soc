// Test Controller: executes a Scheduler decision {blk, tset} on the DFT engines in a fixed order
// FULL -> PARTIAL -> MBIST -> ONLINE -> DIAG, collecting pass/fail and cycle counts.  blk==7 => all blocks (baseline).
module test_controller #(parameter DIAG_L0 = 9, DIAG_L1 = 24, DIAG_L2 = 31, DIAG_L3 = 27, DIAG_L4 = 128) (
  input  wire clk, rst_n,
  input  wire go, input wire [2:0] blk, input wire [4:0] tset,
  output reg  busy, output reg done, output reg fail, output reg [2:0] done_blk, output reg [31:0] cycles,
  // engines
  output reg  [4:0] scan_start, scan_partial, input wire [4:0] scan_done, scan_fail,
  output reg  mb_start, input wire mb_done, mb_fail,
  output reg  on_start, input wire on_done, on_fail,
  output wire [2:0] on_sel
);
  // phase: 0 idle,1 scan,2 mbist,3 online,4 diag,5 finish
  reg [2:0] ph; reg [2:0] cur; reg [4:0] ts; reg multi; reg [15:0] dcnt; reg started;
  assign on_sel = cur;
  function [15:0] dlen(input [2:0] b);
    case (b) 0: dlen = 2*DIAG_L0; 1: dlen = 2*DIAG_L1; 2: dlen = 2*DIAG_L2; 3: dlen = 2*DIAG_L3; default: dlen = 2*DIAG_L4; endcase
  endfunction
  always @(posedge clk) begin
    if (!rst_n) begin busy <= 0; done <= 0; fail <= 0; ph <= 0; scan_start <= 0; scan_partial <= 0; mb_start <= 0; on_start <= 0; cycles <= 0; done_blk <= 0; cur <= 0; ts <= 0; multi <= 0; started <= 0; dcnt <= 0; end
    else begin
      done <= 0; scan_start <= 0; mb_start <= 0; on_start <= 0;
      if (!busy) begin
        if (go) begin busy <= 1; fail <= 0; cycles <= 0; ts <= tset; multi <= (blk == 3'd7); cur <= (blk == 3'd7) ? 3'd0 : blk; ph <= 1; started <= 0; done_blk <= blk; end
      end else begin
        cycles <= cycles + 1;
        case (ph)
          3'd1: begin   // scan (FULL or PARTIAL)
            if (!(ts[0] | ts[1])) ph <= 3'd2;
            else if (!started) begin scan_start[cur] <= 1; scan_partial[cur] <= ~ts[0] & ts[1]; started <= 1; end
            else if (scan_done[cur]) begin fail <= fail | scan_fail[cur]; started <= 0;
              if (multi && cur != 3'd4) cur <= cur + 1; else begin ph <= 3'd2; if (multi) cur <= 3'd4; end end
          end
          3'd2: begin   // MBIST on register file
            if (!ts[2] || !(multi || cur == 3'd4)) ph <= 3'd3;
            else if (!started) begin mb_start <= 1; started <= 1; end
            else if (mb_done) begin fail <= fail | mb_fail; started <= 0; ph <= 3'd3; end
          end
          3'd3: begin   // online window
            if (!ts[3]) ph <= 3'd4;
            else if (!started) begin on_start <= 1; started <= 1; end
            else if (on_done) begin fail <= fail | on_fail; started <= 0; ph <= 3'd4; end
          end
          3'd4: begin   // diagnostics: scan-chain flush length (cycle accounting; flush data path exercised in tb_scan)
            if (!ts[4]) ph <= 3'd5;
            else if (!started) begin dcnt <= dlen(cur); started <= 1; end
            else if (dcnt == 0) begin started <= 0; ph <= 3'd5; end else dcnt <= dcnt - 1;
          end
          default: begin busy <= 0; done <= 1; ph <= 0; end
        endcase
      end
    end
  end
endmodule
