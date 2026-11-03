# 密参考入网：具体执行卡（尚未提交）

2026-10-27。用户本轮授权为按方案实现。本卡准备可审阅的超算运行范围，**不是已取得的运行回执**。封存包身份、解包复验与测试汇总见包外 `PACKAGE_RECEIPT.json`、`VALIDATION.json`。

## 当前可申请的运行范围

仅一次 `runtime → encode → source_cal`，不训练、不做 A/B 新评价。补编码包含源/A/B合法正常参考位置，但不评价目标查询。先过计算节点依赖导入、原104严格逐字节重放，再补源4,624、A5,237、B11,799，共21,660个固定位置，最后用真正4,728位置密源库执行148,819行源CAL，保存四ε工作点与ε=0兼容证据。

完整三池矩阵代码已实现，但第三池缺历史冻结BASE/B2和有效receipt，正式入口在加载目标或启动编码前拒绝完整矩阵命令。本卡不将三池改为A/B-only。解决缺口或明确登记范围修订后，必须封新包、更新卡和授权。

## 数据与运行位置

超算项目根：`/public/home/jiangxinwei.zr/work/paper04`。

| 内容 | 位置/处理 |
|---|---|
| 新包 | `runs/dense_reference_matrix_v1_20261027/`，创建全新目录解包 |
| 冻结编码器 | 包内 `vendor/encoding_v2/`；原SHA256SUMS身份 `50969f127dbb258b851f36ea03669456863a7d532b1c6f1b70a9c6a84088a910` |
| checkpoint | `assets/model.safetensors`，复用698,780,900字节；SHA `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105` |
| 原源大件 | 复用 `runs/hpc_readiness_v1_20261026/assets/` 中LEARN.npy、LEARN.jsonl.gz、LEARN_q.npy等，仅按显式alias与SHA绑定，不搜索替代 |
| 源CAL布局 | 按 `config/SOURCE_ASSET_MANIFEST.json` 建立canonical hardlink view，不复制源E3，不修改输入；必须同一文件系统 |
| 每次输出 | 新 `runtime/job_<SlurmID>/science/`；编码、CAL、控制日志与异常现场独立保留 |
| 实际运行授权 | 包外/可变 `.private/APPROVED.json`，只在用户批准后生成；模板 `config/APPROVAL.template.json` 的false不能直接使用 |

输入清单逐项保存路径、字节数、SHA。小件随包、大件复用。完整矩阵另需的目标查询大件目前不属于本卡传输/运行范围。旧封存编码包、旧BASE/CTX作业179460与其进度页保持。

## 资源与耗时

单节点amd、4 CPU、16 GiB Slurm内存、CPU-only、单worker、BLAS/Torch 4线程、12小时硬限、no-requeue。整个工作进程树RSS守卫8 GiB；空闲磁盘至少12 GiB。runtime输出上限256 MiB、编码4 GiB、CAL128 MiB。readonly输入和698.8MB checkpoint另记，不计新输出载荷。

runtime阶段上限480秒、编码36,000秒、源CAL7,200秒；每阶段取自身上限和总12小时剩余额度的较小者，不能加总扩大总合同。前置包SHA门180秒、合成单测门240秒也受Slurm12小时硬限。超时、资源或数值异常停止，不自动续跑或增加配额。

历史本地计时对编码的规划约4–6小时，源CAL另按约1–2小时预留；**5–8小时只是规划区间，尚无本次超算吞吐或完成时间保证**。实际ABI/原104门禁可能提前停止。源CAL两库支持466,187,551对，不能用E3行/秒推算该kernel时间。完整矩阵A/B三臂另912,302,797对，第三池工作量未知，本卡不执行。

## 执行前检查与提交顺序

1. 用户批准这份具体范围、包身份与资源后，上传并解包新归档；不覆盖已有目录。验证归档SHA及包内完整SHA清单，复用大件也重新验SHA。先创建包内 `runtime/` 和 `.private/`；Slurm日志目录必须在提交前存在。
2. 将真实用户授权证据、包 `PACKAGE_SHA256SUMS` 的SHA、三阶段、43200秒、retries=0写入 `.private/APPROVED.json`。不要把模板或测试授权当生产批准。
3. 仅提交一次 `sbatch hpc/run_dense.slurm`，记录job ID。脚本先验已有environment.sh SHA，再加载环境；私有NumPy2.0.1 overlay离线装到新作业内，原共享环境保持。新子进程核验六依赖、NumPy实际模块与分发路径、Torch桥接和真实netFound类导入；不屏蔽ABI失败。
4. 保存原104逐UID float32字节门禁；任一不符即停止，不能放宽容差或用本地计时E3替代。通过才进入补编码→密源CAL。科学FAIL仅记录，不构成技术重跑理由。
5. 拉回终态、日志、编码receipt、CAL seal/工作点和SHA后审计。前缀完成显示“补编码与源CAL完成，目标矩阵未运行”，不能称密参考已达到1%或完整实验完成。

## 清晰进度与无弹窗

新进度页预留本地 `http://127.0.0.1:18770/`，当前未启动；旧 `http://127.0.0.1:18769/` 继续保留BASE/CTX终态。新页展示作业ID、调度器/工作进程状态、当前阶段、真实内部编码计数（若有）、最近更新时间、异常原因和已授权范围。

授权部署时，在既有登录通道运行只读 `hpc/status_bridge.py --root <包内runtime目录> --job-id <ID> --token-file <私有token文件>`；本地 `status_sync.py --private-config <私有JSON> --cache <新缓存目录>` 每5秒读取，`progress_server.py --cache <同目录> --port 18770` 提供页面。桥默认远端loopback18780，仅GET固定job，24小时寿命；token不写进包、页面或日志。

本地私有JSON含 `job_id` 字符串、`token`、`remote_port=18780`、既有school-hpc SOCKS的 `socks_port`。同步器只复用既有唯一SSH监听，不另建登录；端口变化须同token/job/schema验证后保存。Windows用Pythonw或 `Start-Process -WindowStyle Hidden` 启动辅助程序，子进程也隐藏；普通传输重试不等于重新运行实验。

页面区分尚未提交、排队、运行、完成、异常停止、连接状态未知。失联不冒充仍正常，调度器结束但缺完成回执不冒充成功。终态缓存离线保留，同步终态后自动退出，无持续AI轮询。任何身份异常停止同步并明确显示；实验资源异常0自动重试。
