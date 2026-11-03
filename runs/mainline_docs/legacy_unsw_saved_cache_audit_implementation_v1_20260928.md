# UNSW 已保存缓存只读核验：实现与交付

日期：2026-09-28。状态：IMPLEMENTED / LOCAL_VALIDATION_PASS / REMOTE_NOT_STARTED。

本步承接 `legacy_unsw_attack_transfer_diagnosis_and_repair_direction_20260928.md` 及其只读缓存规格。用户已授权“执行下一步”；沿用用户上传、提交、拉回的超算工作方式，本轮不再要求阶段间重复授权。

## 目标与范围

用户明确：只恢复到当前外部 Q 的 59.9369% 攻击检出不足够，目标仍是争取接近原数据集约 99% 的高检出，同时保持低 OOD/ID 误报。这里是诊断工具，不是已经达到该目标的新模型。

既有诊断证明五设备各有七种保存联合分数，第七条攻击查询起不再变化。本工具核对重复位于哪一层，避免直接从“分数重复”推导“模型没看到当前包”。只读取原 Job176975 已保存流量字段、特征和分数；本地只使用既有返回元数据生成身份合同。没有新模型 forward、PCAP 解码、训练、CAL、阈值搜索、数据下载或远程操作。

实际张量重建未启用。缓存没有原帧到 token 的映射，目标包保留率标记 UNAVAILABLE；源字段相同而特征不同也只报告和保留批次定位，不临时扩大执行。

## 实现

- `repo/ood/legacy_unsw_saved_cache_audit_v1.py`：校验授权、Job176975 身份及成功状态；18 个输入逐一 SHA/大小校验；清单角色、分母、设备、UID 顺序、特征 receipt 与 shard 索引匹配；核验结束前再次校验原输入未变化。
- 全部 148,408 UID 保留：148,316 查询（75,763 正常、72,553 攻击）及 92 参考。读取 float32 `(148408,768)` 保存特征，不重算。源字段哈希排除 unused duration，duration 单独统计；13 维保存分数独立哈希。参考可用性单独标识，避免将占位零解释为实测分数。
- 全量按设备/用途/标签、协议、组件及原攻击区间/速率统计；保存每 UID 的三个哈希、时间、burst/packet 数、原 shard/行/batch16 位置；攻击首六、第七和最后查询例证与连续恒定尾段一起输出。
- `legacy_unsw_saved_cache_delivery_v1.py`：纯 Python3.9 标准库安装与结果导出；拒绝覆盖、路径逃逸、重复或符号链接成员，校验精确包闭包。即使 numpy 预检失败也能导出日志。
- 单独输出 `runs/cache_audit`；已存在输出不能重启；出现异常停止、零自动重试。状态含阶段和进度，最终 COMPLETE 为 100%。失败保存首因与 traceback；调度退出码与实时队列信息分别展示，退出后不把旧 RUNNING 快照当作仍在执行。

源目录固定为 `/public/home/jiangxinwei.zr/work/legacy_commissioning_unsw_recovery_v2_20260927`。18 个输入共 503,251,984 字节。旧 seal 文件仅作已锁定的来源收据；不声称复验旧 run 所有文件。源 export_manifest 的 source_job=176411 指恢复来源，根 job.id=176975 才是本次已完成作业，不混淆两者。

## 验证与边界

本次自审，无新增代理审查。

1. Windows Python3.9，干净安装交付包后 26 项生成数据测试通过（19 项缓存核验 + 7 项交付）。覆盖字节损坏、UID 错位、缺缓存、NaN、dtype、重复快照、协议不符、读取中变更、停止/时限、输出重启拒绝；源字段与特征不一致时分别统计。正常完成测试确认源文件未改变。
2. WSL Linux 7 项纯标准库交付测试通过；3 个 Bash 脚本语法、Linux SHA 校验通过。模拟器覆盖缺授权、一次提交、重复提交拒绝、调度预检/提交失败，以及成功、预检失败、核验失败、缺授权四种执行/导出路径。没有调用真实 sbatch/ssh。
3. PowerShell 传输脚本语法通过；包内文本与 SHA 侧车为 LF，避免此前 CRLF 校验失败；安装闭包 10 个文件。安装助手在不载入 site-packages 的进程中仍可导出环境失败证据。
4. WSL 未安装 numpy，未声称其完成数值核验。目标节点必须先执行全部 26 项合成测试，临时目录放在本轮输出文件系统；通过后才读真实缓存。目标运行尚未执行。

`validation/` 保存测试日志和模拟结果。调度资源固定为 amd/1CPU/8GiB/30min，程序 wall guard=1200s；这是保护上限，不是时长承诺。不会启动 GPU，也不会因为缺数据退回长时间特征推理。

## 交付与后续

目录：`runs/legacy_unsw_saved_cache_audit_delivery_v1_20260928`。

- 包：`legacy_unsw_saved_cache_audit_v1_20260928.tar.gz`，16,427 字节。
- 包 SHA256：`d327ca4fa59be54122a33cde32dbd6ad304096eb1266810943b2d5b0e3ca6b07`。
- 输入合同 SHA256：`6acd3362cd1daf9c49d3fe6b0f29568b4a092757bbbdc5f1d2a887641094b5ea`。
- `OPERATE_HPC.md` 提供上传、一次提交、watch 状态与拉回命令；用户已授权此只读链，无需再确认。

返回后先验证输出身份/封存，再判断是源字段重复、表示压缩还是判别投影问题。不能根据核验成功宣称科学结果修复；旧 scientific FAIL、独立 ID_NOT_RUN、foundation exposure 未决均保留。已经查看的外部 UNSW 数据是开发证据，不恢复独立验证资格。

维护：原冻结诊断、协议、模型及结果不改；仅新增工具/交付/本记录，更新 living handoff 与 experiment map。分支 HEAD 仍为 codex/exp-mainline / 4b28747b09480471e2bac1beb3a9badf27280efb，八份无关 tracked 修改按既有 SHA 基线验证保护。
