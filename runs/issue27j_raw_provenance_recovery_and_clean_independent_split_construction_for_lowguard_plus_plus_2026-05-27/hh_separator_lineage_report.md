# HH Separator Lineage Report

The three separator features are legal Kitsune/KitNET traffic-stat features, not explicit labels or split IDs.

| feature_name | original100_index | channel_or_grouping | statistic | lambda | source_code_location | calculation | uses_future_packets | uses_current_packet | online_deployable_if_state_available | computed_before_split_in_current_assets | temporal_leakage_risk | capture_artifact_risk | needs_splitwise_reconstruction | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HH_radius_lambda_0.01 | 46 | HH = host-host bandwidth stream keyed by srcIP,dstIP | radius | 0.010000 | repo/kitsune_frontend_original/netStat.py:88-92; repo/kitsune_frontend_original/AfterImage.py:88-98,390-391 | update_get_1D2D_Stats returns weight/mean/std plus radius/magnitude/covariance/pcc after sequential update for the current packet. | False | True | True | True | medium_if_validation_requires_split-reset_state | medium_low_until_session_disjoint_check | True | No explicit label/split/bin feature, but the feature state is time-evolving and can carry capture/window conditions. |
| HH_magnitude_lambda_0.01 | 47 | HH = host-host bandwidth stream keyed by srcIP,dstIP | magnitude | 0.010000 | repo/kitsune_frontend_original/netStat.py:88-92; repo/kitsune_frontend_original/AfterImage.py:94-98,390-391 | Magnitude is sqrt(sum(mean^2)) over paired stream statistics after decay/update. | False | True | True | True | medium_if_validation_requires_split-reset_state | medium_low_until_session_disjoint_check | True | No explicit label/split/bin feature, but the feature state is time-evolving and can carry capture/window conditions. |
| HH_radius_lambda_0.1 | 39 | HH = host-host bandwidth stream keyed by srcIP,dstIP | radius | 0.100000 | repo/kitsune_frontend_original/netStat.py:88-92; repo/kitsune_frontend_original/AfterImage.py:88-98,390-391 | Same HH radius statistic at faster decay lambda=0.1. | False | True | True | True | medium_if_validation_requires_split-reset_state | medium_low_until_session_disjoint_check | True | No explicit label/split/bin feature, but the feature state is time-evolving and can carry capture/window conditions. |


Technical interpretation:
- HH uses host-host traffic state keyed by `srcIP,dstIP`.
- `radius` and `magnitude` are derived from decayed mean/variance statistics in AfterImage.
- The extractor updates and then reports stats for the current packet; it does not use future packets.
- Because current features were generated continuously over each capture before downstream splits, a strict temporal validation should rebuild/reset feature state or use purge/embargo to avoid adjacent-window state carryover.
- The features are online-computable in deployment, but they can still encode capture/window conditions through decayed traffic history.
