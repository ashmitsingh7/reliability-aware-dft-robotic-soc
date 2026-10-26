# Step 2A results comparison (generated from results_step2a/campaign_summary.json)

Faults: 2515; mission ticks: 600 x 20000 cycles; injection seed 4242; mission seed 2024; commit at run time: 5ce425badd (working tree had uncommitted Step 2A edits).

## Experiment 1 - first-detection, fault-free schedule replay

| profile | coverage | crit4 | crit3 | crit2 | crit1 | mean lat | median lat | p95 lat | censored mean lat | total test cyc | interruption cyc | full | partial | MBIST | online | ticks I/A/D |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1_adaptive | 0.8231 | 0.768 | 0.978 | 0.742 | 0.745 | 319349 | 236983 | 864669 | 554997 | 283671 | 67690 | 98 | 151 | 18 | 158 | 136/313/151 |
| fixed_N5 | 0.9992 | 1.000 | 0.998 | 1.000 | 1.000 | 55171 | 54453 | 100350 | 59092 | 1161120 | 832136 | 600 | 0 | 120 | 0 | 136/313/151 |
| fixed_N10 | 0.9992 | 1.000 | 0.998 | 1.000 | 1.000 | 105430 | 105938 | 194809 | 109310 | 580560 | 425744 | 300 | 0 | 60 | 0 | 136/313/151 |
| fixed_N20 | 0.9992 | 1.000 | 0.998 | 1.000 | 1.000 | 206504 | 207876 | 382402 | 210304 | 290280 | 222548 | 150 | 0 | 30 | 0 | 136/313/151 |
| fixed_N40 | 0.9992 | 1.000 | 0.998 | 1.000 | 1.000 | 404833 | 401573 | 763373 | 408475 | 145140 | 125788 | 75 | 0 | 15 | 0 | 136/313/151 |
| fixed_N80 | 0.9416 | 0.944 | 0.952 | 0.962 | 0.932 | 812891 | 822207 | 1514949 | 792874 | 67732 | 58056 | 35 | 0 | 7 | 0 | 136/313/151 |
| s1_recovery_only | 0.9746 | 0.968 | 0.990 | 0.981 | 0.964 | 333458 | 258072 | 863478 | 333818 | 268155 | 13852 | 124 | 9 | 23 | 209 | 174/414/12 |
| s1_all3 | 0.9746 | 0.968 | 0.990 | 0.981 | 0.964 | 343846 | 267088 | 886900 | 343941 | 253151 | 13435 | 110 | 9 | 22 | 209 | 174/414/12 |
| s2a_all3_evid | 0.9746 | 0.968 | 0.990 | 0.981 | 0.964 | 348667 | 268036 | 902502 | 348640 | 250156 | 9544 | 110 | 0 | 22 | 216 | 173/427/0 |
| s2a_all3_evid_aflag | 0.9746 | 0.968 | 0.990 | 0.981 | 0.964 | 343846 | 267088 | 886900 | 343941 | 253151 | 13435 | 110 | 9 | 22 | 209 | 174/414/12 |

Latency in DUT clock cycles. Mean/median/p95 over detected faults (p95 = sorted[int(0.95*(n-1))]); censored mean counts undetected faults at end-of-mission minus injection cycle.

## Coverage by block

| profile | safety | motor | encoder | comm | regfile |
|---|---|---|---|---|---|
| v1_adaptive | 0.768 | 0.986 | 0.961 | 0.742 | 0.745 |
| fixed_N5 | 1.000 | 0.997 | 1.000 | 1.000 | 1.000 |
| fixed_N10 | 1.000 | 0.997 | 1.000 | 1.000 | 1.000 |
| fixed_N20 | 1.000 | 0.997 | 1.000 | 1.000 | 1.000 |
| fixed_N40 | 1.000 | 0.997 | 1.000 | 1.000 | 1.000 |
| fixed_N80 | 0.944 | 0.964 | 0.926 | 0.962 | 0.932 |
| s1_recovery_only | 0.968 | 0.991 | 0.988 | 0.981 | 0.964 |
| s1_all3 | 0.968 | 0.991 | 0.988 | 0.981 | 0.964 |
| s2a_all3_evid | 0.968 | 0.991 | 0.988 | 0.981 | 0.964 |
| s2a_all3_evid_aflag | 0.968 | 0.991 | 0.988 | 0.981 | 0.964 |

## Full scans per block / ticks since last full scan at end (derived from decisions) / max gap between full scans

