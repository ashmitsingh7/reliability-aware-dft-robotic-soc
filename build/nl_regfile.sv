module nl_regfile(input clk, input [30:0] pi, output [23:0] po, output [127:0] sq);
  register_file u(.clk(clk), .rst_n(1'b1), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(sq),
        .pi(pi), .po(po), .fi_s0(128'd0), .fi_s1(128'd0));
endmodule
