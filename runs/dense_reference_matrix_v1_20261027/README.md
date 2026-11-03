# 密参考入网验证：实现包

2026-10-27。依据 Claude 第二步 r1/r2 与完整矩阵最小规格 r3，实现冻结密参考、源 CAL 预算工作点和 WRONG 对照。**实现与合成测试通过，不代表正式补编码、密源 CAL 或目标效果已有结果。** 本轮没有真实模型前向、补编码、目标评价、训练或 Slurm 作业提交。

## 当前状态

| 内容 | 状态 |
|---|---|
| 冻结源/A/B密参考位置、补编码请求 | 复用原冻结清单，新增位置 21,660 |
| WRONG 供体/UID、组件数、密度比例 | 已按 r3 确定性冻结 |
| 预算保护、矩阵 runner、输入物化、资源监督、状态页代码 | 已实现；具体测试回执和最终封包 SHA 随执行卡记录 |
| 超算私有 NumPy 2.0.1 overlay | 已准备；计算节点实际导入与数值兼容待运行 |
| 原104逐字节门禁、正式补编码、真正密源 CAL | 尚未运行 |
| 完整三池矩阵 | **BLOCKED：第三池冻结 BASE/B2 真实缺失** |

第三池的缺口不是“原资产齐全，只是没有观察窗口”。旧 v3 协议、服务完成记录、四 suffix 科学判定和 V4-EVAL1 全量 parent inventory 都只提供 A/B，并明确第三池 NOT_RUN 或缺证据。因此不得新设第三池窗口、制造银行或拿源 CAL 代替；也不得将登记的三池矩阵擅自改为 A/B-only。

当前允许准备独立的 `runtime → encode → source_cal` 有序前缀。**正式使用超算运行这个前缀仍须后续具体云端授权**，完成前缀不等于完成矩阵。完整矩阵必须先解决第三池资产与登记口径，再封新包、更新执行卡并取得对应运行授权。

## 主要文件

- `PROTOCOL.md`：冻结科研口径、工作量与停止规则。
- `config/MATRIX_TEMPLATE.json`：可重定位的固定参数、A/B真实资产和 WRONG 表；派生密库与源 CAL 尚待物化。
- `config/ASSET_MANIFEST.json`、`config/SOURCE_ASSET_MANIFEST.json`：完整与前缀所需资产清单；已有大件只按注册路径/SHA复用。
- `src/binding.py`：metadata-only 冻结、WRONG 构造及严格第三池分支。
- `src/materialize.py`：编码和源 CAL 完成后，只补充派生资产 pin；不改变窗口、UID、供体、切点、半径或分数尺度。
- `src/matrix.py`、`src/metrics.py`：固定分数与参考支持的三臂、四 ε、四 suffix 评价；无模型训练入口。
- `src/chain.py`、`src/supervisor.py`：授权范围内顺序执行、资源护栏、零自动重试。
- `src/prepare_runtime.py`、`src/runtime_probe.py`：离线私有 overlay 与实际模型依赖导入核查。
- `hpc/run_dense.slurm`：**仅为准备的提交脚本**；创建该文件不会提交作业，当前脚本只列已实现的三阶段前缀。
- `hpc/status_bridge.py`、`hpc/status_sync.py`、`hpc/progress_server.py`：普通程序同步状态；连接中断、异常停止与完成明确区分。
- `preparation/frozen_final/`：冻结 donor/UID 表、真实输入 SHA、距离预算、第三池证据。
- `preparation/MATRIX_INDEPENDENT_REVIEW.md/json`、`preparation/ENCODER_PORTABILITY_AUDIT.md/json`：独立审阅与兼容性审计；不是正式科研结果。

## 超算环境与资源

申请规格为 **amd 分区、单节点、4 CPU、16 GiB Slurm 内存、最多12小时、CPU-only、单 worker**。进程树 RSS 守卫为8 GiB，Torch/BLAS固定4线程。任何阶段实际可用 wall-time 为“阶段上限”与“总12小时剩余额度”的较小者；阶段上限不能相加解释为已授权超过12小时，也不自动延长。

原封存编码器要求 NumPy 2.0.1，当前超算共享环境为1.26.4。新包离线安装已核SHA的官方wheel到**新作业私有** `runtime/numpy201`，不修改共享环境。新的子进程核查真实模块路径、版本、分发路径与 netFound/E3 完整依赖导入；发现 ABI 或依赖异常即停，不屏蔽模块或放宽旧版本门。

计算节点导入通过后，还必须先重新编码原104并与原E3逐 UID、float32字节完全相等。**版本号相同与导入成功均不能替代原104实际数值门禁。** 任一字节不符即保留现场停止，不能使用本地计时向量拼库，不能放宽容差后继续。

## 本地验证与运行边界

在解包后的包目录运行合成测试（需提供本机 NumPy 和 psutil）：

```powershell
python -B -m unittest discover -s tests -v
```

测试只用临时合成数据；涉及真实资产的准备只做 metadata、身份和 SHA 核查。不要把示例、测试或已生成的 Slurm 脚本视作运行授权。生产必须使用新输出目录、精确封包 SHA 和实际授权回执；身份、数据、数值或资源异常零自动重试。科学 FAIL 则继续完成当次已登记且有条件执行的对照，不按目标结果重新选位置或调参。

进度同步由普通程序完成，Windows 辅助进程保持隐藏窗口；不持续调用 AI 轮询。旧 BASE/CTX 完成页和历史异常记录继续保留，不能改写为本轮新作业状态。
