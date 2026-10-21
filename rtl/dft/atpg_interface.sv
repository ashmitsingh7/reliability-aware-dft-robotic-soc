// On-chip scan pattern player ("ATPG interface"): applies ATPG-generated patterns (ROM produced by python/atpg.py)
// through a block's scan chain and compares captured responses.  Cycle count = P*(L+1)+L.
// ROM word = {exp_po[NO], exp_state[L], pi[NPI], state[L]}.
module atpg_interface #(parameter L = 9, NPI = 6, NO = 9, NP = 13, parameter ROMFILE = "results/rom/safety.mem") (
  input  wire clk, rst_n, start,
  input  wire [15:0] n_pat,
  output reg  busy, done, fail,
  output wire scan_en, scan_in,
  output wire [NPI-1:0] tpi,
  input  wire scan_out,
  input  wire [NO-1:0] po_obs,
  output reg  [31:0] cycles
);
  localparam W = 2*L + NPI + NO;
  reg [W-1:0] rom [0:NP-1];
  initial $readmemh(ROMFILE, rom);
  reg [1:0] st; reg [15:0] k, np; reg [15:0] j;       // st: 0 idle, 1 shift, 2 capture
  wire [W-1:0] cw = (k < np) ? rom[k] : {W{1'b0}};
  wire [W-1:0] pw = (k > 0) ? rom[k-1] : {W{1'b0}};
  wire [L-1:0] c_state = cw[L-1:0];
  wire [NPI-1:0] c_pi  = cw[L+NPI-1:L];
  wire [L-1:0] p_exp   = pw[2*L+NPI-1:L+NPI];
  wire [NO-1:0] c_expo = cw[2*L+NPI+NO-1:2*L+NPI];
  assign scan_en = busy & (st == 2'd1);
  assign scan_in = (st == 2'd1) ? c_state[L-1-j] : 1'b0;
  assign tpi = c_pi;
  always @(posedge clk) begin
    if (!rst_n) begin busy <= 0; done <= 0; fail <= 0; st <= 0; k <= 0; j <= 0; np <= 0; cycles <= 0; end
    else begin
      done <= 0;
      if (!busy) begin
        if (start) begin busy <= 1; fail <= 0; st <= 1; k <= 0; j <= 0; np <= n_pat; cycles <= 0; end
      end else begin
        cycles <= cycles + 1;
        if (st == 2'd1) begin
          if (k > 0 && scan_out !== p_exp[L-1-j]) fail <= 1'b1;
          if (j == L-1) begin
            j <= 0;
            if (k >= np) begin busy <= 0; done <= 1; st <= 0; end else st <= 2'd2;
          end else j <= j + 1;
        end else begin                                     // capture cycle: PI applied, PO sampled before capture edge
          if (po_obs !== c_expo) fail <= 1'b1;
          k <= k + 1; st <= 2'd1;
        end
      end
    end
  end
endmodule

// Bank of five pattern players (one per block) wired to the core's per-block wrapper/scan ports.
module scan_test_bank (
  input  wire clk, rst_n,
  input  wire [4:0] start, partial,
  output wire [4:0] busy, done, fail,
  output wire [4:0] tm, scan_en, scan_in,
  output wire [30:0] tpi,
  input  wire [4:0] scan_out,
  input  wire [73:0] po_flat,
  output wire [31:0] cycles0, cycles1, cycles2, cycles3, cycles4
);
  `include "dft_params.svh"
  wire [30:0] t0, t1, t2, t3, t4; wire [5:0] x0; wire [19:0] x1; wire [2:0] x2; wire [1:0] x3; wire [30:0] x4;
  atpg_interface #(.L(9),   .NPI(6),  .NO(9),  .NP(NP0), .ROMFILE("results/rom/safety.mem"))  u0 (clk, rst_n, start[0], partial[0] ? NPP0[15:0] : NP0[15:0], busy[0], done[0], fail[0], scan_en[0], scan_in[0], x0, scan_out[0], po_flat[8:0],   cycles0);
  atpg_interface #(.L(24),  .NPI(20), .NO(10), .NP(NP1), .ROMFILE("results/rom/motor.mem"))   u1 (clk, rst_n, start[1], partial[1] ? NPP1[15:0] : NP1[15:0], busy[1], done[1], fail[1], scan_en[1], scan_in[1], x1, scan_out[1], po_flat[18:9],  cycles1);
  atpg_interface #(.L(31),  .NPI(3),  .NO(16), .NP(NP2), .ROMFILE("results/rom/encoder.mem")) u2 (clk, rst_n, start[2], partial[2] ? NPP2[15:0] : NP2[15:0], busy[2], done[2], fail[2], scan_en[2], scan_in[2], x2, scan_out[2], po_flat[34:19], cycles2);
  atpg_interface #(.L(27),  .NPI(2),  .NO(15), .NP(NP3), .ROMFILE("results/rom/comm.mem"))    u3 (clk, rst_n, start[3], partial[3] ? NPP3[15:0] : NP3[15:0], busy[3], done[3], fail[3], scan_en[3], scan_in[3], x3, scan_out[3], po_flat[49:35], cycles3);
  atpg_interface #(.L(128), .NPI(31), .NO(24), .NP(NP4), .ROMFILE("results/rom/regfile.mem")) u4 (clk, rst_n, start[4], partial[4] ? NPP4[15:0] : NP4[15:0], busy[4], done[4], fail[4], scan_en[4], scan_in[4], x4, scan_out[4], po_flat[73:50], cycles4);
  assign tm = busy;
  assign tpi = ({25'd0, x0} & {31{busy[0]}}) | ({11'd0, x1} & {31{busy[1]}}) | ({28'd0, x2} & {31{busy[2]}}) |
               ({29'd0, x3} & {31{busy[3]}}) | (x4 & {31{busy[4]}});
endmodule
