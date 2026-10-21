// Quadrature encoder interface.  High criticality.
// pi: [0]=a [1]=b [2]=clr
// po: [7:0]=position [13:8]=speed (steps per 32-cycle window) [14]=dir [15]=err (invalid transition)
module encoder_interface (
  input  wire clk, rst_n, scan_en, scan_in,
  output wire scan_out,
  output wire [30:0] state_q,   // observation of FF outputs (netlist/debug); unconnected in the SoC
  input  wire [2:0]  pi,
  output wire [15:0] po,
  input  wire [30:0] fi_s0, fi_s1
);
  localparam NS = 31;
  wire [NS-1:0] s_raw, s;
  assign s = (s_raw & ~fi_s0) | fi_s1;
  reg  [NS-1:0] n;
  // s[0]=a1 s[1]=b1 s[2]=a2 s[3]=b2 s[11:4]=pos s[16:12]=win s[22:17]=cnt s[28:23]=speed s[29]=dir s[30]=err
  wire a1 = s[0], b1 = s[1], a2 = s[2], b2 = s[3];
  wire [7:0] pos = s[11:4];
  wire [4:0] win = s[16:12];
  wire [5:0] cnt = s[22:17];
  wire [1:0] prev = {a2, b2};
  wire [1:0] cur  = {a1, b1};
  wire step  = (prev != cur);
  wire both  = (a1 ^ a2) & (b1 ^ b2);
  wire fwd   = ((prev == 2'b00) & (cur == 2'b01)) | ((prev == 2'b01) & (cur == 2'b11)) |
               ((prev == 2'b11) & (cur == 2'b10)) | ((prev == 2'b10) & (cur == 2'b00));
  wire valid = step & ~both;
  wire win_end = (win == 5'd31);
  always_comb begin
    n = s;
    n[0] = pi[0]; n[1] = pi[1]; n[2] = a1; n[3] = b1;
    if (pi[2]) n[11:4] = 8'd0;
    else if (valid & fwd)  n[11:4] = pos + 8'd1;
    else if (valid & ~fwd) n[11:4] = pos - 8'd1;
    n[16:12] = win + 5'd1;
    if (win_end) n[22:17] = 6'd0;
    else if (valid && cnt != 6'd63) n[22:17] = cnt + 6'd1;
    if (win_end) n[28:23] = cnt;
    if (valid) n[29] = fwd;
    if (pi[2]) n[30] = 1'b0; else n[30] = s[30] | both;
  end
  scan_chain #(.N(NS)) u_sc (.clk(clk), .rst_n(rst_n), .scan_en(scan_en), .scan_in(scan_in),
                             .d(n), .q(s_raw), .scan_out(scan_out));
  assign po[7:0]  = pos;
  assign po[13:8] = s[28:23];
  assign po[14]   = s[29];
  assign po[15]   = s[30];
  assign state_q = s_raw;
endmodule
