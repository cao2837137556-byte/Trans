# 第二环境资产缺口

## 1. 已找到的本地资产

- BoT-IoT 5% 本地资产：`D:\study\paper\anomaly_detection\paper04\worktrees\data\5%`。上一轮 E4 gate 已发现 10-best full 资产中 benign 只有 477 行、attack 3,668,045 行，无法干净构造当前 low-OOD 协议需要的良性 OOD / 校准 / 评估角色。
- TON-IoT network 资产：`D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset\train_test_network.csv`。上一轮 E4 使用过一个 16 维 numeric split（ID-train 8000、ID-eval 4000、OOD-eval 8000、attack-eval 12000），但它不是当前 original100/source_rich/GDA 特征空间。

## 2. 正式第二环境仍缺什么

- 能区分 ID benign、OOD benign、high-purity attack train candidate、validation、final evaluation 的 role manifest。
- 与 original100 可比的特征抽取，或者一个明确说明不可比但自洽的替代表征。
- 能支持 support provenance、threshold provenance 和 final-eval exclusion 检查的 row-id manifest。
- 同一 split 下的 base detector score 与 GDA-minimal score。
- 不使用 final OOD eval 或 attack eval 的预注册阈值协议。

## 3. 建议

不要把 BoT-IoT 或 TON-IoT 当作当前可立即使用的 second-environment validation。如果要推进外部环境验证，应另开 `second_environment_asset_acquisition_and_protocol_conversion` 任务，先补齐数据角色、特征、标签与 row-id manifest，再做模型评估。
