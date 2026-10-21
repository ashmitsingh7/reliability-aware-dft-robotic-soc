k# Reliability-Aware Design-for-Test for Autonomous Robotic SoCs

**Research, RTL Implementation, and Simulation-Based Verification**

This repository contains the implementation and experimental evaluation accompanying the research paper:

**Reliability-Aware Design-for-Test Architectures for Autonomous Robotic SoCs: A Survey of Conventional, Aging-Aware, and Adaptive Runtime Testing**

The project investigates a runtime Design-for-Test (DFT) scheduling architecture for a robotic System-on-Chip (SoC). The proposed approach combines block criticality, diagnostic evidence, behavioural aging indicators, system operating state, and mission context to guide the scheduling of online tests.

The repository includes a SystemVerilog SoC model, DFT infrastructure, a reliability-aware scheduler, a Python reference model, fault-injection experiments, automated verification, and the associated research paper.

> **Research scope:** This is a behavioural RTL/Python prototype evaluated through simulation and synthetic fault-injection campaigns. It is not a fabricated silicon implementation, and the reported results do not establish physical power, timing, area, or silicon-level reliability.

## Research objectives

Conventional DFT techniques primarily address manufacturing-time testability. This project explores how test selection and scheduling could adapt to changing reliability evidence and operating conditions during a robotic controller's runtime.

The implementation investigates four questions:

1. How can a runtime scheduler prioritize tests using block criticality, health evidence, aging indicators, fault history, and mission state?
2. How should diagnostic evidence be managed when a passing test does not adequately cover the suspected failure class?
3. How can full-depth diagnostic escalation improve fault recovery while accounting for mission-interruption cost?
4. How can RTL behavior be checked against an independent Python reference model across normal operation, degraded operation, resets, and long-duration counter rollover scenarios?

The work builds on established DFT and reliability-monitoring concepts. The scheduler and its evaluation are presented as a research prototype rather than as a claim that the individual underlying techniques are new.

## System architecture

The prototype models five functional blocks:

| Block | Role |
|---|---|
| Safety FSM | Models safety-related operating-state control |
| Motor Controller | Represents robotic actuator-control logic |
| Encoder Interface | Models encoder-data interfacing |
| Communication Interface | Represents communication-related logic |
| Register File | Models the SoC's register storage |

The DFT and reliability infrastructure includes:

- **Scan testing:** scan-chain and scan flip-flop models for internal-state observability.
- **ATPG interface:** a PODEM-based software implementation for generating patterns under the modeled fault assumptions.
- **Memory testing:** a March C− MBIST controller for the modeled register-file memory.
- **Online testing:** a shadow-comparison mechanism for detecting modeled functional discrepancies.
- **Fault injection:** configurable faults used to evaluate detection and diagnostic behavior.
- **Reliability management:** behavioral aging, health evidence, operating-state monitoring, priority calculation, and runtime test scheduling.

### Adaptive scheduling

The scheduler uses a priority function of the form:

\[
Priority_i =
w_1 Crit_i +
w_2 Health_i +
w_3 Aging_i +
w_4 Faults_i +
w_5 Mission_i
\]

where the terms represent block criticality, health evidence, aging state, fault history, and mission context.

The reported profiles use unit weights. The function is an implementation-level scheduling heuristic; its coefficients are not claimed to be physically calibrated or globally optimized.

## Implementation and verification

The implementation is organized into the following areas:

| Directory | Contents |
|---|---|
| `rtl/dut/` | Functional SoC blocks and top-level integration |
| `rtl/dft/` | Scan, ATPG interface, MBIST, online test, and test control |
| `rtl/reliability/` | Aging and health models, priority engine, and test scheduler |
| `rtl/common/` | Shared fault-injection logic |
| `tb/` | SystemVerilog testbenches |
| `python/` | Reference models, fault campaigns, analysis, and automated checks |
| `scripts/` | Simulation, fault-campaign, and Yosys execution scripts |
| `docs/` | Architecture, methodology, implementation details, results, and limitations |
| `results_step3/` | Step 3 campaign summaries and profile-level episode data |
| `results_paper/` | Saved paper-claim validation output |
| `paper/` | Research paper source and PDF |

### Scheduler refinement history

The implementation evolved through staged correctness work:

- **Step 1 — Scheduler correctness:** recovery gating, persistent full-scan progress, and starvation prevention.
- **Step 2A — Health-evidence separation:** separated diagnostic evidence from the aging estimate and corrected long-horizon age-counter rollover behavior.
- **Step 2B — Root-cause analysis:** examined premature diagnostic-flag clearing and the relationship between failure evidence and test observability.
- **Step 3 Phase 1 — Observability-aware diagnostics:** introduced configurable evidence-dominance checks, rate-limited full-scan escalation, and stale-age tracking.

