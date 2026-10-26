module nl_safety(input clk, input [5:0] pi, output [8:0] po, output [8:0] sq);
  safety_fsm u(.clk(clk), .rst_n(1'b1), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(sq),
        .pi(pi), .po(po), .fi_s0(9'd0), .fi_s1(9'd0));
endmodule
