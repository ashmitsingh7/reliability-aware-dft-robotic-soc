# Results summary (auto-generated from results/*.csv)

## ATPG / scan (per block)

| block | state_bits | faults_collapsed | faults_uncollapsed | patterns | patterns_partial | atpg_aborted | atpg_untestable | fault_coverage | full_scan_cycles | partial_scan_cycles |
|---|---|---|---|---|---|---|---|---|---|---|
| safety | 9 | 125 | 166 | 13 | 7 | 0 | 0 | 1 | 139 | 79 |
| motor | 24 | 577 | 776 | 36 | 18 | 2 | 0 | 0.9965 | 924 | 474 |
| encoder | 31 | 256 | 318 | 10 | 5 | 0 | 0 | 1 | 351 | 191 |
| comm | 27 | 213 | 270 | 12 | 6 | 0 | 0 | 1 | 363 | 195 |
| regfile | 128 | 1344 | 2002 | 59 | 30 | 0 | 0 | 1 | 7739 | 3998 |

## Coverage per test mechanism

| block | faults_collapsed | full_scan | partial_scan | mbist | online_any_window | online_single_window_mean | union_all_mechanisms | campaign_baseline | campaign_adaptive |
|---|---|---|---|---|---|---|---|---|---|
| safety | 125 | 1 | 0.928 | nan | 0.944 | 0.77 | 1 | 1 | 0.768 |
| motor | 577 | 0.9965 | 0.948 | nan | 0.7886 | 0.6161 | 0.9965 | 0.9965 | 0.9861 |
| encoder | 256 | 1 | 0.9453 | nan | 0.8945 | 0.8613 | 1 | 1 | 0.9609 |
| comm | 213 | 1 | 0.9437 | nan | 0.8357 | 0.7782 | 1 | 1 | 0.7418 |
| regfile | 1344 | 1 | 0.9583 | 0.971 | 0.971 | 0.7805 | 1 | 1 | 0.7448 |
| ALL | 2515 | 0.9992 | 0.9519 | 0.5189 | 0.9085 | 0.7503 | 0.9992 | 0.9992 | 0.8231 |

## Baseline vs adaptive

| metric | adaptive | baseline_N20 |
|---|---|---|
| faults_injected | 2515 | 2515 |
| fault_coverage | 0.8231 | 0.9992 |
| coverage_criticality_4_safety | 0.768 | 1 |
| coverage_criticality_3_motor/encoder | 0.9784 | 0.9976 |
| coverage_criticality_2_comm | 0.7418 | 1 |
| coverage_criticality_1_regfile | 0.7448 | 1 |
| mean_detection_latency_cycles | 3.193e+05 | 2.065e+05 |
| median_detection_latency_cycles | 2.368e+05 | 2.079e+05 |
| p95_detection_latency_cycles | 8.648e+05 | 3.826e+05 |
| censored_mean_latency_cycles(undetected=mission_end) | 5.55e+05 | 2.103e+05 |
| total_test_cycles | 2.837e+05 | 2.903e+05 |
| mission_interruption_cycles | 6.769e+04 | 2.225e+05 |
| test_overhead_pct_of_mission | 2.364 | 2.419 |
| interruption_overhead_pct | 0.5641 | 1.855 |
| full_scans | 98 | 150 |
| partial_scans | 151 | 0 |
| mbist_runs | 18 | 30 |
| online_tests | 158 | 0 |
| tests_on_safety | 103 | 30 |
| tests_on_motor | 223 | 30 |
| tests_on_encoder | 40 | 30 |
| tests_on_comm | 23 | 30 |
| tests_on_regfile | 18 | 30 |
| coverage_per_Mcycle | 2.901 | 3.442 |
| detections_while_IDLE | 1443 | 409 |
| detections_while_ACTIVE | 447 | 1462 |
| detections_while_DEGRADED | 180 | 642 |
| ticks_in_IDLE | 136 | 136 |
| ticks_in_ACTIVE | 313 | 313 |
| ticks_in_DEGRADED | 151 | 151 |
| detections_by_FULL_SCAN | 1443 | 2513 |
| detections_by_PARTIAL_SCAN | 180 | 0 |
| detections_by_MBIST | 0 | 0 |
| detections_by_ONLINE | 447 | 0 |
| test_duration_mean_cycles_per_decision | 697 | 9676 |
| faults_detected_only_by_adaptive | 0 | nan |
| faults_detected_only_by_baseline | nan | 443 |
| faster_detection_adaptive_vs_baseline(both detected) | 966 | nan |

## Baseline period sweep

| config | fault_coverage | mean_detection_latency_cycles | censored_mean_latency_cycles | total_test_cycles | mission_interruption_cycles | coverage_per_mcycle |
|---|---|---|---|---|---|---|
| adaptive_default | 0.8231 | 3.193e+05 | 5.55e+05 | 283671 | 67690 | 2.901 |
| baseline_N5 | 0.9992 | 5.517e+04 | 5.909e+04 | 1161120 | 832136 | 0.8606 |
| baseline_N10 | 0.9992 | 1.054e+05 | 1.093e+05 | 580560 | 425744 | 1.721 |
| baseline_N20 | 0.9992 | 2.065e+05 | 2.103e+05 | 290280 | 222548 | 3.442 |
| baseline_N40 | 0.9992 | 4.048e+05 | 4.085e+05 | 145140 | 125788 | 6.884 |
| baseline_N80 | 0.9416 | 8.129e+05 | 7.929e+05 | 67732 | 58056 | 13.9 |

