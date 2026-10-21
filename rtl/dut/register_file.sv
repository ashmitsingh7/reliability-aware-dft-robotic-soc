// 16 x 8 register file / configuration memory with MBIST access mux.  Lowest criticality tier.
// pi: [3:0]=raddr [11:4]=wdata [15:12]=waddr [16]=we [24:17]=mb_wdata [28:25]=mb_addr [29]=mb_we [30]=mb_en
// po: [7:0]=rdata [15:8]=reg0 (speed setpoint) [23:16]=reg1 (config: bit0 run, bit1 clear, bit2 enc_clr)
module register_file (
  input  wire clk, rst_n, scan_en, scan_in,
  output wire scan_out,
  output wire [127:0] state_q,   // observation of FF outputs (netlist/debug); unconnected in the SoC
  input  wire [30:0]  pi,
  output wire [23:0]  po,
  input  wire [127:0] fi_s0, fi_s1
);
  localparam NS = 128;
  wire [NS-1:0] s_raw, s;
  assign s = (s_raw & ~fi_s0) | fi_s1;
  reg  [NS-1:0] n;
  wire mb_en = pi[30];
  wire        we_e = mb_en ? pi[29]    : pi[16];
  wire [3:0]  wa_e = mb_en ? pi[28:25] : pi[15:12];
  wire [7:0]  wd_e = mb_en ? pi[24:17] : pi[11:4];
  wire [3:0]  ra_e = mb_en ? pi[28:25] : pi[3:0];
  integer k;
  always_comb begin
    n = s;
    for (k = 0; k < 16; k = k + 1)
      if (we_e && (wa_e == k[3:0])) n[8*k +: 8] = wd_e;
  end
  scan_chain #(.N(NS)) u_sc (.clk(clk), .rst_n(rst_n), .scan_en(scan_en), .scan_in(scan_in),
                             .d(n), .q(s_raw), .scan_out(scan_out));
  assign po[7:0]   = s[8*ra_e +: 8];
  assign po[15:8]  = s[7:0];
  assign po[23:16] = s[15:8];
  assign state_q = s_raw;
endmodule
