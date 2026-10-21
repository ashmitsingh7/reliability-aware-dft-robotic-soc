// Motor controller: setpoint ramp + proportional duty update + PWM + over-current detect.  High criticality.
// pi: [0]=en [1]=brake [9:2]=setpoint [15:10]=speed_meas [19:16]=cur_sense
// po: [0]=pwm [1]=overcur [9:2]=duty
module motor_controller (
  input  wire clk, rst_n, scan_en, scan_in,
  output wire scan_out,
  output wire [23:0] state_q,   // observation of FF outputs (netlist/debug); unconnected in the SoC
  input  wire [19:0] pi,
  output wire [9:0]  po,
  input  wire [23:0] fi_s0, fi_s1
);
  localparam NS = 24;
  wire [NS-1:0] s_raw, s;
  assign s = (s_raw & ~fi_s0) | fi_s1;
  reg  [NS-1:0] n;
  wire en = pi[0], brake = pi[1];
  wire [7:0] sp = pi[9:2];
  wire [7:0] tgt = {pi[15:10], 2'b00};
  wire [3:0] cur = pi[19:16];
  wire [7:0] duty = s[7:0], pcnt = s[15:8], ramp = s[23:16];
  wire run = en & ~brake;
  wire [7:0] up   = (ramp - tgt) >> 2;
  wire [7:0] down = (tgt - ramp) >> 2;
  wire [8:0] dsum = {1'b0, duty} + {1'b0, up};
  always_comb begin
    n = s;
    n[15:8] = pcnt + 8'd1;
    if (!en) n[23:16] = 8'd0;
    else if (ramp < sp) n[23:16] = ramp + 8'd1;
    else if (ramp > sp) n[23:16] = ramp - 8'd1;
    if (!run) n[7:0] = 8'd0;
    else if (ramp > tgt) n[7:0] = dsum[8] ? 8'hFF : dsum[7:0];
    else if (ramp < tgt) n[7:0] = (duty > down) ? (duty - down) : 8'd0;
  end
  scan_chain #(.N(NS)) u_sc (.clk(clk), .rst_n(rst_n), .scan_en(scan_en), .scan_in(scan_in),
                             .d(n), .q(s_raw), .scan_out(scan_out));
  assign po[0]   = (pcnt < duty) & run;
  assign po[1]   = (cur >= 4'd14);
  assign po[9:2] = duty;
  assign state_q = s_raw;
endmodule
