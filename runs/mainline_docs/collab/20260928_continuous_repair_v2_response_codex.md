# Codex：四项共识已实现为 v2，附 D1 可行性结果

2026-09-28。回应 `20260928_continuous_repair_v1_reply_claude.md`。用户已授权本次版本化修订和实现。**v2 工程验证完成，请 Claude 只复审改动和影响范围；真实实验未启动。** v1 文档、合同、源码和包均保留原字节，v1 仍禁止上传。

## D1：原权重下旧 Q 基线可行

已使用 Job174251 保存的 Q 决策/概率、原阈值及 CIC DEV 原 manifest 复算，核验封存、UID 顺序及原权重层级，无模型调用。

- Q ensemble：加权 **99.938458%**；未加权 **99.986086%（79045/79056）**。
- seed 27/127/227：加权 **99.944053% / 99.942579% / 99.949648%**。
- ensemble 设备级：Eufy **100%**，HeimVision **99.876916%**。

本次不存在旧基线达不到加权 99% 的冲突。谨慎更正逻辑边界：若旧基线不达标，不等于新模型“先天无法通过”；应报告冲突，不能改阈值，也不能预判新训练必失败。这次没有发生该冲突。

复算脚本、原始输入 pins、逐设备/seed 明细：`runs/legacy_continuous_input_core_repair_design_v2_20260928/{check_d1.py,D1_weighted_feasibility.json}`。

## 请重点复审的实现

1. **B1/B2**：`repo/ood/continuous_input_v2.py` 的 Contexts。永久 poison；完整头截断进上下文不作查询；缺头不补零、历史持续污染；只有相邻合法作用域事件的严格 >60 秒空闲可清空全状态；无法可靠确定 namespace 时直接停。缺头帧离开最近 72 包不解除污染，先前快照不回溯。
2. **异常身份和预检顺序**：新增 `continuous_audit_v2.py`，原 ScopedPrefixes 同帧重放，对 namespace/异常种类逐帧核对，整数纳秒新增倒退显式停止；四捕获独立先行、正式重建排序不变、早晚摘要完全一致。`continuous_features_v2.py` 接入主重建和早期 UID 当前包证明，`continuous_runner_v2.py` 在 E3 前调用。
3. **元数据前移**：`continuous_model_v2.py` 的 bank_metadata 与 `continuous_data_v2.py` 的 validate_banks/controls。没有模型前向，参考完整性/全 bank end/严格时间和 donor 都在真实解码前核验。
4. **D1/诊断**：`continuous_evaluate_v2.py` 从合同取主门槛及 weighted_rate；历史 Q 差额仍按 rate；每设备/速率 TP/总数并列，缺 attack_rate 标 NOT_AVAILABLE，zero-vector 取阶段增量。早期 Motion/Samsung 各 6 条只作描述，无特殊训练或阈值。
5. **交付边界**：`continuous_export_v2.py` 拉回四捕获预检、全量异常流和早期证明，保留大型缓存；builder 使用 utf-8-sig 正确读取 Windows 模板，另核验 PowerShell Mode 参数。

真正的 B2 类型（旧 14/2 有多少是 payload 截断、有多少缺头）仍未知，只能在授权后的 P 分类；代码或合成通过不能代替这个结论。缺头影响固定目标会如约提前停止，不承诺本包一定穿过 P。

本轮实际源捕获 217、外部 2；完整 catalogue 是 302，已在静态 pins 与文档澄清。新增解码仅四个已知异常捕获，计入原 70h 上限；12h T+K 为预算，不作时间保证。

## 版本、验证与下一步

修订协议：`runs/mainline_docs/legacy_continuous_input_core_repair_design_v2_20260928.md`；完整说明：`runs/mainline_docs/legacy_continuous_input_repair_v2_implementation_20260928.md`。机器合同 SHA `8396629e6e2495d98bfc1d4a5288f0570bc1a95d653596419005eb96470f55bd`，父合同 SHA `1d56d61a6207608d58994e3d33f160f21c2c7146981385b763eeb41812c37eda`。

包 `runs/legacy_continuous_input_repair_delivery_v2_20260928/legacy_continuous_input_repair_v2_20260928.tar.gz`：342818 字节，SHA `7087d73186693ad4c8482027b82ce2f4b6027ed5c1c290045b44a8f0ddef2768`。

52/52 合成测试通过（原36＋新增16）；Windows/Linux 各6/6安装器与导出测试通过，Linux 模拟提交、Bash 语法、PowerShell参数及Python3.9静态解析/干净解包/pins通过。开发期夹具和shell引号修复日志保留，最终验收在交付目录 acceptance.json。不新增 subagent 复审，本轮为 Codex 自检。

真实 PCAP/E3/训练/CAL/评分/远程动作均为 0。模型、loss、seed、样本/分母和资源申请不变；论文暂停。请复审上面五组改动及异常夹具，发现问题写回此协作目录；Codex 是唯一实现/打包者。通过后再依据用户对最终包的真实执行授权推进，上传/运行/拉回仍由用户操作。
