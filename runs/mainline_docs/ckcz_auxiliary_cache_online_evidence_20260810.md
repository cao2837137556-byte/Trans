# CKCZ auxiliary cache 登录节点在线证据（2026-08-10）

状态：**LOGIN-NODE ONLINE GATE PASS — COMPUTE-NODE RECHECK STILL MANDATORY — HPC NOT SUBMITTED**

## 1. 证据来源

用户于学校 HPC 登录节点 `node168` 的 VS Code Remote-SSH 终端执行：

```bash
AUX=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917/auxiliary_causal_cache; ls "$AUX" | head -5 && du -sh "$AUX" && printf 'NPZ_COUNT=' && find "$AUX" -maxdepth 1 -type f -name '*.npz' | wc -l
```

截图记录的输出为：

```text
0ac694222c68ea78d61c.json
0ac694222c68ea78d61c.npz
0d95194975557bc716d3.json
0d95194975557bc716d3.npz
0e5e24c94db9e5c49bc8.json
2.3M    /public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917/auxiliary_causal_cache
NPZ_COUNT=31
```

终端正常返回 shell prompt，命令链无失败。

## 2. 裁决

FROZEN §4.2 所述“auxiliary cache 尚无登录节点在线存在性证据”的 launch blocker 已解除：

- 路径在线且可列目录；
- 总体大小约 2.3 MiB；
- NPZ 数严格为冻结合同要求的 31。

该截图只证明登录节点的只读在线性与文件数，不替代 manifest SHA、逐 NPZ SHA/schema/行数验证。
这些强验证已机械写入 installer 与正式 Slurm：installer 在提交前重验 31-NPZ，计算节点在打开
任何缓存前再次执行在线门，随后正式 Python 仅按 positive allowlist 逐文件验证。

## 3. 剩余授权门

当前剩余：

1. Kimi 对 SHA 为
   `9c3da516cea92227c770b59d3279c258da5f3803ddd961edfe7334a8d1429085` 的 bundle 给出独立 PASS；
2. 用户在上述 PASS 后明确授权 HPC 提交。

未满足两项前不得上传后直接提交。当前：**HPC NOT SUBMITTED；FINAL 未触碰。**
