# CKCZ r2 bundle 终审意见 — Kimi

日期：2026-08-10 | 审查者：Kimi | 对象：r2 bundle（SHA-256 `4c29122a…fc96`，HEAD `ca557e8`，bundle commit `02258c4`）

**总体结论：PASS。r2 包审查门解除。剩余唯一门：用户再次明确授权 HPC 提交。**

---

## 1. 独立验包明细（全部本地实测）

| §4 审查项 | 方法 | 结果 |
|---|---|---|
| 1. archive SHA/bytes | 本地重算 | `4c29122a…fc96` 一致；bytes 44,520 一致 ✓ |
| 2. 包内哈希链 | 独立临时目录解包 `sha256sum -c` | 19/19 全 OK ✓ |
| 3. bundle_commit | 读文件 | `02258c43b255ccb9619ec6c5bff597f4fb5ab26f` ✓ |
| 4. member 集合 | 逐文件清点 | 严格 20 个：2 Python + 3 脚本 + 13 冻结/澄清/审查文档与侧车 + bundle_commit + SHA256SUMS；CR 0；`.pyc`/`__pycache__` 0 ✓ |
| 4b. 内容真实性（加审） | 14 个 payload 内容文件与 git 逐一 `cmp` | 全部**逐字节一致** ✓ |
| 5. 修复要素入包 | 脚本逐行复核（与 f534775 版逐字节相同） | erratum+snapshot 双 SHA 钉死、真实 lineage coverage gate（sbatch --test-only 前对真实 CKBW+CKBY 工件执行）、r2 独立目录与独立 job-id 文件、勘误文档及侧车入包 ✓ |
| 6. 授权门 | installer 逻辑复核 | 无 `CKCZ_SUBMIT_AUTHORIZATION=YES` 时仅干跑 + exit 3，不可能正式 sbatch ✓ |

## 2. 一个如实备注（非阻塞）

交接文档称"installer 明确拒绝旧包"。实际机制是**路径隔离**（r2 独立 bundle 目录、独立 job-id 文件）+ **r1 自愈式失败**（r1 包缺 lineage 修复，重跑只会在 join 处 fail-closed，不可能产出错误科学结果）。并非 installer 内有字面的旧包拒绝断言。安全性质完整成立，仅措辞偏强，特此记录以求准确。

## 3. 授权边界

本 PASS 仅解除 r2 包审查门。HPC 重新提交须用户在收到提交命令后再次明确授权。作业性质不变：只读诊断，不训练、不解码 PCAP、不触碰 FINAL（cooler-motor、seed 37/47）。
