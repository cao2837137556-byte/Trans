# Preflight V1/V2 Backtest Check

- V1 fixed as original100 + kcenter32 + fixed guard LR: yes.
- V2 fixed as selected_source_rich_top32 + kcenter32 + fixed guard LR: yes.
- V2 topK is fixed at 32 and is not re-selected by outcome: yes.
- V2 does not concatenate original100: yes.
- V2 does not use margin-hardneg: yes.
- Support is selected from each dataset/holdout local attack train pool only: yes.
- Thresholds use ID calibration + OOD validation only: yes.
- Alarm-budget curve uses pre-registered validation targets, not final-OOD selection: yes.
- All V1/V2 target results are written, not only the best point: yes.
- V2 definition is not modified based on this backtest: yes.
