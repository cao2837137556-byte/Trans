# 密参考批次修复正式提交与启动验收

**最新执行回执：2026-10-27，作业179602 / node185 / RUNNING。原104严格数值门已通过，新参考补编码已开始。** 本文替代此前“待授权／未提交”的当前状态；不改写179523、179536失败及179591诊断历史。

## 授权和实际提交

用户在主手给出明确执行范围及资源卡后回复 **“允许提交”**。据此仅新投递一次：环境核验 → 全104严格重验 → 冻结参考补编码 → 密源CAL。4 CPU、16 GiB、CPU-only、amd、最多12小时；无训练、无新增目标评价、无自动重试或requeue。

19:47:49（北京时间）取得新作业 **179602**，提交返回0；状态桥绑定新runtime、job179602和loopback18784，旧诊断桥及旧现场不动。通过已有VS Code school-hpc会话上传了30,454字节分发包，无原数据重传、无新SSH登录或凭据创建。

归档SHA `279d5006cc7f155f22186e6d5d2b09c0926fb26e2085a99798649f037ee087a7`，新15件封条SHA `ff81556b59801426c10779908be2363f002f8945673c0eac9fa235bc9cc1d57a`。先验证归档、解包成员、原1492件、新15件、预算和批准范围，再调用sbatch。授权单独写新overlay/.private，未覆盖原批准及false模板。提交前排他创建attempt，超时或不确定均禁止重投。

## 已真实通过的门禁

- 计算节点26项人工／替身测试全过，日志为 `Ran 26 tests in 1.493s`、`OK`。
- 环境核验通过，原chain的运行环境与已绑定的179536/179591依赖、CPU数值构建核对通过。
- **ORIGINAL104：104/104逐字节一致；mismatch_count=0，max_abs_error=0。** 没有放宽容差，没有把小诊断直接替代完整重验。
- 真实编码已进入 **CIC_DEV** 合法参考。页面验收快照（已用2分44秒）显示CIC_DEV完成8/352批，43条逻辑行／88个物理位置；这是启动时快照，不是最终计数。

这已越过179536停止的位置，当前未见启动异常。完整新增编码和密源CAL尚未完成，不能写成整链完成或新A/B指标。

## 范围、后续与监控

精确预算仍是21,764逻辑行（含原104重验）、22,514物理位置、750条额外计算复制；新增唯一参考21,660，源密库合并后4728。复制不入库。完成全部编码及receipt后才允许CAL。

沿用规划5–8小时、总上限12小时；尚无完整HPC吞吐ETA。本次完成可交付参考库及密源CAL预算λ／保护回执。完整目标矩阵仍缺冻结第三池BASE/B2资产，不改成A/B-only；本次不会产出新A/B误报率或检出率。

[进度页仍为18770](http://127.0.0.1:18770/)，已切新job并分开显示环境、原104、新参考、密源CAL及逻辑／物理计数，保留179523、179536、179591三个历史页。原本地页面进程经PID+脚本+cache+端口核对后换页；新同步与页面均pythonw隐藏运行，无终端弹窗。普通程序同步，断连显示未知，终态离线保留，AI不持续轮询。后续有具体工作任务则继续完成。

## 核验凭据

- [新授权记录](../../dense_reference_batch_repair_deployment_20261027/APPROVED.json)
- [一次提交与状态桥回执](../../dense_reference_batch_repair_deployment_20261027/EXECUTION.json)
- [远端启动门禁原始读回](../../dense_reference_batch_repair_deployment_20261027/STARTUP_REMOTE_READBACK.json)
- [启动验收](../../dense_reference_batch_repair_deployment_20261027/STARTUP_ACCEPTANCE.json)
- [启动独立复核](../../dense_reference_batch_repair_deployment_20261027/STARTUP_INDEPENDENT_REVIEW.json)（PASS，仅本地已存回执核查）
- [页面及隐藏进程验收](../../dense_reference_batch_repair_deployment_20261027/PROGRESS_ACCEPTANCE.json)
- [本地修复完成和运行卡](20261027_dense_reference_singleton_batch_repair_codex.md)

部署辅助代码另经过14项单次提交测试、4项桥状态核查及13组页面检查；这些是工程验证，不计作科学结果。身份、数据、数值或资源异常继续停止保留现场、0自动重试，科学FAIL按预登记规则处理。
