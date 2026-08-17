# CKDA D1 本地 L2 结果 — Kimi 独立终审

- 日期：2026-08-17
- 对象：本地拉回包 `issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu_pullback.tar.gz` + Codex 自审 `2e7b508`
- 冻结合同：`ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`

## 总结论：RESULT VERIFIED —— 判决 `CKDA_D1_WEAK_ONLY`、`GO_D2=false` 成立，接受

## 独立复验记录（全部本地重算）

| 项 | 实测 | 结果 |
|---|---|---|
| 拉回包 SHA-256 / 侧车 | `20988f87…929b` 一致 | PASS |
| 包内文件哈希 | 20/20 在包文件全部一致（10 项 stage-only 大文件不入包，设计如此） | PASS |
| verdict | `CKDA_D1_WEAK_ONLY`，`go_d2=false` | PASS |
| 一次性性质（事后密码学确认） | 阈值冻结标记 SHA `84576a50…dd5b` 与 L2 门记录一致；标记钉死 plan/embedding/probe-state/三 frontier 哈希，冻结时点 `report_labels_opened=0`、`report_rows_opened=0` | PASS |
| 推进合法性 | `e3_open_reason=I1_PRIMARY_PRECONDITION_FAILED`，I1 未训练未生成 embedding | PASS |

## 核心指标复算确认（与 Codex 报告一致）

| 探针 | 全局攻击召回 | future 召回 | OOD macro | ROC-AUC |
|---|---:|---:|---:|---:|
| G0 | 92.69% | 92.23% | 60.32% | 0.682 |
| P1 | 96.94% | 96.27% | 57.89% | 0.814 |
| **P2** | **97.37%** | **96.68%** | **29.88%** | **0.882** |

- C1 同行基线：91.30% / 86.83%。P2 分别 +6.07pp / **+9.85pp**。
- P2 的 11 项门通过 10 项，唯一失败：`each_ood_delta_le_2pp`——hydraulic-system 76.30% vs FrozenCKBQ 45.70%（+30.6pp）。其余三池全部大幅改善（−8.0 / −14.8 / −29.4pp）。
- 16 攻击族 delta 全部 ≥ −2pp（独立清点，0 个违规）。
- P1 在 ip-camera-street 池 99.7% 饱和——探针间不稳定真实存在，宏观平均遮不住，逐池门的设计价值被实证。

## 流程备注（非阻塞）

L2 开启经由用户明确授权 Codex 自审、跳过 Kimi L1 门（`ckda_d1_local_l1_codex_review_gate_20260816.json` 在案）。与增补协议的"独立审查"表述有偏差；但冻结标记在 report 开启前已密码学钉死全部上游产物，一次性性质事后可验证成立，科学完整性未受损。后续默认恢复 Kimi 独立审查门，除非用户再次明确授权豁免。

## 授权边界

- 判决接受：当前预注册下**不进入 D2**，不允许阈值重选、候选改动、hydraulic 专项补丁。
- 下一步仅限方案讨论/设计；论文级声明仍须 HPC 正式重放确认。
