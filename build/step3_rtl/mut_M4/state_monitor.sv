// State Monitor: IDLE(0) / ACTIVE(1) / DEGRADED(2).  Observes DUT mission activity and Health-Manager degraded flags.
// state_n is the state for the current tick (combinational); `state` is the registered value.
module state_monitor #(parameter DEB = 2) (
  input  wire clk, rst_n, tick, mission_active, deg_any,
  output reg  [1:0] state_n,
  output reg  [1:0] state
);
  reg [3:0] dbc, dbc_n;
  reg [1:0] raw;
  always @* begin
    state_n = state; dbc_n = dbc; raw = mission_active ? 2'd1 : 2'd0;
    if (deg_any) begin state_n = 2'd2; dbc_n = 4'd0; end
    else if (state == 2'd2) begin state_n = raw; dbc_n = 4'd0; end
    else if (raw == state) dbc_n = 4'd0;
    else if (dbc + 4'd1 >= DEB) begin state_n = raw; dbc_n = 4'd0; end
    else dbc_n = dbc + 4'd1;
  end
  always @(posedge clk) begin
    if (!rst_n) begin state <= 2'd0; dbc <= 4'd0; end
    else if (tick) begin state <= state_n; dbc <= dbc_n; end
  end
endmodule