| profile | safety | motor | encoder | comm | regfile | overdue at end |
|---|---|---|---|---|---|---|
| v1_adaptive | 20 / 158 / 59 | 20 / 160 / 57 | 20 / 159 / 55 | 20 / 157 / 57 | 18 / 156 / 55 | safety,motor,encoder,comm,regfile |
| fixed_N5 | 120 / 0 / 5 | 120 / 0 / 5 | 120 / 0 / 5 | 120 / 0 / 5 | 120 / 0 / 5 | - |
| fixed_N10 | 60 / 0 / 10 | 60 / 0 / 10 | 60 / 0 / 10 | 60 / 0 / 10 | 60 / 0 / 10 | - |
| fixed_N20 | 30 / 0 / 20 | 30 / 0 / 20 | 30 / 0 / 20 | 30 / 0 / 20 | 30 / 0 / 20 | - |
| fixed_N40 | 15 / 0 / 40 | 15 / 0 / 40 | 15 / 0 / 40 | 15 / 0 / 40 | 15 / 0 / 40 | - |
| fixed_N80 | 7 / 40 / 80 | 7 / 40 / 80 | 7 / 40 / 80 | 7 / 40 / 80 | 7 / 40 / 80 | - |
| s1_recovery_only | 25 / 20 / 59 | 26 / 22 / 57 | 25 / 21 / 55 | 25 / 19 / 57 | 23 / 18 / 55 | - |
| s1_all3 | 22 / 20 / 89 | 22 / 22 / 90 | 22 / 21 / 86 | 22 / 19 / 89 | 22 / 18 / 55 | - |
| s2a_all3_evid | 22 / 20 / 89 | 22 / 22 / 90 | 22 / 21 / 86 | 22 / 19 / 89 | 22 / 18 / 55 | - |
| s2a_all3_evid_aflag | 22 / 20 / 89 | 22 / 22 / 90 | 22 / 21 / 86 | 22 / 19 / 89 | 22 / 18 / 55 | - |

## Starvation classification at end of mission (adaptive profiles; recorded-evidence report)

- v1_adaptive: safety=OVERDUE_SERVED_ELSEWHERE_OR_PENDING, motor=OVERDUE_SERVED_ELSEWHERE_OR_PENDING, encoder=OVERDUE_SERVED_ELSEWHERE_OR_PENDING, comm=OVERDUE_SERVED_ELSEWHERE_OR_PENDING, regfile=OVERDUE_ELIGIBLE_WINDOWS_AVAILABLE_BUT_UNUSED
- s1_recovery_only: safety=OK, motor=OK, encoder=OK, comm=OK, regfile=OK
- s1_all3: safety=OK, motor=OK, encoder=OK, comm=OK, regfile=OK
- s2a_all3_evid: safety=OK, motor=OK, encoder=OK, comm=OK, regfile=OK
- s2a_all3_evid_aflag: safety=OK, motor=OK, encoder=OK, comm=OK, regfile=OK

## Experiment 2 - closed-loop, sequential single persistent-fault episodes (one episode per fault, 2515 episodes)

| profile | flagged | cleared while fault persists | rate | mean DEGRADED ticks (detected) | mean interruption cyc/episode | episodes ending DEGRADED | episodes with overdue blocks at end |
|---|---|---|---|---|---|---|---|
| v1_adaptive | 2076 | 94 | 0.045 | 336.1 | 447270 | 2515 | 2515 |
| fixed_N5 | 833 | 0 | 0.000 | 151.0 | 832136 | 2515 | 2515 |
| fixed_N10 | 833 | 0 | 0.000 | 151.0 | 425744 | 2515 | 2515 |
| fixed_N20 | 833 | 0 | 0.000 | 151.0 | 222548 | 2515 | 2515 |
| fixed_N40 | 833 | 0 | 0.000 | 151.0 | 125788 | 2515 | 2515 |
| fixed_N80 | 833 | 0 | 0.000 | 151.0 | 58056 | 2515 | 2515 |
| s1_recovery_only | 2459 | 275 | 0.112 | 288.5 | 463923 | 2374 | 1959 |
| s1_all3 | 2459 | 275 | 0.112 | 286.5 | 460790 | 2372 | 1895 |
| s2a_all3_evid | 2451 | 117 | 0.048 | 284.1 | 469680 | 2371 | 1893 |
| s2a_all3_evid_aflag | 2459 | 275 | 0.112 | 286.6 | 460821 | 2369 | 1895 |

For fixed_* profiles the 'flagged' / DEGRADED columns describe the manager's aging flag only; the fixed schedule never uses it, so they are not a response metric.

