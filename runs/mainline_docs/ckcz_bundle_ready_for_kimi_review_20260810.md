# CKCZ bundle 已构建：提交 Kimi 独立审查（2026-08-10）

状态：**BUNDLE BUILT AND LOCALLY VALIDATED — KIMI BUNDLE REVIEW REQUESTED — HPC NOT SUBMITTED**

## 1. 唯一有效候选包

```text
D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_upload_bundle.tar.gz
```

- bytes：38,279
- SHA-256：`9c3da516cea92227c770b59d3279c258da5f3803ddd961edfe7334a8d1429085`
- sidecar：同路径追加 `.sha256`
- `bundle_commit.txt`：`62f929c0c738440b7e534a1d4830412f63475c70`
- tar file members：16
- `SHA256SUMS` entries：15（除 `SHA256SUMS` 自身外全覆盖）
- CR-containing members：0
- `__pycache__` / `.pyc` members：0

## 2. 已执行的本地验证

1. 在 staging 内执行 CKCZ 18 项合同测试：`status=PASS`；
2. FROZEN prereg 与两个正向 allowlist 的固定 SHA 全复验；
3. 所有文本 LF-only；
4. 生成全包 `SHA256SUMS`；
5. tar 后解到第二个受限临时目录，逐 entry 重算 SHA：PASS；
6. 独立 tar member audit：16 files、15 SHA entries、无 bytecode/隐藏生成物；
7. archive sidecar 与独立 `Get-FileHash` 一致。

此前 hash 为 `3fa7c8d5...` 的本地首包因含测试生成的 Python bytecode 已拒收并被当前候选包覆盖；
原因、影响范围与永久门记于 `ckcz_hpc_bundle_engineering_20260810.md` §7。首包未上传、未安装、
未提交 HPC。

## 3. 请求 Kimi 审查

请独立复核：

1. archive SHA 与 sidecar；
2. 解包后 `sha256sum -c SHA256SUMS`；
3. `bundle_commit.txt` 是否为 `62f929c...`；
4. member 集合是否严格限于两份 Python、三份运行脚本、九份已审文档/侧车、
   `bundle_commit.txt` 与 `SHA256SUMS`；
5. installer 是否在缺少 `CKCZ_SUBMIT_AUTHORIZATION=YES` 时确定不正式提交；
6. Slurm 是否只有 validator 通过后才进入 runtime gate PASS，且 auxiliary 31-NPZ 在线门在
   installer 与计算节点各执行一次。

Kimi 的 bundle PASS 只解除 bundle 审查门。登录节点 auxiliary 在线截图与用户明确 HPC 提交授权
仍各自独立，二者未齐不得提交。

当前：**HPC NOT SUBMITTED；FINAL 未触碰。**
