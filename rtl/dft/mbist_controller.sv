// MBIST controller, March C- : {any(w0); up(r0,w1); up(r1,w0); down(r0,w1); down(r1,w0); any(r0)}  = 10N operations.
// Address generator (up/down counter), data generator (solid 0x00/0xFF), read/write sequencer, comparator, FSM.
// Written independently; algorithm reference: Happy251005/mbist-march-algorithms (no license file -> nothing copied).
module mbist_controller #(parameter AW = 4, parameter DW = 8) (
  input  wire clk, rst_n, start,
  output reg  busy, done, fail,
  output wire mem_en, mem_we,
  output wire [AW-1:0] mem_addr,
  output wire [DW-1:0] mem_wdata,
  input  wire [DW-1:0] mem_rdata,
  output reg  [AW-1:0] fail_addr
);
  localparam [AW-1:0] LAST = {AW{1'b1}};
  reg [2:0] ph; reg [AW-1:0] a; reg sub;
  wire down   = (ph == 3'd3) || (ph == 3'd4);
  wire is_wr  = (ph == 3'd0) || (sub == 1'b1);                    // phase 0: write only; others: sub0=read, sub1=write
  wire is_rd  = (ph != 3'd0) && (sub == 1'b0);
  wire one_op = (ph == 3'd0) || (ph == 3'd5);
  wire [DW-1:0] exp_rd = ((ph == 3'd2) || (ph == 3'd4)) ? {DW{1'b1}} : {DW{1'b0}};
  assign mem_wdata = ((ph == 3'd1) || (ph == 3'd3)) ? {DW{1'b1}} : {DW{1'b0}};
  assign mem_en = busy; assign mem_we = busy & is_wr; assign mem_addr = a;
  wire last_addr = down ? (a == 0) : (a == LAST);
  always @(posedge clk) begin
    if (!rst_n) begin busy <= 0; done <= 0; fail <= 0; ph <= 0; a <= 0; sub <= 0; fail_addr <= 0; end
    else begin
      done <= 1'b0;
      if (!busy) begin
        if (start) begin busy <= 1; fail <= 0; ph <= 0; a <= 0; sub <= 0; end
      end else begin
        if (is_rd && (mem_rdata != exp_rd)) begin if (!fail) fail_addr <= a; fail <= 1'b1; end
        if (one_op || sub) begin
          sub <= 1'b0;
          if (last_addr) begin
            if (ph == 3'd5) begin busy <= 0; done <= 1; end
            else begin ph <= ph + 3'd1; a <= ((ph + 3'd1) == 3'd3 || (ph + 3'd1) == 3'd4) ? LAST : {AW{1'b0}}; end
          end else a <= down ? a - 1'b1 : a + 1'b1;
        end else sub <= 1'b1;
      end
    end
  end
endmodule
