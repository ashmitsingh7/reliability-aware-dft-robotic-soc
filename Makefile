# Reliability-aware DFT prototype - reproduction flow.  Run from this directory.  Needs: iverilog>=12, yosys (or yowasp-yosys), python3 + numpy/pandas/matplotlib.
PY      := python3
IV      := iverilog -g2012 -I rtl/dft -I rtl/reliability
CORE    := rtl/common/fault_injector.sv rtl/dft/scan_ff.sv rtl/dft/scan_chain.sv rtl/dft/mbist_controller.sv rtl/dft/atpg_interface.sv \
           rtl/dft/online_test.sv rtl/dft/test_controller.sv rtl/dut/safety_fsm.sv rtl/dut/motor_controller.sv rtl/dut/encoder_interface.sv \
           rtl/dut/comm_interface.sv rtl/dut/register_file.sv rtl/dut/robotic_soc_core.sv
REL     := rtl/reliability/state_monitor.sv rtl/reliability/aging_model.sv rtl/reliability/health_manager.sv rtl/reliability/priority_engine.sv \
           rtl/reliability/test_scheduler.sv rtl/reliability/reliability_manager.sv
ALL     := $(CORE) $(REL) rtl/dut/robotic_soc.sv
TBS     := soc scan mbist adaptive baseline fault_injection full_system

.PHONY: all test sim fault-campaign analyze plots synth clean prep test-step1 report-step1 test-step3 campaign-step3 check-paper-claims paper paper-pdf
all: prep test fault-campaign analyze plots synth

# NOTE on 'prep': it OVERWRITES the committed build/ and results/ inputs.  The paper's 2,515-fault database was built from the committed build/ netlists
# (Yosys 0.69; Yosys 0.70 maps differently and yields 2,517 faults).  To reproduce the paper's numbers run test-step3 / check-paper-claims on the committed files.
prep:            ## netlists, ATPG, fault database, RTL parameter headers, mission trace (see NOTE above)
	mkdir -p build results/plots results/rom
	$(PY) python/build_netlists.py
	$(PY) python/build_fault_db.py
	$(PY) python/mission.py
	$(PY) python/gen_rtl_params.py

build/tb_soc.vvp:        tb/tb_soc.sv $(CORE);        $(IV) -o $@ $^
build/tb_scan.vvp:       tb/tb_scan.sv $(CORE);       $(IV) -o $@ $^
build/tb_mbist.vvp:      tb/tb_mbist.sv $(CORE);      $(IV) -o $@ $^
build/tb_adaptive.vvp:   tb/tb_adaptive.sv $(REL);    $(IV) -o $@ $^
build/tb_baseline.vvp:   tb/tb_baseline.sv $(REL);    $(IV) -o $@ $^
build/tb_fault_injection.vvp: tb/tb_fault_injection.sv tb/stim_gen.sv $(CORE); $(IV) -o $@ $^
build/tb_full_system.vvp: tb/tb_full_system.sv tb/stim_gen.sv $(ALL); $(IV) -o $@ $^

sim: $(addprefix build/tb_,$(addsuffix .vvp,$(TBS)))   ## compile all testbenches

test: sim        ## self-checking RTL testbenches + cross-checks
	$(PY) python/check_netlist_equiv.py
	$(PY) python/check_rtl_equiv.py
	@for t in soc scan mbist adaptive baseline fault_injection full_system; do echo "== tb_$$t"; vvp build/tb_$$t.vvp | grep -E "PASS|FAIL|detected|injected|Phase|cycles" ; done | tee results/testbench_summary.txt
	@! grep -q FAIL results/testbench_summary.txt && echo "ALL TESTBENCHES PASS"

fault-campaign:  ## baseline-vs-adaptive campaign (+ literal-stepping verification of 200 faults) and weight sensitivity
	$(PY) python/fault_campaign.py --verify 200
	$(PY) python/weight_sensitivity.py

analyze:
	$(PY) python/calculate_coverage.py
	$(PY) python/analyze_results.py

plots:
	$(PY) python/plot_results.py

synth:           ## Yosys cell/flop counts (no timing/power)
	$(PY) python/run_synthesis.py

clean:
	rm -rf build/* results/plots results/*.csv results/rom results/testbench_summary.txt rtl/reliability/rel_params.svh rtl/dft/dft_params.svh

# ---- Step-1 scheduler-correctness refinements (all OFF by default; does not alter any target above)
test-step1:      ## directed tests + RTL/Python full-trace equivalence for Fix A/B/C -> results_step1/step1_directed_tests.txt
	$(PY) python/check_step1_scheduler.py
report-step1:    ## original-mission v1 vs refined analysis -> results_step1/
	$(PY) python/step1_report.py

# ---- Step-3 Phase-1 correctness fixes (obs_en / esc_en / stale_en, all OFF by default; does not alter any target above)
campaign-step3:  ## closed-loop campaign (2,515 faults x persistent+transient) -> results_step3/   (development seeds only)
	$(PY) python/step3_campaign.py
test-step3:      ## directed tests + RTL/Python equivalence + mutation sensitivity + campaign checks -> results_step3/step3_phase1_tests.txt
	$(PY) python/check_step3_phase1.py

# ---- Paper Section X ("Implementation of the Reliability-Aware DFT Architecture"): every number/configuration claim is asserted against the committed artifacts
check-paper-claims:  ## python-only, seconds -> results_paper/paper_claims_check.txt (claim IDs P01.. map to docs/PAPER_TRACEABILITY.md)
	$(PY) python/check_paper_claims.py
paper-pdf:       ## rebuild paper/paper.pdf from paper/paper.tex (needs pdflatex + IEEEtran)
	cd paper && latexmk -pdf -interaction=nonstopmode paper.tex

# ---- Everything reported in the paper, regenerated from scratch (long: Icarus + Yosys + campaigns).  Uses development seeds only; the sealed
#      evaluation (docs/SEED_PROTOCOL.md) is a separate Phase-5 step and is NOT part of this target yet.
paper: prep test fault-campaign analyze plots synth
	$(PY) python/step2a_campaign.py --closed-loop
	$(PY) python/step2b_analysis.py
	$(PY) python/check_step1_scheduler.py
	$(PY) python/check_step2a.py
	$(MAKE) campaign-step3
	$(MAKE) test-step3
	$(MAKE) check-paper-claims
