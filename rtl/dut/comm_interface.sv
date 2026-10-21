// Serial command receiver.  Frame: start(0), 12 data bits {addr[3:0],data[7:0]} MSB first, stop(1).
// Medium criticality.
// pi: [0]=rxd [1]=clr
// po: [0]=wr_en (1-cycle pulse) [12:1]=shift reg {addr,data} [13]=timeout [14]=frame_err
module comm_interface (
  input  wire clk, rst_n, scan_en, scan_in,
  output wire scan_out,
  output wire [26:0] state_q,   // observation of FF outputs (netlist/debug); unconnected in the SoC
  input  wire [1:0]  pi,
  output wire [14:0] po,
  input  wire [26:0] fi_s0, fi_s1
);
  localparam NS = 27;
  wire [NS-1:0] s_raw, s;
  assign s = (s_raw & ~fi_s0) | fi_s1;
  reg  [NS-1:0] n;
  // s[1:0]=st s[5:2]=cnt s[17:6]=sh s[23:18]=to s[24]=wr s[25]=tof s[26]=ferr
  wire [1:0]  st = s[1:0];
  wire [3:0]  cnt = s[5:2];
  wire [11:0] sh = s[17:6];
  wire [5:0]  tmo = s[23:18];
  wire rxd = pi[0], clr = pi[1];
  wire wr_n = (st == 2'd2) & rxd;
  wire [5:0] to_n = wr_n ? 6'd0 : ((tmo == 6'd63) ? 6'd63 : tmo + 6'd1);
  always_comb begin
    n = s;
    n[24] = wr_n;
    n[23:18] = to_n;
    n[25] = (to_n == 6'd63);
    n[26] = clr ? 1'b0 : (s[26] | ((st == 2'd2) & ~rxd));
    case (st)
      2'd0: if (!rxd) begin n[1:0] = 2'd1; n[5:2] = 4'd0; end
      2'd1: begin
        n[17:6] = {sh[10:0], rxd};
        if (cnt == 4'd11) n[1:0] = 2'd2; else n[5:2] = cnt + 4'd1;
      end
      2'd2: n[1:0] = 2'd0;
      default: n[1:0] = 2'd0;
    endcase
  end
  scan_chain #(.N(NS)) u_sc (.clk(clk), .rst_n(rst_n), .scan_en(scan_en), .scan_in(scan_in),
                             .d(n), .q(s_raw), .scan_out(scan_out));
  assign po[0]    = s[24];
  assign po[12:1] = sh;
  assign po[13]   = s[25];
  assign po[14]   = s[26];
  assign state_q = s_raw;
endmodule