The Step 3 controls `obs_en`, `esc_en`, and `stale_en` are disabled by default. This permits controlled comparisons against earlier configurations.

## Experimental methodology

The project uses directed verification, RTL/Python equivalence checks, mutation-sensitivity tests, and synthetic fault-injection campaigns.

The recorded Step 3 Phase 1 experiment uses:

- A 600-tick synthetic mission trace.
- 20,000 modeled cycles per scheduler tick.
- A collapsed fault database containing 2,515 modeled faults.
- Development seeds 2024 for the mission trace and 4242 for fault injection.
- Transient faults removed after 60 ticks.
- One injected fault per episode.

The campaign evaluates persistent and transient fault episodes separately. Reported metrics include premature diagnostic-flag clearance, transient-episode recovery, and mission-interruption cycles.

## Recorded Step 3 results

The following values are from the committed campaign artifacts. They are not physical measurements.

| Configuration | Premature persistent-fault flag clearances | Transient episodes recovered | Mean persistent-episode interruption cycles |
|---|---:|---:|---:|
| Step 2A reference | 117 | 2,174* | 469,680 |
| Step 3: observability only | 0 | 0 | 486,764 |
| Step 3: observability + escalation | 0 | 2,267 | 526,202 |

\*The reference transient campaign also recorded 112 premature clearances and 155 episodes still flagged at mission end. Persistent-fault interruption cycles and transient-fault recovery counts refer to different episode populations.

### Interpretation

Observability-aware evidence handling eliminated premature diagnostic-flag clearances in the recorded campaign. Observability alone did not recover flagged transient episodes in the tested configuration.

Adding full-scan escalation recovered 2,267 of the 2,440 flagged transient episodes, with 173 remaining unresolved at mission end. This improvement came with increased mean interruption cycles for persistent episodes: approximately 3.6% for observability alone and 12.0% for observability plus escalation relative to the Step 2A reference.

These results demonstrate a trade-off within the modeled experiment. They do not establish statistical generality across seeds, missions, or physical devices.

## Reproducing the validation

### Prerequisites

- Python 3
- Icarus Verilog (`iverilog` and `vvp`)
- GNU Make
- Git
- Yosys for synthesis-related checks

Install the Python dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the documented Step 3 and paper-claim checks:

```bash
make test-step3 check-paper-claims
```

The recorded validation reports:

- **18/18 Step 3 Phase 1 tests passed.**
- **25 paper claims checked, with zero failures.**
- RTL/Python equivalence across 285,300 ticks and 55 compared columns per tick.
- All six deliberately injected RTL defects detected by the mutation-sensitivity checks.

These figures describe the saved validation run. Re-running the command should be used to establish the result for a specific checkout and tool environment.

## Documentation and research traceability

For a detailed review, start with:

1. `docs/ARCHITECTURE.md` — system organization and architecture.
2. `docs/EXPERIMENTAL_METHODOLOGY.md` — experimental setup and evaluation methodology.
3. `docs/IMPLEMENTATION_DOCUMENT.md` — implementation details.
4. `docs/RESULTS_SUMMARY.md` — result interpretation.
5. `docs/PAPER_TRACEABILITY.md` — links between paper claims and implementation artifacts.
6. `docs/LIMITATIONS.md` — assumptions and limitations.
7. `docs/SIMULATION_GUIDE.md` — simulation and verification instructions.
8. `paper/paper.pdf` — rendered research paper.
9. `paper/paper.tex` — paper source.

## Limitations

The evaluation is a behavioral simulation study with a synthetic fault campaign. In particular:

- The aging model is behavioral and is not calibrated to physical NBTI/HCI degradation measurements.
- Fault-injection results depend on the modeled fault database, mission trace, and selected seeds.
- The reported Step 3 campaign uses one mission trace and one injection seed.
- The escalation interval is configured to 10 scheduler ticks and has not been established as an optimal value.
- Power, timing, area, and silicon-level reliability have not been demonstrated.
- Passing the RTL/Python equivalence and paper-claim checks establishes consistency for the tested cases; it does not prove correctness for all possible inputs or physical conditions.

These limitations define the scope of the current prototype and identify areas for further validation.

## Research paper

The paper and its implementation are included in this repository:

- `paper/paper.pdf`
- `paper/paper.tex`

The paper surveys conventional DFT, aging-aware monitoring, online testing, and adaptive scheduling concepts, then documents the behavioral implementation and preliminary simulation-based evaluation.

## License and third-party sources

See `LICENSE`, `OPEN_SOURCE_SOURCES.md`, and `docs/OPEN_SOURCE_REUSE.md` for licensing and third-party reuse information. Review applicable licenses before redistributing reused source code or derived artifacts.

---

**Project focus:** Design-for-Test · SystemVerilog · RTL Verification · ATPG · MBIST · Fault Injection · Reliability-Aware Scheduling · Robotic SoCs

