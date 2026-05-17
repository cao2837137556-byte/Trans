# Problem Reframing Acceptance Summary

## 1. 接收结论

`22年-26年问题定义报告.md` 已读取并接收为当前科研总控升级依据。本轮不跑实验、不训练模型、不改论文主稿、不改历史实验数字。

## 2. 新问题定义

当前主问题重构为：

**Low-Alert Intrusion Detection under Benign-OOD Drift**

更具体的论文表述为：

**Deployment-stage guarded few-shot adaptation for low-alert intrusion detection under benign-OOD drift.**

## 3. 新方法命名

推荐论文命名：

- `LOW-GUARD`
- `LOW-GUARD-minimal`
- `Deployment-stage guarded adaptation`

当前实现：

`LOW-GUARD-minimal = original100 representation + fixed OOD-benign guard + few-shot LR adapter`.

`GDA` 可以继续作为内部方法演化术语，但不应在论文中暗示 full neural GDA 已完成。

## 4. 当前最强证据

- ordinary sanity 表明 dA / Transformer 不是无效模型。
- low-OOD collapse 表明问题来自部署工作点与 benign-OOD drift，而不是 base detector 普通能力缺失。
- scalar score fusion 是负结果，不应继续作为主路线。
- fixed OOD guard 是当前最稳机制。
- original100 fixed guard / LOW-GUARD-minimal 是当前最稳主方法。
- mode-gated arbitration 与 bounded review 支撑 base detector 和 LOW-GUARD 共存。
- review queue 是 safety net，不是 confirmed attack pool。

## 5. 当前最大风险

- 单数据集 / 单 split 泛化不足。
- LR 太简单，容易被压成 cost-sensitive LR。
- few-shot anomaly detection 已有，必须做同协议 baseline。
- review queue attack fraction 低，不能写成新增检出贡献。
- OOD 设置可能被质疑人为。
- detector-agnostic 证据不足。
- second environment 缺失或不稳。

## 6. 下一步

下一步必须由 issue16 结果决定：优先考虑 issue16b formal harder-holdout fixed-guard validation；同时规划 few-shot anomaly baseline comparison。不要在 harder-holdout / baseline 之前继续复杂 adapter upgrade。
