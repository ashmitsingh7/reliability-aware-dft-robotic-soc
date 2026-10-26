module nl_comm(input clk, input [1:0] pi, output [14:0] po, output [26:0] sq);
  comm_interface u(.clk(clk), .rst_n(1'b1), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(sq),
        .pi(pi), .po(po), .fi_s0(27'd0), .fi_s1(27'd0));
endmodule
