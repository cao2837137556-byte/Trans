# CKCZ lineage 修复 r2 bundle：待 Kimi 独立审查（2026-08-10）

状态：**REVOKED AFTER JOB 158038 LUSTRE HARD STALL — SHA 4c29122a...fc96 MUST NOT BE RESUBMITTED**

> r2 的包完整性在构建时成立，但真实运行暴露大型 CSV 整体原子写入的 Lustre
> `osc_extent_wait` 硬停滞。本文只保留为历史证据；修复走独立 r3 bundle。

## 1. 唯一有效候选包

```text
D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r2_upload_bundle.tar.gz
```

- bytes：`44,520`
- SHA-256：`4c29122a7844b0a772a9bad759e86ce6ede2ed9e2d842e90b8a7de33c490fc96`
- sidecar：同路径追加 `.sha256`
- `bundle_commit.txt`：`02258c43b255ccb9619ec6c5bff597f4fb5ab26f`
- tar file members：`20`
- `SHA256SUMS` entries：`19`（覆盖除 `SHA256SUMS` 自身外的全部文件）
- `__pycache__` / `.pyc` members：`0`

r1 包 SHA `9c3da516...` 已作废，严禁再次上传或提交。job 158015 仅保留为工程失败证据，不产生科学 verdict。

## 2. r2 相对 r1 的受控变化

1. 按 FROZEN erratum，以 CKBY job 157930 snapshot 的
   `(uid, source, role, m1_phase) -> recorded_index` 精确映射修复 Gotham lineage；
2. 同时钉住 erratum SHA 与 lineage snapshot SHA，并在真实输入上要求 Gotham protocol rows 的
   lineage miss 为零；
3. 合同测试由 18 项增至 19 项，新增非索引 UID 尾段正例，永久阻断 job 158015 根因；
4. r2 与 r1 路径隔离，installer 明确拒绝旧包；
5. 本包纳入 Kimi 的 lineage 修复实现审查 PASS 文档 `ef5551e`。

科学协议、frontier、停止规则、FINAL 排除和非晋升边界均未改变。

## 3. 已完成的本地验证

1. PowerShell builder 语法解析：PASS；
2. 三个 HPC shell/Slurm 脚本 `bash -n`：PASS；
3. CKCZ 19 项合同测试：`status=PASS`；
4. builder 首次 staging 后逐文件哈希、固定文档 SHA、LF-only、成员数与禁止生成物检查：PASS；
5. tar 解到第二个独立临时根后，逐 entry 重算 `SHA256SUMS`：PASS；
6. archive sidecar 与独立 `Get-FileHash`：一致；
7. 独立 tar envelope audit：20 files、19 SHA entries、无 bytecode/隐藏生成物，且
   `bundle_commit.txt` 与已推送提交一致。

## 4. 请求 Kimi 审查

请独立复核：

1. archive SHA、sidecar、bytes 与上述值一致；
2. 解包后 `sha256sum -c SHA256SUMS` 全 PASS；
3. `bundle_commit.txt` 为 `02258c43b255ccb9619ec6c5bff597f4fb5ab26f`；
4. r2 member 集合只包含两份 Python、三份运行脚本、既有冻结/澄清/审查证据、
   `bundle_commit.txt` 与 `SHA256SUMS`；
5. FROZEN erratum、snapshot 双 SHA、真实 coverage gate、r2 隔离与旧包拒绝均进入最终包；
6. installer 在缺少 `CKCZ_SUBMIT_AUTHORIZATION=YES` 时确定不执行正式 `sbatch`。

Kimi 的 r2 bundle PASS 只解除包审查门。HPC 重新提交仍需要用户在该 PASS 之后再次明确授权。

当前：**未重新提交 HPC；未触碰 cooler-motor、seed 37/47 或任何 FINAL 数据。**
