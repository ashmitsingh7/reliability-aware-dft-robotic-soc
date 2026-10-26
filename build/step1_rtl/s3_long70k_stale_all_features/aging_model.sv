// Behavioural aging abstraction - NOT a transistor-level NBTI/HCI/TDDB model.
// stress accumulates per-block switching activity; aging = min(255, stress*RATE >> RSHIFT).
module aging_model #(parameter RATE = 175, parameter RSHIFT = 16) (
  input  wire clk, rst_n, tick,
  input  wire [39:0] act,          // 5 x 8-bit activity (this tick)
  output reg  [39:0] aging_n       // aging scores including this tick's activity
);
  reg [119:0] stress;
  reg [23:0] sn; reg [47:0] prod; integer b;
  always @* begin
    for (b = 0; b < 5; b = b + 1) begin
      sn = stress[24*b +: 24] + {16'd0, act[8*b +: 8]};
      prod = {24'd0, sn} * RATE;
      prod = prod >> RSHIFT;
      aging_n[8*b +: 8] = (prod > 48'd255) ? 8'd255 : prod[7:0];
    end
  end
  always @(posedge clk) begin
    if (!rst_n) stress <= 120'd0;
    else if (tick) for (b = 0; b < 5; b = b + 1) stress[24*b +: 24] <= stress[24*b +: 24] + {16'd0, act[8*b +: 8]};
  end
endmodule

// DUT-derived activity: per-block output-toggle counts accumulated between ticks, quantised to 8 bits.
module activity_monitor #(parameter SHIFT = 2) (
  input  wire clk, rst_n, tick,
  input  wire [73:0] po_flat,
  output reg  [39:0] act
);
  reg [73:0] prev; reg [79:0] cnt; integer i, k; reg [15:0] c;
  function [4:0] pc(input [23:0] v); integer q; begin pc = 0; for (q = 0; q < 24; q = q + 1) pc = pc + v[q]; end endfunction
  wire [73:0] tg = po_flat ^ prev;
  always @(posedge clk) begin
    if (!rst_n) begin prev <= 0; cnt <= 0; act <= 0; end
    else begin
      prev <= po_flat;
      if (tick) begin
        for (i = 0; i < 5; i = i + 1) begin c = cnt[16*i +: 16] >> SHIFT; act[8*i +: 8] <= (c > 255) ? 8'd255 : c[7:0]; end
        cnt <= 0;
      end else begin
        cnt[15:0]   <= cnt[15:0]   + pc({15'd0, tg[8:0]});
        cnt[31:16]  <= cnt[31:16]  + pc({14'd0, tg[18:9]});
        cnt[47:32]  <= cnt[47:32]  + pc({8'd0,  tg[34:19]});
        cnt[63:48]  <= cnt[63:48]  + pc({9'd0,  tg[49:35]});
        cnt[79:64]  <= cnt[79:64]  + pc(tg[73:50]);
      end
    end
  end
endmodule
