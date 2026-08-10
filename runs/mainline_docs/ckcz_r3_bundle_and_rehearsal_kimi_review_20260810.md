# CKCZ r3 bundle 终审 + 彩排拉回命令审查 — Kimi

日期：2026-08-10 | 审查者：Kimi | 对象：r3 bundle（SHA-256 `0f68b154…9d59c`，HEAD `2529fb9`）+ 彩排拉回交接文档

**总体结论：双 PASS。r3 包审查门解除；彩排拉回命令可执行。HPC 提交仍需用户在彩排 PASS 后明确授权。**

---

## 1. r3 bundle 独立验包（全部本地实测）

| 审查项 | 结果 |
|---|---|
| archive SHA / bytes | 重算 `0f68b154…9d59c` 一致；52,581 bytes 一致 ✓ |
| 包内哈希链 | 独立临时目录解包 `sha256sum -c`：22/22 全 OK ✓ |
| bundle_commit | `6ec2686f690ab29021f9b5225b8c8d469bbd9e42` ✓ |
| member 集合 | 23 个文件：2 Python + 3 脚本 + 16 文档/侧车 + bundle_commit + SHA256SUMS；CR=0；bytecode=0 ✓ |
| 内容真实性 | 10 个关键 payload 文件（含流式修复后的诊断程序、watchdog Slurm、installer、validator）与 git HEAD 逐字节 cmp 全一致 ✓ |
| 包内代码版本 | 即我审查过的 `f6e89ae` 流式修复版 + `f534775` lineage 修复版，无新增未审代码 ✓ |

## 2. 彩排拉回命令审查（`ckcz_local_rehearsal_input_pullback_handoff_20260810.md`）

§1（HPC bash）安全性质逐项确认：

- 两个 manifest SHA 钉死；allowlist schema 严格 `{source_group}`；allowlist→manifest exact subset 强制；
- **只复制白名单内 55 个 npz**（逐文件 SHA 复制前后双验）；gotham 目录其余 5 个非白名单 npz 从不被读取；
- source 名含 FINAL marker（cooler-motor/seed37/seed47）直接拒绝；行数合同 317,523/18,600 与 55 总数断言；
- 不提交 Slurm、不读写 FINAL、临时目录清埋有路径安全守卫。

**两个如实备注（非阻塞）**：

1. §1 从 HPC 上的 **r2 bundle 目录**取 allowlist 文件——r2 作为"作业包"已作废，但其中 allowlist 是逐字节等于冻结资产的文件，且脚本使用前强制 SHA 断言（`65b48041…`/`be4ad12a…`），来源安全性有保证。
2. §2 使用 ssh 别名 `school-hpc`。用户此前成功命令用的是显式 `jiangxinwei.zr@172.24.3.168`；若别名未配置导致 scp 失败，把 `school-hpc:` 替换为 `jiangxinwei.zr@172.24.3.168:` 即可，无需改其他内容。

§2（PowerShell）SHA 双验 + 失败即抛错，逻辑正确。

## 3. 流程确认

彩排（bootstrap-reps=20）只验证工程合同，其内部 verdict 不解释、不保存、PASS 后销毁——该纪律正确。正式 HPC 提交的三道门保持：彩排 PASS → 用户明确授权 → r3 提交。

## 4. 授权边界

本 PASS 解除 r3 包审查门并认可彩排流程，不构成 HPC 提交授权。
