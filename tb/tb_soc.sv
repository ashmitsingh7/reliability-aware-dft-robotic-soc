// Functional self-checking testbench for the robotic SoC core (no DFT active).
`timescale 1ns/1ps
module tb_soc;
  reg clk = 0, rst_n = 0, rxd = 1, a = 0, b = 0, estop = 0; reg [3:0] cur = 0, rda = 0; always #5 clk = ~clk;
  wire pwm, men, brk; wire [2:0] st; wire [7:0] rdata; wire [73:0] po;
  robotic_soc_core core (.clk(clk), .rst_n(rst_n), .rxd(rxd), .enc_a(a), .enc_b(b), .estop(estop), .cur_sense(cur), .rd_addr(rda),
    .pwm(pwm), .motor_en(men), .brake(brk), .fsm_state(st), .rdata(rdata), .tm(5'd0), .scan_en(5'd0), .scan_in(5'd0), .scan_out(), .tpi(31'd0),
    .mb_en(1'b0), .mb_we(1'b0), .mb_addr(4'd0), .mb_wdata(8'd0), .po_flat(po), .fi_en(1'b0), .fi_blk(3'd0), .fi_reg(2'd0), .fi_bit(8'd0), .fi_val(1'b0));
  integer errors = 0, i, pwm_hi = 0; reg [1:0] gray [0:3]; integer gi = 0;
  task frame(input [3:0] addr, input [7:0] data);
    reg [11:0] w; integer j;
    begin w = {addr, data}; rxd = 0; @(negedge clk);
      for (j = 11; j >= 0; j = j - 1) begin rxd = w[j]; @(negedge clk); end
      rxd = 1; @(negedge clk); repeat (3) @(negedge clk); end
  endtask
  task chk(input cond, input [255:0] msg); begin if (!cond) begin errors = errors + 1; $display("FAIL: %0s (t=%0t state=%0d)", msg, $time, st); end end endtask
  task enc_steps(input integer n, input integer dir); integer q; begin
    for (q = 0; q < n; q = q + 1) begin gi = (gi + dir + 4) % 4; {a, b} = gray[gi]; repeat (2) @(negedge clk); end end endtask
  initial begin
    gray[0] = 2'b00; gray[1] = 2'b01; gray[2] = 2'b11; gray[3] = 2'b10;
    repeat (3) @(negedge clk); rst_n = 1; repeat (2) @(negedge clk);
    chk(st == 0 && !men, "reset state IDLE");
    frame(4'd0, 8'h80); frame(4'd1, 8'h01); frame(4'd5, 8'hA5);
    rda = 4'd5; #1 chk(rdata == 8'hA5, "register write/read via serial frame");
    rda = 4'd0; #1 chk(rdata == 8'h80, "setpoint register");
    repeat (5) @(negedge clk); chk(st == 1 && men, "RUN after cmd_run");
    for (i = 0; i < 600; i = i + 1) begin @(negedge clk); if (pwm) pwm_hi = pwm_hi + 1; if (i % 40 == 0) frame(4'd6, i[7:0]); end
    chk(pwm_hi > 0, "PWM active while running");
    enc_steps(10, 1); chk(core.po2[7:0] == 8'd10, "encoder counts forward 10 steps");
    enc_steps(4, -1); chk(core.po2[7:0] == 8'd6, "encoder counts backward 4 steps");
    cur = 4'd15; repeat (3) @(negedge clk); chk(st == 3 && brk && !men, "over-current -> STOP, brake, motor off"); cur = 0;
    frame(4'd1, 8'h03); repeat (6) @(negedge clk); frame(4'd1, 8'h01); repeat (6) @(negedge clk);
    chk(st == 1, "recovery STOP->RECOVER->IDLE->RUN");
    estop = 1; repeat (3) @(negedge clk); chk(st == 3, "estop -> STOP"); estop = 0;
    frame(4'd1, 8'h03); repeat (5) @(negedge clk); frame(4'd1, 8'h01); repeat (6) @(negedge clk); chk(st == 1, "recover after estop");
    repeat (70) @(negedge clk); chk(st == 2 || st == 3, "comm timeout -> WARN/STOP");
    if (errors == 0) $display("tb_soc PASS"); else $display("tb_soc FAIL errors=%0d", errors);
    $finish;
  end
endmodule
