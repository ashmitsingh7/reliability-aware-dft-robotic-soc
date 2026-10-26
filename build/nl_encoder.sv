module nl_encoder(input clk, input [2:0] pi, output [15:0] po, output [30:0] sq);
  encoder_interface u(.clk(clk), .rst_n(1'b1), .scan_en(1'b0), .scan_in(1'b0), .scan_out(), .state_q(sq),
        .pi(pi), .po(po), .fi_s0(31'd0), .fi_s1(31'd0));
endmodule
