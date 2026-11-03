# RAW复现停止后的隔离修复 r1

状态：工程修复准备，**未重跑、未提交远端任务**。原v2的 `source_01` 失败现场与冻结代码保留。实施与合成验收见本包 `IMPLEMENTATION_RECEIPT.json`。

## 本次已知事实

原运行在G0_BASE_27的第一组CAL 26,349条前向后，触发 `SOURCE_RAW_REPLAY_MISMATCH:G027CAL`。没有进入HELD重放、own-FIT前向、D0/L距离或A/B。当前未保存的重放向量不能由静态审阅补出，差异数量、幅度和判定影响仍未知。

历史源179460的真实环境是Python3.11.11、NumPy1.26.4、Torch2.5.1、Linux；本次使用Python3.10.0、NumPy2.2.6、Torch2.8.0、Windows。此前原执行卡把历史NumPy2.0.1写在源环境旁，混淆了主头/密参考链路；源重放应绑定179460的1.26.4环境。版本及平台差异是候选原因，**尚未确诊根因**。

## 修复范围

1. 使用记录在179460的历史解释器与兼容环境。`historical_source.py`在任何模型前向前检查精确版本/Linux并核本包SHA；当前本地环境会被拒绝。
2. RAW严格门前新增差异审计，失败时保存原分数与重放分数、索引和UID，报告dtype/shape/字节SHA、差异数量/幅度及cut判定影响。成功保留摘要；所有存盘仍计入原源阶段预算。
3. RAW门依然严格逐值/逐字节一致，不加容差、不换阈值、不改batch或算法、不减少评分人口。仍只有一个L。原B1和独立源1C状态保持。

## 部署与一次运行

历史环境来自：

- `runs/source_controls_base_ctx_repair_v2_20261026/result_retrieval_20261027/evidence179460/environment.json`
- `/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python`
- `/public/home/jiangxinwei.zr/work/paper04/frontend_compat_v1/environment.sh`（SHA `8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf`）
- `PYTHONPATH=/public/home/jiangxinwei.zr/work/paper04/environment/vendor_py311_v1`

远端包目录为 `/public/home/jiangxinwei.zr/work/paper04/runs/local_geometry_budgeted_v2_replay_repair_r1_20261029`。代码分发包只包含实现、测试、规格与验收；数据不重复打包。必须先按 `SOURCE_TRANSFER_MANIFEST.json` 核验同root下全部历史输入存在且SHA一致；历史环境/资产在远端的当前可用性尚待只读核验，不能称已部署验收。

先做输入SHA与导入/版本检查（0模型/前向/距离，需先按上文设置兼容环境和PYTHONPATH）：

```bash
/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B verify_source_inputs.py
/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B historical_source.py --check-env
```

部署及只读SHA核验完成、且用户同意失败后的单次重跑后，仅提交一次：

```bash
sbatch hpc/source_once.slurm
```

脚本为amd 4CPU、8GiB、4小时，`--no-requeue`；源阶段仍限2e9实际距离对、4,600,362条小头评分、2GiB新输出，不训练、不新编码。任何技术/资源异常均停止保留，绝不自动重试。该脚本只启动源阶段。

源PASS才可能进入此前固定的条件主CAL及一次A/B，仍须完整源回执/代码/输出SHA与资源一致。源重试若通过，目标阶段应按主头历史环境及旧D0精确锚验收，不能因源使用NumPy1.26.4而混称主头已复现。目标4CPU/8GiB/另4h、9e9对/2GiB上限保持；没有任何新A/B成绩。

本修复改变工程取证与指定运行环境，不把环境假说写成已经证明的机制解释，也不将先前合成测试当成真实重放已通过。