## Weight sensitivity

| weight_set | w1 | w2 | w3 | w4 | w5 | fault_coverage | mean_latency | censored_mean_latency | total_test_cycles | coverage_crit4 | coverage_crit1 | online_tests_safety | online_tests_motor | online_tests_encoder | online_tests_comm | online_tests_regfile |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| equal(1,1,1,1,1) [default] | 1 | 1 | 1 | 1 | 1 | 0.8231 | 3.193e+05 | 5.55e+05 | 283671 | 0.768 | 0.7448 | 83 | 57 | 15 | 3 | 0 |
| crit_only | 1 | 0 | 0 | 0 | 0 | 0.7996 | 3.842e+05 | 6.38e+05 | 285016 | 0.768 | 0.7448 | 158 | 0 | 0 | 0 | 0 |
| health_only | 0 | 1 | 0 | 0 | 0 | 0.8243 | 1.701e+05 | 4.345e+05 | 288441 | 0.768 | 0.7433 | 26 | 45 | 36 | 28 | 23 |
| aging_only | 0 | 0 | 1 | 0 | 0 | 0.7996 | 3.408e+05 | 6.033e+05 | 285016 | 0.768 | 0.7448 | 1 | 157 | 0 | 0 | 0 |
| faults_only | 0 | 0 | 0 | 1 | 0 | 0.7996 | 3.842e+05 | 6.38e+05 | 285016 | 0.768 | 0.7448 | 158 | 0 | 0 | 0 | 0 |
| mission_only | 0 | 0 | 0 | 0 | 1 | 0.7996 | 3.842e+05 | 6.38e+05 | 285016 | 0.768 | 0.7448 | 158 | 0 | 0 | 0 | 0 |
| crit_heavy(4,1,1,1,1) | 4 | 1 | 1 | 1 | 1 | 0.8231 | 3.772e+05 | 6.027e+05 | 283671 | 0.768 | 0.7448 | 155 | 2 | 1 | 0 | 0 |
| health_heavy(1,4,1,1,1) | 1 | 4 | 1 | 1 | 1 | 0.8243 | 2.218e+05 | 4.747e+05 | 282057 | 0.768 | 0.7448 | 41 | 61 | 34 | 14 | 8 |
| aging_heavy(1,1,4,1,1) | 1 | 1 | 4 | 1 | 1 | 0.8258 | 3.226e+05 | 5.581e+05 | 284209 | 0.768 | 0.7448 | 31 | 113 | 12 | 2 | 0 |
| mission_heavy(1,1,1,1,4) | 1 | 1 | 1 | 1 | 4 | 0.8235 | 3.478e+05 | 5.773e+05 | 283940 | 0.776 | 0.7448 | 123 | 29 | 5 | 1 | 0 |
| no_crit(0,1,1,1,1) | 0 | 1 | 1 | 1 | 1 | 0.8231 | 2.658e+05 | 5.109e+05 | 283671 | 0.768 | 0.7448 | 26 | 96 | 24 | 9 | 3 |

## Synthesis (Yosys generic cells; timing/power NOT evaluated)

| module | total_cells | flip_flops | combinational_cells |
|---|---|---|---|
| safety_with_scan | 145 | 9 | 136 |
| safety_functional_only(scan tied off) | 77 | 9 | 68 |
| motor_with_scan | 508 | 24 | 484 |
| motor_functional_only(scan tied off) | 369 | 24 | 345 |
| encoder_with_scan | 355 | 31 | 324 |
| encoder_functional_only(scan tied off) | 156 | 31 | 125 |
| comm_with_scan | 316 | 27 | 289 |
| comm_functional_only(scan tied off) | 133 | 27 | 106 |
| regfile_with_scan | 1862 | 128 | 1734 |
| regfile_functional_only(scan tied off) | 970 | 128 | 842 |
| robotic_soc_core(5 blocks+wrappers+scan chains+FI hooks) | 4475 | 219 | 4256 |
| mbist_controller | 159 | 15 | 144 |
| online_test(checker only; shadow copy NOT included) | 430 | 38 | 392 |
| test_controller | 595 | 79 | 516 |
| reliability_manager(state mon+aging+health+priority+scheduler) | 12991 | 276 | 12715 |
| scan_test_bank(pattern ROMs synthesised as logic) | 4947 | 425 | 4522 |

## MBIST fault classes (RTL simulation)

| fault_class | injected | detected |
|---|---|---|
| SAF0 | 128 | 128 |
| SAF1 | 128 | 128 |
| TF_up | 128 | 128 |
| TF_down | 128 | 128 |
| AF_alias | 240 | 240 |
| CFin_inter_word | 240 | 240 |
| CFid_up_to_1 | 240 | 240 |
| CFid_down_to_0 | 240 | 240 |
| CFin_intra_word | 112 | 112 |
| RF_state_SA | 256 | 256 |
