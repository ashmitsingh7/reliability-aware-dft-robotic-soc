module nl_motor(input clk, input [19:0] pi, output [9:0] po, output [23:0] sq);
  motor_controller u(.clk(clk), .rst_n(1'b1), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(sq),
        .pi(pi), .po(po), .fi_s0(24'd0), .fi_s1(24'd0));
endmodule
