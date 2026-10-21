// RTL stuck-at injection mask generator.  One instance per (block, region).
// region 0 = block state bits, 1 = block primary inputs, 2 = block primary outputs.
// Concept: runtime flip-flop-level fault injection (cf. FIawase, Apache-2.0 - conceptual reference only; written independently).
module fi_mask #(parameter B = 0, parameter R = 0, parameter W = 8) (
  input  wire         en,
  input  wire [2:0]   blk,
  input  wire [1:0]   reg_sel,
  input  wire [7:0]   bit_idx,
  input  wire         val,
  output wire [W-1:0] m0,   // force-to-0 mask
  output wire [W-1:0] m1    // force-to-1 mask
);
  wire hit = en && (blk == B) && (reg_sel == R);
  wire [W-1:0] oh = hit ? ({{(W-1){1'b0}}, 1'b1} << bit_idx) : {W{1'b0}};
  assign m1 = val ? oh : {W{1'b0}};
  assign m0 = val ? {W{1'b0}} : oh;
endmodule
