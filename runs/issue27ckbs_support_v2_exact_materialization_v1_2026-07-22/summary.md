# CKBS exact diagnostic materialization

Status: `SUPPORT_V2_DIAGNOSTIC_MATERIALIZATION_QUARANTINED_FUTURE_ORDER`.

- Reused the vendored mature Kitsune/AfterImage `RestoredNetStat115` frontend and frozen ID-train state.
- Exactly materialized 160 labeled diagnostic rows; matrix shape is `[160, 115]`, with zero missing targets and zero timestamp ambiguity.
- Every candidate is from the same capture after the already frozen TCP/Telnet future-query interval.
- All 160 rows are forbidden for fit, select, standardization, thresholding, negative sampling, and model selection.
- Active support remains train `385`, validation `127` (fit/select `58/69`). This is not a model-performance result.
