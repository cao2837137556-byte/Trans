# CKDB D0 可行性审计 — Kimi round 2 审查

- 日期：2026-08-17
- 对象：`ckdb_d0_feasibility_audit_codex_20260817.md`（commit `b704122`）
- 性质：设计讨论回应；不授权训练、下载 PCAP、FINAL 或 HPC

## 总结论：D0 审计 ACCEPT —— 分裂判决（现数据 NO_GO / 外部导入 GO）成立，授权进入 D0-P1 元数据审计阶段

## 独立复验记录

| 项 | 实测 | 结果 |
|---|---|---|
| 审计 JSON SHA-256 | `4b6ec3c7…3047d`，与声明一致 | PASS |
| 域→标签泄漏 | 排除 ToN 后 **99.68%**（0.9968263）；全集 78.08% | PASS，NO_GO 判决的证据成立 |
| 良性粗域 | 5 个（building-monitor 3,204 / combined-cycle 3,600+1,409 / domotic 1,800 / ToN 4,000），有效域数 HHI⁻¹=4.42 | PASS |
| 攻击域偏斜 | 4,385 攻击行中 91.22% 来自 ToN | PASS |
| hydraulic 结构诊断 | TCP 75.43% vs 对照 0.20%；中位 flow 662 包/2,675 s vs 对照 8,666 包/56 s——注意 hydraulic 与对照在包数上同量级但**时间跨度差 48 倍、包长差 17 倍**，"像攻击"主要来自协议混合与时频结构 | PASS |
| UNSW-IoTraffic 事实 | 联网多源核实：27 设备、95,543,405 包、203 天、~26.9 GB PCAP、Dryad DOI `10.5061/dryad.w0vt4b94b`、IEEE 描述论文（Wannigama et al. 2025）均与报告一致 | PASS |

## 逐项裁定

1. **"不等导师公式"：接受。** 损失设计是项目责任；候选公式（攻击组均值 BCE + 良性域 smooth-max + 正则）作为 D0 候选合法。我 round 1 提的反退化诊断与 LODO 选择已进入其 §7 必备清单，闭环。
2. **现数据训练 NO_GO：接受且证据硬。** 5 个有效域 + 99.68% 域→标签可预测性，GroupDRO/IRM 在该数据上不可识别，这一点有文献支持（报告引用的 Risks of IRM 等）。
3. **外部导入 GO：接受，但有三个必须写进 D0-P1 的审计点：**
   - **谱系污染**：UNSW-IoTraffic 采集于 2016-09~2017-04，是 2018 年 UNSW 早期 IoT traces（Sivanathan 等）的扩展版。必须审计：(a) 与 ToN-IoT 的采集重叠（不同测试床，预期无重叠，但须证明而非假设）；(b) **与 netFound 预训练语料的关系**——E3 是 `NO_KNOWN_OVERLAP`，若其预训练见过这些公开 PCAP，E3 对照路线的解释力要降级；(c) 与 select/report/FINAL 零重叠的显式证明。
   - **良性边界**：无逐行标注，只有"已验证良性的采集段"可进自监督；良性-use 标准须在 PCAP 下载前冻结。
   - **域类型差距（我新增）**：UNSW-IoTraffic 是消费级智能家居设备，我们的测试床是工业/仿真 ICS。它增加设备多样性，但不保证覆盖 hydraulic 类工业域。D0-P1 的设备清单审计应记录每个设备的类型标签，供后续评估"域多样性是否足够"——不要默认 27 个设备 = 27 个有效域。
4. **hydraulic 机制诊断：接受。** "长时双向 TCP 组件"定位与数据一致；协议允许诊断禁止补丁的边界被正确遵守。
5. **cooler-motor 一次性 FINAL：接受。** 全方案冻结后才开，开后无反馈回路。

## 授权边界

- 授权 **CKDB D0-P1**：仅下载 UNSW-IoTraffic 的 README/设备清单等小文件，完成重叠/许可/良性边界审计。
- 不授权 PCAP 大包下载；元数据门 PASS 后由用户明确授权再下载 13.92 GB。
- 不授权任何训练、embedding、阈值、FINAL、HPC。
