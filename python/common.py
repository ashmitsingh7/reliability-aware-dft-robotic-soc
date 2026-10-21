"""Shared constants.  Block order == criticality order (index 0 = highest)."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
RESULTS = os.path.join(ROOT, "results")
RTL = os.path.join(ROOT, "rtl")

# name, module, #PI, #PO, #state, criticality tier (4 = highest)  -- criticality is configurable here
BLOCKS = [
    dict(name="safety",  mod="safety_fsm",        ni=6,  no=9,  ns=9,   crit=4),
    dict(name="motor",   mod="motor_controller",  ni=20, no=10, ns=24,  crit=3),
    dict(name="encoder", mod="encoder_interface", ni=3,  no=16, ns=31,  crit=3),
    dict(name="comm",    mod="comm_interface",    ni=2,  no=15, ns=27,  crit=2),
    dict(name="regfile", mod="register_file",     ni=31, no=24, ns=128, crit=1),
]
NB = len(BLOCKS)
BNAMES = [b["name"] for b in BLOCKS]
REGFILE = 4
EPOCH_CYCLES = 20000      # Implementation assumption: one scheduler tick = 20,000 DUT clock cycles
PARTIAL_FRAC = 0.5        # Implementation assumption: partial scan = first 50% of coverage-ordered patterns
MBIST_WORDS = 16
ONLINE_WINDOW = 128       # cycles of concurrent checking per online test
ONLINE_K = 4              # number of distinct functional windows
def mbist_cycles():       # March C-: 10 N operations (verified against RTL in tb_mbist)
    return 10 * MBIST_WORDS
