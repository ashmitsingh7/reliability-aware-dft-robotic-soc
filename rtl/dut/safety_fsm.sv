// Safety FSM.  Highest-criticality block.
// pi: [0]=estop [1]=overcur [2]=comm_fault [3]=enc_fault [4]=clear [5]=cmd_run
// po: [0]=motor_en [1]=brake [2]=in_stop [5:3]=state [8:6]=stop_cause
// state: 0 IDLE, 1 RUN, 2 WARN, 3 STOP, 4 RECOVER, 5..7 illegal -> STOP
module safety_fsm (
  input  wire clk, rst_n, scan_en, scan_in,
  output wire scan_out,
  output wire [8:0] state_q,   // observation of FF outputs (netlist/debug); unconnected in the SoC
  input  wire [5:0] pi,
  output wire [8:0] po,
  input  wire [8:0] fi_s0, fi_s1          // RTL fault-injection masks on state bits
);
  localparam NS = 9;
  wire [NS-1:0] s_raw, s;
  assign s = (s_raw & ~fi_s0) | fi_s1;
  reg  [NS-1:0] n;
  wire estop = pi[0], oc = pi[1], cf = pi[2], ef = pi[3], clr = pi[4], run = pi[5];
  wire hflt = estop | oc;
  wire sflt = cf | ef;
  wire [2:0] st = s[2:0];
  wire [2:0] wc = s[5:3];
  always_comb begin
    n = s;
    case (st)
      3'd0: begin
        if (hflt)              begin n[2:0] = 3'd3; n[8:6] = {oc, estop, sflt}; end
        else if (run && !sflt) n[2:0] = 3'd1;
      end
      3'd1: begin
        if (hflt)            begin n[2:0] = 3'd3; n[8:6] = {oc, estop, sflt}; end
        else if (sflt)       begin n[2:0] = 3'd2; n[5:3] = 3'd0; end
        else if (!run)       n[2:0] = 3'd0;
      end
      3'd2: begin
        n[5:3] = wc + 3'd1;
        if (hflt)            begin n[2:0] = 3'd3; n[8:6] = {oc, estop, sflt}; end
        else if (!sflt)      n[2:0] = 3'd1;
        else if (wc == 3'd7) begin n[2:0] = 3'd3; n[8:6] = {oc, estop, sflt}; end
      end
      3'd3: begin
        if (clr && !hflt)    n[2:0] = 3'd4;
      end
      3'd4: begin
        if (hflt)            begin n[2:0] = 3'd3; n[8:6] = {oc, estop, sflt}; end
        else                 n[2:0] = 3'd0;
      end
      default: n[2:0] = 3'd3;
    endcase
  end
  scan_chain #(.N(NS)) u_sc (.clk(clk), .rst_n(rst_n), .scan_en(scan_en), .scan_in(scan_in),
                             .d(n), .q(s_raw), .scan_out(scan_out));
  assign po[0] = (st == 3'd1) | (st == 3'd2);
  assign po[1] = (st == 3'd3) | (st == 3'd4) | (st[2] & (st[1] | st[0]));
  assign po[2] = (st == 3'd3);
  assign po[5:3] = st;
  assign po[8:6] = s[8:6];
  assign state_q = s_raw;
endmodule
