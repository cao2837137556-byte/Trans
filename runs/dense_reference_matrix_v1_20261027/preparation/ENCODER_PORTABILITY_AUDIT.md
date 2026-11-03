# 密参考补编码与源 CAL 的超算迁移审计

2026-10-27，Codex 独立只读审计。原封存包未修改，未访问远端，未前向、编码、计算新参考支持或训练。本文件记录迁移要求，不是生产数值验收。

## 结论

原 `encoding_package_v2` 不能在现有超算共享 NumPy 1.26.4 环境中原样正式编码。其编码器在加载模型前强校验生产依赖版本，NumPy 必须是 2.0.1。采用**新作业私有 NumPy 2.0.1 overlay**，保留原六项版本配置和原 104 条逐 UID、float32 字节完全相等的数值门，技术上是合理的保守迁移路径；共享环境不得修改。实际移植是否成功仍待计算节点完整依赖导入和原 104 重放。

原始依据：`runs/diagnostics_c5_step2_package_v1_20261025/encoding_package_v2/config.json`、同包 `repo/ood/onboarding_supplement_encoder_r2.py`、`chain/run_dense_source_cal.py`；最新依赖实测为 `runs/hpc_readiness_preparation_v1_20261026/repair_v2/environment.json`。

## 版本与数值身份

| 依赖 | 原正式配置 | 超算已验共享环境 |
| --- | --- | --- |
| torch | 2.5.1 | 2.5.1 |
| numpy | 2.0.1 | 1.26.4，必须由私有 overlay 提供 2.0.1 |
| transformers | 4.57.3 | 4.57.3 |
| tokenizers | 0.22.2 | 0.22.2 |
| safetensors | 0.6.2 | 0.6.2 |
| huggingface_hub | 0.36.2 | 0.36.2 |

超算共享 Python 为 `/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python`（3.11.11），vendor 为 `/public/home/jiangxinwei.zr/work/paper04/environment/vendor_py311_v1`。最新 readiness 的范围是依赖导入和 2×2 CPU 算术，明确记录 `old104_parity=NOT_ASSESSED_NO_MODEL_FORWARD`。10月21日旧 E3 重放因共享文件系统阻塞未取得完成结果，不能用历史 RUNNING 页面或环境导入成功推定 104 数值身份通过。本地 Windows benchmark 的 104 条均不逐位相同，只能用于计时，不能拼入生产参考库。

`encoder_r2.py:269` 起的版本门不应改成接受共享 1.26.4。`encoder_r2.py:340` 起重放全部原 104，生产模式任一字节不符即 `ORIGINAL104_NUMERICAL_IDENTITY_STOP`，补充位置不得继续。原编码器与新编码器均按 `(protocol,width,bursts)` 分组、UID 排序、每批最多 16 条，未发现这部分批次配方不一致。

版本号相同不等于原云端硬件、Torch 构建和 BLAS 完全相同。必须保存实际 Python、模块路径、Torch 构建/CPU 能力和 NumPy BLAS 信息，并以原 104 严格门作为本次复用旧 E3 的必要证据。不得加入近似容差或自动另起新数值路线。

## 私有 overlay 的最小执行要求

1. 将官方 `numpy-2.0.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` 纳入新包 SHA。只从该 wheel 离线安装到新作业私有目录：`pip --no-index --no-deps --target <private-overlay> <wheel>`；不用在线依赖解析，不写共享 site-packages。
2. 先加载已验环境脚本，再设置新子进程的 `PYTHONPATH`。旧 `environment.sh:7` 会覆盖 PYTHONPATH；最终顺序应为私有 overlay、既有 vendor、必要的本次封存源码目录。
3. 编码器在模块第 20 行即导入 NumPy；必须启动一个继承上述环境的新子进程。不能在已经导入 1.26.4 的 Python 进程中仅修改路径。源 CAL 子进程也使用同一 overlay。
4. 同时核对 `numpy.__version__`、`numpy.__file__` 位于私有目录、`importlib.metadata` 版本与分发路径、其余五项正式版本。单看 dist-info 版本不够。
5. 在模型前向前导入实际 E3/netFound 所需完整类和辅助依赖。E3 embed 会导入 pandas；Transformers 可能触发共享 SciPy/sklearn 等编译扩展。NumPy 1.x ABI 的共享扩展可能在 NumPy 2 下报错。发现缺依赖/ABI 问题即停止并留现场，不能通过屏蔽模块或静默改模型实现继续。已有 pandas 2.3.3 vendor 版本理论兼容，但尚未在本次 overlay 中实测。
6. 完整依赖导入后运行原 104 门，成功才正式补 21,660 个冻结位置。保留单 worker、4 线程、8 GiB 进程树 RSS 守卫、16 GiB Slurm 硬限、编码 10 小时/源 CAL 2 小时、零自动重试。监督器必须把临时运行目录和实际输出均纳入资源约束。

