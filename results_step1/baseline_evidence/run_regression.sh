#!/bin/bash
cd /home/claude/work/reliability_aware_dft
echo "== make sim"; make sim 2>&1 | grep -v sorry | tail -2
echo "== netlist equiv"; python3 python/check_netlist_equiv.py 2>&1 | tail -2
echo "== rtl equiv (v1 default)"; python3 python/check_rtl_equiv.py 2>&1 | tail -3
for t in soc scan mbist adaptive baseline fault_injection full_system; do echo "== tb_$t"; vvp build/tb_$t.vvp | grep -E "PASS|FAIL|detected|injected|Phase|cycles" | tail -4; done
echo "== DONE"
