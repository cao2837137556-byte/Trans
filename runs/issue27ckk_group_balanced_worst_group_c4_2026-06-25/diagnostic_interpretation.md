# issue27ckk diagnostic interpretation

## Verdict

This run tests whether legal group-balanced/worst-group training views are enough to repair C4's review instability and shortcut risk.

Best eligible candidate by sealed OOD review: `baseline_cap20000`.

- future hard mean/min: `0.9717` / `0.9016`
- sealed attack hard mean/min: `0.9944` / `0.9922`
- sealed OOD hard mean/max: `0.0026` / `0.0034`
- sealed OOD review mean/max: `0.0733` / `0.1047`

Rejected trade-offs:

- `fit_tail_source_balanced`: sealed OOD review mean `0.0083`, rejected because sealed attack hard mean 0.9715 < 0.99; sealed OOD hard max 0.0118 > 0.01.
- `source_balanced_group_weighted`: sealed OOD review mean `0.0110`, rejected because sealed OOD hard max 0.0385 > 0.01.
- `device_time_balanced`: sealed OOD review mean `0.0663`, rejected because sealed attack hard mean 0.9776 < 0.99; future hard mean 0.9419 < 0.97.
- `source_balanced`: sealed OOD review mean `0.1099`, rejected because future hard mean 0.9502 < 0.97.

## Remaining shortcut risk

At least one device-family leave-out stress case still has hard alarm above `10%`.
That means training-view repair alone has not fully solved cross-family generalization.
Worst observed case: `source_balanced_group_weighted` leaving `iotsim-stream-consumer` on `ood_stress` produced hard alarm `0.9978`.

## Data-use boundary

Training used only support_train, id_calib fit, ood_val fit, and ood_stress fit.
No support_val select, same_file/future query select, or sealed final rows were used for fitting.