## 已有大件与源 CAL 的固定路径

远端项目根为 `/public/home/jiangxinwei.zr/work/paper04`。10月26日已验大件在 `runs/hpc_readiness_v1_20261026/assets/`：

| 文件 | 字节 | 处理 |
| --- | ---: | --- |
| LEARN.npy | 2,435,125,080 | 复用 SHA 已验文件，建立只读 canonical view |
| LEARN.jsonl.gz | 93,547,174 | 同上 |
| LEARN_q.npy | 42,936,840 | 同上 |
| CAL.npz | 1,190,820 | 同上 |

checkpoint 已在 `assets/model.safetensors`，698,780,900 字节，SHA256 为 `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`。不需重新传输或生成百万行源 E3。

`run_dense_source_cal.py` 的 `--root` 需要保留以下相对布局；只有 flat assets 不会自动满足它：

- `runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/` 中 LEARN.jsonl.gz、LEARN_q.npy、CAL.npz、normalizer.npz、SHA256SUMS；以及 `heads/run/cache_binding.json`。
- `runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy`。
- `runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/evaluation/calibration/{cuts,geometry,scales,protection}.json`，及其父目录 evaluation/SHA256SUMS。
- `runs/diagnostics_d1_d2_v1_20261022/assets/reference_scores/SOURCE_REFS.{npz,jsonl.gz}`。
- `runs/diagnostics_d1_d2_v1_20261022/output/d1/r2/source_actual_trace.npz`（10,674,250 字节，SHA256 `1dedf849ce024a07aa91254d55b3f898e919cd6ee1fa59203ff632a98ca4234f`）。
- `runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/{INPUT_SEAL,RESULT}.json`。
- `runs/onboarding_new_lineage_v1_20261022/package_v3/constrained_onboarding_core_v3.py`，和 `repo/ood` 的冻结 core、budget、indexed_features 及其 legacy_qref_data 导入闭包。

新生成输入包括完整编码 RESULT、`banks/SOURCE_REFS/{bank.npz,references.jsonl.gz,receipt.json}`、冻结 source DENSE_PLAN 与绑定包 SHA/source plan SHA 的真实授权 receipt。源密库必须恰好 4,728 个冻结 UID，原 104 的 E3/q14 和科学元数据保持。源 CAL 为 148,819 行（115,672 攻击、33,147 正常），不重拟合原 cuts、geometry、scales。

ε=0 的同环境 legacy/预算修正 logits 和决定逐位比较继续保留；R-B2 原候选撤警集合、原 λ、旧科学决定也有硬门。旧本机 NumPy 2.2.6 修正 logit SHA 仅报告跨环境差异，不是放宽原 104 E3 门。

## 当前仍待验

私有 overlay 的实际模块路径、完整依赖 ABI、原 104 逐位重放、真实补编码完成、密源 CAL 和其资源消耗均未由本审计执行。完整目标矩阵另需最新规格和新 runner 的独立验收，本审计不把旧 `MATRIX_PLAN.json` 的 `execution_ready=false` 改称已经就绪。

## 新执行代码的独立静态审查

已读新 `src/common.py`、`prepare_runtime.py`、`runtime_probe.py`、`chain.py` 和 `source_cal.py`，未导入真实依赖或运行实际前向。私有 wheel 安装、新解释器环境继承、NumPy 实际导入路径与分发路径核查、旧编码包委托 SHA、全新输出目录及源 CAL canonical view 的衔接总体正确。

两项审查发现已在新副本中修正：

- 原 `runtime_probe.py` 只导入 wrapper，不能证明 lazy import 的真实 netFound 模型依赖可用。现已显式调用原 translator 的 `import_netfound` 导入实际四类，未构造模型或读取 checkpoint。
- 旧源 CAL 的 `initial` 用 canonical 未 resolve 的路径作键，`expected_inputs` 却 resolve symlink，迁移 view 下会跳过 prior seal 检查。新 `source_cal.py` 已统一 resolved key。与封存旧稿逐行比对，仅这项身份适配及结尾移植说明改变，104/ε0/原决定门和预算科学算法保留。

**总 wall 预算问题已修复：** 初审发现各阶段 cap 求和门会拒绝原12小时总cap。根实现已改为 `stage_limits(stage,total,elapsed)`：总cap必须是1–43,200秒整数，每阶段实际预算取 `min(stage_cap,remaining_total)`，整体耗尽即停；不要求各阶段cap之和预留足额，也不扩大总授权。本地 `test_chain.py` 已验证12小时共享预算、剩余17秒、整体耗尽及已授权前缀的真实参数接线。

最终 monitor/runtime 复核与新增合成测试见同目录 `FINAL_RUNTIME_REVIEW.md/json`。生产依赖、104门和密源CAL仍待真实计算节点验收。
