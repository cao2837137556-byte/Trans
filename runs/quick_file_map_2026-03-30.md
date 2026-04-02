# Frontend100 主线文件速查（2026-03-30）

## 1) 先看这个总交接（给 Prism）
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\prism_handoffs\2026-03-30\handoff_for_prism_strongerood_calibration_tailreg.md`

## 2) 主线结果（按论文叙事顺序）

### A. stronger OOD 现象建立
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stage1_2026-03-25\summary.md`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stability_2026-03-25\summary.md`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stability_2026-03-25\aggregate_mean_var.csv`

### B. 阈值层机制（threshold/calibration）
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_threshold_2026-03-25\summary.md`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_threshold_2026-03-25\threshold_comparison.csv`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calibration_scan_2026-03-25\summary.md`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calibration_scan_2026-03-25\calibration_grid_results.csv`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calib_stability_local_2026-03-30\summary.md`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calib_stability_local_2026-03-30\aggregate_mean_var.csv`

### C. TailReg 方法补充
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_bestcfg_stability_2026-03-28\summary.md`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_bestcfg_stability_2026-03-28\aggregate_mean_var.csv`

## 3) 最常用图（直接用于写作）

### calibration 多 seed 稳定
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calib_stability_local_2026-03-30\plots\fixed_alarm_ratio_by_seed.png`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calib_stability_local_2026-03-30\plots\calibrated_alarm_ratio_by_seed.png`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calib_stability_local_2026-03-30\plots\fixed_vs_calibrated_mean.png`

### TailReg 多 seed 稳定
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_bestcfg_stability_2026-03-28\plots\fixed_alarm_ratio_by_seed.png`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_bestcfg_stability_2026-03-28\plots\calibrated_alarm_ratio_by_seed.png`
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_bestcfg_stability_2026-03-28\plots\fixed_vs_calibrated_mean.png`

## 4) 一句话导读
- 先读 Prism 交接文档，再看 `crosscapture_stability -> threshold -> calibration_scan -> calib_stability_local -> tailreg_bestcfg_stability`。
