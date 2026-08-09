# CKCZ implementation checkpoint 1（2026-08-09）

状态：**CORE CONTRACT PASS — BOOTSTRAP/HPC BLOCKED — NO SCIENTIFIC VERDICT**

## 已实现

- CKBV Gotham/auxiliary manifest、正向 allowlist、逐 NPZ SHA/schema/row 检查；
- Gotham `recorded_index` 与 auxiliary 冻结 UID 的 exact join；ToN 无 endpoint metadata 时
  固定保持 M7，不插值；
- 每个 `held_value` 独立、member-local 有向 endpoint-pair causal state；
- 四个且仅四个 FROZEN scalar；
- VIEWED exact-cut oracle frontier、16 族/四池分母和兼容门；
- atomic CSV/CSV.GZ/JSON、deterministic union schema、readback 与 SHA256SUMS；
- FINAL marker fail-closed。

## 本地合同测试

`python repo/ood/issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py`：**PASS**。

已覆盖：

- current-inclusive conflict count；
- non-conflict 后 consecutive reset；
- conflict span 只在当前 conflict 上产生；
- protocol slice 不串 state；
- PCAP member 是 interaction key 的组成部分；
- label/role/attack family 改写不改变 state；
- metadata missing 不产生 state；
- frontier 有显式 no-veto 点且 exact cut 降序；
- FINAL marker 阻断；
- heterogeneous CSV union schema 回读。

## 未完成且已硬阻断

FROZEN 要求每个 frontier 点报告 source/pair bootstrap 区间。checkpoint 1 尚未实现该阶段，
因此程序固定输出：

```text
bootstrap_complete = false
scientific_verdict_valid = false
PENDING_IMPLEMENTATION_BLOCKS_HPC
```

CLI 终态返回非零。该状态不得组正式 bundle、不得提交 HPC、不得产生 episode 可行/不可行
科学声明。

## 实现审计新发现

Kimi review 中“Gotham 24 + auxiliary 31 = CKBY snapshot 55 source”只能视为总数旁证，
不能证明成员集合相同：CKBY snapshot 的 55 可分为 20 个 `processed/` source、31 个
auxiliary source 和 4 个 ToN source。FROZEN 的 Gotham 24/317,523 合同仍来自 154917
unified manifest，而不是这条加法。实现按 FROZEN 处理：必须用提交入库的 24-source
正向 allowlist 与 manifest exact subset 校验；在拿到精确 allowlist 前继续阻断 bundle。

## 下一步

1. 实现并回归 source/pair cluster bootstrap；
2. 补 first-trigger 前 misses 与 time-to-first-veto frontier 审计；
3. 从 154917 manifest 只读取得 24/31 精确 allowlist，生成 SHA-256 后入库；
4. 用本地冻结 CKBW 预测 + 可用 cache 做真实回放；
5. 完成实现报告后交 Kimi 独立代码/合同审查。
