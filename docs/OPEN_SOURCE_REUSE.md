# Open-source sources

**Bottom line: no third-party code is included in this repository.** All RTL, Python and testbenches were written for this project.
The nine repositories named in the task were cloned and their LICENSE files / top-level contents were checked; their source code was
**not reviewed in depth**, so they are cited only as *conceptual references* for textbook techniques, not as studied implementations.

| Repository | URL | License (from cloned LICENSE file) | Component | Files used | Modified? | Attribution |
|---|---|---|---|---|---|---|
| Fault (AUCOHL) | https://github.com/AUCOHL/Fault | Apache-2.0 | Reference for overall RTL->scan->ATPG flow (concept) | none | n/a | concept only |
| dft-scan-atpg (SandeepGorrepati) | https://github.com/SandeepGorrepati/dft-scan-atpg | **no license file found** | Reference for scan + stuck-at ATPG (concept) | none | n/a | **not copied** (unlicensed) |
| dft-fundamentals (ChargeInMotion) | https://github.com/ChargeInMotion/dft-fundamentals | **no license file found** | Reference for mux-D scan cell (concept) | none | n/a | **not copied** (unlicensed) |
| Digital-Circuit-Fault-Simulator-ATPG (zilindev) | https://github.com/zilindev/Digital-Circuit-Fault-Simulator-ATPG | **no license file found** | Concepts: word-parallel fault sim, SCOAP | none | n/a | **not copied** (unlicensed) |
| atpg-toolkit (jack-mil) | https://github.com/jack-mil/atpg-toolkit | MIT | Concept: PODEM | none | n/a | concept only |
| ScanForge (Rueilian) | https://github.com/Rueilian/ScanForge | MIT | Concept: stress/wear-aware partial scan. **Not examined in depth; no ScanForge idea is implemented** | none | n/a | none |
| mbist-march-algorithms (Happy251005) | https://github.com/Happy251005/mbist-march-algorithms | **no license file found** | Concept: March C- | none | n/a | **not copied** (unlicensed) |
| FIawase (mutouTry) | https://github.com/mutouTry/FIawase | Apache-2.0 | Concept: flop-level runtime fault injection | none | n/a | concept only |
| open-source-dft-flow (inaved-semicon) | https://github.com/inaved-semicon/open-source-dft-flow | **no license file found** | Concept: RTL->Yosys->DFT flow | none | n/a | **not copied** (unlicensed) |

Author/organisation names beyond the GitHub account names in the URLs were not recorded.

## Tools used (not redistributed)
Icarus Verilog 12, Yosys (via `yowasp-yosys`), Python 3 with numpy / pandas / matplotlib.

## Classification of code
| Class | Content |
|---|---|
| A. Directly reused code | none |
| B. Modified open-source code | none |
| C. Independently implemented | everything in `rtl/`, `tb/`, `python/` (scan cell, PODEM, fault simulators, collapsing, SCOAP, March C- MBIST, scheduler, ...). The algorithms themselves are textbook (PODEM: Goel 1981; March C-: van de Goor; SCOAP: Goldstein 1979) |
| D. Paper-derived architecture | Reliability Manager structure, Eq.(2), Algorithm 1, IDLE/ACTIVE/DEGRADED, fixed-vs-adaptive comparison |

## Repositories not searched
The task asked for independent GitHub searches (reliability-aware scan, aging-aware test, adaptive test scheduling, RTL fault injection, ...).
Beyond the nine listed repositories, **no additional search was performed**.
