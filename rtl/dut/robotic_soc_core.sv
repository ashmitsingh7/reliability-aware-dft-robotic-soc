// Robotic controller SoC core: Safety FSM, Motor Controller, Encoder I/F, Comm I/F, Register File.
// Each block sits in an IEEE-1500-style test wrapper (input mux selecting functional vs test PI), has its own scan
// chain, and has RTL stuck-at injection hooks on state / PI / PO.  Block index order == criticality order.
module robotic_soc_core (
  input  wire clk, rst_n,
  // functional I/O
  input  wire rxd, enc_a, enc_b, estop,
  input  wire [3:0] cur_sense, rd_addr,
  output wire pwm, motor_en, brake,
  output wire [2:0] fsm_state,
  output wire [7:0] rdata,
  // test access
  input  wire [4:0] tm, scan_en, scan_in,
  output wire [4:0] scan_out,
  input  wire [30:0] tpi,
  input  wire mb_en, mb_we, input wire [3:0] mb_addr, input wire [7:0] mb_wdata,
  output wire [73:0] po_flat,
  // RTL fault injection (region 0=state 1=PI 2=PO)
  input  wire fi_en, input wire [2:0] fi_blk, input wire [1:0] fi_reg, input wire [7:0] fi_bit, input wire fi_val
);
  // block outputs (raw)
  wire [8:0] po0r; wire [9:0] po1r; wire [15:0] po2r; wire [14:0] po3r; wire [23:0] po4r;
  wire [8:0] po0; wire [9:0] po1; wire [15:0] po2; wire [14:0] po3; wire [23:0] po4;
  // functional connectivity
  wire [7:0] reg0 = po4[15:8], reg1 = po4[23:16];
  wire cfg_run = reg1[0], cfg_clr = reg1[1], cfg_encclr = reg1[2];
  wire wr_en = po3[0]; wire [11:0] sh = po3[12:1]; wire c_tof = po3[13];
  wire enc_err = po2[15]; wire [5:0] speed = po2[13:8];
  wire m_oc = po1[1];
  wire s_men = po0[0], s_brk = po0[1];
  wire [5:0]  f0 = {cfg_run, cfg_clr, enc_err, c_tof, m_oc, estop};
  wire [19:0] f1 = {cur_sense, speed, reg0, s_brk, s_men};
  wire [2:0]  f2 = {cfg_encclr, enc_b, enc_a};
  wire [1:0]  f3 = {1'b0, rxd};
  wire [30:0] f4 = {mb_en, mb_we, mb_addr, mb_wdata, wr_en, sh[11:8], sh[7:0], rd_addr};
  // wrapper muxes + PI injection
  wire [5:0] m0 = tm[0] ? tpi[5:0] : f0;   wire [19:0] m1 = tm[1] ? tpi[19:0] : f1;  wire [2:0] m2 = tm[2] ? tpi[2:0] : f2;
  wire [1:0] m3 = tm[3] ? tpi[1:0] : f3;   wire [30:0] m4 = tm[4] ? tpi[30:0] : f4;
  wire [5:0] pi0_0, pi0_1; wire [19:0] pi1_0, pi1_1; wire [2:0] pi2_0, pi2_1; wire [1:0] pi3_0, pi3_1; wire [30:0] pi4_0, pi4_1;
  fi_mask #(0,1,6)  mp0(fi_en,fi_blk,fi_reg,fi_bit,fi_val,pi0_0,pi0_1);  fi_mask #(1,1,20) mp1(fi_en,fi_blk,fi_reg,fi_bit,fi_val,pi1_0,pi1_1);
  fi_mask #(2,1,3)  mp2(fi_en,fi_blk,fi_reg,fi_bit,fi_val,pi2_0,pi2_1);  fi_mask #(3,1,2)  mp3(fi_en,fi_blk,fi_reg,fi_bit,fi_val,pi3_0,pi3_1);
  fi_mask #(4,1,31) mp4(fi_en,fi_blk,fi_reg,fi_bit,fi_val,pi4_0,pi4_1);
  wire [8:0] po0_0, po0_1; wire [9:0] po1_0, po1_1; wire [15:0] po2_0, po2_1; wire [14:0] po3_0, po3_1; wire [23:0] po4_0, po4_1;
  fi_mask #(0,2,9)  mo0(fi_en,fi_blk,fi_reg,fi_bit,fi_val,po0_0,po0_1);  fi_mask #(1,2,10) mo1(fi_en,fi_blk,fi_reg,fi_bit,fi_val,po1_0,po1_1);
  fi_mask #(2,2,16) mo2(fi_en,fi_blk,fi_reg,fi_bit,fi_val,po2_0,po2_1);  fi_mask #(3,2,15) mo3(fi_en,fi_blk,fi_reg,fi_bit,fi_val,po3_0,po3_1);
  fi_mask #(4,2,24) mo4(fi_en,fi_blk,fi_reg,fi_bit,fi_val,po4_0,po4_1);
  wire [8:0] s0_0, s0_1; wire [23:0] s1_0, s1_1; wire [30:0] s2_0, s2_1; wire [26:0] s3_0, s3_1; wire [127:0] s4_0, s4_1;
  fi_mask #(0,0,9)  ms0(fi_en,fi_blk,fi_reg,fi_bit,fi_val,s0_0,s0_1);    fi_mask #(1,0,24) ms1(fi_en,fi_blk,fi_reg,fi_bit,fi_val,s1_0,s1_1);
  fi_mask #(2,0,31) ms2(fi_en,fi_blk,fi_reg,fi_bit,fi_val,s2_0,s2_1);    fi_mask #(3,0,27) ms3(fi_en,fi_blk,fi_reg,fi_bit,fi_val,s3_0,s3_1);
  fi_mask #(4,0,128) ms4(fi_en,fi_blk,fi_reg,fi_bit,fi_val,s4_0,s4_1);
  safety_fsm        u0 (.clk(clk),.rst_n(rst_n),.scan_en(scan_en[0]),.scan_in(scan_in[0]),.scan_out(scan_out[0]),.state_q(),.pi((m0&~pi0_0)|pi0_1),.po(po0r),.fi_s0(s0_0),.fi_s1(s0_1));
  motor_controller  u1 (.clk(clk),.rst_n(rst_n),.scan_en(scan_en[1]),.scan_in(scan_in[1]),.scan_out(scan_out[1]),.state_q(),.pi((m1&~pi1_0)|pi1_1),.po(po1r),.fi_s0(s1_0),.fi_s1(s1_1));
  encoder_interface u2 (.clk(clk),.rst_n(rst_n),.scan_en(scan_en[2]),.scan_in(scan_in[2]),.scan_out(scan_out[2]),.state_q(),.pi((m2&~pi2_0)|pi2_1),.po(po2r),.fi_s0(s2_0),.fi_s1(s2_1));
  comm_interface    u3 (.clk(clk),.rst_n(rst_n),.scan_en(scan_en[3]),.scan_in(scan_in[3]),.scan_out(scan_out[3]),.state_q(),.pi((m3&~pi3_0)|pi3_1),.po(po3r),.fi_s0(s3_0),.fi_s1(s3_1));
  register_file     u4 (.clk(clk),.rst_n(rst_n),.scan_en(scan_en[4]),.scan_in(scan_in[4]),.scan_out(scan_out[4]),.state_q(),.pi((m4&~pi4_0)|pi4_1),.po(po4r),.fi_s0(s4_0),.fi_s1(s4_1));
  assign po0 = (po0r & ~po0_0) | po0_1; assign po1 = (po1r & ~po1_0) | po1_1; assign po2 = (po2r & ~po2_0) | po2_1;
  assign po3 = (po3r & ~po3_0) | po3_1; assign po4 = (po4r & ~po4_0) | po4_1;
  assign po_flat = {po4, po3, po2, po1, po0};
  assign pwm = po1[0]; assign motor_en = s_men; assign brake = s_brk; assign fsm_state = po0[5:3]; assign rdata = po4[7:0];
endmodule
