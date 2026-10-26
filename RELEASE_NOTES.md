# Public release

Built from development base commit `e21fb09f244982a94bb3e85cee8d7c165d067bf1` plus the
validated working-tree implementation and experiment updates. The public release itself
is identified by its Git commit and archive checksum.

This release includes fairness-enabled RTL/Python scheduler plumbing, test-controller
acceptance and completion reporting, an independent fairness oracle, preserved historical
results, and a fresh `results_final/` campaign namespace.

Validation: `make test-step3-fairness` (19/19), `make check-paper-claims` (25/25),
`make verify-final`, and a final campaign with 2,515 persistent and 2,515 transient
episodes per profile. RTL/Python equivalence covered 285,660 ticks and 55 columns per
tick with zero mismatches.

The 154-tick fairness value is an observed campaign maximum, not a formal universal proof.
The results are behavioral, single-seed measurements; no physical PPA or silicon validation
is claimed, and PDF compilation depends on an external LaTeX toolchain.
