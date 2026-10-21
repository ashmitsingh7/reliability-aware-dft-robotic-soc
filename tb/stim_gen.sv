// Deterministic mission-like stimulus for the SoC core (shared by tb_fault_injection and tb_full_system).
// run_en=1: config frames keep reg1 run bit set; run_en=0: they clear it.
module stim_gen (input clk, rst_n, run_en, estop_en, output reg rxd, enc_a, enc_b, estop, output reg [3:0] cur, rd_addr);
  reg [15:0] lfsr; reg [5:0] cnt; reg [11:0] w; reg [15:0] fcnt, cyc; reg [1:0] g; reg dir; reg [1:0] hold;
  wire [15:0] nl = {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
  always @(posedge clk) begin
    if (!rst_n) begin lfsr <= 16'hACE1; cnt <= 0; rxd <= 1; fcnt <= 0; cyc <= 0; g <= 0; dir <= 1; hold <= 0; enc_a <= 0; enc_b <= 0; estop <= 0; cur <= 0; rd_addr <= 0; w <= 0; end
    else begin
      lfsr <= nl; cyc <= cyc + 1; rd_addr <= nl[7:4]; cur <= {1'b0, nl[2:0]} + 4'd1;
      cnt <= (cnt == 6'd29) ? 6'd0 : cnt + 6'd1;
      if (cnt == 0) begin
        rxd <= 0;
        if (fcnt == 0) w <= {4'd1, 7'd0, run_en};
        else if (fcnt == 1) w <= {4'd0, 8'h90};
        else if (nl[3:0] == 4'd1) w <= {4'd1, 7'd0, run_en};
        else if (nl[3:0] == 4'd0) w <= {4'd0, 1'b1, nl[10:4]};
        else w <= {nl[3:0], nl[11:4]};
        fcnt <= fcnt + 1;
      end else if (cnt <= 12) rxd <= w[12 - cnt];
      else rxd <= 1;
      if (hold == 0) begin
        if (nl[9:8] == 0) dir <= ~dir;
        g <= g + (dir ? 2'd1 : 2'd3);
        {enc_a, enc_b} <= (g == 0) ? 2'b00 : (g == 1) ? 2'b01 : (g == 2) ? 2'b11 : 2'b10;
        hold <= 1;
      end else hold <= hold - 1;
      estop <= estop_en && (cyc >= 520 && cyc < 523);
    end
  end
endmodule
