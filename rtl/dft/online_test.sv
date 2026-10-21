// Lightweight concurrent online test: time-multiplexed duplicate-and-compare ("shadow compare") of ONE selected
// block's primary outputs over a WINDOW-cycle interval, with mission operation uninterrupted (no scan, no stall).
// Needs a reference copy of the monitored block (ref_po) - its area is NOT included in this repo's synthesis numbers.
// Detects faults only if they propagate to block outputs during the window.
module online_test #(parameter WINDOW = 128) (
  input  wire clk, rst_n, start,
  input  wire [2:0]  sel,
  input  wire [73:0] dut_po, ref_po,
  output reg  busy, done, fail,
  output reg  [15:0] first_mismatch_cycle
);
  reg [15:0] cnt; reg [2:0] s;
  reg [73:0] mask;
  always @* begin
    case (s)
      3'd0: mask = 74'h1FF;
      3'd1: mask = 74'h1FF << 9;
      3'd2: mask = 74'hFFFF << 19;
      3'd3: mask = 74'h7FFF << 35;
      default: mask = 74'hFFFFFF << 50;
    endcase
  end
  wire mism = |((dut_po ^ ref_po) & mask);
  always @(posedge clk) begin
    if (!rst_n) begin busy <= 0; done <= 0; fail <= 0; cnt <= 0; s <= 0; first_mismatch_cycle <= 0; end
    else begin
      done <= 0;
      if (!busy) begin if (start) begin busy <= 1; cnt <= 0; fail <= 0; s <= sel; end end
      else begin
        if (mism && !fail) begin fail <= 1; first_mismatch_cycle <= cnt; end
        cnt <= cnt + 1;
        if (cnt == WINDOW-1) begin busy <= 0; done <= 1; end
      end
    end
  end
endmodule
