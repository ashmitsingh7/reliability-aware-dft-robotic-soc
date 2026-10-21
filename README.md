# Reliability-aware DFT for autonomous robotic SoCs - research prototype
Prototype of the architecture proposed in A. Singh, *"Reliability-Aware Design-for-Test Architectures for Autonomous Robotic SoCs: A Survey ..."* (`paper/paper.tex`, `paper/paper.pdf`).
**The paper is a survey with one implementation section.** Sections I-IX fix the architecture (Fig. 1), Eq. (2) and Algorithm 1 but no DUT internals, thresholds or numbers; **Section X of the paper describes this repository** and
reports the Step-3 Phase-1 results (`results_step3/`). Every Section-X number and configuration claim is asserted by `make check-paper-claims` (`results_paper/paper_claims_check.txt`; map in `docs/PAPER_TRACEABILITY.md`).
Everything beyond the survey's Fig. 1 / Eq. (2) / Algorithm 1 is an *implementation assumption* (`docs/PAPER_TRACEABILITY.md`, `docs/LIMITATIONS.md`).

**What it does:** a small five-block robotic SoC (Safety FSM, Motor Controller, Encoder I/F, Comm I/F, Register File) with scan chains, ATPG (PODEM), March C- MBIST, a lightweight
online test, and a Reliability Manager (State Monitor, behavioural Aging model, Health Manager, Priority Engine per Eq. (2), adaptive Test Scheduler with IDLE/ACTIVE/DEGRADED modes).
The central experiment compares a **fixed periodic schedule** against the **adaptive schedule** on the same DUT, mission trace and stuck-at fault list.

**Reproducing the paper's numbers:** `make test-step3 check-paper-claims` on the committed files (do **not** run `make prep` first: it overwrites the committed netlists/fault database, and a different Yosys version changes the fault count, 2,515 -> 2,517 with Yosys 0.70).
**Honest status:** see `IMPLEMENTATION_STATUS.md`. Results: `docs/RESULTS_SUMMARY.md` (auto-generated) and `results/*.csv`. In the experiment as run, the adaptive scheduler lowers
mission-interrupting test time but has *lower* fault coverage than the fixed baseline; the paper's novelty claim is therefore not supported or refuted in general by this single synthetic scenario.
No third-party code is included (`OPEN_SOURCE_SOURCES.md`). Not evaluated: timing, power, PPA.

## Quick start
```
pip install -r requirements.txt     # iverilog (>=12) must be installed separately
make prep test fault-campaign analyze plots synth
python3 python/make_results_summary.py
```
Layout: `rtl/{dut,dft,reliability,common}`, `tb/`, `python/`, `scripts/`, `results/`, `docs/`. Start with `docs/IMPLEMENTATION_DOCUMENT.md`.
Long simulations (`tb_full_system`, `tb_fault_injection`) take minutes in Icarus.
