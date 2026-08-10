# CKCZ 流式修复 r3 bundle：待 Kimi 独立审查（2026-08-10）

状态：**R3 BUNDLE BUILT AND LOCALLY VALIDATED — HPC NOT AUTHORIZED**

## 1. 唯一有效候选包

```text
D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3_upload_bundle.tar.gz
```

- bytes：`52,581`
- SHA-256：`0f68b154f0d2c45cc5520e25746d30a273a096a8026cf0df6fdbb1c1d8e9d59c`
- sidecar：同路径追加 `.sha256`
- `bundle_commit.txt`：`6ec2686f690ab29021f9b5225b8c8d469bbd9e42`
- tar file members：`23`
- `SHA256SUMS` entries：`22`
- `__pycache__` / `.pyc` members：`0`

r1/r2 均已作废。r2 SHA `4c29122a...fc96` 严禁重提。

## 2. 已完成验证

1. Kimi 对 streaming repair 的实现审查：PASS（commit `0c3b948`）；
2. 22 项合同测试：全 PASS；
3. builder PowerShell parse：PASS；三个 shell/Slurm `bash -n`：PASS；
4. staging 内冻结 prereg、erratum、两个 allowlist SHA：PASS；
5. LF-only、禁止 bytecode、动态成员数门：PASS；
6. tar 解到第二个独立临时根后，22/22 entry SHA 重算：PASS；
7. archive sidecar 与独立 `Get-FileHash`：一致；
8. 独立 tar envelope audit：23 files、22 SHA entries、无 forbidden member，commit 一致。

## 3. 请求 Kimi 审查

请独立复核：

1. archive SHA/bytes/sidecar；
2. 解包后 `sha256sum -c SHA256SUMS` 22/22；
3. `bundle_commit.txt` 精确等于 `6ec2686f690ab29021f9b5225b8c8d469bbd9e42`；
4. 23-member 集合仅为 2 Python、3 运行脚本、16 份冻结/勘误/失败/审查文档及侧车、
   `bundle_commit.txt`、`SHA256SUMS`；
5. payload 内容与 git `6ec2686` 逐字节一致；
6. streaming writer、8 MiB cap、node-local progress、1,200 秒 watchdog、r3 独立 job-id wiring
   全部进入最终包；
7. installer 缺少 `CKCZ_SUBMIT_AUTHORIZATION=YES` 时不能 `sbatch`。

本 bundle PASS 只解除包审查门。按 Kimi 建议，正式提交前还必须完成严格 55-NPZ 本地全流程
彩排；之后仍需用户新的明确授权。

当前：**未提交 HPC；未触碰 FINAL。**
