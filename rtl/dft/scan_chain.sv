// N-bit scan register.  q[0] is nearest scan_in, q[N-1] drives scan_out.
// Loading state vector S: shift S[N-1] first ... S[0] last (MSB first).
module scan_chain #(parameter N = 8) (
  input  wire         clk, rst_n, scan_en, scan_in,
  input  wire [N-1:0] d,
  output wire [N-1:0] q,
  output wire         scan_out
);
  genvar i;
  generate
    for (i = 0; i < N; i = i + 1) begin : g_ff
      wire si_w;
      if (i == 0) begin : g_first
        assign si_w = scan_in;
      end else begin : g_rest
        assign si_w = q[i-1];
      end
      scan_ff u_ff (.clk(clk), .rst_n(rst_n), .scan_en(scan_en), .si(si_w), .d(d[i]), .q(q[i]));
    end
  endgenerate
  assign scan_out = q[N-1];
endmodule
