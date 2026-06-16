# Open Parameters Registry

The following parameters remain explicitly open. Later issues must bind them using development-only data and must not use sealed final/report-only roles.

| Parameter | Status | Bind no earlier than | Forbidden evidence |
|---|---|---|---|
| support_budget | open | issue27cf or later | sealed final attack/OOD |
| support_train_val_ratio | open | issue27cf or later | sealed final attack/OOD |
| region_cap | open | issue27cf or later | sealed final attack/OOD |
| min_per_region | open | issue27cf or later | sealed final attack/OOD |
| max_per_file | open | issue27cf or later | sealed final attack/OOD |
| max_per_phase | open | issue27cf or later | sealed final attack/OOD |
| selection_method | open | issue27cf or later | final/report-only outcomes |
| region_distance_metric | open | issue27cf or later | final/report-only outcomes |
| region_merge_threshold | open | after region audit | final/report-only outcomes |
| region_split_threshold | open | after region audit | final/report-only outcomes |
| controller_hard_alarm_threshold | open | after legal dev controller calibration | final/report-only outcomes |
| controller_suppress_threshold | open | after legal dev controller calibration | final/report-only outcomes |
| review_budget | open | after mixed-stream realism issue | final/report-only outcomes |
| temporal_persistence_horizon | open | after past-only temporal audit | future windows |

