# 源侧 8 UID 的 B1 / B16 克隆技术诊断：已准备，尚未获准真实运行

作业 179536 已通过启动、86 项合成测试和生产依赖导入，在原 104 门禁处保留现场停止。104 条中 96 条逐字节相同，8 条不同，最大绝对误差 9.238719940185547e-7。8 条不同恰好对应 8 个 B1 形状组；B2、B3、B4、B12、B16 的其余 96 条均相同。正式 21,660 新位置、源 CAL 和目标评价均未开始。

这支持优先隔离批次大小的数值影响，但尚未证明唯一原因。旧运行时为 Py3.9 / torch2.5.1+cpu / MKL2024.2；本次为 Py3.11 / torch2.5.1 CUDA 构建 / MKL2023.1，两个 CPU 均 AVX2。当前诊断保持失败作业运行时，先把其他变化控制住。

## 冻结输入与边界

仅使用 8 个原 SOURCE_REFS / LEARN / REFERENCE UID 的旧缓存 `flow` 与 `provenance`，以及原 8×768 float32 期望向量。8 个 flow/provenance 均与失败作业输入逐字段一致。每 UID 绑定失败作业实际 tensor SHA、B1 feature SHA、旧期望 feature SHA、原 shape、UID/type/来源身份。原 SQLite SHA 采用此前已验证的 `f0afb582a0d3c513e29d13dd637ad550c2e967de1dc734e70b43031d24aa6a9c`；不复制或重复哈希 4.4GB 数据库。

**本包不恢复原 batch cohort。** 原 8 个历史 batch 的 128 个成员中有 80 LEARN、8 SOURCE_REFS、25 CIC_DEV、15 UNSW_DEV。本包排除全部 40 个目标 query 输入，不复制任何目标标签、目标分数或状态特征；只保留 8 个源参考。每个 B16 由同一个源参考克隆 16 次，用来隔离 B1 与 B16 的内核／批维影响。

原逐行 tensor receipt 对这些导入缓存行不可用；绑定的是 179536 实际 B1 tensor receipt，不把它称为历史原始 receipt。原代码、checkpoint、期望库和失败作业均不改动。

## 固定步骤与判据

1. 完整核验本包封条、8 UID 顺序、flow/provenance 和期望 float32 每 UID SHA。默认 dry-run 到此结束，零模型导入、零权重加载、零前向。
2. 真实运行须新用户批准绑定最终封条和 manifest；先核完整原 r2 封条、固定解释器、179536 原 runtime receipt 的原始 SHA、NumPy overlay、六依赖的 module/distribution 版本及精确导入路径、完整 Python 与 torch 构建配置。冻结 wrapper/vendor 字节继续受 r2 保护，禁止 fallback 安装或修改共享环境。
3. 先执行全部 8 个 B1。每次前向前，tensor SHA 必须等于失败作业。每个输出 feature SHA 必须原样复现失败作业 B1；任一不同立即停止，保存观察，不运行 B16，也不解释批次大小效应。
4. B1 全部复现后，依次执行 8 个 B16 克隆。全部 16 行 tensor SHA 都须相同且等于失败作业；同 UID 的 16 个输出必须逐字节一致，再与旧期望向量逐字节比较。零容差。
5. 保存全部输入 hash、输出 hash 和原始诊断 float32 观察，报告 0–8 个 UID 的旧字节复现数。B16 负结果也是有效诊断观察，不自动换环境、改 batch、放宽容差或进入生产。

固定预算 **8 + 8×16 = 136 个前向位置，8 个唯一 UID**。即使 B16 全部恢复旧 8 字节，也只支持该隔离诊断，不能替代正式原 104 门禁，更不能授权新编码、CAL 或 A/B 评价。诊断观察禁止作为生产特征或参考库复用。

## 资源、执行与授权

拟用 amd 单节点、4 CPU、16GiB、CPU-only；Slurm 总 wall-time 10 分钟、0 自动重试、no-requeue。程序进程树 RSS <8GiB，输出 <256MiB，空闲磁盘 >1GiB；独立新输出根 `runs/dense_reference_original104_batch_diagnostic_v1_20261027_runtime/job_ID/science`，既有目录不可复用。预计分钟量级，10 分钟是硬限，尚无本诊断实际耗时测量。

复用只读解释器 `/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python`，以及只读的 `dense_reference_launch_repair_v1_20261027/runtime/job_179536/science/runtime/numpy201`。冻结原环境 receipt 原字节 SHA 为 `b404d8c8db68495846dabfbc540a3ff325157b145876240396e0ecd7c939173d`，完整内容已作为输入封存；其真实 torch-config SHA 为 `cd50548e77abb900f46eb68fc69139124e58024034a7915fef6cd194d4f59ce3`。这使用真实原文件，不使用整理后的摘要哈希。

运行环境须与 179536 一致：`PYTHONNOUSERSITE=1`、`PYTHONDONTWRITEBYTECODE=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`CUDA_VISIBLE_DEVICES` 为空，OMP/MKL/OpenBLAS/NUMEXPR 均 4 线程，`PYTHONPATH` 指向上述 NumPy overlay、`environment/vendor_py311_v1` 和原 `vendor/encoding_v2/repo/ood`。不执行 pip，不调用原生产 chain，不生成任何委托批准。

本地只读验收：`python -B diagnostic.py --package <本包目录>`。真实执行接口仅为同一固定包上的 `--execute --approval-file <新私密批准> --output <上述固定新目录>`；此文件不包含 sbatch 调用，准备本包不提交作业。`APPROVAL_TEMPLATE.json` 为 false；最终授权只能写在封条以外的私密文件。

需要用户批准的是这一次 **136 位置、10 分钟、仅源参考的技术诊断**。此次准备与测试未进行任何真实前向、补编码、CAL、目标评价或远端提交。
