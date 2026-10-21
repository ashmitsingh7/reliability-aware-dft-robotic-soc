# Architecture
```
 robotic_soc_core: Safety FSM(crit 4) | Motor Ctrl(3) | Encoder I/F(3) | Comm I/F(2) | Register File(1)
   each block: test wrapper (functional/test PI mux) + scan chain + RTL stuck-at injection hooks
 DFT: scan_test_bank (5 x atpg_interface pattern players) | mbist_controller (March C-, register file) | online_test (shadow compare) | test_controller
 Reliability Manager (one evaluation per tick):
   state_monitor -> IDLE/ACTIVE/DEGRADED        aging_model -> Aging_i        health_manager -> Health_i, Faults_i, degraded flags
   priority_engine -> Priority_i (Eq. 2)        test_scheduler -> {block, test set}  (MODE 0 adaptive / MODE 1 fixed baseline)
 results (pass/fail per test) -> health_manager (fault history, staleness)
```
Block index order is criticality order (0 = highest). Test-set bits: FULL=1, PARTIAL=2, MBIST=4, ONLINE=8, DIAG=16.
Scheduler rules per tick (Algorithm 1 + ASSUMPTIONS): IDLE: sweep all blocks, highest priority first, FULL+DIAG(+MBIST for regfile), re-arm sweep after 10 idle ticks; ACTIVE: ONLINE on argmax priority every 2nd tick;
DEGRADED (block flagged when aging/2 + 32*fault_history >= 64): PARTIAL+DIAG on the highest-priority flagged block every tick. Health_i also includes a staleness term (4 per tick since last passing test) so that equal-priority blocks rotate (ASSUMPTION, not in the paper).
