# Simulation guide
Requirements: Icarus Verilog >= 12, Python 3 (numpy, pandas, matplotlib), Yosys (`yosys` or `pip install yowasp-yosys`). Run everything from the project root.
```
make prep            # netlists, ATPG, fault DB, mission trace, RTL param headers (rtl/reliability/rel_params.svh, rtl/dft/dft_params.svh)
make test            # netlist<->RTL check, RTL<->Python scheduler check, all testbenches
make fault-campaign  # baseline vs adaptive campaign (+ literal re-simulation of 200 faults), weight sensitivity
make analyze plots synth
scripts/run_sim.sh scan      # a single testbench: soc scan mbist adaptive baseline fault_injection full_system
```
`tb_full_system` simulates ~0.4M cycles with two cores and takes several minutes in Icarus; `tb_fault_injection` runs 710 x 600 cycles. The tool call limit of some environments requires running these in the background.
Verilator and Questa are not supported/tested.
