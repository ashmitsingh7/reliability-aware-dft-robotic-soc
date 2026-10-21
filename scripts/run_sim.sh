#!/usr/bin/env bash
# Compile and run one testbench:  scripts/run_sim.sh <soc|scan|mbist|adaptive|baseline|fault_injection|full_system>
set -e; cd "$(dirname "$0")/.."; make -s build/tb_$1.vvp && vvp build/tb_$1.vvp
