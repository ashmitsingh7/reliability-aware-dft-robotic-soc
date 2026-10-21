# RTL module reference
| Module | File | Role |
|---|---|---|
| scan_ff / scan_chain | rtl/dft | mux-D scan cell; N-bit chain (q[N-1] -> scan_out, MSB-first load) |
| safety_fsm | rtl/dut | IDLE/RUN/WARN/STOP/RECOVER; pi{run,clr,enc_fault,comm_fault,overcur,estop}; po{cause,state,in_stop,brake,motor_en} |
| motor_controller | rtl/dut | setpoint ramp, proportional duty, PWM, over-current (cur>=14) |
| encoder_interface | rtl/dut | quadrature decode, 8-bit position, 32-cycle speed window, invalid-transition flag |
| comm_interface | rtl/dut | start+12-bit{addr,data}+stop receiver, 64-cycle timeout, frame error |
| register_file | rtl/dut | 16x8 memory with MBIST access mux; reg0 = setpoint, reg1 = {enc_clr, clear, run} |
| robotic_soc_core | rtl/dut | five blocks, wrappers, injection |
| robotic_soc | rtl/dut | core + DFT + Reliability Manager (+ core_restore) |
| fi_mask | rtl/common | stuck-at mask generator (region 0 state, 1 PI, 2 PO) |
| mbist_controller | rtl/dft | March C-, 10N ops |
| atpg_interface / scan_test_bank | rtl/dft | ROM pattern player, P(L+1)+L cycles |
| online_test | rtl/dft | 128-cycle shadow compare of one block |
| test_controller | rtl/dft | FULL -> PARTIAL -> MBIST -> ONLINE -> DIAG sequencing |
| state_monitor, aging_model (+activity_monitor), health_manager, priority_engine, test_scheduler, reliability_manager | rtl/reliability | see ARCHITECTURE.md |
Each DUT block exposes a `state_q` observation port (used by the netlist builder; unconnected in the SoC) and `fi_s0/fi_s1` state-injection masks.
