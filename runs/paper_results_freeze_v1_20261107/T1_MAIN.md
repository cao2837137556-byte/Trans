Ensemble. NORMAL is FPR; ATTACK/HTTP/UDP are query detection rates. A/B are consumed development pools; Edge is external cross-dataset evaluation and was not used in development. All rate columns are percentages; no event-level claim.

| Pool | View | Method | Group | Alarms/N | Sample (%) | Weighted (%) | HT (%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CIC_DEV | post_window_primary | RAW | NORMAL | 99/96041 | 0.103081 | 5.526880 | -- |
| CIC_DEV | post_window_primary | RAW | ATTACK | 79056/79056 | 100.000000 | 100.000000 | -- |
| CIC_DEV | post_window_primary | C5_FROZEN | NORMAL | 22/96041 | 0.022907 | 0.233716 | -- |
| CIC_DEV | post_window_primary | C5_FROZEN | ATTACK | 79051/79056 | 99.993675 | 99.998731 | -- |
| CIC_DEV | post_window_primary | C5_3D_OLD | NORMAL | 18/96041 | 0.018742 | 0.002235 | -- |
| CIC_DEV | post_window_primary | C5_3D_OLD | ATTACK | 79056/79056 | 100.000000 | 100.000000 | -- |
| UNSW_DEV | post_window_primary | RAW | NORMAL | 40121/74444 | 53.894202 | 27.110961 | -- |
| UNSW_DEV | post_window_primary | RAW | ATTACK | 72543/72553 | 99.986217 | 99.991298 | -- |
| UNSW_DEV | post_window_primary | C5_FROZEN | NORMAL | 1299/74444 | 1.744936 | 0.560510 | -- |
| UNSW_DEV | post_window_primary | C5_FROZEN | ATTACK | 72543/72553 | 99.986217 | 99.991298 | -- |
| UNSW_DEV | post_window_primary | C5_3D_OLD | NORMAL | 210/74444 | 0.282091 | 0.286266 | -- |
| UNSW_DEV | post_window_primary | C5_3D_OLD | ATTACK | 72543/72553 | 99.986217 | 99.991298 | -- |
| EDGE | full | RAW | NORMAL | 16699/20000 | 83.495000 | 78.946445 | 84.913525 |
| EDGE | full | RAW | HTTP | 19966/20000 | 99.830000 | 99.793905 | 99.836712 |
| EDGE | full | RAW | UDP | 19732/20000 | 98.660000 | 98.660000 | 98.660000 |
| EDGE | full | C5_FROZEN | NORMAL | 1158/20000 | 5.790000 | 9.332313 | 5.531273 |
| EDGE | full | C5_FROZEN | HTTP | 18999/20000 | 94.995000 | 96.243810 | 94.423895 |
| EDGE | full | C5_FROZEN | UDP | 19732/20000 | 98.660000 | 98.660000 | 98.660000 |
| EDGE | full | C5_3D_OLD | NORMAL | 24/20000 | 0.120000 | 1.220180 | 0.017457 |
| EDGE | full | C5_3D_OLD | HTTP | 19958/20000 | 99.790000 | 99.751165 | 99.795250 |
| EDGE | full | C5_3D_OLD | UDP | 19732/20000 | 98.660000 | 98.660000 | 98.660000 |
