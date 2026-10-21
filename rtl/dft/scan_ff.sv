// Scan flip-flop: functional D input or serial scan input (mux-D scan cell).
// Synchronous active-low reset.  Written independently; mux-D scan cell is textbook DFT
// (educational equivalents exist in dft-fundamentals / dft-scan-atpg - conceptual reference only).
module scan_ff (
  input  wire clk, rst_n, scan_en, si, d,
  output reg  q
);
  always @(posedge clk) begin
    if (!rst_n)        q <= 1'b0;
    else if (scan_en)  q <= si;
    else               q <= d;
  end
endmodule
