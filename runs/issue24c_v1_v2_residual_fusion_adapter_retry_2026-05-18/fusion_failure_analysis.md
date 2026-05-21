# Fusion Failure Analysis

- No fusion candidate delivers a clean adapter replacement over V2_top64 LR.
- The best fusion only gives a very small locked mean/min gain, does not repair bin6/bin7, and degrades the holdout_bin_2 consistency check relative to V2_top64 LR.
- The issue24b complementarity is real but too small or too bin-specific to justify replacing the LR adapter in this pass.
- Repeated locked-bin optimization risk is now high; stop adapter upgrade unless a new independent validation object provides a fresh reason.
