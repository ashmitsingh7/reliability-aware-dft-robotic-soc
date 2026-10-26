// Step-1 refinement switches.  DEFAULT = ALL OFF (v1 behaviour).  Test builds shadow this file via an earlier -I path.
localparam REC_EN_P = 0;
localparam REC_N_P = 3;
localparam MARGIN_P = 16;
localparam SWEEP_PERSIST_P = 0;
localparam STARVE_EN_P = 0;
localparam OVERDUE_T_P = 150;
localparam FAIR_GAP_P = 4;
// Step-2A health-evidence separation (DEFAULT OFF)
localparam EVID_EN_P = 0;
localparam ARISK_DEG_P = 0;
// Step-3 Phase-1 (DEFAULT OFF)
localparam OBS_EN_P = 0;
localparam ESC_EN_P = 0;
localparam ESC_GAP_P = 10;
localparam STALE_EN_P = 0;
// Step-3 fairness exemption (DEFAULT OFF): unresolved evidence on a flagged block does not withhold overdue healthy-block scans when enabled.
localparam FAIR_UNRES_EN_P = 0;
