// Priority_i = w1*Crit_i + w2*Health_i + w3*Aging_i + w4*Faults_i + w5*Mission_i   (paper Eq. 2)
// Terms normalised to 0..255, weights 4-bit (runtime configurable).  Pure combinational.
module priority_engine #(parameter [39:0] CRIT = 40'd0) (
  input  wire [39:0] health, aging, faults, urg,
  input  wire [19:0] w,                 // {w5,w4,w3,w2,w1}
  output reg  [79:0] prio               // 5 x 16-bit
);
  integer b; reg [15:0] p;
  always @* begin
    for (b = 0; b < 5; b = b + 1) begin
      p = w[3:0]   * CRIT[8*b +: 8]   + w[7:4]   * health[8*b +: 8] + w[11:8] * aging[8*b +: 8] +
          w[15:12] * faults[8*b +: 8] + w[19:16] * urg[8*b +: 8];
      prio[16*b +: 16] = p;
    end
  end
endmodule
