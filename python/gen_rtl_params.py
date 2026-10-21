from reliability_model import *
open(RTL + "/reliability/rel_params.svh", "w").write(rtl_header(Params(), load_stats()))
print("wrote rel_params.svh")
s = load_stats(); L = ["// AUTO-GENERATED from results/atpg_stats.json by python/gen_rtl_params.py"]
for i, n in enumerate(BNAMES):
    L.append(f"localparam NP{i} = {s[n]['patterns']};"); L.append(f"localparam NPP{i} = {s[n]['patterns_partial']};")
open(RTL + "/dft/dft_params.svh", "w").write("\n".join(L) + "\n")
